#!/usr/bin/env python3
"""One-time test evaluation on dataset v2.0.0 (ticket 25, D-V2-5).

Order of operations (fail-closed):
1. Lock: build the candidate list and selection rule from validation results only, fingerprint it,
   and write ``lock.json``. Before any test access, re-run every Fly pipeline on validation from its saved
   checkpoints and require an exact match with the stored validation metrics.
2. Reserve: one ``PersistentTestRunLedger`` slot per candidate (a second run refuses). The quality gate
   field records the user's spec change: automated QA replaces manual review for v2 (D-V2-4).
3. Only then read the 150 test transcripts, encode them with the pinned E5 (test vectors stay in this run
   directory, never in the shared embedding cache), and score every locked candidate once.

    python scripts/run_v2_test_evaluation.py --snapshot-dir <E5 snapshot> \
        --runs <tuning-run-T2> <tuning-run-T4> --e5-run <m2-2b run> --output-dir <dir>
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import joblib  # noqa: E402
import numpy as np  # noqa: E402
import torch  # noqa: E402

from diagnose_fly_a_b import load_inputs_for  # noqa: E402
from flycall_data.brain_comparison import load_trained  # noqa: E402
from flycall_data.dataset_versions import get_dataset_version  # noqa: E402
from flycall_data.e5_runtime import load_e5_encoder  # noqa: E402
from flycall_data.evaluation import (  # noqa: E402
    LABEL_ORDER,
    PersistentTestRunLedger,
    classification_metrics,
    fingerprint_candidate_list,
)
from flycall_data.loader import load_frozen_dataset  # noqa: E402
from flycall_data.model_config import E5_SMALL_CONFIG  # noqa: E402
from flycall_data.reducer_classifier_factorial import fit_lda_reducer, run_svm  # noqa: E402
from run_independent_tuning import GRAPH_ORDER, OBJECTIVES, SEEDS, load_graphs  # noqa: E402

DATASET = "v2.0.0"
PIPELINES = ("lda_to_svm", *[f"fly_a_{o}_to_svm" for o in OBJECTIVES], "lda_to_fly_b",
             *[f"fly_a_{o}_to_fly_b" for o in OBJECTIVES])
BASELINES = {"e5_logistic_regression": "m2-logistic_regression-checkpoint.joblib",
             "e5_mlp": "m2-mlp-checkpoint.joblib",
             "e5_lda_logistic": "m2-3-lda-logistic-checkpoint.joblib"}
SELECTION_RULE = ("Selected Fly model = the *_to_fly_b pipeline (any T, any graph) with the highest mean validation "
                  "macro-F1 over seeds 42/1337/2026; ties broken by T, then graph order, then pipeline order. "
                  "Fixed before any test access; test numbers are reported for every locked candidate but never "
                  "change the selection.")
APPROVAL = ("User decision 2026-11-14, ticket 25 D-V2-4/D-V2-5: for dataset v2.0.0 the automated QA "
            "(validation_report_v2.0.0.md) replaces the manual-review gate; test is evaluated once after the "
            "configuration is locked on validation.")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_json(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def f1_mean(block: dict[str, Any]) -> float:
    rows = block.get("by_seed") or [{"validation": v} for v in block["validation_by_seed"]]
    return statistics.fmean(float(row["validation"]["macro_f1"]) for row in rows)


class Pipelines:
    """Rebuild every pipeline of one tuning run from its checkpoints (LDA/SVM refits are deterministic)."""

    def __init__(self, run_dir: Path, xtr: torch.Tensor, labels_tr: list[str], graph0) -> None:
        self.run_dir = run_dir
        self.results = json.loads((run_dir / "results.json").read_text(encoding="utf-8"))
        settings = self.results["settings"]
        hops = settings.get("step_semantics", "").startswith("input_at_step_zero")
        self.steps = int(settings.get("steps", 2))
        self.graphs = {k: replace(v, input_at_step_zero=hops, steps=self.steps) for k, v in load_graphs(graph0).items()}
        self.xtr, self.labels_tr = xtr, labels_tr

    def predict(self, graph: str, pipeline: str, seed: int, x_eval: torch.Tensor, labels_eval: list[str]) -> list[str]:
        g = self.graphs[graph]
        base = self.run_dir / "checkpoints" / graph
        if pipeline.startswith("lda_"):
            reduced = fit_lda_reducer(self.xtr.numpy().astype(np.float64), self.labels_tr,
                                      x_eval.numpy().astype(np.float64))
            tr, ev = reduced.train, reduced.validation
        else:
            objective = pipeline.removeprefix("fly_a_").rsplit("_to_", 1)[0]
            fly_a, _ = load_trained("fly_a", g, base / f"fly_a_{objective}" / f"seed-{seed}.pt")
            with torch.no_grad():
                tr = fly_a(self.xtr).detach().numpy().astype(np.float64)
                ev = fly_a(x_eval).detach().numpy().astype(np.float64)
        if pipeline.endswith("_to_svm"):
            return list(run_svm(tr, self.labels_tr, ev, labels_eval).validation_predictions)
        kind = pipeline.rsplit("_to_", 1)[0]
        fly_b, _ = load_trained("fly_b", g, base / f"fly_b_on_{kind}" / f"seed-{seed}.pt", input_width=ev.shape[1])
        with torch.no_grad():
            index = fly_b(torch.tensor(ev, dtype=torch.float32)).argmax(dim=1).tolist()
        return [LABEL_ORDER[i] for i in index]

    def stored_validation(self, graph: str, pipeline: str) -> list[float]:
        block = self.results["by_graph"][graph]["final"][pipeline]
        rows = block.get("by_seed") or [{"validation": v} for v in block["validation_by_seed"]]
        return [float(row["validation"]["macro_f1"]) for row in rows]


def baseline_predict(path: Path, x: np.ndarray) -> list[str]:
    payload = joblib.load(path)
    order = list(payload["label_order"])
    if "lda" in payload:
        out = payload["classifier"].predict(payload["lda"].transform(x))
    elif isinstance(payload["model"], torch.nn.Module):
        with torch.no_grad():
            out = payload["model"](torch.tensor(x, dtype=torch.float32)).argmax(dim=1).tolist()
    else:
        out = payload["model"].predict(x)
    return [order[int(v)] if not isinstance(v, str) else str(v) for v in out]


def summarize(values: list[float]) -> dict[str, float]:
    return {"mean": statistics.fmean(values), "std": statistics.stdev(values) if len(values) > 1 else 0.0}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot-dir", type=Path, required=True)
    parser.add_argument("--runs", nargs="+", required=True, help="tuning run directories (relative to the project)")
    parser.add_argument("--e5-run", required=True, help="dataset-v2 M2.2b run with the locked baselines")
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()
    out = PROJECT_ROOT / args.output_dir
    if out.exists() and any(out.iterdir()):
        raise SystemExit(f"Refusing to overwrite {out}.")
    out.mkdir(parents=True, exist_ok=True)
    version = get_dataset_version(DATASET)
    e5_run = PROJECT_ROOT / args.e5_run
    item = load_inputs_for(DATASET, str((e5_run / "embedding_manifest.json").relative_to(PROJECT_ROOT).as_posix()))
    xtr, xval = item["train"].embeddings, item["validation"].embeddings
    labels_tr, labels_val = list(item["train"].labels), list(item["validation"].labels)

    # 1) lock + validation reproduction check (no test access yet)
    runs = {}
    for rel in args.runs:
        p = Pipelines(PROJECT_ROOT / rel, xtr, labels_tr, item["graph"])
        if p.results.get("dataset_version") != DATASET:
            raise SystemExit(f"{rel} was not trained on dataset {DATASET}.")
        runs[f"T{p.steps}"] = p
    candidates, checkpoints, reproduction = [], {}, {}
    for t_name, p in sorted(runs.items()):
        for graph in [g for g in GRAPH_ORDER if g in p.results["by_graph"]]:
            for pipeline in PIPELINES:
                name = f"{t_name}/{graph}/{pipeline}"
                candidates.append(name)
                recomputed = [float(classification_metrics(labels_val, p.predict(graph, pipeline, s, xval, labels_val),
                                                           LABEL_ORDER)["macro_f1"]) for s in SEEDS]
                stored = p.stored_validation(graph, pipeline)
                reproduction[name] = {"stored": stored, "recomputed": recomputed}
                if any(not math.isclose(a, b, abs_tol=1e-9) for a, b in zip(stored, recomputed)):
                    raise SystemExit(f"validation does not reproduce from checkpoints for {name}: {stored} vs {recomputed}")
        checkpoints[t_name] = p.results.get("checkpoint_sha256", {})
    for name, filename in BASELINES.items():
        candidates.append(name)
        checkpoints[name] = sha256_file(e5_run / filename)
    fly_b_scores = [(f1_mean(runs[t].results["by_graph"][c.split("/")[1]]["final"][c.split("/")[2]]), c)
                    for c in candidates if c.endswith("_to_fly_b") for t in [c.split("/")[0]]]
    best = max(fly_b_scores, key=lambda s: s[0])[1]  # first maximum keeps the declared tie-break order
    lock = {"dataset_version": DATASET, "candidates": candidates, "selection_rule": SELECTION_RULE,
            "selected_fly_model": best, "validation_macro_f1": {c: s for s, c in fly_b_scores},
            "checkpoint_sha256": checkpoints, "runs": args.runs, "e5_run": args.e5_run,
            "locked_at_utc": datetime.now(timezone.utc).isoformat()}
    config_fp = sha256_json({k: v for k, v in lock.items() if k != "locked_at_utc"})
    lock["configuration_fingerprint"] = config_fp
    (out / "lock.json").write_text(json.dumps(lock, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "validation_reproduction.json").write_text(json.dumps(reproduction, indent=1), encoding="utf-8")
    print(f"locked {len(candidates)} candidates; selected Fly model {best}; validation reproduced exactly")

    # 2) one-use reservations
    sources = {"jsonl": sha256_file(version.paths.jsonl_path), "csv": sha256_file(version.paths.csv_path),
               "taxonomy": sha256_file(version.paths.taxonomy_path),
               "manifest": sha256_file(version.paths.frozen_manifest_path)}
    qa_report = PROJECT_ROOT / "data/1999_synthetic/formal/v2.0.0/validation_report_v2.0.0.md"
    ledger = PersistentTestRunLedger(PROJECT_ROOT / ".scratch/1999-connectome-demo/test-ledger/dataset-v2.0.0")
    list_fp = fingerprint_candidate_list(candidates)
    reservations = [ledger.reserve(candidate_name=c, candidate_names=candidates, candidate_list_fingerprint=list_fp,
                                   configuration_fingerprint=config_fp, candidate_list_locked=True,
                                   configuration_locked=True, manual_review_gate_passed=True,
                                   manual_review_summary_sha256=sha256_file(qa_report),
                                   approval_reference=APPROVAL, source_sha256=sources) for c in candidates]
    for r in reservations:
        ledger.consume_for_evaluation(r)

    # 3) test access: read, encode (kept local to this run), score once
    bundle = load_frozen_dataset(version.paths)
    test_rows = sorted((r for r in bundle.records if r["split"] == "test"), key=lambda r: r["id"])
    labels_te = [r["label_id"] for r in test_rows]
    encoder = load_e5_encoder(args.snapshot_dir)
    vectors = encoder.encode([E5_SMALL_CONFIG.prefix + r["transcript"] for r in test_rows])
    xte = torch.tensor(vectors, dtype=torch.float32)
    norms = torch.linalg.vector_norm(xte, dim=1)
    if not torch.allclose(norms, torch.ones_like(norms), atol=1e-5):
        raise SystemExit("test embeddings are not unit-normalized.")
    results: dict[str, Any] = {}
    for name in candidates:
        if name in BASELINES:
            pred = baseline_predict(e5_run / BASELINES[name], xte.numpy().astype(np.float64))
            m = classification_metrics(labels_te, pred, LABEL_ORDER)
            results[name] = {"macro_f1": {"mean": float(m["macro_f1"]), "std": 0.0},
                             "accuracy": {"mean": float(m["accuracy"]), "std": 0.0}, "by_seed": [m]}
            continue
        t_name, graph, pipeline = name.split("/")
        per_seed = [classification_metrics(labels_te, runs[t_name].predict(graph, pipeline, s, xte, labels_te), LABEL_ORDER)
                    for s in SEEDS]
        results[name] = {"macro_f1": summarize([float(m["macro_f1"]) for m in per_seed]),
                         "accuracy": summarize([float(m["accuracy"]) for m in per_seed]), "by_seed": per_seed}
    payload = {"schema_version": 1, "dataset_version": DATASET, "status": "test_evaluated_once",
               "review_status": version.review_status, "test_records": len(test_rows),
               "label_counts": {lab: labels_te.count(lab) for lab in LABEL_ORDER},
               "configuration_fingerprint": config_fp, "selected_fly_model": best,
               "selected_fly_model_test": results[best], "results": results,
               "reservation_ids": [r.reservation_id for r in reservations],
               "created_at_utc": datetime.now(timezone.utc).isoformat()}
    (out / "test_results.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    lines = ["# Dataset v2.0.0 一次性 test 評估（D-V2-5）", "",
             "自動品質檢查通過，未經人工複核。設定在讀取 test 前以 validation 鎖定（`lock.json`），每個候選只評估一次。", "",
             f"- 選定的 Fly 模型（validation 規則）：`{best}` → test Macro-F1 {results[best]['macro_f1']['mean']:.4f}"
             f" ± {results[best]['macro_f1']['std']:.4f}", "",
             "| 候選 | validation Macro-F1 | test Macro-F1 (mean ± sd) | test accuracy |", "|---|---:|---:|---:|"]
    for name in candidates:
        val = lock["validation_macro_f1"].get(name)
        if val is None and "/" in name:
            t_name, graph, pipeline = name.split("/")
            val = f1_mean(runs[t_name].results["by_graph"][graph]["final"][pipeline])
        r = results[name]
        lines.append(f"| {name} | {'' if val is None else f'{val:.4f}'} | {r['macro_f1']['mean']:.4f} ± {r['macro_f1']['std']:.4f} "
                     f"| {r['accuracy']['mean']:.4f} |")
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"test evaluated once: {best} macro-F1 {results[best]['macro_f1']['mean']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

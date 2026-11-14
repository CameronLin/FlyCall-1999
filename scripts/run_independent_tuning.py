#!/usr/bin/env python3
"""Tickets 20 + 22: tune Fly A and Fly B separately on train-only grouped CV,
then train final models with fixed epochs and read validation once, for
G0 / G1 / G2 / G2-glu+.

Preregistration: .scratch/1999-connectome-demo/research/
independent-fly-a-fly-b-tuning-preregistration-20261113.md
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for extra in (PROJECT_ROOT / "src", PROJECT_ROOT / "scripts"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import numpy as np  # noqa: E402
import torch  # noqa: E402

from diagnose_fly_a_b import (  # noqa: E402
    DEFAULT_CACHE_ROOT,
    DEFAULT_EMBEDDING_MANIFEST,
    DEFAULT_RUNS,
    load_inputs_for,
    load_train_validation_inputs,
)
from flycall_data.evaluation import LABEL_ORDER, classification_metrics  # noqa: E402
from flycall_data.fly_ab_training import GraphDefinition, _write_checkpoint  # noqa: E402
from flycall_data.graph_core import distance_preserving_loss  # noqa: E402
from flycall_data.independent_tuning import (  # noqa: E402
    FOLDS,
    LEARNING_RATES,
    MAX_EPOCHS,
    OBJECTIVES,
    PATIENCE,
    SEEDS,
    SUPCON_LAMBDA,
    SUPCON_TEMPERATURE,
    choose_learning_rate,
    fit_fly_a,
    fit_fly_b,
    grouped_stratified_folds,
    label_tensor,
    macro_f1,
    median_epoch,
)
from flycall_data.reducer_classifier_factorial import fit_lda_reducer, paired_delta, run_svm, summarize  # noqa: E402

PREREGISTRATION = ".scratch/1999-connectome-demo/research/independent-fly-a-fly-b-tuning-preregistration-20261113.md"
SIGNED_DIR = "data/connectome/derived/malecns_v1.0/subgraphs/signed-quota-v1.0"
GRAPH_FILES = {"G1": "G1_all_positive", "G2": "G2_glu_inhibitory", "G2_glu_plus": "G2_glu_excitatory"}
GRAPH_ORDER = ("G0", "G1", "G2", "G2_glu_plus")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_graphs(g0: GraphDefinition) -> dict[str, GraphDefinition]:
    if len(g0.node_ids) != 500 or len(g0.edges) != 2216 or g0.steps != 2 or g0.node_signs is not None:
        raise SystemExit("G0 differs from the pinned M3.2 graph.")
    manifest = json.loads((PROJECT_ROOT / SIGNED_DIR / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("status") != "completed":
        raise SystemExit("signed-quota manifest is not completed.")
    graphs = {"G0": g0}
    for key, name in GRAPH_FILES.items():
        path = PROJECT_ROOT / SIGNED_DIR / f"graph_definition_{name}.json"
        if _sha256(path) != manifest["graphs"][name]["sha256"]:
            raise SystemExit(f"{path.name} differs from its manifest checksum.")
        value = json.loads(path.read_text(encoding="utf-8"))
        graph = GraphDefinition(
            tuple(value["node_ids"]), tuple(value["input_node_ids"]), tuple(value["output_node_ids"]),
            tuple(tuple(edge) for edge in value["edges"]), int(value["steps"]),
            tuple(tuple(pair) for pair in value["node_signs"]),
        )
        if (len(graph.node_ids), len(graph.edges), graph.steps) != (manifest["node_count"], manifest["edge_count"], 2):
            raise SystemExit(f"{name} does not match manifest counts.")
        if len(graph.input_node_ids) != 32 or len(graph.output_node_ids) != 32:
            raise SystemExit(f"{name} must have 32+32 I/O nodes.")
        graphs[key] = graph
    return graphs


def _svm_f1(train_x: np.ndarray, train_labels, test_x: np.ndarray, test_labels) -> tuple[list[str], dict[str, Any]]:
    result = run_svm(train_x, train_labels, test_x, test_labels)
    return list(result.validation_predictions), result.validation_metrics


def run_graph(name: str, graph: GraphDefinition, data: dict[str, Any], max_epochs: int, log) -> dict[str, Any]:
    xtr, ytr, labels_tr, folds = data["xtr"], data["ytr"], data["labels_tr"], data["folds"]
    xval, labels_val = data["xval"], data["labels_val"]
    rows = np.arange(len(labels_tr))
    fold_index = [(rows[np.asarray(folds) != fold], rows[np.asarray(folds) == fold]) for fold in range(FOLDS)]

    # Phase A: Fly A grouped CV, scored by a fixed SVM probe on out-of-fold predictions.
    cv_a: dict[str, Any] = {}
    fold_reps: dict[tuple, torch.Tensor] = {}
    for objective in OBJECTIVES:
        cv_a[objective] = {}
        for rate in LEARNING_RATES:
            per_seed, epochs = [], []
            for seed in SEEDS:
                oof = [None] * len(labels_tr)
                for fold, (train_rows, held_rows) in enumerate(fold_index):
                    tr_t, he_t = torch.from_numpy(train_rows), torch.from_numpy(held_rows)
                    supervised = objective == "distance_supcon"
                    fit = fit_fly_a(
                        graph, xtr[tr_t], ytr[tr_t] if supervised else None, objective=objective,
                        learning_rate=rate, seed=seed, max_epochs=max_epochs, patience=PATIENCE,
                        select=(xtr[he_t], ytr[he_t] if supervised else None),
                    )
                    epochs.append(fit.selected_epoch)
                    with torch.no_grad():
                        z = fit.model(xtr).detach()
                    fold_reps[(objective, rate, seed, fold)] = z
                    predictions, _ = _svm_f1(z[tr_t].numpy(), [labels_tr[i] for i in train_rows],
                                             z[he_t].numpy(), [labels_tr[i] for i in held_rows])
                    for row, label in zip(held_rows, predictions):
                        oof[row] = label
                per_seed.append(float(classification_metrics(labels_tr, oof, LABEL_ORDER)["macro_f1"]))
            cv_a[objective][str(rate)] = {"oof_macro_f1_by_seed": per_seed, "mean": statistics.fmean(per_seed),
                                          "selected_epochs": epochs}
            log(f"{name} A {objective} lr={rate}: OOF SVM F1 {statistics.fmean(per_seed):.4f}")
    chosen_a = {obj: choose_learning_rate({rate: cv_a[obj][str(rate)]["mean"] for rate in LEARNING_RATES})
                for obj in OBJECTIVES}

    # Phase B: Fly B grouped CV on per-fold inputs (LDA refit per fold; Fly A from the chosen rate).
    def fold_input(kind: str, seed: int, fold: int) -> tuple[np.ndarray, np.ndarray]:
        train_rows, held_rows = fold_index[fold]
        if kind == "lda":
            reduced = fit_lda_reducer(xtr[train_rows].numpy().astype(np.float64),
                                      [labels_tr[i] for i in train_rows], xtr[held_rows].numpy().astype(np.float64))
            return reduced.train, reduced.validation
        objective = kind.removeprefix("fly_a_")
        z = fold_reps[(objective, chosen_a[objective], seed, fold)].numpy().astype(np.float64)
        return z[train_rows], z[held_rows]

    inputs = ("lda", *[f"fly_a_{obj}" for obj in OBJECTIVES])
    cv_b: dict[str, Any] = {}
    for kind in inputs:
        cv_b[kind] = {"svm_oof_macro_f1_by_seed": []}
        cache = {(seed, fold): fold_input(kind, seed, fold) for seed in SEEDS for fold in range(FOLDS)}
        for seed in SEEDS:
            oof = [None] * len(labels_tr)
            for fold, (train_rows, held_rows) in enumerate(fold_index):
                tr_x, he_x = cache[(seed, fold)]
                predictions, _ = _svm_f1(tr_x, [labels_tr[i] for i in train_rows], he_x, [labels_tr[i] for i in held_rows])
                for row, label in zip(held_rows, predictions):
                    oof[row] = label
            cv_b[kind]["svm_oof_macro_f1_by_seed"].append(float(classification_metrics(labels_tr, oof, LABEL_ORDER)["macro_f1"]))
        for rate in LEARNING_RATES:
            per_seed, epochs = [], []
            for seed in SEEDS:
                oof_idx = [0] * len(labels_tr)
                for fold, (train_rows, held_rows) in enumerate(fold_index):
                    tr_x, he_x = cache[(seed, fold)]
                    tr_t, he_t = torch.from_numpy(train_rows), torch.from_numpy(held_rows)
                    fit = fit_fly_b(graph, torch.tensor(tr_x, dtype=torch.float32), ytr[tr_t], learning_rate=rate,
                                    seed=seed, max_epochs=max_epochs, patience=PATIENCE,
                                    select=(torch.tensor(he_x, dtype=torch.float32), ytr[he_t]))
                    epochs.append(fit.selected_epoch)
                    with torch.no_grad():
                        predicted = fit.model(torch.tensor(he_x, dtype=torch.float32)).argmax(dim=1).tolist()
                    for row, index in zip(held_rows, predicted):
                        oof_idx[row] = index
                per_seed.append(macro_f1(ytr, oof_idx))
            cv_b[kind][str(rate)] = {"oof_macro_f1_by_seed": per_seed, "mean": statistics.fmean(per_seed),
                                     "selected_epochs": epochs}
            log(f"{name} B {kind} lr={rate}: OOF Fly B F1 {statistics.fmean(per_seed):.4f} "
                f"(SVM {statistics.fmean(cv_b[kind]['svm_oof_macro_f1_by_seed']):.4f})")
    chosen_b = {kind: choose_learning_rate({rate: cv_b[kind][str(rate)]["mean"] for rate in LEARNING_RATES})
                for kind in inputs}

    # Phase C: final fixed-epoch training on all train rows; validation read once per model.
    final: dict[str, Any] = {"seeds": list(SEEDS)}
    epochs_a = {obj: median_epoch(cv_a[obj][str(chosen_a[obj])]["selected_epochs"]) for obj in OBJECTIVES}
    epochs_b = {kind: median_epoch(cv_b[kind][str(chosen_b[kind])]["selected_epochs"]) for kind in inputs}
    lda_full = fit_lda_reducer(xtr.numpy().astype(np.float64), labels_tr, xval.numpy().astype(np.float64))
    _, lda_svm = _svm_f1(lda_full.train, labels_tr, lda_full.validation, labels_val)
    final["lda_to_svm"] = {"validation_by_seed": [lda_svm] * len(SEEDS)}
    final_reps: dict[tuple, tuple[np.ndarray, np.ndarray]] = {}
    for obj in OBJECTIVES:
        rows_out = []
        for seed in SEEDS:
            fit = fit_fly_a(graph, xtr, ytr if obj == "distance_supcon" else None, objective=obj,
                            learning_rate=chosen_a[obj], seed=seed, max_epochs=epochs_a[obj])
            with torch.no_grad():
                ztr, zval = fit.model(xtr).detach(), fit.model(xval).detach()
                stress = float(distance_preserving_loss(xval, zval))
            final_reps[(obj, seed)] = (ztr.numpy().astype(np.float64), zval.numpy().astype(np.float64))
            _, metrics = _svm_f1(final_reps[(obj, seed)][0], labels_tr, final_reps[(obj, seed)][1], labels_val)
            rows_out.append({"seed": seed, "validation": metrics, "validation_distance_stress": stress})
            data["save"](f"{name}/fly_a_{obj}/seed-{seed}.pt", fit.model, {
                "task": f"fly_a_{obj}", "graph": name, "seed": seed, "learning_rate": chosen_a[obj],
                "epochs": epochs_a[obj], "supcon_lambda": SUPCON_LAMBDA if obj == "distance_supcon" else None})
        final[f"fly_a_{obj}_to_svm"] = {"by_seed": rows_out}
    for kind in inputs:
        rows_out = []
        for seed in SEEDS:
            if kind == "lda":
                tr_x, val_x = lda_full.train, lda_full.validation
            else:
                tr_x, val_x = final_reps[(kind.removeprefix("fly_a_"), seed)]
            fit = fit_fly_b(graph, torch.tensor(tr_x, dtype=torch.float32), ytr, learning_rate=chosen_b[kind],
                            seed=seed, max_epochs=epochs_b[kind])
            with torch.no_grad():
                predicted = fit.model(torch.tensor(val_x, dtype=torch.float32)).argmax(dim=1).tolist()
            metrics = classification_metrics(labels_val, [LABEL_ORDER[i] for i in predicted], LABEL_ORDER)
            rows_out.append({"seed": seed, "validation": metrics})
            data["save"](f"{name}/fly_b_on_{kind}/seed-{seed}.pt", fit.model, {
                "task": "fly_b", "input": kind, "graph": name, "seed": seed,
                "learning_rate": chosen_b[kind], "epochs": epochs_b[kind]})
        final[f"{kind}_to_fly_b"] = {"by_seed": rows_out}
    log(f"{name} final: " + ", ".join(
        f"{key} {statistics.fmean(_f1_list(value)):.4f}" for key, value in final.items() if key != "seeds"))
    return {"cv_fly_a": cv_a, "cv_fly_b": cv_b, "chosen_learning_rate": {"fly_a": chosen_a, "fly_b": chosen_b},
            "final_epochs": {"fly_a": epochs_a, "fly_b": epochs_b}, "final": final}


def _f1_list(block: dict[str, Any]) -> list[float]:
    if "validation_by_seed" in block:
        return [float(item["macro_f1"]) for item in block["validation_by_seed"]]
    return [float(item["validation"]["macro_f1"]) for item in block["by_seed"]]


def _acc_list(block: dict[str, Any]) -> list[float]:
    if "validation_by_seed" in block:
        return [float(item["accuracy"]) for item in block["validation_by_seed"]]
    return [float(item["validation"]["accuracy"]) for item in block["by_seed"]]


METRIC_ROWS = (
    ("fly_a_distance_to_svm", "Fly A（distance）→ SVM"),
    ("fly_a_distance_supcon_to_svm", "Fly A（distance+SupCon）→ SVM"),
    ("lda_to_svm", "LDA → SVM（參考）"),
    ("lda_to_fly_b", "LDA → Fly B"),
    ("fly_a_distance_to_fly_b", "Fly A（distance）→ Fly B"),
    ("fly_a_distance_supcon_to_fly_b", "Fly A（distance+SupCon）→ Fly B"),
)


def summarize_results(by_graph: dict[str, Any]) -> dict[str, Any]:
    summary = {graph: {key: {"macro_f1": summarize(_f1_list(result["final"][key])),
                             "accuracy": summarize(_acc_list(result["final"][key]))}
                       for key, _ in METRIC_ROWS}
               for graph, result in by_graph.items()}
    comparisons = {}
    pairs = [("G2", "G1", "加入抑制（G2 − G1）"), ("G2", "G2_glu_plus", "麩胺酸符號（G2 − G2-glu+）"),
             ("G1", "G0", "換圖整體（G1 − G0）")]
    for first, second, label in pairs:
        if first in by_graph and second in by_graph:
            comparisons[label] = {key: paired_delta(_f1_list(by_graph[first]["final"][key]),
                                                    _f1_list(by_graph[second]["final"][key]))
                                  for key, _ in METRIC_ROWS if key != "lda_to_svm"}
    for graph, result in by_graph.items():
        comparisons[f"Fly A 目標（SupCon − distance），{graph}"] = {
            target: paired_delta(_f1_list(result["final"][f"fly_a_distance_supcon_to_{target}"]),
                                 _f1_list(result["final"][f"fly_a_distance_to_{target}"]))
            for target in ("svm", "fly_b")}
    return {"summary": summary, "comparisons": comparisons}


def markdown(results: dict[str, Any]) -> str:
    s = results["summary"]
    graphs = [graph for graph in GRAPH_ORDER if graph in s]
    lines = [
        "# Fly A／Fly B 各自調參與四張圖比較（validation）",
        "",
        f"- 預註冊：`{PREREGISTRATION}`",
        f"- 資料：`synthetic` {results.get('dataset_version', 'v1.0.0')}；複核：`{results.get('review_status', 'pending_manual_review')}`；test：`not_run`（0 model inputs）",
        "- 設定只用 train 分組 5-fold 交叉驗證選出；最終模型以固定 epoch 訓練，validation 每個模型只讀一次。",
        f"- Seeds：{', '.join(map(str, SEEDS))}；數值為 validation Macro-F1 平均 ± 樣本標準差",
        "",
        "## Validation Macro-F1",
        "",
        "| 組合 | " + " | ".join(graphs) + " |",
        "|---|" + "---:|" * len(graphs),
    ]
    for key, label in METRIC_ROWS:
        cells = [f"{s[g][key]['macro_f1']['mean']:.4f} ± {s[g][key]['macro_f1']['sample_std']:.4f}" for g in graphs]
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
    lines += ["", "## 差異（三個 seed 同號且 |平均 Δ| ≥ 0.02 才算一致）", "", "| 比較 | 組合 | 平均 Δ | 各 seed | 判讀 |", "|---|---|---:|---|---|"]
    labels = dict(METRIC_ROWS) | {"svm": "→ SVM", "fly_b": "→ Fly B"}
    for comparison, block in results["comparisons"].items():
        for key, value in block.items():
            seeds = ", ".join(f"{x:+.4f}" for x in value["per_seed"])
            lines.append(f"| {comparison} | {labels.get(key, key)} | {value['mean']:+.4f} | {seeds} | "
                         f"{'一致' if value['consistent'] else '不明確'} |")
    lines += ["", "## 交叉驗證選出的設定", "", "| 圖 | 項目 | 學習率 | 最終 epoch |", "|---|---|---:|---:|"]
    for graph in graphs:
        result = results["by_graph"][graph]
        for obj, rate in result["chosen_learning_rate"]["fly_a"].items():
            lines.append(f"| {graph} | Fly A {obj} | {rate} | {result['final_epochs']['fly_a'][obj]} |")
        for kind, rate in result["chosen_learning_rate"]["fly_b"].items():
            lines.append(f"| {graph} | Fly B on {kind} | {rate} | {result['final_epochs']['fly_b'][kind]} |")
    lines += ["", "## Fly A validation 距離 stress（越低越能保留距離）", "", "| 圖 | distance | distance+SupCon |", "|---|---:|---:|"]
    for graph in graphs:
        final = results["by_graph"][graph]["final"]
        cells = [statistics.fmean(row["validation_distance_stress"] for row in final[f"fly_a_{obj}_to_svm"]["by_seed"])
                 for obj in OBJECTIVES]
        lines.append(f"| {graph} | {cells[0]:.4f} | {cells[1]:.4f} |")
    lines += ["", "## 限制", "",
              "- G1 − G0 混合起點、點組成（G0 多為無符號片段）與邊數（6,691 vs 2,216）差異，不歸因於單一因素。",
              "- 四張圖、兩種目標在同一個 validation 上比較；資料為合成資料、待人工複核。不取代 M3.4／M4 結果。",
              "", "完整交叉驗證分數、各類別指標、checkpoint 雜湊見 `results.json`。", ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=".scratch/1999-connectome-demo/runs/independent-tuning-20261113")
    parser.add_argument("--graphs", default=",".join(GRAPH_ORDER))
    parser.add_argument("--smoke", action="store_true", help="2 epochs only, for pipeline checks; not a result")
    parser.add_argument("--input-at-step-zero", action="store_true",
                        help="ticket 23 / D6a: T steps carry signals T hops (default: legacy T-1 hops)")
    parser.add_argument("--steps", type=int, default=2, help="graph-core steps T (ticket 24 compares 2 vs 4)")
    parser.add_argument("--dataset-version", default="v1.0.0", help="frozen formal dataset (ticket 25 adds v2.0.0)")
    parser.add_argument("--embedding-manifest", default=None,
                        help="E5 embedding_manifest.json for --dataset-version other than v1.0.0")
    args = parser.parse_args()
    output_dir = PROJECT_ROOT / args.output_dir
    if output_dir.exists() and any(output_dir.iterdir()):
        raise SystemExit(f"Refusing to overwrite {output_dir}.")
    output_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    log_path = output_dir / "progress.log"

    def log(message: str) -> None:
        line = f"[{time.perf_counter() - started:7.1f}s] {message}"
        print(line, flush=True)
        with log_path.open("a", encoding="utf-8") as stream:
            stream.write(line + "\n")

    checkpoints: dict[str, str] = {}

    def save(relative: str, model: torch.nn.Module, metadata: dict[str, Any]) -> None:
        path = output_dir / "checkpoints" / relative
        payload = {"schema_version": 1, "metadata": metadata,
                   "model_metadata": model.checkpoint_metadata(), "state_dict": model.state_dict()}
        checkpoints[relative] = _write_checkpoint(payload, path)

    item = load_inputs_for(args.dataset_version, args.embedding_manifest)
    train, validation = item["train"], item["validation"]
    labels_tr, labels_val = list(train.labels), list(validation.labels)
    data = {"xtr": train.embeddings, "ytr": label_tensor(labels_tr), "labels_tr": labels_tr,
            "folds": grouped_stratified_folds(train.family_ids, labels_tr),
            "xval": validation.embeddings, "labels_val": labels_val, "save": save}
    graphs = load_graphs(item["graph"])
    if args.input_at_step_zero:
        graphs = {key: replace(value, input_at_step_zero=True) for key, value in graphs.items()}
    if args.steps != 2:
        graphs = {key: replace(value, steps=args.steps) for key, value in graphs.items()}
    selected = [name for name in args.graphs.split(",") if name]
    max_epochs = 2 if args.smoke else MAX_EPOCHS
    by_graph = {}
    for name in selected:
        by_graph[name] = run_graph(name, graphs[name], data, max_epochs, log)
    analysis = summarize_results(by_graph)
    results = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "smoke_only_not_a_result" if args.smoke else f"validation_complete_{item['review_status']}",
        "preregistration": PREREGISTRATION,
        "data_status": "synthetic", "review_status": item["review_status"],
        "dataset_version": item["dataset_version"], "embedding_manifest": args.embedding_manifest,
        "test": {"status": "not_run", "model_inputs": 0, "metrics": None},
        "split_counts": {"train": 700, "validation": 150, "test": 0},
        "fold_sizes": {str(f): sum(1 for value in data["folds"] if value == f) for f in range(FOLDS)},
        "settings": {"objectives": list(OBJECTIVES), "supcon_lambda": SUPCON_LAMBDA,
                     "supcon_temperature": SUPCON_TEMPERATURE, "learning_rates": list(LEARNING_RATES),
                     "max_epochs": max_epochs, "patience": PATIENCE, "folds": FOLDS, "seeds": list(SEEDS),
                     "step_semantics": "input_at_step_zero (T hops)" if args.input_at_step_zero else "legacy (T-1 hops)",
                     "steps": args.steps},
        "graph_sha256": {name: hashlib.sha256(json.dumps(graphs[name].build_core().checkpoint_metadata(),
                                                         sort_keys=True).encode()).hexdigest() for name in selected},
        "by_graph": by_graph,
        **analysis,
        "checkpoint_sha256": checkpoints,
        "elapsed_seconds": time.perf_counter() - started,
    }
    (output_dir / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "report.md").write_text(markdown(results), encoding="utf-8")
    log(f"done; wrote {output_dir.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Probe frozen Fly A outputs, then tune Fly B only if A retains label signal.

This exploratory tool reads saved train/validation artifacts and cached E5
vectors only. It never loads dataset transcripts or the test split.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import torch  # noqa: E402

from flycall_data.embedding_pipeline import EmbeddingCache, SplitEmbeddings, run_baseline  # noqa: E402
from flycall_data.evaluation import LABEL_ORDER, classification_metrics  # noqa: E402
from flycall_data.fly_ab_diagnostics import (  # noqa: E402
    FLY_B_TUNING_SCHEDULES,
    FlyABDiagnosticError,
    fly_a_retains_label_signal,
    load_fly_b_e5_residual_checkpoint,
    train_fly_b_with_e5_residual,
    validate_embedding_manifest_entries,
)
from flycall_data.fly_ab_training import (  # noqa: E402
    EmbeddingSplit,
    GraphDefinition,
    TrainingConfig,
    load_fly_a_checkpoint,
    train_fly_b,
)
from flycall_data.m32_inputs import _sha256_json  # noqa: E402


DEFAULT_RUNS = (
    ".scratch/1999-connectome-demo/runs/m3-2-fly-ab-seed-42-crlf-fix-20261026",
    ".scratch/1999-connectome-demo/runs/m3-2-fly-ab-seed-1337-20261026",
    ".scratch/1999-connectome-demo/runs/m3-2-fly-ab-seed-2026-20261026",
)
DEFAULT_EMBEDDING_MANIFEST = ".scratch/1999-connectome-demo/runs/m2-2b-e5-provisional-20261026T015843Z/embedding_manifest.json"
DEFAULT_CACHE_ROOT = ".scratch/1999-connectome-demo/caches/m2-2b-e5-small"
EXPECTED_SEEDS = (42, 1337, 2026)
GRAPH_HASH_KEYS = ("graph_manifest", "io_manifest", "nodes_parquet", "edges_parquet")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise FlyABDiagnosticError(f"Expected a JSON object in {path}.")
    return value


def _verify_output(run_dir: Path, manifest: dict[str, Any], filename: str) -> None:
    outputs = manifest.get("outputs")
    if not isinstance(outputs, dict):
        raise FlyABDiagnosticError(f"{run_dir.name} has no checksummed output map.")
    matches = [spec for key, spec in outputs.items() if Path(key).name == filename]
    if len(matches) != 1 or not isinstance(matches[0], dict):
        raise FlyABDiagnosticError(f"{run_dir.name} has no unique checksum entry for {filename}.")
    path = run_dir / filename
    spec = matches[0]
    if not path.is_file() or path.stat().st_size != spec.get("bytes") or _sha256_file(path) != spec.get("sha256"):
        raise FlyABDiagnosticError(f"{run_dir.name}/{filename} differs from its saved artifact manifest.")


def _read_prediction_rows(path: Path) -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"split", "record_id", "family_id", "expected_label", "predicted_label"}
        if not required.issubset(reader.fieldnames or ()):
            raise FlyABDiagnosticError(f"{path.name} lacks required prediction columns.")
        for row in reader:
            if row["split"] not in {"train", "validation"}:
                raise FlyABDiagnosticError(f"{path.name} contains a non-train/validation row.")
            record_id = row["record_id"]
            if not record_id or record_id in rows:
                raise FlyABDiagnosticError(f"{path.name} contains a missing or duplicate record ID.")
            if row["expected_label"] not in LABEL_ORDER or row["predicted_label"] not in LABEL_ORDER:
                raise FlyABDiagnosticError(f"{path.name} contains a label outside the fixed taxonomy.")
            rows[record_id] = row
    if len(rows) != 850:
        raise FlyABDiagnosticError(f"{path.name} must contain exactly 850 train/validation rows.")
    return rows


def _load_graph(path: Path) -> GraphDefinition:
    value = _read_json(path)
    graph = GraphDefinition(
        node_ids=tuple(int(item) for item in value["node_ids"]),
        input_node_ids=tuple(int(item) for item in value["input_node_ids"]),
        output_node_ids=tuple(int(item) for item in value["output_node_ids"]),
        edges=tuple(tuple(int(part) for part in edge) for edge in value["edges"]),
        steps=int(value["steps"]),
    )
    if len(graph.node_ids) != 500 or len(graph.edges) != 2216 or graph.steps != 2:
        raise FlyABDiagnosticError("Saved graph does not match the pinned 500-node/2,216-edge/T=2 M3.2 graph.")
    return graph


def _make_split(
    split: str,
    entries: list[dict[str, Any]],
    prediction_rows: dict[str, dict[str, str]],
    cache: EmbeddingCache,
) -> tuple[EmbeddingSplit, SplitEmbeddings]:
    selected = sorted((entry for entry in entries if entry["split"] == split), key=lambda item: item["record_id"])
    ids = tuple(str(entry["record_id"]) for entry in selected)
    families = tuple(prediction_rows[record_id]["family_id"] for record_id in ids)
    labels = tuple(prediction_rows[record_id]["expected_label"] for record_id in ids)
    vectors: list[tuple[float, ...]] = []
    for entry in selected:
        if entry.get("dimension") != 384:
            raise FlyABDiagnosticError("The pinned E5 embedding dimension must be 384.")
        key = entry.get("cache_key")
        if not isinstance(key, str) or len(key) != 64:
            raise FlyABDiagnosticError("E5 manifest contains an invalid cache key.")
        vector = cache.get(key)
        if vector is None or len(vector) != 384:
            raise FlyABDiagnosticError(f"Pinned E5 cache vector is missing or has the wrong dimension for {entry['record_id']}.")
        if _sha256_json([float(value) for value in vector]) != entry.get("embedding_sha256"):
            raise FlyABDiagnosticError(f"E5 cache vector checksum differs for {entry['record_id']}.")
        norm = math.sqrt(sum(value * value for value in vector))
        if not math.isclose(norm, 1.0, rel_tol=1e-6, abs_tol=1e-6):
            raise FlyABDiagnosticError(f"E5 cache vector is not unit-normalized for {entry['record_id']}.")
        vectors.append(vector)
    embedding_split = EmbeddingSplit(
        split=split,
        record_ids=ids,
        family_ids=families,
        embeddings=torch.tensor(vectors, dtype=torch.float32, device="cpu"),
        labels=labels,
    )
    feature_split = SplitEmbeddings(split, ids, families, tuple(vectors), labels)
    return embedding_split, feature_split


def load_train_validation_inputs(
    *,
    run_dirs: list[Path],
    embedding_manifest_path: Path,
    cache_root: Path,
) -> list[dict[str, Any]]:
    """Read only checksummed train/validation predictions, embeddings, and A checkpoints."""

    if len(run_dirs) != 3:
        raise FlyABDiagnosticError("Exactly three preregistered seed run directories are required.")
    embedding_manifest_path = embedding_manifest_path.resolve(strict=True)
    embedding_manifest = _read_json(embedding_manifest_path)
    if (
        embedding_manifest.get("evaluation_status") != "smoke_test/provisional"
        or embedding_manifest.get("data_status") != "synthetic"
        or embedding_manifest.get("review_status") != "pending_manual_review"
    ):
        raise FlyABDiagnosticError("E5 manifest is not the frozen provisional train/validation artifact.")
    entries = embedding_manifest.get("entries")
    if not isinstance(entries, list):
        raise FlyABDiagnosticError("E5 embedding manifest has no entry list.")
    validate_embedding_manifest_entries(entries)
    if embedding_manifest.get("splits") != {"train": 700, "validation": 150}:
        raise FlyABDiagnosticError("E5 embedding manifest does not declare exactly 700/150 rows.")
    manifest_digest = _sha256_file(embedding_manifest_path)
    entries_by_id = {str(entry["record_id"]): entry for entry in entries}
    cache = EmbeddingCache(cache_root.resolve(strict=True))

    inputs: list[dict[str, Any]] = []
    shared_identity: tuple[tuple[str, str], ...] | None = None
    shared_reference: dict[str, dict[str, str]] | None = None
    shared_graph: GraphDefinition | None = None
    graph_identity: dict[str, str] | None = None
    observed_seeds: set[int] = set()
    for supplied_run in run_dirs:
        run_dir = supplied_run.resolve(strict=True)
        manifest = _read_json(run_dir / "run_manifest.json")
        run_id = manifest.get("run_id")
        if not isinstance(run_id, str) or not run_id:
            raise FlyABDiagnosticError(f"{run_dir.name} has no run_id.")
        try:
            seed = int(run_id.rsplit("seed-", 1)[1].split("-", 1)[0])
        except (IndexError, ValueError) as error:
            raise FlyABDiagnosticError(f"Unable to determine the preregistered seed for {run_id}.") from error
        if seed not in EXPECTED_SEEDS or seed in observed_seeds:
            raise FlyABDiagnosticError(f"Unexpected or duplicate M3.2 training seed {seed}.")
        observed_seeds.add(seed)
        dataset_audit = manifest.get("dataset_audit")
        data_status = manifest.get("data_status") or (
            dataset_audit.get("data_status") if isinstance(dataset_audit, dict) else None
        )
        review_status = manifest.get("review_status") or (
            dataset_audit.get("review_status") if isinstance(dataset_audit, dict) else None
        )
        if manifest.get("status") != "completed_provisional" or data_status != "synthetic":
            raise FlyABDiagnosticError(f"{run_id} is not a completed synthetic provisional run.")
        if review_status != "pending_manual_review":
            raise FlyABDiagnosticError(f"{run_id} has an unexpected manual review status.")
        if manifest.get("test") != {"metrics": "not_run", "model_inputs": 0, "status": "not_run"}:
            raise FlyABDiagnosticError(f"{run_id} does not prove that test remained unopened.")
        if manifest.get("embedding_counts") != {"test": 0, "train": 700, "validation": 150}:
            raise FlyABDiagnosticError(f"{run_id} does not prove a zero-test embedding boundary.")
        sources = manifest.get("source_sha256")
        if not isinstance(sources, dict) or sources.get("embedding_manifest") != manifest_digest:
            raise FlyABDiagnosticError(f"{run_id} does not reference the frozen E5 manifest checksum.")
        current_graph_identity = {key: str(sources.get(key, "")) for key in GRAPH_HASH_KEYS}
        if any(len(value) != 64 for value in current_graph_identity.values()):
            raise FlyABDiagnosticError(f"{run_id} is missing pinned graph source hashes.")
        if graph_identity is None:
            graph_identity = current_graph_identity
        elif graph_identity != current_graph_identity:
            raise FlyABDiagnosticError("The saved M3.2 runs do not share the same graph provenance.")
        identity = tuple(sorted((key, str(value)) for key, value in sources.items()))
        if shared_identity is None:
            shared_identity = identity
        elif identity != shared_identity:
            raise FlyABDiagnosticError("The saved M3.2 runs do not share source provenance.")
        for filename in ("fly-a-checkpoint.pt", "graph_definition.json", "predictions.csv"):
            _verify_output(run_dir, manifest, filename)
        graph = _load_graph(run_dir / "graph_definition.json")
        if shared_graph is None:
            shared_graph = graph
        elif graph != shared_graph:
            raise FlyABDiagnosticError("M3.2 runs contain different graph definitions.")
        predictions = _read_prediction_rows(run_dir / "predictions.csv")
        if set(predictions) != set(entries_by_id):
            raise FlyABDiagnosticError(f"{run_id} predictions do not exactly cover the frozen 850 train/validation IDs.")
        if shared_reference is None:
            shared_reference = predictions
        else:
            signature = lambda rows: {
                record_id: (row["split"], row["family_id"], row["expected_label"])
                for record_id, row in rows.items()
            }
            if signature(predictions) != signature(shared_reference):
                raise FlyABDiagnosticError("M3.2 seed runs do not share train/validation labels and families.")
        if any(entries_by_id[record_id]["split"] != row["split"] for record_id, row in predictions.items()):
            raise FlyABDiagnosticError(f"{run_id} prediction split identities differ from the embedding manifest.")
        for split, expected_count in (("train", 700), ("validation", 150)):
            split_rows = [row for row in predictions.values() if row["split"] == split]
            if len(split_rows) != expected_count or {row["expected_label"] for row in split_rows} != set(LABEL_ORDER):
                raise FlyABDiagnosticError(f"{run_id} violates the frozen five-class {split} split contract.")
        train_family_ids = {row["family_id"] for row in predictions.values() if row["split"] == "train"}
        validation_family_ids = {row["family_id"] for row in predictions.values() if row["split"] == "validation"}
        if train_family_ids & validation_family_ids:
            raise FlyABDiagnosticError(f"{run_id} has scenario families crossing train and validation.")
        train, train_features = _make_split("train", entries, predictions, cache)
        validation, validation_features = _make_split("validation", entries, predictions, cache)
        checkpoint = run_dir / "fly-a-checkpoint.pt"
        model_a = load_fly_a_checkpoint(
            graph,
            384,
            checkpoint,
            expected_source_sha256=sources,
        )
        model_a.eval()
        with torch.no_grad():
            train_z = model_a(train.embeddings).detach().cpu()
            validation_z = model_a(validation.embeddings).detach().cpu()
        train_probe = SplitEmbeddings(
            "train", train.record_ids, train.family_ids,
            tuple(tuple(float(value) for value in row) for row in train_z.tolist()), train.labels or (),
        )
        validation_probe = SplitEmbeddings(
            "validation", validation.record_ids, validation.family_ids,
            tuple(tuple(float(value) for value in row) for row in validation_z.tolist()), validation.labels or (),
        )
        inputs.append({
            "seed": seed,
            "run_id": run_id,
            "run_dir": run_dir,
            "graph": graph,
            "source_sha256": dict(sources),
            "fly_a_source_sha256": dict(sources),
            "fly_a_checkpoint": checkpoint,
            "fly_a_checkpoint_sha256": _sha256_file(checkpoint),
            "train": train,
            "validation": validation,
            "raw_train_features": train_features,
            "raw_validation_features": validation_features,
            "fly_a_train_features": train_probe,
            "fly_a_validation_features": validation_probe,
            "old_validation": classification_metrics(
                [predictions[record_id]["expected_label"] for record_id in validation.record_ids],
                [predictions[record_id]["predicted_label"] for record_id in validation.record_ids],
                LABEL_ORDER,
            ),
        })
    if observed_seeds != set(EXPECTED_SEEDS):
        raise FlyABDiagnosticError(f"M3.2 diagnostics require exactly seeds {EXPECTED_SEEDS}.")
    return sorted(inputs, key=lambda item: item["seed"])


def _probe_one(train: SplitEmbeddings, validation: SplitEmbeddings, *, seed: int) -> dict[str, Any]:
    results: dict[str, Any] = {}
    for candidate in ("logistic_regression", "mlp"):
        result = run_baseline(
            candidate,
            train,
            validation,
            label_order=LABEL_ORDER,
            seed=seed,
            epochs=80,
            hidden_size=16,
            learning_rate=0.02,
        )
        if result.fit_record_ids != train.record_ids or result.validation_record_ids != validation.record_ids:
            raise FlyABDiagnosticError("Probe estimator fit/evaluation record provenance is incorrect.")
        results[candidate] = {
            "configuration": result.parameters,
            "fit_record_count": len(result.fit_record_ids),
            "validation_record_count": len(result.validation_record_ids),
            "train": result.train_metrics,
            "validation": result.validation_metrics,
        }
    return results


def _aggregate(results: list[dict[str, Any]], *, path: tuple[str, ...]) -> dict[str, float]:
    values = [float(_nested_get(row, path)) for row in results]
    return {
        "mean": statistics.fmean(values),
        "sample_std": statistics.stdev(values) if len(values) > 1 else 0.0,
    }


def _nested_get(value: dict[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = value
    for key in path:
        current = current[key]
    return current


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _markdown(probe: dict[str, Any], tuning: dict[str, Any] | None) -> str:
    lines = [
        "# Fly A→B validation diagnosis",
        "",
        f"- Status: `{probe['status']}`",
        "- Data: `synthetic`; review: `pending_manual_review`",
        "- Test: `not_run`; model inputs: `0`",
        "- Inputs: saved train/validation E5 cache vectors, checksummed M3.2 Fly A checkpoints, and M3.2 train/validation predictions only.",
        "",
        "## Frozen Fly A representation probes",
        "",
        "| Representation | Probe | Mean validation Macro-F1 | Sample SD | Mean validation accuracy | Sample SD |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for representation in ("raw_e5", "fly_a_32d"):
        for candidate in ("logistic_regression", "mlp"):
            summary = probe["summary"][representation][candidate]
            lines.append(
                f"| {representation} | {candidate} | {summary['validation']['macro_f1']['mean']:.4f} | "
                f"{summary['validation']['macro_f1']['sample_std']:.4f} | "
                f"{summary['validation']['accuracy']['mean']:.4f} | "
                f"{summary['validation']['accuracy']['sample_std']:.4f} |"
            )
    lines.extend(["", "### Per-seed probe Macro-F1", "", "| Seed | Raw E5 LR | Raw E5 MLP | Fly A LR | Fly A MLP |", "|---:|---:|---:|---:|---:|"])
    for seed in EXPECTED_SEEDS:
        item = probe["by_seed"][str(seed)]
        lines.append(
            f"| {seed} | {item['raw_e5']['logistic_regression']['validation']['macro_f1']:.4f} | "
            f"{item['raw_e5']['mlp']['validation']['macro_f1']:.4f} | "
            f"{item['fly_a_32d']['logistic_regression']['validation']['macro_f1']:.4f} | "
            f"{item['fly_a_32d']['mlp']['validation']['macro_f1']:.4f} |"
        )
    lines.extend([
        "",
        f"Fly A label-signal decision: `{probe['decision']['branch']}`. "
        f"Mean Fly A MLP Macro-F1 {probe['decision']['fly_a_mlp_mean']:.4f}; "
        f"raw E5 MLP mean {probe['decision']['raw_e5_mlp_mean']:.4f}; "
        f"gap {probe['decision']['raw_minus_fly_a']:.4f}.",
    ])
    if tuning is None:
        lines.extend(["", "No Fly B adjustment experiment was run."])
    elif tuning.get("kind") == "gated_e5_residual_to_fly_b_graph":
        cfg = tuning["configuration"]
        summary = tuning["summary"]
        lines.extend([
            "",
            "## Gated E5 residual candidate",
            "",
            "The candidate combines `FlyB.input_adapter(FlyA(E5)) + sigmoid(g) * W(E5)` immediately before the Fly B graph core. "
            "All logits still pass through that graph core and readout; Fly A remains frozen.",
            "",
            f"Training: Adam, LR `{cfg['learning_rate']}`, batch `{cfg['batch_size']}`, max epochs `{cfg['max_epochs']}`, "
            f"patience `{cfg['patience']}`, clip `{cfg['gradient_clip_norm']}`; same three seeds.",
            "",
            "| Candidate | Mean validation Macro-F1 | Sample SD | Mean accuracy | Sample SD | Δ Macro-F1 vs original | Mean learned gate |",
            "|---|---:|---:|---:|---:|---:|---:|",
            f"| gated E5 residual → Fly B graph | {summary['validation_macro_f1']['mean']:.4f} | "
            f"{summary['validation_macro_f1']['sample_std']:.4f} | {summary['validation_accuracy']['mean']:.4f} | "
            f"{summary['validation_accuracy']['sample_std']:.4f} | {summary['delta_macro_f1_vs_original_mean']:+.4f} | "
            f"{summary['residual_gate_mean']:.4f} |",
            "",
            "### Per-seed comparison",
            "",
            "| Seed | Original F1 | Residual F1 | Δ F1 | Original accuracy | Residual accuracy | Δ accuracy | Selected epoch | Gate |",
            "|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ])
        for row in tuning["by_seed"]:
            lines.append(
                f"| {row['seed']} | {row['original_macro_f1']:.4f} | {row['validation_macro_f1']:.4f} | "
                f"{row['delta_macro_f1']:+.4f} | {row['original_accuracy']:.4f} | {row['validation_accuracy']:.4f} | "
                f"{row['delta_accuracy']:+.4f} | {row['selected_epoch']} | {row['residual_gate']:.4f} |"
            )
        lines.extend([
            "",
            "This is a separate exploratory validation candidate, not a replacement M3.2/M3.4 result. Checkpoint selection used this validation set, so its score is not an unbiased final estimate.",
            "",
            "## Test and review boundary",
            "",
            "No test rows, transcripts, embeddings, predictions, or metrics were read. Formal data remains synthetic and pending manual review. The new candidate remains unlocked and test-ineligible.",
        ])
    else:
        lines.extend(["", "The Fly B schedule sweep ran after Fly A passed the predeclared information-retention rule.", ""])
        for name, result in tuning["schedules"].items():
            lines.append(f"- `{name}`: validation Macro-F1 mean `{result['validation_macro_f1']['mean']:.4f}`; accuracy mean `{result['validation_accuracy']['mean']:.4f}`; Δ Macro-F1 `{result['delta_macro_f1_vs_original_mean']:+.4f}`.")
        lines.extend(["", "All values are exploratory validation metrics; the candidate remains unlocked and test-ineligible."])
    lines.extend(["", "See `diagnosis.json` for source checksums, per-seed train/validation metrics, all schedules, and checkpoint hashes.", ""])
    return "\n".join(lines)


def run_diagnosis(inputs: list[dict[str, Any]], output_dir: Path) -> tuple[dict[str, Any], dict[str, Any] | None]:
    by_seed: dict[str, Any] = {}
    for item in inputs:
        seed = item["seed"]
        by_seed[str(seed)] = {
            "run_id": item["run_id"],
            "source_sha256": item["source_sha256"],
            "fly_a_checkpoint_sha256": item["fly_a_checkpoint_sha256"],
            "original_fly_a_to_fly_b_validation": item["old_validation"],
            "raw_e5": _probe_one(item["raw_train_features"], item["raw_validation_features"], seed=seed),
            "fly_a_32d": _probe_one(item["fly_a_train_features"], item["fly_a_validation_features"], seed=seed),
        }
    probe_summary: dict[str, Any] = {}
    for representation in ("raw_e5", "fly_a_32d"):
        probe_summary[representation] = {}
        for candidate in ("logistic_regression", "mlp"):
            for metric, metric_key in (("macro_f1", "macro_f1"), ("accuracy", "accuracy")):
                for split in ("train", "validation"):
                    probe_summary[representation].setdefault(candidate, {}).setdefault(split, {})[metric] = _aggregate(
                        [by_seed[str(seed)][representation][candidate] for seed in EXPECTED_SEEDS],
                        path=(split, metric_key),
                    )
    raw_mlp_mean = probe_summary["raw_e5"]["mlp"]["validation"]["macro_f1"]["mean"]
    fly_a_mlp_mean = probe_summary["fly_a_32d"]["mlp"]["validation"]["macro_f1"]["mean"]
    signal_retained = fly_a_retains_label_signal(raw_mlp_macro_f1=raw_mlp_mean, fly_a_mlp_macro_f1=fly_a_mlp_mean)
    probe = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "probe_complete",
        "data_status": "synthetic",
        "review_status": "pending_manual_review",
        "label_order": list(LABEL_ORDER),
        "seeds": list(EXPECTED_SEEDS),
        "split_counts": {"train": 700, "validation": 150, "test": 0},
        "test": {"status": "not_run", "model_inputs": 0, "metrics": None},
        "summary": probe_summary,
        "by_seed": by_seed,
        "source_code_sha256": {
            relative: _sha256_file(PROJECT_ROOT / relative)
            for relative in (
                "src/flycall_data/fly_ab_diagnostics.py",
                "src/flycall_data/fly_ab_training.py",
                "src/flycall_data/graph_core.py",
                "scripts/diagnose_fly_a_b.py",
            )
        },
        "decision": {
            "rule": "fly A 32-D MLP mean validation Macro-F1 >= 0.85 and no more than 0.10 below raw E5 MLP",
            "fly_a_mlp_mean": fly_a_mlp_mean,
            "raw_e5_mlp_mean": raw_mlp_mean,
            "raw_minus_fly_a": raw_mlp_mean - fly_a_mlp_mean,
            "signal_retained": signal_retained,
            "branch": "tune_fly_b_schedule" if signal_retained else "add_e5_residual_to_fly_b_graph",
        },
    }
    _write_json(output_dir / "probe_results.json", probe)

    tuning: dict[str, Any] | None
    if signal_retained:
        tuning = _run_fly_b_sweep(inputs, output_dir)
        probe["status"] = "fly_a_probe_and_fly_b_schedule_sweep_complete"
    else:
        tuning = _run_e5_residual(inputs, output_dir)
        probe["status"] = "fly_a_probe_and_gated_e5_residual_complete"
    _write_json(output_dir / "probe_results.json", probe)
    _write_json(output_dir / "tuning_results.json", tuning)
    _write_json(output_dir / "diagnosis.json", {"probe": probe, "tuning": tuning})
    (output_dir / "report.md").write_text(_markdown(probe, tuning), encoding="utf-8")
    return probe, tuning


def _run_e5_residual(inputs: list[dict[str, Any]], output_dir: Path) -> dict[str, Any]:
    by_seed: list[dict[str, Any]] = []
    for item in inputs:
        seed = item["seed"]
        config = TrainingConfig(
            seed=seed,
            batch_size=32,
            max_epochs=100,
            patience=10,
            learning_rate=0.001,
            gradient_clip_norm=1.0,
            torch_threads=1,
        )
        output_path = output_dir / "checkpoints" / "gated-e5-residual" / f"seed-{seed}" / "fly-b-residual-checkpoint.pt"
        source_hashes = dict(item["source_sha256"])
        source_hashes["fly_a_checkpoint"] = item["fly_a_checkpoint_sha256"]
        result = train_fly_b_with_e5_residual(
            item["graph"],
            item["train"],
            item["validation"],
            fly_a_checkpoint_path=item["fly_a_checkpoint"],
            fly_a_source_sha256=item["fly_a_source_sha256"],
            source_sha256=source_hashes,
            checkpoint_path=output_path,
            config=config,
            candidate_name=f"fly_a_to_fly_b_gated_e5_residual_seed_{seed}",
        )
        if result.evaluation is None:
            raise FlyABDiagnosticError("Residual candidate did not produce an evaluation report.")
        validation_metrics = result.evaluation["splits"]["validation"]["metrics"]
        training_metrics = result.evaluation["splits"]["train"]["metrics"]
        reloaded = load_fly_b_e5_residual_checkpoint(
            item["graph"], 384, output_path, expected_source_sha256=source_hashes
        )
        with torch.no_grad():
            fly_a = load_fly_a_checkpoint(
                item["graph"], 384, item["fly_a_checkpoint"],
                expected_source_sha256=item["fly_a_source_sha256"],
            )
            validation_embeddings = item["validation"].embeddings
            a_values = fly_a(validation_embeddings)
            before_reload = result.model(a_values, validation_embeddings)
            after_reload = reloaded(a_values, validation_embeddings)
        reload_diff = float((before_reload - after_reload).abs().max())
        if reload_diff > 1e-6:
            raise FlyABDiagnosticError(f"Residual checkpoint reload changed validation logits by {reload_diff}.")
        original = item["old_validation"]
        by_seed.append({
            "seed": seed,
            "selected_epoch": result.selected_epoch,
            "checkpoint": str(output_path.relative_to(output_dir)).replace("\\", "/"),
            "checkpoint_sha256": result.checkpoint_sha256,
            "parameter_counts": result.model.parameter_counts,
            "train": training_metrics,
            "validation_macro_f1": float(validation_metrics["macro_f1"]),
            "validation_accuracy": float(validation_metrics["accuracy"]),
            "validation_per_class": validation_metrics["per_class"],
            "original_macro_f1": float(original["macro_f1"]),
            "original_accuracy": float(original["accuracy"]),
            "delta_macro_f1": float(validation_metrics["macro_f1"]) - float(original["macro_f1"]),
            "delta_accuracy": float(validation_metrics["accuracy"]) - float(original["accuracy"]),
            "residual_gate": float(result.model.residual_gate.detach()),
            "checkpoint_reload_validation_logits_max_abs_diff": reload_diff,
            "test": "not_run",
        })
    macro_f1 = [row["validation_macro_f1"] for row in by_seed]
    accuracy = [row["validation_accuracy"] for row in by_seed]
    delta_f1 = [row["delta_macro_f1"] for row in by_seed]
    gates = [row["residual_gate"] for row in by_seed]
    return {
        "kind": "gated_e5_residual_to_fly_b_graph",
        "status": "exploratory_validation_candidate_complete_pending_manual_review",
        "configuration": {
            "optimizer": "Adam",
            "learning_rate": 0.001,
            "batch_size": 32,
            "max_epochs": 100,
            "patience": 10,
            "gradient_clip_norm": 1.0,
            "residual_projection": "bias-free 384-to-32 linear",
            "residual_gate_initial_logit": -2.0,
            "fusion": "B adapter(A(E5)) + sigmoid(gate) * E5 residual before B graph",
            "classifier_shortcut": False,
        },
        "summary": {
            "validation_macro_f1": {"mean": statistics.fmean(macro_f1), "sample_std": statistics.stdev(macro_f1)},
            "validation_accuracy": {"mean": statistics.fmean(accuracy), "sample_std": statistics.stdev(accuracy)},
            "delta_macro_f1_vs_original_mean": statistics.fmean(delta_f1),
            "residual_gate_mean": statistics.fmean(gates),
            "checkpoint_reload_max_abs_diff": max(row["checkpoint_reload_validation_logits_max_abs_diff"] for row in by_seed),
        },
        "by_seed": by_seed,
        "test": {"status": "not_run", "model_inputs": 0, "metrics": None},
        "formal_test_eligible": False,
    }


def _run_fly_b_sweep(inputs: list[dict[str, Any]], output_dir: Path) -> dict[str, Any]:
    schedules: dict[str, Any] = {}
    for schedule in FLY_B_TUNING_SCHEDULES:
        by_seed: list[dict[str, Any]] = []
        config_data = {key: value for key, value in schedule.items() if key != "name"}
        for item in inputs:
            seed = item["seed"]
            config = TrainingConfig(seed=seed, batch_size=32, gradient_clip_norm=1.0, torch_threads=1, **config_data)
            output_path = output_dir / "checkpoints" / schedule["name"] / f"seed-{seed}" / "fly-b-checkpoint.pt"
            source_hashes = dict(item["source_sha256"])
            source_hashes["fly_a_checkpoint"] = item["fly_a_checkpoint_sha256"]
            result = train_fly_b(
                item["graph"],
                item["train"],
                item["validation"],
                fly_a_checkpoint_path=item["fly_a_checkpoint"],
                fly_a_source_sha256=item["fly_a_source_sha256"],
                source_sha256=source_hashes,
                checkpoint_path=output_path,
                config=config,
                candidate_name=f"fly_a_to_fly_b_diagnostic_{schedule['name']}_seed_{seed}",
            )
            assert result.evaluation is not None
            validation = result.evaluation["splits"]["validation"]["metrics"]
            original = item["old_validation"]
            by_seed.append({
                "seed": seed,
                "selected_epoch": result.selected_epoch,
                "checkpoint": str(output_path.relative_to(output_dir)).replace("\\", "/"),
                "checkpoint_sha256": result.checkpoint_sha256,
                "train": result.evaluation["splits"]["train"]["metrics"],
                "validation_macro_f1": float(validation["macro_f1"]),
                "validation_accuracy": float(validation["accuracy"]),
                "validation_per_class": validation["per_class"],
                "original_macro_f1": float(original["macro_f1"]),
                "original_accuracy": float(original["accuracy"]),
                "delta_macro_f1": float(validation["macro_f1"]) - float(original["macro_f1"]),
                "delta_accuracy": float(validation["accuracy"]) - float(original["accuracy"]),
                "test": "not_run",
            })
        f1 = [row["validation_macro_f1"] for row in by_seed]
        accuracy = [row["validation_accuracy"] for row in by_seed]
        delta_f1 = [row["delta_macro_f1"] for row in by_seed]
        schedules[schedule["name"]] = {
            "configuration": {**config_data, "batch_size": 32, "gradient_clip_norm": 1.0},
            "validation_macro_f1": {"mean": statistics.fmean(f1), "sample_std": statistics.stdev(f1)},
            "validation_accuracy": {"mean": statistics.fmean(accuracy), "sample_std": statistics.stdev(accuracy)},
            "delta_macro_f1_vs_original_mean": statistics.fmean(delta_f1),
            "by_seed": by_seed,
        }
    selected = min(schedules, key=lambda name: (-schedules[name]["validation_macro_f1"]["mean"], name))
    return {
        "status": "exploratory_validation_tuning_complete_pending_manual_review",
        "selected_schedule": selected,
        "selection_rule": "highest mean validation Macro-F1 across seeds; lexical schedule name breaks ties",
        "schedules": schedules,
        "test": {"status": "not_run", "model_inputs": 0, "metrics": None},
        "formal_test_eligible": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", action="append", default=None, help="one of the three checksummed M3.2 run directories; repeat 3 times")
    parser.add_argument("--embedding-manifest", default=DEFAULT_EMBEDDING_MANIFEST)
    parser.add_argument("--cache-root", default=DEFAULT_CACHE_ROOT)
    parser.add_argument("--output-dir", default=".scratch/1999-connectome-demo/runs/fly-ab-diagnosis-20261026")
    args = parser.parse_args()
    run_dirs = [Path(value) for value in (args.run_dir or DEFAULT_RUNS)]
    output_dir = Path(args.output_dir)
    inputs = load_train_validation_inputs(
        run_dirs=run_dirs,
        embedding_manifest_path=PROJECT_ROOT / args.embedding_manifest,
        cache_root=PROJECT_ROOT / args.cache_root,
    )
    probe, tuning = run_diagnosis(inputs, output_dir)
    print(f"Wrote validation-only Fly A/B diagnosis to {output_dir.as_posix()}")
    print(f"Fly A probe branch: {probe['decision']['branch']}")
    if tuning is not None:
        print(f"Best exploratory Fly B schedule: {tuning['selected_schedule']}")
    print("Test status: not_run; test model inputs: 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

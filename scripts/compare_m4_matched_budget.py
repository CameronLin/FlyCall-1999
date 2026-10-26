#!/usr/bin/env python3
"""Compare MLP, pure Fly A→B, and gated E5 residual on frozen train/validation only."""

from __future__ import annotations

import hashlib
import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"
for import_path in (SRC_ROOT, SCRIPTS_ROOT):
    if str(import_path) not in sys.path:
        sys.path.insert(0, str(import_path))

import torch
from torch.nn import functional as F

from diagnose_fly_a_b import DEFAULT_CACHE_ROOT, DEFAULT_EMBEDDING_MANIFEST, DEFAULT_RUNS, load_train_validation_inputs
from flycall_data.evaluation import LABEL_ORDER, classification_metrics
from flycall_data.fly_ab_training import (
    TrainingConfig,
    load_fly_a_checkpoint,
    load_fly_b_checkpoint,
    train_fly_b,
)


OUTPUT_DIR = PROJECT_ROOT / ".scratch/1999-connectome-demo/runs/m4-matched-budget-validation-20261026"
RESIDUAL_REPORT = PROJECT_ROOT / ".scratch/1999-connectome-demo/runs/fly-ab-diagnosis-20261026/residual_followup.json"
SEEDS = (42, 1337, 2026)
MAX_EPOCHS = 200
PATIENCE = 25


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _mlp_validation_selected(item: dict[str, Any]) -> dict[str, Any]:
    """Train the registered 384→16→5 ReLU MLP and select with the Fly B rule."""

    seed = item["seed"]
    train = item["raw_train_features"]
    validation = item["raw_validation_features"]
    x_train = torch.tensor(train.features, dtype=torch.float32, device="cpu")
    x_validation = torch.tensor(validation.features, dtype=torch.float32, device="cpu")
    y_train = torch.tensor([LABEL_ORDER.index(label) for label in train.labels], dtype=torch.long)
    y_validation = torch.tensor([LABEL_ORDER.index(label) for label in validation.labels], dtype=torch.long)
    previous_threads = torch.get_num_threads()
    try:
        torch.set_num_threads(1)
        with torch.random.fork_rng(devices=[]):
            torch.manual_seed(seed)
            model = torch.nn.Sequential(
                torch.nn.Linear(384, 16),
                torch.nn.ReLU(),
                torch.nn.Linear(16, len(LABEL_ORDER)),
            )
            optimizer = torch.optim.Adam(model.parameters(), lr=0.02)
            best_f1 = -1.0
            best_loss = float("inf")
            best_epoch = 0
            best_state: dict[str, torch.Tensor] | None = None
            stale = 0
            for epoch in range(1, MAX_EPOCHS + 1):
                model.train()
                optimizer.zero_grad(set_to_none=True)
                loss = F.cross_entropy(model(x_train), y_train)
                if not torch.isfinite(loss):
                    raise FloatingPointError("non-finite matched-budget MLP train loss.")
                loss.backward()
                optimizer.step()
                model.eval()
                with torch.no_grad():
                    validation_logits = model(x_validation)
                    validation_loss = F.cross_entropy(validation_logits, y_validation)
                    predictions = tuple(LABEL_ORDER[index] for index in validation_logits.argmax(1).tolist())
                f1 = float(classification_metrics(validation.labels, predictions, LABEL_ORDER)["macro_f1"])
                loss_value = float(validation_loss)
                improved = f1 > best_f1 or (f1 == best_f1 and loss_value < best_loss)
                if improved:
                    best_f1, best_loss, best_epoch = f1, loss_value, epoch
                    best_state = {name: value.detach().clone() for name, value in model.state_dict().items()}
                    stale = 0
                else:
                    stale += 1
                    if stale >= PATIENCE:
                        break
            if best_state is None:
                raise RuntimeError("matched-budget MLP did not produce a validation checkpoint.")
            model.load_state_dict(best_state, strict=True)
            model.eval()
            with torch.no_grad():
                train_logits = model(x_train)
                validation_logits = model(x_validation)
            train_predictions = tuple(LABEL_ORDER[index] for index in train_logits.argmax(1).tolist())
            validation_predictions = tuple(LABEL_ORDER[index] for index in validation_logits.argmax(1).tolist())
        return {
            "selected_epoch": best_epoch,
            "train": classification_metrics(train.labels, train_predictions, LABEL_ORDER),
            "validation": classification_metrics(validation.labels, validation_predictions, LABEL_ORDER),
            "configuration": {
                "input_dimension": 384,
                "hidden_size": 16,
                "activation": "ReLU",
                "optimizer": "Adam",
                "learning_rate": 0.02,
                "max_epochs": MAX_EPOCHS,
                "patience": PATIENCE,
                "batch_size": "full train split (700)",
                "selection": "validation Macro-F1, then lower validation loss; earliest tie",
                "fit_ids": len(train.record_ids),
                "validation_ids": len(validation.record_ids),
            },
            "test": "not_run",
        }
    finally:
        torch.set_num_threads(previous_threads)


def run_comparison() -> dict[str, Any]:
    inputs = load_train_validation_inputs(
        run_dirs=[PROJECT_ROOT / value for value in DEFAULT_RUNS],
        embedding_manifest_path=PROJECT_ROOT / DEFAULT_EMBEDDING_MANIFEST,
        cache_root=PROJECT_ROOT / DEFAULT_CACHE_ROOT,
    )
    residual = json.loads(RESIDUAL_REPORT.read_text(encoding="utf-8"))
    residual_name = "residual_gate_0_lr3_long"
    residual_by_seed = {
        row["seed"]: row for row in residual["configurations"][residual_name]["by_seed"]
    }
    all_rows: dict[str, list[dict[str, Any]]] = {
        "mlp_matched_budget": [],
        "fly_a_to_fly_b_matched_budget": [],
        "gated_e5_residual": [],
    }
    for item in inputs:
        seed = item["seed"]
        mlp = _mlp_validation_selected(item)
        all_rows["mlp_matched_budget"].append({
            "seed": seed,
            **mlp,
        })
        config = TrainingConfig(
            seed=seed,
            batch_size=32,
            max_epochs=MAX_EPOCHS,
            patience=PATIENCE,
            learning_rate=0.003,
            gradient_clip_norm=1.0,
            torch_threads=1,
        )
        checkpoint = OUTPUT_DIR / "checkpoints" / "pure-fly-a-to-fly-b" / f"seed-{seed}" / "fly-b.pt"
        sources = dict(item["source_sha256"])
        sources["fly_a_checkpoint"] = item["fly_a_checkpoint_sha256"]
        result = train_fly_b(
            item["graph"],
            item["train"],
            item["validation"],
            fly_a_checkpoint_path=item["fly_a_checkpoint"],
            fly_a_source_sha256=item["fly_a_source_sha256"],
            source_sha256=sources,
            checkpoint_path=checkpoint,
            config=config,
            candidate_name=f"fly_a_to_fly_b_matched_budget_seed_{seed}",
        )
        if result.evaluation is None:
            raise RuntimeError("matched-budget Fly A→B did not return validation metrics.")
        a_model = load_fly_a_checkpoint(
            item["graph"], 384, item["fly_a_checkpoint"],
            expected_source_sha256=item["fly_a_source_sha256"],
        )
        b_model = load_fly_b_checkpoint(item["graph"], checkpoint, expected_source_sha256=sources)
        with torch.no_grad():
            a_values = a_model(item["validation"].embeddings)
            original_logits = result.model(a_values)
            reloaded_logits = b_model(a_values)
        reload_diff = float((original_logits - reloaded_logits).abs().max())
        if reload_diff > 1e-6:
            raise RuntimeError(f"matched-budget Fly B reload difference exceeds tolerance: {reload_diff}")
        split_metrics = result.evaluation["splits"]
        all_rows["fly_a_to_fly_b_matched_budget"].append({
            "seed": seed,
            "selected_epoch": result.selected_epoch,
            "train": split_metrics["train"]["metrics"],
            "validation": split_metrics["validation"]["metrics"],
            "configuration": {
                "optimizer": "Adam", "learning_rate": 0.003, "batch_size": 32,
                "max_epochs": MAX_EPOCHS, "patience": PATIENCE, "gradient_clip_norm": 1.0,
            },
            "checkpoint": checkpoint.relative_to(OUTPUT_DIR).as_posix(),
            "checkpoint_sha256": _sha256(checkpoint),
            "checkpoint_reload_validation_logits_max_abs_diff": reload_diff,
            "test": "not_run",
        })
        residual_row = residual_by_seed[seed]
        all_rows["gated_e5_residual"].append({
            "seed": seed,
            "selected_epoch": residual_row["selected_epoch"],
            "train": residual_row["train"],
            "validation": {
                "macro_f1": residual_row["validation_macro_f1"],
                "accuracy": residual_row["validation_accuracy"],
                "per_class": residual_row["validation_per_class"],
            },
            "configuration": residual["configurations"][residual_name]["configuration"],
            "checkpoint": residual_row["checkpoint"],
            "checkpoint_sha256": residual_row["checkpoint_sha256"],
            "checkpoint_reload_validation_logits_max_abs_diff": residual_row["checkpoint_reload_validation_logits_max_abs_diff"],
            "test": "not_run",
        })

    summaries: dict[str, Any] = {}
    for candidate, rows in all_rows.items():
        f1 = [
            row["validation"]["macro_f1"]
            if candidate == "mlp_matched_budget"
            else row["validation"]["macro_f1"]
            for row in rows
        ]
        accuracy = [
            row["validation"]["accuracy"]
            if candidate == "mlp_matched_budget"
            else row["validation"]["accuracy"]
            for row in rows
        ]
        summaries[candidate] = {
            "validation_macro_f1": {"mean": statistics.fmean(f1), "sample_std": statistics.stdev(f1)},
            "validation_accuracy": {"mean": statistics.fmean(accuracy), "sample_std": statistics.stdev(accuracy)},
            "by_seed": rows,
        }
    result = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "matched_budget_validation_only_complete_pending_manual_review",
        "data_status": "synthetic",
        "review_status": "pending_manual_review",
        "seeds": list(SEEDS),
        "split_counts": {"train": 700, "validation": 150, "test": 0},
        "candidates": summaries,
        "test": {"status": "not_run", "model_inputs": 0, "metrics": None},
        "formal_test_eligible": False,
        "source_code_sha256": {
            name: _sha256(PROJECT_ROOT / name)
            for name in (
                "scripts/compare_m4_matched_budget.py",
                "scripts/diagnose_fly_a_b.py",
                "src/flycall_data/fly_ab_training.py",
                "src/flycall_data/fly_ab_diagnostics.py",
                "src/flycall_data/graph_core.py",
            )
        },
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _write_json(OUTPUT_DIR / "matched_budget_comparison.json", result)
    _write_markdown(result)
    files = {}
    for path in sorted(OUTPUT_DIR.rglob("*")):
        if path.is_file() and path.name != "artifact_manifest.json":
            files[path.relative_to(OUTPUT_DIR).as_posix()] = {"bytes": path.stat().st_size, "sha256": _sha256(path)}
    _write_json(OUTPUT_DIR / "artifact_manifest.json", {
        "scope": "M4 matched-budget train/validation comparison; test not run",
        "review_status": "pending_manual_review",
        "test": {"status": "not_run", "model_inputs": 0},
        "files": files,
    })
    return result


def _write_markdown(result: dict[str, Any]) -> None:
    lines = [
        "# M4 matched-budget validation comparison",
        "",
        "- Status: `matched_budget_validation_only_complete_pending_manual_review`",
        "- Data: `synthetic`; review: `pending_manual_review`",
        "- Test: `not_run`; test inputs: `0`",
        "- Same frozen seeds: `42, 1337, 2026`; each candidate fits train only and selects/checks on validation.",
        "",
        "| Candidate | Macro-F1 mean | Sample SD | Accuracy mean | Sample SD |",
        "|---|---:|---:|---:|---:|",
    ]
    for name, summary in result["candidates"].items():
        lines.append(
            f"| {name} | {summary['validation_macro_f1']['mean']:.4f} | "
            f"{summary['validation_macro_f1']['sample_std']:.4f} | "
            f"{summary['validation_accuracy']['mean']:.4f} | {summary['validation_accuracy']['sample_std']:.4f} |"
        )
    lines.extend(["", "## Per-seed validation metrics", "", "| Candidate | Seed | Macro-F1 | Accuracy | Selected epoch |", "|---|---:|---:|---:|---:|"])
    for candidate, summary in result["candidates"].items():
        for row in summary["by_seed"]:
            validation = row["validation"]
            lines.append(
                f"| {candidate} | {row['seed']} | {validation['macro_f1']:.4f} | "
                f"{validation['accuracy']:.4f} | {row.get('selected_epoch', 'fixed') } |"
            )
    lines.extend([
        "",
        "The original registered M3.4 comparison remains authoritative for candidate selection. This matched-budget run is a validation-only diagnostic; no test data were opened.",
        "",
    ])
    (OUTPUT_DIR / "report.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    result = run_comparison()
    print("Matched-budget validation comparison completed.")
    print(f"Candidates: {', '.join(result['candidates'])}")
    print("Test status: not_run; test inputs: 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

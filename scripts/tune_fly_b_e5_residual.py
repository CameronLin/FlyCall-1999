#!/usr/bin/env python3
"""Run the preregistered train/validation-only stability sweep for the Fly B E5 residual."""

from __future__ import annotations

import json
import hashlib
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

from diagnose_fly_a_b import DEFAULT_CACHE_ROOT, DEFAULT_EMBEDDING_MANIFEST, DEFAULT_RUNS, load_train_validation_inputs
from flycall_data.fly_ab_diagnostics import load_fly_b_e5_residual_checkpoint, train_fly_b_with_e5_residual
from flycall_data.fly_ab_training import TrainingConfig, load_fly_a_checkpoint


FOLLOWUP_CONFIGS = (
    {"name": "residual_gate_m2_long", "gate_logit_init": -2.0, "learning_rate": 0.001, "max_epochs": 200, "patience": 25},
    {"name": "residual_gate_m2_lr3_long", "gate_logit_init": -2.0, "learning_rate": 0.003, "max_epochs": 200, "patience": 25},
    {"name": "residual_gate_0_long", "gate_logit_init": 0.0, "learning_rate": 0.001, "max_epochs": 200, "patience": 25},
    {"name": "residual_gate_0_lr3_long", "gate_logit_init": 0.0, "learning_rate": 0.003, "max_epochs": 200, "patience": 25},
)
OUTPUT_DIR = PROJECT_ROOT / ".scratch/1999-connectome-demo/runs/fly-ab-diagnosis-20261026"


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object in {path}.")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run_sweep() -> dict[str, Any]:
    existing = _read_json(OUTPUT_DIR / "diagnosis.json")
    if existing.get("probe", {}).get("decision", {}).get("signal_retained") is not False:
        raise ValueError("Residual tuning is authorized only after the registered Fly A probe failed its signal-retention rule.")
    control = existing.get("tuning")
    if not isinstance(control, dict) or control.get("kind") != "gated_e5_residual_to_fly_b_graph":
        raise ValueError("The fixed-schedule residual control must be present before its follow-up sweep.")
    if existing.get("probe", {}).get("test") != {"status": "not_run", "model_inputs": 0, "metrics": None}:
        raise ValueError("The probe report does not prove that test remained untouched.")

    inputs = load_train_validation_inputs(
        run_dirs=[PROJECT_ROOT / item for item in DEFAULT_RUNS],
        embedding_manifest_path=PROJECT_ROOT / DEFAULT_EMBEDDING_MANIFEST,
        cache_root=PROJECT_ROOT / DEFAULT_CACHE_ROOT,
    )
    control_by_seed = {row["seed"]: row for row in control["by_seed"]}
    config_results: dict[str, Any] = {}
    for candidate in FOLLOWUP_CONFIGS:
        rows: list[dict[str, Any]] = []
        for item in inputs:
            seed = item["seed"]
            training = TrainingConfig(
                seed=seed,
                batch_size=32,
                max_epochs=candidate["max_epochs"],
                patience=candidate["patience"],
                learning_rate=candidate["learning_rate"],
                gradient_clip_norm=1.0,
                torch_threads=1,
            )
            checkpoint = (
                OUTPUT_DIR
                / "checkpoints"
                / "residual-follow-up"
                / candidate["name"]
                / f"seed-{seed}"
                / "fly-b-residual-checkpoint.pt"
            )
            source_hashes = dict(item["source_sha256"])
            source_hashes["fly_a_checkpoint"] = item["fly_a_checkpoint_sha256"]
            result = train_fly_b_with_e5_residual(
                item["graph"],
                item["train"],
                item["validation"],
                fly_a_checkpoint_path=item["fly_a_checkpoint"],
                fly_a_source_sha256=item["fly_a_source_sha256"],
                source_sha256=source_hashes,
                checkpoint_path=checkpoint,
                config=training,
                candidate_name=f"{candidate['name']}_seed_{seed}",
                gate_logit_init=candidate["gate_logit_init"],
            )
            if result.evaluation is None:
                raise RuntimeError(f"{candidate['name']} seed {seed} did not yield train/validation metrics.")
            validation_metrics = result.evaluation["splits"]["validation"]["metrics"]
            train_metrics = result.evaluation["splits"]["train"]["metrics"]
            reloaded = load_fly_b_e5_residual_checkpoint(
                item["graph"],
                384,
                checkpoint,
                expected_source_sha256=source_hashes,
                gate_logit_init=candidate["gate_logit_init"],
            )
            with torch.no_grad():
                fly_a = load_fly_a_checkpoint(
                    item["graph"], 384, item["fly_a_checkpoint"],
                    expected_source_sha256=item["fly_a_source_sha256"],
                )
                e5_values = item["validation"].embeddings
                a_values = fly_a(e5_values)
                before = result.model(a_values, e5_values)
                after = reloaded(a_values, e5_values)
            reload_diff = float((before - after).abs().max())
            if reload_diff > 1e-6:
                raise RuntimeError(f"{candidate['name']} seed {seed} reload diff={reload_diff}.")
            base = control_by_seed[seed]
            original = item["old_validation"]
            f1 = float(validation_metrics["macro_f1"])
            accuracy = float(validation_metrics["accuracy"])
            rows.append({
                "seed": seed,
                "selected_epoch": result.selected_epoch,
                "checkpoint": checkpoint.relative_to(OUTPUT_DIR).as_posix(),
                "checkpoint_sha256": result.checkpoint_sha256,
                "parameter_counts": result.model.parameter_counts,
                "train": train_metrics,
                "validation_macro_f1": f1,
                "validation_accuracy": accuracy,
                "validation_per_class": validation_metrics["per_class"],
                "original_macro_f1": float(original["macro_f1"]),
                "original_accuracy": float(original["accuracy"]),
                "control_residual_macro_f1": base["validation_macro_f1"],
                "control_residual_accuracy": base["validation_accuracy"],
                "delta_macro_f1_vs_original": f1 - float(original["macro_f1"]),
                "delta_accuracy_vs_original": accuracy - float(original["accuracy"]),
                "delta_macro_f1_vs_control_residual": f1 - base["validation_macro_f1"],
                "residual_gate": float(result.model.residual_gate.detach()),
                "checkpoint_reload_validation_logits_max_abs_diff": reload_diff,
                "test": "not_run",
            })
        f1_values = [row["validation_macro_f1"] for row in rows]
        accuracy_values = [row["validation_accuracy"] for row in rows]
        config_results[candidate["name"]] = {
            "configuration": {key: value for key, value in candidate.items() if key != "name"} | {
                "batch_size": 32,
                "gradient_clip_norm": 1.0,
            },
            "validation_macro_f1": {"mean": statistics.fmean(f1_values), "sample_std": statistics.stdev(f1_values)},
            "validation_accuracy": {"mean": statistics.fmean(accuracy_values), "sample_std": statistics.stdev(accuracy_values)},
            "delta_macro_f1_vs_original_mean": statistics.fmean(row["delta_macro_f1_vs_original"] for row in rows),
            "delta_macro_f1_vs_control_mean": statistics.fmean(row["delta_macro_f1_vs_control_residual"] for row in rows),
            "by_seed": rows,
        }
    best = min(config_results, key=lambda name: (-config_results[name]["validation_macro_f1"]["mean"], name))
    output = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "kind": "gated_e5_residual_stability_sweep",
        "status": "exploratory_validation_sweep_complete_pending_manual_review",
        "data_status": "synthetic",
        "review_status": "pending_manual_review",
        "seeds": [42, 1337, 2026],
        "source_code_sha256": {
            relative: _sha256_file(PROJECT_ROOT / relative)
            for relative in (
                "src/flycall_data/fly_ab_diagnostics.py",
                "src/flycall_data/fly_ab_training.py",
                "src/flycall_data/graph_core.py",
                "scripts/diagnose_fly_a_b.py",
                "scripts/tune_fly_b_e5_residual.py",
            )
        },
        "configurations": config_results,
        "highest_mean_validation_macro_f1_configuration": best,
        "selection_rule": "highest mean validation Macro-F1 across the same three seeds; this is exploratory and not a final model lock",
        "test": {"status": "not_run", "model_inputs": 0, "metrics": None},
        "formal_test_eligible": False,
    }
    _write_json(OUTPUT_DIR / "residual_followup.json", output)
    existing["residual_followup"] = output
    _write_json(OUTPUT_DIR / "diagnosis.json", existing)
    _append_report(OUTPUT_DIR / "report.md", output)
    files = {}
    for path in sorted(OUTPUT_DIR.rglob("*")):
        if not path.is_file() or path.name == "artifact_manifest.json":
            continue
        relative = path.relative_to(OUTPUT_DIR).as_posix()
        files[relative] = {"bytes": path.stat().st_size, "sha256": _sha256_file(path)}
    _write_json(OUTPUT_DIR / "artifact_manifest.json", {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "validation-only exploratory Fly A/B diagnostics; test not run",
        "files": files,
    })
    return output


def _append_report(path: Path, output: dict[str, Any]) -> None:
    lines = [
        "",
        "## Residual stability follow-up",
        "",
        "All configurations were preregistered in `fly-a-b-diagnostic-preregistration-20261026.md` before this sweep. Every result uses the same three train/validation seeds.",
        "",
        "| Configuration | Gate init | LR | Epochs | Patience | Mean validation Macro-F1 | Sample SD | Mean accuracy | Sample SD | Δ F1 vs original | Δ F1 vs first residual |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, result in output["configurations"].items():
        cfg = result["configuration"]
        lines.append(
            f"| {name} | {cfg['gate_logit_init']:.1f} | {cfg['learning_rate']:.3g} | {cfg['max_epochs']} | {cfg['patience']} | "
            f"{result['validation_macro_f1']['mean']:.4f} | {result['validation_macro_f1']['sample_std']:.4f} | "
            f"{result['validation_accuracy']['mean']:.4f} | {result['validation_accuracy']['sample_std']:.4f} | "
            f"{result['delta_macro_f1_vs_original_mean']:+.4f} | {result['delta_macro_f1_vs_control_mean']:+.4f} |"
        )
    lines.extend(["", "### Per-seed results", "", "| Configuration | Seed | Original F1 | First residual F1 | Follow-up F1 | Δ vs original | Δ vs residual | Accuracy | Epoch | Gate |", "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"])
    for name, result in output["configurations"].items():
        for row in result["by_seed"]:
            lines.append(
                f"| {name} | {row['seed']} | {row['original_macro_f1']:.4f} | {row['control_residual_macro_f1']:.4f} | "
                f"{row['validation_macro_f1']:.4f} | {row['delta_macro_f1_vs_original']:+.4f} | "
                f"{row['delta_macro_f1_vs_control_residual']:+.4f} | {row['validation_accuracy']:.4f} | "
                f"{row['selected_epoch']} | {row['residual_gate']:.4f} |"
            )
    lines.extend([
        "",
        f"Highest validation mean: `{output['highest_mean_validation_macro_f1_configuration']}`. "
        "This used the same validation split for configuration comparison, so report it as exploratory. No test split was read; the candidate remains unlocked.",
        "",
    ])
    with path.open("a", encoding="utf-8", newline="") as stream:
        stream.write("\n".join(lines))


def main() -> int:
    output = run_sweep()
    print("Residual stability sweep complete.")
    print(f"Highest mean validation Macro-F1 config: {output['highest_mean_validation_macro_f1_configuration']}")
    print("Test status: not_run; test model inputs: 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

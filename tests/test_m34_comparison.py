from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import compare_m3_4_validation as comparison_cli
from flycall_data.comparison import CANDIDATE_NAMES, ComparisonError, aggregate_validation_runs
from flycall_data.evaluation import LABEL_ORDER


SEEDS = (42, 1337, 2026)
DATASET_HASHES = {
    name: hashlib.sha256(name.encode("utf-8")).hexdigest()
    for name in ("jsonl", "csv", "taxonomy", "manifest")
}
GRAPH_HASHES = {
    name: hashlib.sha256(name.encode("utf-8")).hexdigest()
    for name in ("graph_manifest", "io_manifest", "nodes_parquet", "edges_parquet")
}
E5_IDENTITY = {
    "model_id": "intfloat/multilingual-e5-small",
    "revision": "614241f622f53c4eeff9890bdc4f31cfecc418b3",
    "prefix": "query: ",
    "max_seq_length": 512,
    "pooling": "masked_mean",
    "normalize_embeddings": True,
    "model_file_sha256": [["model.safetensors", "a" * 64]],
}


def _write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _metrics(candidate_name: str, errors_per_class: int) -> dict:
    matrix = [
        [30 - errors_per_class if row == column else errors_per_class // 4 for column in range(5)]
        for row in range(5)
    ]
    per_class = {}
    for index, label in enumerate(LABEL_ORDER):
        tp = matrix[index][index]
        predicted_support = sum(matrix[row][index] for row in range(5))
        precision = tp / predicted_support if predicted_support else 0.0
        recall = tp / 30
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class[label] = {"precision": precision, "recall": recall, "f1": f1, "support": 30}
    return {
        "evaluation_status": "smoke_test/provisional",
        "data_status": "synthetic",
        "review_status": "pending_manual_review",
        "candidate_name": candidate_name,
        "label_order": list(LABEL_ORDER),
        "splits": {
            "train": {"status": "evaluated", "n_records": 700},
            "validation": {
                "status": "evaluated",
                "n_records": 150,
                "metrics": {
                    "labels": list(LABEL_ORDER),
                    "accuracy": sum(matrix[index][index] for index in range(5)) / 150,
                    "macro_f1": sum(value["f1"] for value in per_class.values()) / 5,
                    "per_class": per_class,
                    "confusion_matrix": matrix,
                },
            },
            "test": {"status": "not_run"},
        },
    }


def _registration(candidate: str, seed: int) -> dict:
    if candidate == "fly_a_to_fly_b":
        value = {
            "schema_version": 1,
            "status": "pre_registered",
            "embedding": dict(E5_IDENTITY),
            "graph": {
                "pinned_m12_manifest_sha256": GRAPH_HASHES["graph_manifest"],
                "pinned_m13_io_manifest_sha256": GRAPH_HASHES["io_manifest"],
                "steps": 2,
                "node_count": 500,
            },
            "training": {"candidate_name": f"fly_a_to_fly_b_m3_2_seed_{seed}", "seed": seed, "batch_size": 32},
        }
    else:
        candidates = {}
        for name in CANDIDATE_NAMES[:-1]:
            candidates[name] = {"classifier": name, "seed": seed, "random_state": seed, "epochs": 80}
        value = {
            "schema_version": 1,
            "status": "pre_registered",
            "seed": seed,
            "embedding": dict(E5_IDENTITY),
            "candidates": candidates,
        }
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    value["configuration_fingerprint"] = hashlib.sha256(encoded).hexdigest()
    return value


def _make_run(root: Path, candidate: str, seed: int, score_rank: int) -> Path:
    run_dir = root / f"{candidate}-{seed}"
    run_dir.mkdir()
    registration = _registration(candidate, seed)
    _write_json(run_dir / "pre_registered_candidates.json", registration)
    errors = (score_rank + (seed // 42) % 2) * 4
    if candidate == "fly_a_to_fly_b":
        metrics = _metrics(f"fly_a_to_fly_b_m3_2_seed_{seed}", errors)
        sources = {**DATASET_HASHES, **GRAPH_HASHES}
        run_manifest = {
            "run_id": run_dir.name,
            "status": "completed_provisional",
            "configuration_fingerprint": registration["configuration_fingerprint"],
            "dataset_audit": {"data_status": "synthetic", "review_status": "pending_manual_review"},
            "source_sha256": sources,
            "test": {"status": "not_run", "model_inputs": 0, "metrics": "not_run"},
        }
    else:
        outputs = {}
        for name in CANDIDATE_NAMES[:-1]:
            metrics_candidate = _metrics(name, errors + (0 if name == candidate else 4))
            outputs[name] = {"report": metrics_candidate}
        metrics = {
            "data_status": "synthetic",
            "review_status": "pending_manual_review",
            "evaluation_status": "smoke_test/provisional",
            "label_order": list(LABEL_ORDER),
            "test": {"status": "not_run", "input_count": 0, "prediction_count": 0, "metrics": None},
            "candidates": outputs,
        }
        run_manifest = {
            "run_id": run_dir.name,
            "result_status": "provisional",
            "candidate_settings_fingerprint": registration["configuration_fingerprint"],
            "data_status": "synthetic",
            "review_status": "pending_manual_review",
            "source_sha256_after": DATASET_HASHES,
            "test": {"status": "not_run", "input_count": 0, "prediction_count": 0},
        }
    metrics_path = run_dir / "metrics.json"
    _write_json(metrics_path, metrics)
    run_manifest["outputs"] = {
        "metrics.json": {"bytes": metrics_path.stat().st_size, "sha256": hashlib.sha256(metrics_path.read_bytes()).hexdigest()}
    }
    _write_json(run_dir / "run_manifest.json", run_manifest)
    return run_dir


class M34ComparisonTests(unittest.TestCase):
    def _fixture(self, root: Path) -> list[Path]:
        runs: list[Path] = []
        for seed_index, seed in enumerate(SEEDS):
            runs.append(_make_run(root, "baselines", seed, seed_index))
            runs.append(_make_run(root, "fly_a_to_fly_b", seed, seed_index))
        return runs

    def test_aggregates_five_candidates_across_three_seeds_and_selects_validation_winner(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runs = self._fixture(root)
            result = aggregate_validation_runs(runs, required_seeds=SEEDS)

        self.assertEqual(result["status"], "validation_complete_pending_manual_review")
        self.assertEqual(result["candidate_names"], list(CANDIDATE_NAMES))
        self.assertEqual(result["seeds"], list(SEEDS))
        self.assertEqual(result["validation_winner"], "fly_a_to_fly_b")
        self.assertEqual(result["test"]["status"], "not_run")
        self.assertFalse(result["formal_test_eligible"])
        self.assertEqual(result["candidates"]["fly_a_to_fly_b"]["seed_count"], 3)
        self.assertGreaterEqual(result["candidates"]["fly_a_to_fly_b"]["validation_macro_f1"]["sample_std"], 0)

    def test_rejects_metrics_checksum_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runs = self._fixture(root)
            metrics_path = runs[0] / "metrics.json"
            metrics_path.write_text(metrics_path.read_text(encoding="utf-8") + " ", encoding="utf-8")
            with self.assertRaisesRegex(ComparisonError, "checksum differs"):
                aggregate_validation_runs(runs, required_seeds=SEEDS)

    def test_rejects_any_test_result_even_if_status_says_not_run(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runs = self._fixture(root)
            metrics_path = runs[0] / "metrics.json"
            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
            metrics["candidates"]["logistic_regression"]["report"]["splits"]["test"]["accuracy"] = 1.0
            _write_json(metrics_path, metrics)
            run_manifest_path = runs[0] / "run_manifest.json"
            run_manifest = json.loads(run_manifest_path.read_text(encoding="utf-8"))
            run_manifest["outputs"]["metrics.json"]["bytes"] = metrics_path.stat().st_size
            run_manifest["outputs"]["metrics.json"]["sha256"] = hashlib.sha256(metrics_path.read_bytes()).hexdigest()
            _write_json(run_manifest_path, run_manifest)
            with self.assertRaisesRegex(ComparisonError, "test result fields"):
                aggregate_validation_runs(runs, required_seeds=SEEDS)

    def test_cli_persists_preregistration_before_aggregating_run_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runs_root = root / "runs"
            runs_root.mkdir()
            runs = self._fixture(runs_root)
            output_parent = root / "output"
            output_dir = output_parent / "m3-4-validation-comparison-fixture"

            def aggregate_after_preregistration(run_dirs, *, required_seeds, candidate_names):
                self.assertTrue((output_dir / "pre_registered_comparison.json").is_file())
                return aggregate_validation_runs(
                    run_dirs,
                    required_seeds=required_seeds,
                    candidate_names=candidate_names,
                )

            args = ["--output-parent", str(output_parent), "--output-id", "fixture"]
            for seed in SEEDS:
                args.extend(("--seed", str(seed)))
            for run_dir in runs:
                args.extend(("--run-dir", str(run_dir)))
            with patch.object(comparison_cli, "aggregate_validation_runs", side_effect=aggregate_after_preregistration):
                status = comparison_cli.main(args)

            self.assertEqual(status, 0)
            result = json.loads((output_dir / "comparison.json").read_text(encoding="utf-8"))
            selection = json.loads((output_dir / "candidate_selection.json").read_text(encoding="utf-8"))
            report = (output_dir / "report.md").read_text(encoding="utf-8")
            self.assertEqual(result["validation_winner"], "fly_a_to_fly_b")
            self.assertFalse(selection["formal_test_eligible"])
            self.assertEqual(selection["test"], "not_run")
            self.assertIn("## Per-seed validation metrics", report)
            for candidate in CANDIDATE_NAMES:
                for seed in SEEDS:
                    self.assertIn(f"| `{candidate}` | {seed} |", report)
            self.assertIn("| `fly_a_to_fly_b` | 2026 |", report)


if __name__ == "__main__":
    unittest.main()

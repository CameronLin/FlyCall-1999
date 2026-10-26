from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

import run_m3_2_fly_ab_provisional as runner  # noqa: E402
from flycall_data.m32_inputs import M32InputGateError  # noqa: E402


class M32RunnerTests(unittest.TestCase):
    def test_e5_bundle_validates_output_hash_and_zero_test_usage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run_dir = root / "e5-run"
            run_dir.mkdir()
            embedding_manifest_path = run_dir / "embedding_manifest.json"
            embedding_manifest_path.write_text(
                json.dumps({"evaluation_status": "smoke_test/provisional"}),
                encoding="utf-8",
            )
            embedding_hash = hashlib.sha256(embedding_manifest_path.read_bytes()).hexdigest()
            artifact_key = embedding_manifest_path.relative_to(root).as_posix()
            e5_run_manifest = {
                "run_id": "m2-2b-e5-provisional-20261026T015843Z",
                "data_status": "synthetic",
                "review_status": "pending_manual_review",
                "result_status": "provisional",
                "evaluation_status": "smoke_test",
                "checkpoint_reload_verified": True,
                "source_checksums_unchanged": True,
                "test": {
                    "status": "not_run",
                    "transcript_count_passed_to_tokenizer": 0,
                    "embedding_count": 0,
                    "prediction_count": 0,
                    "metrics": None,
                },
                "outputs": {artifact_key: {"sha256": embedding_hash}},
            }
            (run_dir / "run_manifest.json").write_text(
                json.dumps(e5_run_manifest),
                encoding="utf-8",
            )
            requirements_path = root / "requirements.in"
            lock_path = root / "requirements.lock"
            requirements_path.write_text("", encoding="utf-8")
            lock_path.write_text("", encoding="utf-8")
            with (
                patch.object(runner, "PROJECT_ROOT", root),
                patch.object(runner, "E5_RUN_DIR", run_dir),
                patch.object(runner, "E5_EMBEDDING_MANIFEST", embedding_manifest_path),
                patch.object(runner, "E5_CACHE_ROOT", root / "cache"),
                patch.object(runner, "REQUIREMENTS_PATH", requirements_path),
                patch.object(runner, "LOCK_PATH", lock_path),
            ):
                loaded_run, loaded_embedding, loaded_hash = runner._verify_e5_run_bundle()
            self.assertEqual(loaded_run["run_id"], e5_run_manifest["run_id"])
            self.assertEqual(loaded_embedding["evaluation_status"], "smoke_test/provisional")
            self.assertEqual(loaded_hash, embedding_hash)

    def test_source_gate_writes_preregistration_then_stops_before_data_or_graph_load(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output_parent = Path(directory) / "runs"
            with (
                patch.object(
                    runner,
                    "verify_m32_graph_provenance",
                    side_effect=M32InputGateError("pinned manifest mismatch"),
                ),
                patch.object(runner, "load_frozen_dataset") as load_dataset,
                patch.object(runner, "load_m32_graph") as load_graph,
            ):
                result = runner.main(
                    [
                        "--run-id",
                        "m3-2-gate-preflight-fixture",
                        "--output-parent",
                        str(output_parent),
                        "--seed",
                        "1337",
                    ]
                )
            run_dir = output_parent / "m3-2-gate-preflight-fixture"
            self.assertEqual(result, 2)
            self.assertTrue((run_dir / "pre_registered_candidates.json").is_file())
            registration = json.loads((run_dir / "pre_registered_candidates.json").read_text(encoding="utf-8"))
            self.assertEqual(registration["training"]["seed"], 1337)
            self.assertEqual(registration["training"]["candidate_name"], "fly_a_to_fly_b_m3_2_seed_1337")
            manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "blocked")
            self.assertEqual(manifest["stopped_at_phase"], "graph-provenance-preflight")
            self.assertEqual(manifest["test"]["status"], "not_run")
            load_dataset.assert_not_called()
            load_graph.assert_not_called()


if __name__ == "__main__":
    unittest.main()

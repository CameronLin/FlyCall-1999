from __future__ import annotations

import contextlib
import dataclasses
import hashlib
import io
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

import app  # noqa: E402
import predict_flycall  # noqa: E402
import run_m2_2b_e5_provisional as m2_runner  # noqa: E402
import flycall_data.predictor as prediction_module  # noqa: E402
from flycall_data.e5_runtime import E5_MODEL_FILE_SHA256  # noqa: E402
from flycall_data.embedding_pipeline import SplitEmbeddings, run_baseline  # noqa: E402
from flycall_data.evaluation import LABEL_ORDER  # noqa: E402
from flycall_data.fly_ab_training import EmbeddingSplit, GraphDefinition, TrainingConfig, train_fly_a, train_fly_b  # noqa: E402
from flycall_data.lda_baseline import run_lda_logistic_baseline  # noqa: E402
from flycall_data.predictor import FlyCallPredictor, PredictorError  # noqa: E402
from test_m2_checkpoint import _fixture_splits  # noqa: E402


class FakeEncoder:
    def encode(self, texts):
        if len(texts) != 1 or not texts[0].startswith("query: "):
            raise ValueError("unexpected encoder input")
        vector = [0.0] * 384
        vector[0] = 1.0
        return [vector]


def _write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _hash_record(path: Path) -> dict:
    return {"bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


class FakeStreamlit(types.ModuleType):
    def __init__(self):
        super().__init__("streamlit")
        self.events = []

    def __getattr__(self, name):
        if name == "cache_resource":
            return lambda **_kwargs: (lambda function: function)
        if name == "text_area":
            return lambda *_args, **_kwargs: "請協助處理路面坑洞"
        if name == "button":
            return lambda *_args, **_kwargs: True
        return lambda *args, **kwargs: self.events.append((name, args, kwargs))


class M4PredictionTests(unittest.TestCase):
    def _approved_baseline_bundle(
        self, root: Path, candidate: str = "logistic_regression"
    ) -> tuple[Path, Path]:
        run_dir = root / "model-run"
        run_dir.mkdir()
        train = _fixture_splits()[0]
        validation = _fixture_splits()[1]
        seed = 1337
        registration = m2_runner._candidate_registration(seed)
        if candidate in {"mlp", "pca_mlp"}:
            registration["candidates"][candidate].update({"epochs": 3, "hidden_size": 8})
        registration["configuration_fingerprint"] = m2_runner._sha256_bytes(m2_runner._json_bytes(registration))
        prereg_path = run_dir / "pre_registered_candidates.json"
        _write_json(prereg_path, registration)
        source_hashes = {
            name: hashlib.sha256(name.encode("utf-8")).hexdigest()
            for name in ("jsonl", "csv", "taxonomy", "manifest")
        }
        with patch.object(m2_runner, "PROJECT_ROOT", root):
            checkpoint_path = run_dir / f"m2-{candidate}-checkpoint.joblib"
            if candidate == "lda_logistic_regression":
                result = run_lda_logistic_baseline(train, validation, seed=seed)
                checkpoint = m2_runner._write_lda_checkpoint(
                    checkpoint_path,
                    result,
                    validation,
                    registration,
                    source_hashes,
                )
            else:
                config = registration["candidates"][candidate]
                kwargs = {"epochs": config["epochs"], "hidden_size": config["hidden_size"]} if candidate == "mlp" else {}
                if candidate == "pca_mlp":
                    kwargs = {
                        "epochs": config["epochs"],
                        "hidden_size": config["hidden_size"],
                        "pca_components": config["pca_components"],
                    }
                result = run_baseline(
                    candidate,
                    train,
                    validation,
                    label_order=LABEL_ORDER,
                    seed=seed,
                    **kwargs,
                )
                checkpoint = m2_runner._write_baseline_checkpoint(
                    checkpoint_path,
                    result,
                    train,
                    validation,
                    registration,
                    source_hashes,
                )
        run_manifest = {
            "run_id": run_dir.name,
            "result_status": "provisional",
            "data_status": "synthetic",
            "review_status": "pending_manual_review",
            "candidate_settings_fingerprint": registration["configuration_fingerprint"],
            "source_sha256_before": source_hashes,
            "source_sha256_after": source_hashes,
            "checkpoint_reload_verified": True,
            "test": {"status": "not_run", "transcript_count_passed_to_tokenizer": 0},
            "outputs": {
                "pre_registered_candidates.json": _hash_record(prereg_path),
                checkpoint_path.name: _hash_record(checkpoint_path),
            },
        }
        run_manifest_path = run_dir / "run_manifest.json"
        _write_json(run_manifest_path, run_manifest)
        locked_manifest = {
            "schema_version": 1,
            "status": "model_locked_for_demo",
            "candidate_list_locked": True,
            "configuration_locked": True,
            "approval_reference": "fixture-manual-lock-reference",
            "candidate_name": candidate,
            "data_status": "synthetic",
            "review_status": "pending_manual_review",
            "label_order": list(LABEL_ORDER),
            "embedding": {
                "model_id": "intfloat/multilingual-e5-small",
                "revision": "614241f622f53c4eeff9890bdc4f31cfecc418b3",
                "model_file_sha256": [list(item) for item in E5_MODEL_FILE_SHA256],
            },
            "model": {
                "kind": "e5_baseline",
                "seed": seed,
                "configuration_fingerprint": registration["configuration_fingerprint"],
                "run_manifest_path": run_manifest_path.name,
                "run_manifest_sha256": hashlib.sha256(run_manifest_path.read_bytes()).hexdigest(),
                "checkpoint_path": checkpoint_path.name,
                "checkpoint_sha256": checkpoint["sha256"],
            },
        }
        model_manifest_path = run_dir / "locked_model_manifest.json"
        _write_json(model_manifest_path, locked_manifest)
        return model_manifest_path, run_dir

    def test_locked_predictor_checks_sources_and_returns_fixed_order_probabilities(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest_path, _run_dir = self._approved_baseline_bundle(root)
            with patch.object(prediction_module, "PROJECT_ROOT", root):
                predictor = FlyCallPredictor.from_locked_manifest(
                    manifest_path,
                    e5_snapshot=root / "unused-e5-snapshot",
                    encoder=FakeEncoder(),
                )
                result = predictor.predict("  請協助處理路面坑洞  ")
                self.assertEqual(predictor.predict("  請協助處理路面坑洞  "), result)
                self.assertEqual(result.label_order, LABEL_ORDER)
                self.assertEqual(len(result.logits), 5)
                self.assertEqual(len(result.probabilities), 5)
                self.assertAlmostEqual(sum(result.probabilities), 1.0)
                self.assertEqual(result.review_status, "pending_manual_review")
                self.assertEqual(result.dispatch_status, "simulated_only")
                self.assertTrue(result.human_confirmation_required)
                with self.assertRaisesRegex(PredictorError, "non-empty transcript"):
                    predictor.predict("  ")

    def test_predictor_loads_each_registered_e5_baseline_shape(self) -> None:
        for candidate in ("logistic_regression", "mlp", "pca_mlp", "lda_logistic_regression"):
            with self.subTest(candidate=candidate), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                manifest_path, _run_dir = self._approved_baseline_bundle(root, candidate)
                with patch.object(prediction_module, "PROJECT_ROOT", root):
                    predictor = FlyCallPredictor.from_locked_manifest(
                        manifest_path,
                        e5_snapshot=root / "unused-e5-snapshot",
                        encoder=FakeEncoder(),
                    )
                    result = predictor.predict("synthetic baseline shape fixture")
                self.assertEqual(result.candidate_name, candidate)
                self.assertEqual(result.label_order, LABEL_ORDER)
                self.assertEqual(len(result.logits), len(LABEL_ORDER))
                self.assertAlmostEqual(sum(result.probabilities), 1.0)

    def test_cli_and_streamlit_use_the_same_predictor_output(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest_path, _run_dir = self._approved_baseline_bundle(root)
            with patch.object(prediction_module, "PROJECT_ROOT", root):
                predictor = FlyCallPredictor.from_locked_manifest(
                    manifest_path,
                    e5_snapshot=root / "unused-e5-snapshot",
                    encoder=FakeEncoder(),
                )
                cli_output = io.StringIO()
                with (
                    patch.object(predict_flycall.FlyCallPredictor, "from_locked_manifest", return_value=predictor),
                    contextlib.redirect_stdout(cli_output),
                ):
                    self.assertEqual(
                        predict_flycall.main(
                            ["--model-manifest", str(manifest_path), "--e5-snapshot", str(root), "--text", "測試逐字稿"]
                        ),
                        0,
                    )
                cli_result = json.loads(cli_output.getvalue())

                fake_st = FakeStreamlit()
                with (
                    patch.dict(sys.modules, {"streamlit": fake_st}),
                    patch.dict(
                        "os.environ",
                        {"FLYCALL_MODEL_MANIFEST": str(manifest_path), "E5_SNAPSHOT": str(root)},
                        clear=False,
                    ),
                    patch.object(app.FlyCallPredictor, "from_locked_manifest", return_value=predictor),
                ):
                    app.main()

            self.assertTrue(any(event[0] == "warning" and "合成資料" in event[1][0] for event in fake_st.events))
            self.assertTrue(any(event[0] == "info" and "未執行真實派工" in event[1][0] for event in fake_st.events))
            table_event = next(event for event in fake_st.events if event[0] == "dataframe")
            ui_scores = [row["分數"] for row in table_event[1][0]]
            self.assertEqual(ui_scores, list(cli_result["probabilities"].values()))
            self.assertEqual(cli_result["dispatch_status"], "simulated_only")

    def test_unlocked_or_unapproved_manifest_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest_path, run_dir = self._approved_baseline_bundle(root)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["candidate_list_locked"] = False
            _write_json(manifest_path, manifest)
            with patch.object(prediction_module, "PROJECT_ROOT", root):
                with self.assertRaisesRegex(PredictorError, "locked model manifest"):
                    FlyCallPredictor.from_locked_manifest(
                        manifest_path,
                        e5_snapshot=root / "unused-e5-snapshot",
                        encoder=FakeEncoder(),
                    )

    def test_fly_a_to_fly_b_bundle_reloads_and_returns_five_class_logits(self) -> None:
        import torch

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run_dir = root / "fly-run"
            run_dir.mkdir()
            input_ids = tuple(range(1, 33))
            output_ids = tuple(range(101, 133))
            edges = tuple(
                [(source, target, 1) for source, target in zip(input_ids, output_ids)]
                + [(target, target, 1) for target in output_ids]
            )
            graph = GraphDefinition(input_ids + output_ids, input_ids, output_ids, edges, steps=2)

            def split(name: str, count: int, with_labels: bool) -> EmbeddingSplit:
                generator = torch.Generator().manual_seed(800 if name == "train" else 900)
                embeddings = torch.nn.functional.normalize(
                    torch.randn((count, 384), generator=generator, dtype=torch.float32), dim=1
                )
                record_ids = tuple(f"{name}-{index}" for index in range(count))
                family_ids = tuple(f"{name}-family-{index}" for index in range(count))
                labels = tuple(LABEL_ORDER[index % len(LABEL_ORDER)] for index in range(count)) if with_labels else None
                return EmbeddingSplit(name, record_ids, family_ids, embeddings, labels)

            train_a, validation_a = split("train", 10, False), split("validation", 5, False)
            train_b, validation_b = split("train", 10, True), split("validation", 5, True)
            seed = 2026
            config = TrainingConfig(seed=seed, batch_size=5, max_epochs=2, patience=1, learning_rate=0.01)
            source_sha256 = {
                name: hashlib.sha256(name.encode("utf-8")).hexdigest()
                for name in (
                    "jsonl",
                    "csv",
                    "taxonomy",
                    "manifest",
                    "graph_manifest",
                    "io_manifest",
                    "nodes_parquet",
                    "edges_parquet",
                    "embedding_manifest",
                    "e5_run_manifest",
                    "m32_requirements",
                    "m32_lock",
                )
            }
            source_sha256["e5_model_files"] = prediction_module._sha256_json(
                [list(item) for item in E5_MODEL_FILE_SHA256]
            )
            fly_a_path = run_dir / "fly-a-checkpoint.pt"
            result_a = train_fly_a(
                graph,
                train_a,
                validation_a,
                checkpoint_path=fly_a_path,
                source_sha256=source_sha256,
                config=config,
            )
            fly_b_sources = {**source_sha256, "fly_a_checkpoint": result_a.checkpoint_sha256}
            fly_b_path = run_dir / "fly-b-checkpoint.pt"
            train_fly_b(
                graph,
                train_b,
                validation_b,
                fly_a_checkpoint_path=fly_a_path,
                fly_a_source_sha256=source_sha256,
                source_sha256=fly_b_sources,
                checkpoint_path=fly_b_path,
                config=config,
                candidate_name=f"fly_a_to_fly_b_m3_2_seed_{seed}",
            )
            preregistration = {
                "schema_version": 1,
                "status": "pre_registered",
                "embedding": {
                    "model_id": "intfloat/multilingual-e5-small",
                    "revision": "614241f622f53c4eeff9890bdc4f31cfecc418b3",
                    "model_file_sha256": [list(item) for item in E5_MODEL_FILE_SHA256],
                },
                "graph": {
                    "node_count": len(graph.node_ids),
                    "edge_count": len(graph.edges),
                    "pinned_m12_manifest_sha256": source_sha256["graph_manifest"],
                    "pinned_m13_io_manifest_sha256": source_sha256["io_manifest"],
                },
                "training": {
                    "candidate_name": f"fly_a_to_fly_b_m3_2_seed_{seed}",
                    "seed": seed,
                    "batch_size": config.batch_size,
                    "max_epochs": config.max_epochs,
                    "patience": config.patience,
                    "learning_rate": config.learning_rate,
                    "gradient_clip_norm": config.gradient_clip_norm,
                    "torch_threads": config.torch_threads,
                },
            }
            preregistration["configuration_fingerprint"] = prediction_module._sha256_json(preregistration)
            prereg_path = run_dir / "pre_registered_candidates.json"
            _write_json(prereg_path, preregistration)
            graph_path = run_dir / "graph_definition.json"
            _write_json(
                graph_path,
                {
                    "schema_version": 1,
                    "node_ids": list(graph.node_ids),
                    "input_node_ids": list(graph.input_node_ids),
                    "output_node_ids": list(graph.output_node_ids),
                    "edges": [list(edge) for edge in graph.edges],
                    "steps": graph.steps,
                    "source_sha256": source_sha256,
                },
            )
            outputs = {
                path.name: _hash_record(path)
                for path in (prereg_path, graph_path, fly_a_path, fly_b_path)
            }
            run_manifest = {
                "run_id": run_dir.name,
                "status": "completed_provisional",
                "configuration_fingerprint": preregistration["configuration_fingerprint"],
                "dataset_audit": {"data_status": "synthetic", "review_status": "pending_manual_review"},
                "source_sha256": source_sha256,
                "summary": {"checkpoint_reload": {"status": "passed"}},
                "test": {"status": "not_run", "model_inputs": 0, "metrics": "not_run"},
                "outputs": outputs,
            }
            run_manifest_path = run_dir / "run_manifest.json"
            _write_json(run_manifest_path, run_manifest)
            locked_manifest = {
                "schema_version": 1,
                "status": "model_locked_for_demo",
                "candidate_list_locked": True,
                "configuration_locked": True,
                "approval_reference": "fixture-manual-lock-reference",
                "candidate_name": "fly_a_to_fly_b",
                "data_status": "synthetic",
                "review_status": "pending_manual_review",
                "label_order": list(LABEL_ORDER),
                "embedding": preregistration["embedding"],
                "model": {
                    "kind": "fly_a_to_fly_b",
                    "seed": seed,
                    "configuration_fingerprint": preregistration["configuration_fingerprint"],
                    "run_manifest_path": run_manifest_path.name,
                    "run_manifest_sha256": hashlib.sha256(run_manifest_path.read_bytes()).hexdigest(),
                    "graph_definition_path": graph_path.name,
                    "graph_definition_sha256": hashlib.sha256(graph_path.read_bytes()).hexdigest(),
                    "fly_a_checkpoint_path": fly_a_path.name,
                    "fly_a_checkpoint_sha256": result_a.checkpoint_sha256,
                    "fly_b_checkpoint_path": fly_b_path.name,
                    "fly_b_checkpoint_sha256": hashlib.sha256(fly_b_path.read_bytes()).hexdigest(),
                },
            }
            locked_path = run_dir / "locked_model_manifest.json"
            _write_json(locked_path, locked_manifest)

            with patch.object(prediction_module, "PROJECT_ROOT", root):
                predictor = FlyCallPredictor.from_locked_manifest(
                    locked_path,
                    e5_snapshot=root / "unused-e5-snapshot",
                    encoder=FakeEncoder(),
                )
                prediction = predictor.predict("模擬測試逐字稿")

            self.assertEqual(prediction.candidate_name, "fly_a_to_fly_b")
            self.assertEqual(len(prediction.logits), len(LABEL_ORDER))
            self.assertEqual(len(prediction.probabilities), len(LABEL_ORDER))
            self.assertEqual(prediction.stages[-1], "Fly B 32→5 logits")
            self.assertAlmostEqual(sum(prediction.probabilities), 1.0)


if __name__ == "__main__":
    unittest.main()

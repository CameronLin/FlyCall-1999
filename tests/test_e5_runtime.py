from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flycall_data import e5_runtime
from flycall_data.e5_runtime import E5SmallEncoder, inspect_tokenization
from flycall_data.model_config import E5_SMALL_CONFIG


class FakeMatrix(list):
    def __init__(self, rows: list[list[float]], dimension: int) -> None:
        super().__init__(rows)
        self.ndim = 2
        self.shape = (len(rows), dimension)


class FakeTokenizer:
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], dict[str, object]]] = []

    def __call__(self, texts: list[str], **kwargs: object) -> dict[str, list[list[int]]]:
        self.calls.append((list(texts), dict(kwargs)))
        return {"input_ids": [list(range(len(text))) for text in texts]}


class FakeTransformer:
    def __init__(self, max_length: int = 512) -> None:
        self.max_length = max_length
        self.calls: list[list[str]] = []

    def preprocess(self, texts: list[str]) -> dict[str, list[list[int]]]:
        self.calls.append(list(texts))
        return {
            "input_ids": [list(range(min(len(text), self.max_length))) for text in texts]
        }


class FakeModel:
    def __init__(self, *, dimension: int = 384, vector: list[float] | None = None) -> None:
        self.transformer = FakeTransformer()
        self.dimension = dimension
        self.vector = vector or ([1.0] + [0.0] * (dimension - 1))
        self.calls: list[tuple[list[str], dict[str, object]]] = []

    def __getitem__(self, index: int) -> FakeTransformer:
        if index != 0:
            raise IndexError(index)
        return self.transformer

    def encode(self, texts: list[str], **kwargs: object) -> FakeMatrix:
        self.calls.append((list(texts), dict(kwargs)))
        return FakeMatrix([list(self.vector) for _ in texts], self.dimension)


def _write_model_contract(snapshot: Path) -> None:
    (snapshot / "modules.json").write_text(
        json.dumps([
            {"idx": 0, "name": "0", "path": "", "type": "sentence_transformers.models.Transformer"},
            {"idx": 1, "name": "1", "path": "1_Pooling", "type": "sentence_transformers.models.Pooling"},
            {"idx": 2, "name": "2", "path": "", "type": "sentence_transformers.models.Normalize"},
        ]),
        encoding="utf-8",
    )
    pooling_dir = snapshot / "1_Pooling"
    pooling_dir.mkdir(parents=True, exist_ok=True)
    (pooling_dir / "config.json").write_text(
        json.dumps({
            "pooling_mode_mean_tokens": True,
            "pooling_mode_cls_token": False,
            "pooling_mode_max_tokens": False,
            "pooling_mode_mean_sqrt_len_tokens": False,
            "pooling_mode_weightedmean_tokens": False,
            "pooling_mode_lasttoken": False,
        }),
        encoding="utf-8",
    )
    (snapshot / "config.json").write_text(json.dumps({"hidden_size": 384}), encoding="utf-8")


class E5SnapshotTests(unittest.TestCase):
    def test_snapshot_verification_checks_every_configured_file_hash_and_size(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory) / E5_SMALL_CONFIG.revision
            snapshot.mkdir()
            fixture_files = (("weights.bin", b"small fixture weights"), ("tokenizer/config.json", b"{}"))
            expected_files: list[tuple[str, int, str]] = []
            for name, content in fixture_files:
                path = snapshot / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
                expected_files.append((name, len(content), hashlib.sha256(content).hexdigest()))

            with patch.object(e5_runtime, "E5_MODEL_FILES", tuple(expected_files)):
                manifest = e5_runtime.verify_e5_snapshot(snapshot)

            self.assertEqual(manifest["revision"], E5_SMALL_CONFIG.revision)
            self.assertEqual(manifest["total_bytes"], sum(len(data) for _, data in fixture_files))
            self.assertEqual([item["path"] for item in manifest["files"]], [name for name, _ in fixture_files])

            (snapshot / "weights.bin").write_bytes(b"tampered fixture weights")
            with patch.object(e5_runtime, "E5_MODEL_FILES", tuple(expected_files)):
                with self.assertRaisesRegex(ValueError, "size mismatch|SHA-256 mismatch"):
                    e5_runtime.verify_e5_snapshot(snapshot)

    def test_snapshot_requires_the_pinned_revision_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory) / "other-revision"
            snapshot.mkdir()
            with self.assertRaisesRegex(ValueError, "pinned revision"):
                e5_runtime.verify_e5_snapshot(snapshot)

    def test_model_contract_requires_transformer_pooling_then_normalization(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory)
            _write_model_contract(snapshot)
            contract = e5_runtime._read_model_contract(snapshot)
            self.assertEqual(contract["modules"], [
                "sentence_transformers.models.Transformer",
                "sentence_transformers.models.Pooling",
                "sentence_transformers.models.Normalize",
            ])
            self.assertEqual(contract["hidden_size"], 384)

            modules_path = snapshot / "modules.json"
            modules = json.loads(modules_path.read_text(encoding="utf-8"))
            modules[0], modules[1] = modules[1], modules[0]
            modules_path.write_text(json.dumps(modules), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "run Transformer, mean pooling"):
                e5_runtime._read_model_contract(snapshot)

    def test_model_contract_rejects_wrong_pooling_and_dimension(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory)
            _write_model_contract(snapshot)
            pooling_path = snapshot / "1_Pooling" / "config.json"
            pooling = json.loads(pooling_path.read_text(encoding="utf-8"))
            pooling["pooling_mode_mean_tokens"] = False
            pooling_path.write_text(json.dumps(pooling), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "masked mean-token pooling"):
                e5_runtime._read_model_contract(snapshot)

            pooling["pooling_mode_mean_tokens"] = True
            pooling_path.write_text(json.dumps(pooling), encoding="utf-8")
            (snapshot / "config.json").write_text(json.dumps({"hidden_size": 256}), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "384-dimensional contract"):
                e5_runtime._read_model_contract(snapshot)


class E5EncoderAdapterTests(unittest.TestCase):
    def test_inspect_and_encode_report_right_truncation_and_normalized_vectors(self) -> None:
        tokenizer = FakeTokenizer()
        model = FakeModel()
        encoder = E5SmallEncoder(model, tokenizer, {})
        text = "query: " + "x" * 600

        vectors = encoder.encode([text])

        self.assertEqual(len(vectors), 1)
        self.assertEqual(len(vectors[0]), 384)
        self.assertEqual(vectors[0][0], 1.0)
        self.assertEqual(encoder.last_tokenization_diagnostics[0].raw_token_count, len(text))
        self.assertEqual(encoder.last_tokenization_diagnostics[0].effective_token_count, 512)
        self.assertEqual(encoder.last_tokenization_diagnostics[0].truncated_token_count, len(text) - 512)
        self.assertEqual(model.calls[0][1], {
            "batch_size": 1,
            "show_progress_bar": False,
            "convert_to_numpy": True,
            "normalize_embeddings": False,
        })
        self.assertEqual(tokenizer.calls[0][1], {
            "add_special_tokens": True,
            "truncation": False,
            "padding": False,
            "return_attention_mask": False,
        })

    def test_tokenization_batches_diagnostics_and_rejects_invalid_unicode_before_tokenizer(self) -> None:
        tokenizer = FakeTokenizer()
        transformer = FakeTransformer()
        texts = [f"query: fixture-{index}" for index in range(33)]
        diagnostics = inspect_tokenization(tokenizer, transformer, texts, max_seq_length=512)
        self.assertEqual(len(diagnostics), 33)
        self.assertEqual([len(batch) for batch, _ in tokenizer.calls], [32, 1])

        with self.assertRaises(UnicodeEncodeError):
            inspect_tokenization(tokenizer, transformer, ["query: \ud800"], max_seq_length=512)
        self.assertEqual(len(tokenizer.calls), 2)

    def test_encoder_rejects_missing_prefix_wrong_dimension_and_non_unit_vectors(self) -> None:
        tokenizer = FakeTokenizer()
        model = FakeModel()
        encoder = E5SmallEncoder(model, tokenizer, {})
        with self.assertRaisesRegex(ValueError, "start with"):
            encoder.encode(["transcript without prefix"])
        self.assertEqual(tokenizer.calls, [])

        wrong_dimension = E5SmallEncoder(FakeModel(dimension=383), FakeTokenizer(), {})
        with self.assertRaisesRegex(ValueError, r"expected \(1, 384\)"):
            wrong_dimension.encode(["query: text"])

        zero_vector = E5SmallEncoder(
            FakeModel(vector=[0.0] * 384), FakeTokenizer(), {}
        )
        with self.assertRaisesRegex(ValueError, "expected 1"):
            zero_vector.encode(["query: text"])


if __name__ == "__main__":
    unittest.main()

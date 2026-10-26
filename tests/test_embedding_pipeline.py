from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from flycall_data.embedding_pipeline import (
    EmbeddingCache,
    EmbeddingSettings,
    SplitEmbeddings,
    SplitTexts,
    embed_texts,
)
from flycall_data.model_config import E5_SMALL_CONFIG


class MockEncoder:
    def __init__(self, vectors: list[list[float]]) -> None:
        self.vectors = vectors
        self.inputs: list[list[str]] = []

    def encode(self, texts: list[str]) -> list[list[float]]:
        self.inputs.append(list(texts))
        if len(self.vectors) == 1:
            return [list(self.vectors[0]) for _ in texts]
        if len(texts) != len(self.vectors):
            raise AssertionError("fixture vector count does not match encoder input")
        return self.vectors


def text_batch(text: str, *, split: str = "train") -> SplitTexts:
    return SplitTexts(
        split=split,
        record_ids=("synthetic-record-1",),
        family_ids=(f"{split}-family-1",),
        texts=(text,),
        labels=("road_surface_defect",),
    )


def settings(**overrides: object) -> EmbeddingSettings:
    values: dict[str, object] = {
        "model_id": E5_SMALL_CONFIG.model_id,
        "revision": E5_SMALL_CONFIG.revision,
        "tokenizer_revision": E5_SMALL_CONFIG.revision,
        "prefix": E5_SMALL_CONFIG.prefix,
        "preprocessing_version": "transcript-v1",
        "max_seq_length": E5_SMALL_CONFIG.max_seq_length,
        "truncation_policy": "right-truncate",
        "pooling": E5_SMALL_CONFIG.pooling,
        "normalize_embeddings": E5_SMALL_CONFIG.normalize_embeddings,
        "dtype": "float32",
        "output_dimension": 2,
        "device": E5_SMALL_CONFIG.trial_device,
        "batch_size": E5_SMALL_CONFIG.trial_batch_size,
    }
    values.update(overrides)
    return EmbeddingSettings(**values)  # type: ignore[arg-type]


class EmbeddingPipelineTests(unittest.TestCase):
    def test_central_e5_target_configuration_matches_verified_runtime(self) -> None:
        self.assertEqual(E5_SMALL_CONFIG.model_id, "intfloat/multilingual-e5-small")
        self.assertEqual(E5_SMALL_CONFIG.revision, "614241f622f53c4eeff9890bdc4f31cfecc418b3")
        self.assertEqual(E5_SMALL_CONFIG.prefix, "query: ")
        self.assertEqual(E5_SMALL_CONFIG.max_seq_length, 512)
        self.assertEqual(E5_SMALL_CONFIG.output_dimension, 384)
        self.assertEqual(E5_SMALL_CONFIG.pooling, "masked_mean")
        self.assertTrue(E5_SMALL_CONFIG.normalize_embeddings)
        self.assertEqual(E5_SMALL_CONFIG.trial_device, "cpu")
        self.assertEqual(E5_SMALL_CONFIG.trial_batch_size, 1)
        self.assertEqual(E5_SMALL_CONFIG.status, "runtime_verified_cpu")

    def test_central_configuration_builds_complete_cache_settings(self) -> None:
        cache_settings = E5_SMALL_CONFIG.embedding_settings(
            preprocessing_version="transcript-v1",
            truncation_policy="audited-right-truncate",
            dtype="float32",
        )
        self.assertEqual(cache_settings.model_id, E5_SMALL_CONFIG.model_id)
        self.assertEqual(cache_settings.revision, E5_SMALL_CONFIG.revision)
        self.assertEqual(cache_settings.tokenizer_revision, E5_SMALL_CONFIG.revision)
        self.assertEqual(cache_settings.prefix, "query: ")
        self.assertEqual(cache_settings.preprocessing_version, "transcript-v1")
        self.assertEqual(cache_settings.max_seq_length, 512)
        self.assertEqual(cache_settings.truncation_policy, "audited-right-truncate")
        self.assertEqual(cache_settings.pooling, "masked_mean")
        self.assertTrue(cache_settings.normalize_embeddings)
        self.assertEqual(cache_settings.dtype, "float32")
        self.assertEqual(cache_settings.output_dimension, 384)
        self.assertEqual(cache_settings.device, "cpu")
        self.assertEqual(cache_settings.batch_size, 1)

    def test_encoder_receives_prefixed_original_unicode_and_cached_vector_is_normalized(self) -> None:
        encoder = MockEncoder([[3.0, 4.0]])
        with tempfile.TemporaryDirectory() as directory:
            cache = EmbeddingCache(Path(directory))
            first = embed_texts(text_batch("R: 臺灣口語🙂"), encoder, settings(), cache)
            second = embed_texts(text_batch("R: 臺灣口語🙂"), encoder, settings(), cache)

        self.assertEqual(encoder.inputs, [["query: R: 臺灣口語🙂"]])
        self.assertEqual(first.features, ((0.6, 0.8),))
        self.assertEqual(second, first)

    def test_cache_hit_preserves_exact_vector_and_rejects_non_normalized_payload(self) -> None:
        vector = [0.5773502691896257] * 3
        encoder = MockEncoder([vector])
        cache_settings = settings(output_dimension=3)
        with tempfile.TemporaryDirectory() as directory:
            cache = EmbeddingCache(Path(directory))
            first = embed_texts(text_batch("R: stable cache"), encoder, cache_settings, cache)
            second = embed_texts(text_batch("R: stable cache"), encoder, cache_settings, cache)
            self.assertEqual(first.features, second.features)
            self.assertEqual(len(encoder.inputs), 1)

            bad_text = "R: corrupted cache"
            cache.put(cache.key_for(bad_text, cache_settings), [1.0, 1.0, 1.0])
            with self.assertRaisesRegex(ValueError, "not already L2-normalized"):
                embed_texts(text_batch(bad_text), encoder, cache_settings, cache)

    def test_cache_key_isolated_by_model_revision_and_each_embedding_setting(self) -> None:
        encoder = MockEncoder([[3.0, 4.0]])
        base = settings()
        variants = [
            "R: 不同文字",
            replace(base, model_id="intfloat/multilingual-e5-large"),
            replace(base, revision="revision-b"),
            replace(base, tokenizer_revision="tokenizer-b"),
            replace(base, prefix="passage: "),
            replace(base, preprocessing_version="transcript-v2"),
            replace(base, max_seq_length=256),
            replace(base, truncation_policy="reject-over-limit"),
            replace(base, pooling="cls_token"),
            replace(base, normalize_embeddings=False),
            replace(base, dtype="float64"),
            replace(base, device="mps"),
            replace(base, batch_size=2),
            replace(base, model_file_sha256=(("model.safetensors", "a" * 64),)),
        ]
        with tempfile.TemporaryDirectory() as directory:
            cache = EmbeddingCache(Path(directory))
            embed_texts(text_batch("R: 相同文字"), encoder, base, cache)
            for variant in variants:
                variant_settings = base if isinstance(variant, str) else variant
                text = variant if isinstance(variant, str) else "R: 相同文字"
                embed_texts(text_batch(text), encoder, variant_settings, cache)

        self.assertEqual(len(encoder.inputs), 15)
        self.assertNotEqual(
            EmbeddingCache.key_for("R: 相同文字", base),
            EmbeddingCache.key_for("R: 相同文字", replace(base, output_dimension=3)),
        )

    def test_model_file_hash_settings_are_validated(self) -> None:
        with self.assertRaisesRegex(ValueError, "SHA-256"):
            settings(model_file_sha256=(("model.safetensors", "not-a-hash"),))
        with self.assertRaisesRegex(ValueError, "relative paths"):
            settings(model_file_sha256=(("../model.safetensors", "a" * 64),))
        with self.assertRaisesRegex(ValueError, "duplicate names"):
            settings(model_file_sha256=(
                ("model.safetensors", "a" * 64),
                ("model.safetensors", "b" * 64),
            ))

    def test_wrong_dimension_non_finite_and_zero_norm_fail_explicitly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            cache = EmbeddingCache(Path(directory))
            with self.assertRaisesRegex(ValueError, "dimension"):
                embed_texts(text_batch("one"), MockEncoder([[1.0]]), settings(), cache)
            with self.assertRaisesRegex(ValueError, "finite"):
                embed_texts(text_batch("two"), MockEncoder([[float("nan"), 1.0]]), settings(), cache)
            with self.assertRaisesRegex(ValueError, "zero norm"):
                embed_texts(text_batch("three"), MockEncoder([[0.0, 0.0]]), settings(), cache)

    def test_test_split_is_rejected_before_encoder_or_cache_receives_text(self) -> None:
        encoder = MockEncoder([[1.0, 0.0]])
        with tempfile.TemporaryDirectory() as directory:
            cache = EmbeddingCache(Path(directory))
            with self.assertRaisesRegex(ValueError, "train or validation"):
                test_batch = SplitTexts(
                    split="test",
                    record_ids=("synthetic-test-row",),
                    family_ids=("synthetic-test-family",),
                    texts=("TESTONLYTOKEN must not be encoded",),
                    labels=("road_surface_defect",),
                )
                embed_texts(test_batch, encoder, settings(), cache)

        self.assertEqual(encoder.inputs, [])

    def test_model_input_split_type_rejects_test(self) -> None:
        with self.assertRaisesRegex(ValueError, "train or validation"):
            SplitEmbeddings(
                split="test",
                record_ids=("synthetic-test-only",),
                family_ids=("synthetic-test-family",),
                features=((0.1, 0.2),),
                labels=("road_surface_defect",),
            )


if __name__ == "__main__":
    unittest.main()

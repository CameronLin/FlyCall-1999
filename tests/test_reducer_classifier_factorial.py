from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
import torch

from flycall_data.evaluation import LABEL_ORDER
from flycall_data.fly_ab_training import (
    EmbeddingSplit,
    TrainingConfig,
    load_fly_b_checkpoint,
    train_fly_b_on_features,
)
from flycall_data.graph_core import FlyB, GraphCoreError
from flycall_data.reducer_classifier_factorial import (
    FactorialError,
    fit_lda_reducer,
    paired_delta,
    run_svm,
    summarize,
)
from test_fly_ab_training import SOURCE_SHA256, fixture_graph


CONFIG = TrainingConfig(batch_size=4, max_epochs=3, patience=2, learning_rate=0.01)


def feature_split(split: str, width: int, *, scale: float = 3.0) -> EmbeddingSplit:
    count = 10 if split == "train" else 5
    generator = torch.Generator().manual_seed(11 if split == "train" else 12)
    values = torch.randn((count, width), generator=generator, dtype=torch.float32) * scale
    return EmbeddingSplit(
        split,
        tuple(f"{split}-record-{index}" for index in range(count)),
        tuple(f"{split}-family-{index}" for index in range(count)),
        values,
        tuple(LABEL_ORDER[index % len(LABEL_ORDER)] for index in range(count)),
    )


def separable_features(count_per_class: int, seed: int) -> tuple[np.ndarray, list[str]]:
    rng = np.random.default_rng(seed)
    rows, labels = [], []
    for index, label in enumerate(LABEL_ORDER):
        center = np.zeros(12)
        center[index] = 5.0
        rows.append(center + rng.normal(scale=0.3, size=(count_per_class, 12)))
        labels.extend([label] * count_per_class)
    return np.vstack(rows), labels


class FlyBInputWidthTests(unittest.TestCase):
    def test_default_width_keeps_the_m3_3_checkpoint_contract(self) -> None:
        model = FlyB(fixture_graph().build_core(), label_order=LABEL_ORDER)
        self.assertEqual(model.checkpoint_metadata()["input_width"], 32)
        self.assertEqual(model.input_adapter.in_features, 32)

    def test_custom_width_changes_only_the_input_adapter(self) -> None:
        model = FlyB(fixture_graph().build_core(), label_order=LABEL_ORDER, input_width=4)
        self.assertEqual(model.checkpoint_metadata()["input_width"], 4)
        self.assertEqual(model(torch.zeros((3, 4))).shape, (3, 5))
        self.assertEqual(model.parameter_counts["readout"], 32 * 5 + 5)
        with self.assertRaises(GraphCoreError):
            model(torch.zeros((3, 32)))
        with self.assertRaises(GraphCoreError):
            FlyB(fixture_graph().build_core(), label_order=LABEL_ORDER, input_width=0)


class FlyBOnFeaturesTests(unittest.TestCase):
    def test_trains_on_non_normalized_lda_width_and_reloads_exactly(self) -> None:
        graph = fixture_graph()
        train, validation = feature_split("train", 4), feature_split("validation", 4)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fly-b-lda.pt"
            result = train_fly_b_on_features(
                graph, train, validation,
                source_sha256=SOURCE_SHA256, checkpoint_path=path, config=CONFIG,
                candidate_name="lda_to_fly_b_fixture",
            )
            reloaded = load_fly_b_checkpoint(graph, path, expected_source_sha256=SOURCE_SHA256, input_width=4)
            with torch.no_grad():
                difference = (result.model(validation.embeddings) - reloaded(validation.embeddings)).abs().max()
            self.assertEqual(float(difference), 0.0)
            with self.assertRaises(GraphCoreError):
                load_fly_b_checkpoint(graph, path, expected_source_sha256=SOURCE_SHA256)
        self.assertIsNotNone(result.evaluation)
        self.assertEqual(result.evaluation["splits"]["test"]["status"], "not_run")

    def test_same_seed_is_reproducible(self) -> None:
        graph = fixture_graph()
        train, validation = feature_split("train", 4), feature_split("validation", 4)
        with tempfile.TemporaryDirectory() as directory:
            runs = [
                train_fly_b_on_features(
                    graph, train, validation,
                    source_sha256=SOURCE_SHA256, checkpoint_path=Path(directory) / f"run-{index}.pt",
                    config=CONFIG, candidate_name="fixture",
                )
                for index in range(2)
            ]
        self.assertEqual(runs[0].history, runs[1].history)

    def test_rejects_test_split_before_writing_checkpoint(self) -> None:
        graph = fixture_graph()
        train = feature_split("train", 4)
        test_like = EmbeddingSplit(
            "test", ("test-0", "test-1"), ("test-family-0", "test-family-1"),
            torch.ones((2, 4)), (LABEL_ORDER[0], LABEL_ORDER[1]),
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "never.pt"
            with self.assertRaisesRegex(ValueError, "test is never a model input"):
                train_fly_b_on_features(
                    graph, train, test_like,
                    source_sha256=SOURCE_SHA256, checkpoint_path=path, config=CONFIG, candidate_name="x",
                )
            self.assertFalse(path.exists())


class ReducerAndSVMTests(unittest.TestCase):
    def test_lda_uses_train_only_statistics(self) -> None:
        train, labels = separable_features(8, seed=1)
        validation, _ = separable_features(3, seed=2)
        reduced = fit_lda_reducer(train, labels, validation + 100.0)
        self.assertEqual(reduced.train.shape, (40, 4))
        np.testing.assert_allclose(reduced.train.mean(axis=0), 0.0, atol=1e-9)
        np.testing.assert_allclose(reduced.train.std(axis=0), 1.0, atol=1e-9)
        # Shifting only validation must not move the train-fit transform.
        again = fit_lda_reducer(train, labels, validation)
        np.testing.assert_allclose(reduced.train, again.train)
        with self.assertRaises(FactorialError):
            fit_lda_reducer(train, labels, validation[:, :5])
        with self.assertRaises(FactorialError):
            fit_lda_reducer(train, labels[:-8] + [LABEL_ORDER[0]] * 8, validation)

    def test_svm_scores_follow_label_order_and_are_deterministic(self) -> None:
        train, labels = separable_features(8, seed=3)
        validation, validation_labels = separable_features(4, seed=4)
        first = run_svm(train, labels, validation, validation_labels)
        second = run_svm(train, labels, validation, validation_labels)
        self.assertEqual(first.validation_predictions, second.validation_predictions)
        self.assertEqual(first.validation_scores.shape, (20, 5))
        argmax = tuple(LABEL_ORDER[index] for index in first.validation_scores.argmax(axis=1))
        self.assertEqual(argmax, first.validation_predictions)
        self.assertEqual(first.validation_metrics["macro_f1"], 1.0)

    def test_paired_delta_applies_the_preregistered_rule(self) -> None:
        self.assertEqual(paired_delta([0.9, 0.9, 0.9], [0.8, 0.85, 0.87])["verdict"], "consistent")
        self.assertEqual(paired_delta([0.9, 0.8, 0.9], [0.8, 0.85, 0.87])["verdict"], "unclear")
        self.assertEqual(paired_delta([0.81, 0.81, 0.81], [0.80, 0.80, 0.80])["verdict"], "unclear")
        self.assertEqual(summarize([0.5])["sample_std"], 0.0)


if __name__ == "__main__":
    unittest.main()

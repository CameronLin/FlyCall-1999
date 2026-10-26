from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import torch

from flycall_data.evaluation import LABEL_ORDER
from flycall_data.fly_ab_diagnostics import load_fly_b_e5_residual_checkpoint, train_fly_b_with_e5_residual
from flycall_data.fly_ab_training import (
    EmbeddingSplit,
    GraphDefinition,
    TrainingConfig,
    _load_checkpoint,
    train_fly_a,
    train_fly_b,
    validate_engineering_graph,
)
from flycall_data.graph_core import FlyA, GraphCoreError, distance_preserving_loss


def fixture_graph() -> GraphDefinition:
    input_ids = tuple(range(1, 33))
    output_ids = tuple(range(101, 133))
    edges = tuple(
        [(input_id, output_id, 1) for input_id, output_id in zip(input_ids, output_ids)]
        + [(output_id, output_id, 1) for output_id in output_ids]
    )
    return GraphDefinition(input_ids + output_ids, input_ids, output_ids, edges, steps=2)


def fixture_split(split: str, *, labels: bool) -> EmbeddingSplit:
    count = 10 if split == "train" else 5
    generator = torch.Generator().manual_seed(101 if split == "train" else 202)
    values = torch.randn((count, 8), generator=generator, dtype=torch.float32)
    values = torch.nn.functional.normalize(values, dim=1)
    record_ids = tuple(f"{split}-record-{index}" for index in range(count))
    family_ids = tuple(f"{split}-family-{index}" for index in range(count))
    label_values = tuple(LABEL_ORDER[index % len(LABEL_ORDER)] for index in range(count)) if labels else None
    return EmbeddingSplit(split, record_ids, family_ids, values, label_values)


def fixture_e5_split(split: str, *, labels: bool) -> EmbeddingSplit:
    count = 10 if split == "train" else 5
    generator = torch.Generator().manual_seed(301 if split == "train" else 302)
    values = torch.randn((count, 384), generator=generator, dtype=torch.float32)
    values = torch.nn.functional.normalize(values, dim=1)
    record_ids = tuple(f"{split}-record-{index}" for index in range(count))
    family_ids = tuple(f"{split}-family-{index}" for index in range(count))
    label_values = tuple(LABEL_ORDER[index % len(LABEL_ORDER)] for index in range(count)) if labels else None
    return EmbeddingSplit(split, record_ids, family_ids, values, label_values)


SOURCE_SHA256 = {
    "dataset": "a" * 64,
    "graph_manifest": "b" * 64,
    "io_manifest": "c" * 64,
    "embedding_manifest": "d" * 64,
}
CONFIG = TrainingConfig(batch_size=4, max_epochs=3, patience=2, learning_rate=0.01)


class FlyABTrainingTests(unittest.TestCase):
    def test_gated_e5_residual_training_freezes_a_and_reloads_checkpoint(self) -> None:
        graph = fixture_graph()
        train_a = fixture_e5_split("train", labels=False)
        validation_a = fixture_e5_split("validation", labels=False)
        train_b = fixture_e5_split("train", labels=True)
        validation_b = fixture_e5_split("validation", labels=True)
        with tempfile.TemporaryDirectory() as directory:
            fly_a_path = Path(directory) / "fly-a.pt"
            residual_path = Path(directory) / "fly-b-residual.pt"
            result_a = train_fly_a(
                graph, train_a, validation_a, checkpoint_path=fly_a_path,
                source_sha256=SOURCE_SHA256, config=CONFIG,
            )
            frozen_a = {name: value.detach().clone() for name, value in result_a.model.state_dict().items()}
            residual_sources = {**SOURCE_SHA256, "fly_a_checkpoint": result_a.checkpoint_sha256}
            result = train_fly_b_with_e5_residual(
                graph,
                train_b,
                validation_b,
                fly_a_checkpoint_path=fly_a_path,
                fly_a_source_sha256=SOURCE_SHA256,
                source_sha256=residual_sources,
                checkpoint_path=residual_path,
                config=CONFIG,
            )
            self.assertEqual(result.task, "fly_b_e5_residual")
            self.assertEqual(result.evaluation["splits"]["test"]["status"], "not_run")
            self.assertEqual(result.evaluation["splits"]["train"]["n_records"], len(train_b.record_ids))
            self.assertEqual(result.evaluation["splits"]["validation"]["n_records"], len(validation_b.record_ids))
            for name, value in result_a.model.state_dict().items():
                torch.testing.assert_close(value, frozen_a[name], rtol=0, atol=0)

            reloaded = load_fly_b_e5_residual_checkpoint(
                graph, 384, residual_path, expected_source_sha256=residual_sources
            )
            with torch.no_grad():
                expected_a = result_a.model(validation_b.embeddings)
                expected = result.model(expected_a, validation_b.embeddings)
                actual_a = result_a.model(validation_b.embeddings)
                actual = reloaded(actual_a, validation_b.embeddings)
            torch.testing.assert_close(actual, expected, rtol=0, atol=0)

    def test_gated_e5_residual_rejects_test_split_before_writing_checkpoint(self) -> None:
        validation = fixture_e5_split("validation", labels=True)
        test = EmbeddingSplit("test", validation.record_ids, validation.family_ids, validation.embeddings, validation.labels)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "must-not-exist.pt"
            with self.assertRaisesRegex(ValueError, "only train and validation"):
                train_fly_b_with_e5_residual(
                    fixture_graph(),
                    fixture_e5_split("train", labels=True),
                    test,
                    fly_a_checkpoint_path=path,
                    fly_a_source_sha256=SOURCE_SHA256,
                    source_sha256={**SOURCE_SHA256, "fly_a_checkpoint": "f" * 64},
                    checkpoint_path=path,
                    config=CONFIG,
                )
            self.assertFalse(path.exists())

    def test_fly_a_is_label_free_and_rejects_test_split_before_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fly-a.pt"
            test = fixture_split("test", labels=False)
            with self.assertRaisesRegex(ValueError, "only train and validation"):
                train_fly_a(
                    fixture_graph(), fixture_split("train", labels=False), test,
                    checkpoint_path=path, source_sha256=SOURCE_SHA256, config=CONFIG,
                )
            self.assertFalse(path.exists())

            with self.assertRaisesRegex(ValueError, "does not accept labels"):
                train_fly_a(
                    fixture_graph(), fixture_split("train", labels=True), fixture_split("validation", labels=True),
                    checkpoint_path=path, source_sha256=SOURCE_SHA256, config=CONFIG,
                )
            self.assertFalse(path.exists())

    def test_fly_a_training_is_reproducible_and_checkpoint_reloads_exactly(self) -> None:
        graph = fixture_graph()
        train = fixture_split("train", labels=False)
        validation = fixture_split("validation", labels=False)
        with tempfile.TemporaryDirectory() as directory:
            first_path = Path(directory) / "first.pt"
            second_path = Path(directory) / "second.pt"
            first = train_fly_a(
                graph, train, validation, checkpoint_path=first_path,
                source_sha256=SOURCE_SHA256, config=CONFIG,
            )
            second = train_fly_a(
                graph, train, validation, checkpoint_path=second_path,
                source_sha256=SOURCE_SHA256, config=CONFIG,
            )
            self.assertEqual(first.history, second.history)
            self.assertEqual(first.selected_epoch, second.selected_epoch)
            self.assertEqual(first.checkpoint_sha256, second.checkpoint_sha256)

            reloaded = FlyA(8, graph.build_core())
            metadata = _load_checkpoint(
                reloaded, first_path, task="fly_a", expected_source_sha256=SOURCE_SHA256
            )
            self.assertEqual(metadata["selected_epoch"], first.selected_epoch)
            with torch.no_grad():
                expected = first.model(validation.embeddings)
                actual = reloaded(validation.embeddings)
            torch.testing.assert_close(actual, expected, rtol=0, atol=0)
            self.assertGreater(first.history[0]["train_loss"], 0.0)
            self.assertGreaterEqual(first.best_validation_metric, 0.0)

    def test_non_finite_fly_a_loss_keeps_latest_valid_checkpoint(self) -> None:
        graph = fixture_graph()
        train = fixture_split("train", labels=False)
        validation = fixture_split("validation", labels=False)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fly-a.pt"
            calls = 0

            def loss_then_fail(embeddings: torch.Tensor, representations: torch.Tensor) -> torch.Tensor:
                nonlocal calls
                calls += 1
                if calls == 5:  # Three train batches and validation for epoch 1; then fail during epoch 2.
                    return torch.tensor(float("nan"))
                return distance_preserving_loss(embeddings, representations)

            with patch("flycall_data.fly_ab_training.distance_preserving_loss", side_effect=loss_then_fail):
                with self.assertRaisesRegex(FloatingPointError, "non-finite Fly A loss"):
                    train_fly_a(
                        graph, train, validation, checkpoint_path=path,
                        source_sha256=SOURCE_SHA256, config=CONFIG,
                    )

            self.assertTrue(path.exists())
            reloaded = FlyA(8, graph.build_core())
            metadata = _load_checkpoint(
                reloaded, path, task="fly_a", expected_source_sha256=SOURCE_SHA256
            )
            self.assertEqual(metadata["selected_epoch"], 1)

    def test_fly_b_freezes_fly_a_and_reports_only_train_validation(self) -> None:
        graph = fixture_graph()
        train_a = fixture_split("train", labels=False)
        validation_a = fixture_split("validation", labels=False)
        train_b = fixture_split("train", labels=True)
        validation_b = fixture_split("validation", labels=True)
        with tempfile.TemporaryDirectory() as directory:
            fly_a_path = Path(directory) / "fly-a.pt"
            fly_b_path = Path(directory) / "fly-b.pt"
            result_a = train_fly_a(
                graph, train_a, validation_a, checkpoint_path=fly_a_path,
                source_sha256=SOURCE_SHA256, config=CONFIG,
            )
            frozen_before = {name: value.detach().clone() for name, value in result_a.model.state_dict().items()}
            fly_b_sources = {**SOURCE_SHA256, "fly_a_checkpoint": result_a.checkpoint_sha256}
            result_b = train_fly_b(
                graph, train_b, validation_b,
                fly_a_checkpoint_path=fly_a_path,
                fly_a_source_sha256=SOURCE_SHA256,
                source_sha256=fly_b_sources,
                checkpoint_path=fly_b_path,
                config=CONFIG,
            )

            self.assertEqual(result_b.task, "fly_b")
            self.assertGreaterEqual(result_b.selected_epoch, 1)
            self.assertEqual(result_b.evaluation["evaluation_status"], "smoke_test/provisional")
            self.assertEqual(result_b.evaluation["review_status"], "pending_manual_review")
            self.assertEqual(result_b.evaluation["splits"]["test"]["status"], "not_run")
            self.assertEqual(result_b.evaluation["splits"]["train"]["n_records"], len(train_b.record_ids))
            self.assertEqual(result_b.evaluation["splits"]["validation"]["n_records"], len(validation_b.record_ids))
            for name, value in result_a.model.state_dict().items():
                torch.testing.assert_close(value, frozen_before[name], rtol=0, atol=0)

    def test_train_validation_family_overlap_and_wrong_class_order_fail(self) -> None:
        train = fixture_split("train", labels=False)
        validation = fixture_split("validation", labels=False)
        overlapping = EmbeddingSplit(
            "validation", validation.record_ids, (train.family_ids[0], *validation.family_ids[1:]), validation.embeddings
        )
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "scenario families"):
                train_fly_a(
                    fixture_graph(), train, overlapping,
                    checkpoint_path=Path(directory) / "fail.pt", source_sha256=SOURCE_SHA256, config=CONFIG,
                )
            with self.assertRaises(GraphCoreError):
                validate_engineering_graph(fixture_graph())

    def test_fly_b_rejects_checkpoint_source_mismatch(self) -> None:
        graph = fixture_graph()
        train_a = fixture_split("train", labels=False)
        validation_a = fixture_split("validation", labels=False)
        train_b = fixture_split("train", labels=True)
        validation_b = fixture_split("validation", labels=True)
        with tempfile.TemporaryDirectory() as directory:
            fly_a_path = Path(directory) / "fly-a.pt"
            result_a = train_fly_a(
                graph, train_a, validation_a, checkpoint_path=fly_a_path,
                source_sha256=SOURCE_SHA256, config=CONFIG,
            )
            with self.assertRaisesRegex(ValueError, "matching fly_a_checkpoint"):
                train_fly_b(
                    graph, train_b, validation_b,
                    fly_a_checkpoint_path=fly_a_path,
                    fly_a_source_sha256=SOURCE_SHA256,
                    source_sha256={**SOURCE_SHA256, "fly_a_checkpoint": "f" * 64},
                    checkpoint_path=Path(directory) / "fly-b.pt",
                    config=CONFIG,
                )
            self.assertTrue(result_a.checkpoint_path.exists())


if __name__ == "__main__":
    unittest.main()

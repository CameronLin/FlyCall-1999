from __future__ import annotations

import unittest
from dataclasses import replace

import torch

from flycall_data.evaluation import LABEL_ORDER
from flycall_data.independent_tuning import (
    TuningError,
    choose_learning_rate,
    fit_fly_a,
    fit_fly_b,
    grouped_stratified_folds,
    label_tensor,
    median_epoch,
    supcon_loss,
)
from test_fly_ab_training import fixture_graph
from test_signed_graph_core import alternating_signs


def fixture_rows(count: int = 40, width: int = 8, seed: int = 3):
    generator = torch.Generator().manual_seed(seed)
    x = torch.nn.functional.normalize(torch.randn((count, width), generator=generator), dim=1)
    labels = [LABEL_ORDER[index % 5] for index in range(count)]
    return x, label_tensor(labels), labels


class FoldTests(unittest.TestCase):
    def test_families_never_split_and_every_training_part_has_all_classes(self) -> None:
        families, labels = [], []
        for label_index, label in enumerate(LABEL_ORDER):
            for family_index in range(4 + label_index % 3):
                for row in range(5):
                    families.append(f"{label}-fam-{family_index}")
                    labels.append(label)
        folds = grouped_stratified_folds(families, labels)
        by_family = {}
        for family, fold in zip(families, folds):
            self.assertEqual(by_family.setdefault(family, fold), fold)
        self.assertEqual(set(folds), set(range(5)))
        self.assertEqual(folds, grouped_stratified_folds(list(families), list(labels)))
        with self.assertRaises(TuningError):
            grouped_stratified_folds(["a", "a"], [LABEL_ORDER[0], LABEL_ORDER[1]])


class SupConTests(unittest.TestCase):
    def test_clustered_rows_score_lower_than_mixed_rows(self) -> None:
        y = torch.tensor([0, 0, 1, 1])
        clustered = torch.nn.functional.normalize(torch.tensor([[1.0, 0.0], [1.0, 0.01], [0.0, 1.0], [0.01, 1.0]]), dim=1)
        mixed = clustered[[0, 2, 1, 3]]
        self.assertLess(float(supcon_loss(clustered, y)), float(supcon_loss(mixed, y)))
        self.assertEqual(float(supcon_loss(clustered, torch.tensor([0, 1, 2, 3]))), 0.0)


class FitTests(unittest.TestCase):
    def test_fixed_epoch_fly_a_runs_exactly_and_is_reproducible(self) -> None:
        x, y, _ = fixture_rows()
        graph = fixture_graph()
        for objective in ("distance", "distance_supcon"):
            first = fit_fly_a(graph, x, y, objective=objective, learning_rate=0.01, seed=7, max_epochs=3)
            second = fit_fly_a(graph, x, y, objective=objective, learning_rate=0.01, seed=7, max_epochs=3)
            self.assertEqual((first.selected_epoch, first.epochs_run), (3, 3))
            with torch.no_grad():
                self.assertTrue(torch.equal(first.model(x), second.model(x)))
        with self.assertRaises(TuningError):
            fit_fly_a(graph, x, None, objective="distance_supcon", learning_rate=0.01, seed=7, max_epochs=1)

    def test_early_stopping_restores_best_epoch(self) -> None:
        x, y, _ = fixture_rows()
        graph = fixture_graph()
        result = fit_fly_a(graph, x[:30], None, objective="distance", learning_rate=0.05, seed=1,
                           max_epochs=8, patience=2, select=(x[30:], None))
        self.assertLessEqual(result.selected_epoch, result.epochs_run)
        self.assertIsNotNone(result.best_selection_value)

    def test_fly_b_on_signed_graph_keeps_signs_and_selects(self) -> None:
        x, y, _ = fixture_rows(width=4)
        graph = replace(fixture_graph(), node_signs=alternating_signs(fixture_graph().node_ids))
        before = torch.sign(graph.build_core().signed_edge_weights.detach())
        result = fit_fly_b(graph, x[:30], y[:30], learning_rate=0.05, seed=2, max_epochs=6, patience=3,
                           select=(x[30:], y[30:]))
        after = torch.sign(result.model.graph_core.signed_edge_weights.detach())
        self.assertTrue(torch.equal(before, after))
        self.assertGreaterEqual(result.epochs_run, result.selected_epoch)

    def test_selection_helpers(self) -> None:
        self.assertEqual(choose_learning_rate({0.001: 0.8, 0.003: 0.9, 0.01: 0.9}), 0.003)
        self.assertEqual(median_epoch([3, 9, 4]), 4)
        self.assertEqual(median_epoch([3, 4]), 4)
        self.assertEqual(median_epoch([0]), 1)


if __name__ == "__main__":
    unittest.main()

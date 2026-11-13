from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import torch
from torch.nn import functional as F

from flycall_data.evaluation import LABEL_ORDER
from flycall_data.fly_ab_training import (
    TrainingConfig,
    load_fly_b_checkpoint,
    train_fly_b_on_features,
)
from flycall_data.graph_core import FlyB, GraphCoreError, SparseGraphCore
from test_fly_ab_training import SOURCE_SHA256, fixture_graph
from test_reducer_classifier_factorial import feature_split


CONFIG = TrainingConfig(batch_size=4, max_epochs=4, patience=3, learning_rate=0.05)


def alternating_signs(node_ids: tuple[int, ...]) -> tuple[tuple[int, int], ...]:
    return tuple((node_id, 1 if index % 3 else -1) for index, node_id in enumerate(node_ids))


def signed_graph():
    graph = fixture_graph()
    return replace(graph, node_signs=alternating_signs(graph.node_ids))


def reference_unsigned_forward(core: SparseGraphCore, drives: torch.Tensor) -> torch.Tensor:
    """The pre-M3.6 all-positive forward pass, written out independently."""

    hidden = torch.zeros((drives.shape[0], len(core.node_ids)))
    driven = torch.zeros_like(hidden).index_copy(1, core.input_index, drives)
    degree = core.in_degrees.clamp_min(1).to(torch.float32).unsqueeze(0)
    gains = F.softplus(core.raw_edge_parameters) + core.epsilon
    for _ in range(core.steps):
        messages = hidden.index_select(1, core.source_index) * gains.unsqueeze(0)
        hidden = torch.tanh(torch.zeros_like(hidden).index_add(1, core.target_index, messages) / degree + driven)
    return hidden.index_select(1, core.output_index)


class UnsignedCompatibilityTests(unittest.TestCase):
    def test_default_core_matches_the_pre_m3_6_forward_bit_for_bit(self) -> None:
        core = fixture_graph().build_core()
        drives = torch.randn((6, 32), generator=torch.Generator().manual_seed(5))
        with torch.no_grad():
            self.assertTrue(torch.equal(core(drives), reference_unsigned_forward(core, drives)))

    def test_default_core_keeps_state_dict_metadata_and_topology_hash(self) -> None:
        core = fixture_graph().build_core()
        self.assertNotIn("edge_signs", core.state_dict())
        self.assertFalse(hasattr(core, "edge_signs"))
        self.assertIsNone(core.node_signs_sha256)
        metadata = core.checkpoint_metadata()
        self.assertFalse(any("sign" in key for key in metadata))
        self.assertTrue(torch.equal(core.signed_edge_weights, core.edge_gains))


class SignedCoreTests(unittest.TestCase):
    def test_signs_are_a_constant_non_persistent_buffer(self) -> None:
        core = signed_graph().build_core()
        self.assertFalse(core.edge_signs.requires_grad)
        self.assertNotIn("edge_signs", core.state_dict())
        self.assertEqual([name for name, _ in core.named_parameters()], ["raw_edge_parameters"])
        expected = [1.0 if dict(signed_graph().node_signs)[source] > 0 else -1.0 for source, _, _ in core.edges]
        self.assertEqual(core.edge_signs.tolist(), expected)
        summary = core.sign_summary()
        self.assertEqual(summary["inhibitory_edge_count"] + summary["excitatory_edge_count"], len(core.edges))
        self.assertGreater(summary["inhibitory_edge_count"], 0)

    def test_inhibitory_source_lowers_target_activation(self) -> None:
        nodes = (1, 2, 3)
        edges = ((1, 3, 4), (2, 3, 4))
        drives = torch.tensor([[1.0, 1.0]])

        def target_activation(sign_of_node_2: int) -> float:
            core = SparseGraphCore(nodes, (1, 2), (3,), edges, steps=2, node_signs={1: 1, 2: sign_of_node_2, 3: 1})
            with torch.no_grad():
                return float(core(drives)[0, 0])

        excitatory, inhibitory = target_activation(1), target_activation(-1)
        self.assertGreater(excitatory, 0.0)
        self.assertLess(inhibitory, excitatory)
        self.assertAlmostEqual(inhibitory, 0.0, places=6)  # equal-strength +/- inputs cancel

    def test_training_changes_only_magnitudes_never_signs(self) -> None:
        graph = signed_graph()
        train, validation = feature_split("train", 4), feature_split("validation", 4)
        initial = graph.build_core()
        initial_signs = torch.sign(initial.signed_edge_weights.detach())
        with tempfile.TemporaryDirectory() as directory:
            result = train_fly_b_on_features(
                graph, train, validation,
                source_sha256=SOURCE_SHA256, checkpoint_path=Path(directory) / "signed.pt",
                config=CONFIG, candidate_name="signed_fixture",
            )
        trained = result.model.graph_core
        self.assertFalse(torch.equal(trained.raw_edge_parameters.detach(), initial.raw_edge_parameters.detach()))
        self.assertTrue(torch.equal(torch.sign(trained.signed_edge_weights.detach()), initial_signs))
        self.assertTrue(torch.all(trained.edge_gains > 0))

    def test_checkpoint_reloads_exactly_and_rejects_other_signs(self) -> None:
        graph = signed_graph()
        train, validation = feature_split("train", 4), feature_split("validation", 4)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "signed.pt"
            result = train_fly_b_on_features(
                graph, train, validation,
                source_sha256=SOURCE_SHA256, checkpoint_path=path, config=CONFIG, candidate_name="signed",
            )
            reloaded = load_fly_b_checkpoint(graph, path, expected_source_sha256=SOURCE_SHA256, input_width=4)
            with torch.no_grad():
                self.assertTrue(torch.equal(result.model(validation.embeddings), reloaded(validation.embeddings)))
            flipped = replace(graph, node_signs=tuple((node, -sign) for node, sign in graph.node_signs))
            with self.assertRaises(GraphCoreError):
                load_fly_b_checkpoint(flipped, path, expected_source_sha256=SOURCE_SHA256, input_width=4)
            with self.assertRaises(GraphCoreError):
                load_fly_b_checkpoint(fixture_graph(), path, expected_source_sha256=SOURCE_SHA256, input_width=4)

    def test_signed_and_unsigned_topology_hashes_differ(self) -> None:
        self.assertNotEqual(
            signed_graph().build_core().topology_sha256, fixture_graph().build_core().topology_sha256
        )
        model = FlyB(signed_graph().build_core(), label_order=LABEL_ORDER)
        self.assertEqual(model.checkpoint_metadata()["graph_core"]["edge_sign_rule"], "fixed-by-source-node-dale")

    def test_invalid_sign_maps_fail(self) -> None:
        graph = fixture_graph()
        full = dict(alternating_signs(graph.node_ids))
        for bad in (
            {key: value for key, value in list(full.items())[1:]},
            {**full, graph.node_ids[0]: 0},
            {**full, graph.node_ids[0]: True},
            {**full, 999999: 1},
        ):
            with self.assertRaises(GraphCoreError):
                SparseGraphCore(graph.node_ids, graph.input_node_ids, graph.output_node_ids, graph.edges, node_signs=bad)


if __name__ == "__main__":
    unittest.main()

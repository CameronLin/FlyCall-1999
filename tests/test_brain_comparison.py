from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import numpy as np
import torch

from flycall_data.brain_comparison import (
    BrainComparisonError,
    edge_log_change,
    eta_squared,
    fly_a_output,
    fly_b_logits,
    jaccard,
    load_trained,
    node_states,
    top_set,
)
from flycall_data.evaluation import LABEL_ORDER
from flycall_data.graph_core import FlyA, FlyB
from test_fly_ab_training import fixture_graph
from test_signed_graph_core import alternating_signs


def signed_graph():
    graph = fixture_graph()
    return replace(graph, node_signs=alternating_signs(graph.node_ids))


class NodeStateTests(unittest.TestCase):
    def test_matches_forward_for_unsigned_and_signed_cores(self) -> None:
        drives = torch.randn((5, 32), generator=torch.Generator().manual_seed(1))
        for graph in (fixture_graph(), signed_graph()):
            core = graph.build_core()
            with torch.no_grad():
                states = node_states(core, drives)
                self.assertTrue(torch.equal(states.index_select(1, core.output_index), core(drives)))

    def test_lesions(self) -> None:
        core = signed_graph().build_core()
        drives = torch.randn((3, 32), generator=torch.Generator().manual_seed(2))
        with torch.no_grad():
            everything = torch.ones(len(core.node_ids), dtype=torch.bool)
            self.assertEqual(float(node_states(core, drives, silenced=everything).abs().sum()), 0.0)
            intact = node_states(core, drives)
            same = node_states(core, drives, edge_scale=torch.ones(len(core.edges)))
            self.assertTrue(torch.equal(intact, same))
            one = torch.zeros(len(core.node_ids), dtype=torch.bool)
            one[0] = True
            self.assertTrue(torch.all(node_states(core, drives, silenced=one)[:, 0] == 0))
        with self.assertRaises(BrainComparisonError):
            node_states(core, drives, edge_scale=torch.ones(3))

    def test_model_level_wrappers_match_models(self) -> None:
        graph = signed_graph()
        torch.manual_seed(0)
        fly_a, fly_b = FlyA(8, graph.build_core()), FlyB(graph.build_core(), label_order=LABEL_ORDER)
        x = torch.nn.functional.normalize(torch.randn((4, 8)), dim=1)
        with torch.no_grad():
            self.assertTrue(torch.allclose(fly_a_output(fly_a, x), fly_a(x), atol=1e-7))
            z = fly_a(x)
            self.assertTrue(torch.allclose(fly_b_logits(fly_b, z), fly_b(z), atol=1e-7))


class MetricTests(unittest.TestCase):
    def test_eta_squared_extremes(self) -> None:
        labels = [0, 0, 1, 1]
        values = np.array([[1.0, 5.0, 2.0], [1.0, 5.0, 3.0], [-1.0, 5.0, 2.0], [-1.0, 5.0, 3.0]])
        np.testing.assert_allclose(eta_squared(values, labels), [1.0, 0.0, 0.0])

    def test_sets_and_log_change(self) -> None:
        self.assertEqual(top_set(np.array([0.1, 0.9, 0.5, 0.7]), fraction=0.5), {1, 3})
        self.assertEqual(top_set(np.array([3.0, 1.0, 2.0]), count=1), {0})
        self.assertAlmostEqual(jaccard({1, 2}, {2, 3}), 1 / 3)
        graph = fixture_graph()
        np.testing.assert_allclose(edge_log_change(graph.build_core(), graph), 0.0, atol=1e-6)

    def test_load_trained_round_trip_and_contract(self) -> None:
        graph = signed_graph()
        model = FlyB(graph.build_core(), label_order=LABEL_ORDER, input_width=4)
        payload = {"metadata": {"seed": 1}, "model_metadata": model.checkpoint_metadata(), "state_dict": model.state_dict()}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "b.pt"
            torch.save(payload, path)
            loaded, metadata = load_trained("fly_b", graph, path, input_width=4)
            self.assertEqual(metadata, {"seed": 1})
            with self.assertRaises(BrainComparisonError):
                load_trained("fly_b", fixture_graph(), path, input_width=4)


if __name__ == "__main__":
    unittest.main()

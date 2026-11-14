from __future__ import annotations

import unittest
from dataclasses import replace

import torch

from flycall_data.brain_comparison import node_states
from flycall_data.graph_core import GraphCoreError, SparseGraphCore
from test_fly_ab_training import fixture_graph
from test_signed_graph_core import alternating_signs, reference_unsigned_forward

# Chain 1 -> 2 -> 3 -> 4 with input 1 and every other node an output.
CHAIN = dict(node_ids=(1, 2, 3, 4), input_node_ids=(1,), output_node_ids=(2, 3, 4),
             edges=((1, 2, 3), (2, 3, 3), (3, 4, 3)), steps=2)


def reached(core: SparseGraphCore) -> list[bool]:
    with torch.no_grad():
        out = core(torch.ones((1, 1)))
    return [bool(abs(value) > 1e-9) for value in out[0].tolist()]


class HopSemanticsTests(unittest.TestCase):
    def test_legacy_t2_reaches_one_hop_and_new_t2_reaches_two(self) -> None:
        self.assertEqual(reached(SparseGraphCore(**CHAIN)), [True, False, False])
        self.assertEqual(reached(SparseGraphCore(**CHAIN, input_at_step_zero=True)), [True, True, False])
        self.assertEqual(reached(SparseGraphCore(**{**CHAIN, "steps": 3}, input_at_step_zero=True)), [True, True, True])

    def test_new_semantics_trains_the_second_hop(self) -> None:
        for flag, expected in ((False, False), (True, True)):
            core = SparseGraphCore(**CHAIN, input_at_step_zero=flag)
            core(torch.ones((2, 1)))[:, 1].sum().backward()  # output node 3
            self.assertEqual(bool(core.raw_edge_parameters.grad[1].abs() > 0), expected)  # edge 2->3

    def test_legacy_default_is_unchanged(self) -> None:
        core = fixture_graph().build_core()
        drives = torch.randn((4, 32), generator=torch.Generator().manual_seed(9))
        with torch.no_grad():
            self.assertTrue(torch.equal(core(drives), reference_unsigned_forward(core, drives)))
        self.assertNotIn("step_semantics", core.checkpoint_metadata())
        flagged = replace(fixture_graph(), input_at_step_zero=True).build_core()
        self.assertIn("step_semantics", flagged.checkpoint_metadata())
        self.assertNotEqual(core.checkpoint_metadata(), flagged.checkpoint_metadata())
        with self.assertRaises(GraphCoreError):
            SparseGraphCore(**CHAIN, input_at_step_zero=1)

    def test_node_states_mirrors_new_semantics(self) -> None:
        graph = replace(fixture_graph(), node_signs=alternating_signs(fixture_graph().node_ids), input_at_step_zero=True)
        core = graph.build_core()
        drives = torch.randn((3, 32), generator=torch.Generator().manual_seed(4))
        with torch.no_grad():
            self.assertTrue(torch.equal(node_states(core, drives).index_select(1, core.output_index), core(drives)))


if __name__ == "__main__":
    unittest.main()

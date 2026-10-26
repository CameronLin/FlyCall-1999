from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import torch

from flycall_data.graph_core import (
    CLASS_ORDER,
    FlyA,
    FlyB,
    FlyBWithE5Residual,
    GraphCoreError,
    SparseGraphCore,
    distance_preserving_loss,
    load_model_checkpoint,
    save_model_checkpoint,
)

M13_IO_MANIFEST_PATH = (
    Path(__file__).resolve().parents[1]
    / ".scratch/1999-connectome-demo/m1-3/engineering-demo-io-v1.0-20261016/io_manifest.json"
)


def read_m13_io_node_ids() -> tuple[list[int], list[int]]:
    """Read only the two ordered I/O ID lists used by this authorized fixture."""
    manifest = json.loads(M13_IO_MANIFEST_PATH.read_text(encoding="utf-8"))
    selection = manifest.get("io_selection")
    if not isinstance(selection, dict):
        raise AssertionError("manifest is missing io_selection")
    input_ids = selection.get("input_node_ids")
    output_ids = selection.get("output_node_ids")
    if not isinstance(input_ids, list) or not isinstance(output_ids, list):
        raise AssertionError("manifest is missing ordered input/output node IDs")
    if any(type(node_id) is not int for node_id in input_ids + output_ids):
        raise AssertionError("manifest I/O IDs must be integer node IDs")
    return input_ids, output_ids


def synthetic_io_order() -> tuple[list[int], list[int], list[int]]:
    # Manifest-shaped fixture lists deliberately use a non-sorted coordinate order.
    input_ids = [1000 + 7 * ((index * 11) % 32) for index in range(32)]
    output_ids = [2000 + 5 * ((index * 13) % 32) for index in range(32)]
    node_ids = sorted(input_ids + output_ids)
    return node_ids, input_ids, output_ids


def synthetic_edges(input_ids: list[int], output_ids: list[int]) -> list[tuple[int, int, int]]:
    # Each edge is a synthetic fixture edge; no project connectome rows are read.
    return [
        (source, target, 1 if index % 2 == 0 else 3)
        for index, (source, target) in enumerate(zip(input_ids, output_ids, strict=True))
    ]


def make_core(steps: int = 2) -> SparseGraphCore:
    node_ids, input_ids, output_ids = synthetic_io_order()
    return SparseGraphCore(
        node_ids=node_ids,
        input_node_ids=input_ids,
        output_node_ids=output_ids,
        edges=synthetic_edges(input_ids, output_ids),
        steps=steps,
    )


class SparseGraphCoreTests(unittest.TestCase):
    def test_fly_b_e5_residual_joins_before_graph_and_backpropagates(self) -> None:
        model = FlyBWithE5Residual(make_core(), embedding_dim=384)
        fly_a_output = torch.nn.functional.normalize(
            torch.randn((3, 32), generator=torch.Generator().manual_seed(31)), dim=1
        )
        e5_embedding = torch.nn.functional.normalize(
            torch.randn((3, 384), generator=torch.Generator().manual_seed(32)), dim=1
        )

        logits = model(fly_a_output, e5_embedding)
        self.assertEqual(tuple(logits.shape), (3, len(CLASS_ORDER)))
        self.assertTrue(torch.all(torch.isfinite(logits)))
        self.assertAlmostEqual(float(model.residual_gate.detach()), 1 / (1 + torch.exp(torch.tensor(2.0)).item()), places=6)
        self.assertEqual(model.parameter_counts["total"], model.fly_b.parameter_counts["total"] + 384 * 32 + 1)
        self.assertFalse(model.checkpoint_metadata()["classifier_shortcut"])

        logits.square().mean().backward()
        self.assertIsNotNone(model.e5_residual_projection.weight.grad)
        self.assertGreater(float(model.e5_residual_projection.weight.grad.abs().sum()), 0.0)
        self.assertIsNotNone(model.fly_b.graph_core.raw_edge_parameters.grad)
        self.assertGreater(float(model.fly_b.graph_core.raw_edge_parameters.grad.abs().sum()), 0.0)

    def test_fly_b_e5_residual_rejects_invalid_shapes_and_non_finite_values(self) -> None:
        model = FlyBWithE5Residual(make_core(), embedding_dim=384)
        with self.assertRaisesRegex(GraphCoreError, "shape"):
            model(torch.zeros((2, 31)), torch.zeros((2, 384)))
        with self.assertRaisesRegex(GraphCoreError, "finite"):
            model(torch.zeros((2, 32)), torch.full((2, 384), float("nan")))

    def test_actual_m13_manifest_io_order_is_preserved_in_synthetic_fixture(self) -> None:
        input_ids, output_ids = read_m13_io_node_ids()
        self.assertEqual(len(input_ids), 32)
        self.assertEqual(len(output_ids), 32)
        self.assertEqual(len(set(input_ids)), 32)
        self.assertEqual(len(set(output_ids)), 32)
        self.assertTrue(set(input_ids).isdisjoint(output_ids))

        # Edges and weights are synthetic; only endpoint IDs/order come from the manifest.
        synthetic_edges = [
            (input_id, output_id, 1 + 2 * (index % 2))
            for index, (input_id, output_id) in enumerate(
                zip(input_ids, output_ids, strict=True)
            )
        ]
        core = SparseGraphCore(
            node_ids=sorted(input_ids + output_ids),
            input_node_ids=input_ids,
            output_node_ids=output_ids,
            edges=synthetic_edges,
            steps=2,
        )
        self.assertEqual(core.input_node_ids, tuple(input_ids))
        self.assertEqual(core.output_node_ids, tuple(output_ids))

        drives = torch.zeros((1, 32))
        drives[0, 0] = 1.0
        drives[0, 1] = 0.5
        output = core(drives)
        self.assertEqual(tuple(output.shape), (1, 32))
        self.assertGreater(float(output[0, 0].detach()), float(output[0, 1].detach()))
        self.assertEqual(float(output[0, 2].detach()), 0.0)

        a_core = SparseGraphCore(
            sorted(input_ids + output_ids), input_ids, output_ids, synthetic_edges, steps=2
        )
        fly_a = FlyA(embedding_dim=2, graph_core=a_core)
        with torch.no_grad():
            fly_a.input_projection.weight.zero_()
            fly_a.input_projection.bias.zero_()
            fly_a.input_projection.weight[0, 0] = 1.0
            fly_a.input_projection.weight[1, 1] = 1.0
        fly_a_output = fly_a(torch.tensor([[1.0, 0.0]]))
        self.assertEqual(tuple(fly_a_output.shape), (1, 32))
        self.assertEqual(tuple(fly_a.graph_core.output_node_ids), tuple(output_ids))
        self.assertEqual(float(fly_a_output[0, 0].detach()), 1.0)
        self.assertTrue(torch.all(fly_a_output[0, 1:] == 0))

        b_core = SparseGraphCore(
            sorted(input_ids + output_ids), input_ids, output_ids, synthetic_edges, steps=2
        )
        fly_b = FlyB(graph_core=b_core, label_order=CLASS_ORDER)
        with torch.no_grad():
            fly_b.input_adapter.weight.copy_(torch.eye(32))
            fly_b.input_adapter.bias.zero_()
            fly_b.readout.weight.zero_()
            fly_b.readout.bias.zero_()
            fly_b.readout.weight[0, 0] = 1.0
        logits = fly_b(fly_a_output)
        self.assertEqual(tuple(fly_b.graph_core.input_node_ids), tuple(input_ids))
        self.assertEqual(tuple(fly_b.graph_core.output_node_ids), tuple(output_ids))
        self.assertEqual(tuple(logits.shape), (1, 5))
        self.assertGreater(float(logits[0, 0].detach()), 0.0)
        self.assertTrue(torch.all(logits[0, 1:] == 0))

    def test_messages_follow_directed_edges_and_do_not_reverse_them(self) -> None:
        forward = SparseGraphCore(
            node_ids=[10, 20, 30],
            input_node_ids=[10],
            output_node_ids=[20, 30],
            edges=[(10, 20, 1), (20, 30, 1)],
            steps=3,
        )
        forward_values = forward(torch.tensor([[1.0]]))
        self.assertGreater(float(forward_values[0, 0].detach()), 0.0)
        self.assertGreater(float(forward_values[0, 1].detach()), 0.0)

        reverse_only = SparseGraphCore(
            node_ids=[10, 20, 30],
            input_node_ids=[10],
            output_node_ids=[20, 30],
            edges=[(20, 10, 1), (30, 20, 1)],
            steps=3,
        )
        reverse_values = reverse_only(torch.tensor([[1.0]]))
        self.assertTrue(torch.equal(reverse_values, torch.zeros_like(reverse_values)))

    def test_t2_and_t4_control_reachable_path_depth(self) -> None:
        edges = [(1, 2, 1), (2, 3, 1), (3, 4, 1)]
        t2 = SparseGraphCore([1, 2, 3, 4], [1], [4], edges, steps=2)
        t4 = SparseGraphCore([1, 2, 3, 4], [1], [4], edges, steps=4)
        drives = torch.tensor([[0.8]])
        self.assertEqual(tuple(t2(drives).shape), (1, 1))
        self.assertEqual(float(t2(drives)[0, 0].detach()), 0.0)
        self.assertGreater(float(t4(drives)[0, 0].detach()), 0.0)

    def test_input_and_output_coordinate_order_is_preserved(self) -> None:
        node_ids, input_ids, output_ids = synthetic_io_order()
        core = SparseGraphCore(
            node_ids=node_ids,
            input_node_ids=input_ids,
            output_node_ids=output_ids,
            edges=synthetic_edges(input_ids, output_ids),
            steps=2,
        )
        drives = torch.zeros((1, 32))
        drives[0, 0] = 1.0
        drives[0, 1] = 0.5
        values = core(drives)
        self.assertEqual(tuple(values.shape), (1, 32))
        self.assertGreater(float(values[0, 0].detach()), float(values[0, 1].detach()))
        self.assertEqual(float(values[0, 2].detach()), 0.0)
        self.assertEqual(core.input_node_ids, tuple(input_ids))
        self.assertEqual(core.output_node_ids, tuple(output_ids))

    def test_edge_prior_is_per_target_mean_one_and_includes_self_loop(self) -> None:
        core = SparseGraphCore(
            node_ids=[1, 2, 3],
            input_node_ids=[1, 2],
            output_node_ids=[3],
            edges=[(1, 3, 1), (2, 3, 3), (3, 3, 1)],
            steps=2,
        )
        prior_raw = torch.tensor([torch.log(torch.tensor(2.0)), torch.log(torch.tensor(4.0)), torch.log(torch.tensor(2.0))])
        expected_prior = prior_raw / prior_raw.mean()
        self.assertEqual(core.in_degrees[core.node_index[3]], 3)
        torch.testing.assert_close(core.edge_gains.detach(), expected_prior, rtol=1e-5, atol=1e-6)
        torch.testing.assert_close(core.edge_gains.detach().mean(), torch.tensor(1.0), rtol=1e-5, atol=1e-6)

    def test_non_edges_have_no_parameters_and_existing_gains_stay_positive(self) -> None:
        core = make_core()
        self.assertEqual(core.raw_edge_parameters.numel(), len(core.edges))
        self.assertEqual(core.edge_gains.numel(), len(core.edges))
        self.assertTrue(torch.all(torch.isfinite(core.edge_gains)))
        self.assertTrue(torch.all(core.edge_gains > 0))
        self.assertNotIn((synthetic_io_order()[1][0], synthetic_io_order()[2][1]), core.edges)

    def test_invalid_weights_and_unrepresentable_priors_fail_closed(self) -> None:
        for bad_weight in (-1, float("nan"), float("inf")):
            with self.subTest(weight=bad_weight):
                with self.assertRaises(GraphCoreError):
                    SparseGraphCore([1, 2], [1], [2], [(1, 2, bad_weight)], steps=2)

        with self.assertRaises(GraphCoreError):
            SparseGraphCore(
                [1, 2, 3], [1, 2], [3], [(1, 3, 0), (2, 3, 1)], steps=2
            )

    def test_fixed_indegree_normalization_counts_self_loop(self) -> None:
        core = SparseGraphCore(
            node_ids=[1, 2, 3],
            input_node_ids=[1, 2],
            output_node_ids=[3],
            edges=[(1, 3, 1), (2, 3, 1), (3, 3, 1)],
            steps=2,
        )
        values = core(torch.tensor([[1.0, 0.0]]))
        expected = torch.tanh(torch.tensor([[torch.tanh(torch.tensor(1.0)).item() / 3.0]]))
        torch.testing.assert_close(values, expected)


class FlyModelTests(unittest.TestCase):
    def test_fly_a_and_b_dimensions_and_taxonomy_order(self) -> None:
        torch.manual_seed(11)
        fly_a = FlyA(embedding_dim=4, graph_core=make_core())
        embeddings = torch.tensor(
            [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.5, 0.5, 0.5, 0.5]]
        )
        z_a = fly_a(embeddings)
        self.assertEqual(tuple(z_a.shape), (3, 32))
        torch.testing.assert_close(torch.linalg.vector_norm(z_a, dim=1), torch.ones(3))

        fly_b = FlyB(graph_core=make_core(), label_order=CLASS_ORDER)
        logits = fly_b(z_a)
        self.assertEqual(tuple(logits.shape), (3, 5))
        self.assertEqual(fly_b.label_order, CLASS_ORDER)
        self.assertIsNot(fly_a.graph_core.raw_edge_parameters, fly_b.graph_core.raw_edge_parameters)
        b_gains_before = fly_b.graph_core.raw_edge_parameters.detach().clone()
        with torch.no_grad():
            fly_a.graph_core.raw_edge_parameters[0].add_(0.25)
        torch.testing.assert_close(fly_b.graph_core.raw_edge_parameters, b_gains_before)

    def test_edge_parameters_receive_finite_nonzero_gradients_and_update(self) -> None:
        torch.manual_seed(23)
        fly_a = FlyA(embedding_dim=4, graph_core=make_core())
        embeddings = torch.tensor(
            [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.5, 0.5, 0.5, 0.5]]
        )
        loss_a = distance_preserving_loss(embeddings, fly_a(embeddings))
        self.assertTrue(torch.isfinite(loss_a))
        optimizer_a = torch.optim.SGD(fly_a.parameters(), lr=0.01)
        before_a = fly_a.graph_core.raw_edge_parameters.detach().clone()
        support_a = fly_a.graph_core.edges
        optimizer_a.zero_grad()
        loss_a.backward()
        grad_a = fly_a.graph_core.raw_edge_parameters.grad
        self.assertIsNotNone(grad_a)
        self.assertTrue(torch.all(torch.isfinite(grad_a)))
        self.assertTrue(torch.any(grad_a != 0))
        optimizer_a.step()
        self.assertTrue(torch.any(fly_a.graph_core.raw_edge_parameters.detach() != before_a))
        self.assertEqual(fly_a.graph_core.edges, support_a)
        self.assertTrue(torch.all(fly_a.graph_core.edge_gains.detach() > 0))

        fly_a.zero_grad(set_to_none=True)
        fly_b = FlyB(graph_core=make_core(), label_order=CLASS_ORDER)
        for parameter in fly_a.parameters():
            parameter.requires_grad_(False)
        inputs_b = fly_a(embeddings).detach()
        labels = torch.tensor([0, 1, 2])
        logits = fly_b(inputs_b)
        loss_b = torch.nn.functional.cross_entropy(logits, labels)
        self.assertTrue(torch.isfinite(loss_b))
        optimizer_b = torch.optim.SGD(fly_b.parameters(), lr=0.01)
        before_b = fly_b.graph_core.raw_edge_parameters.detach().clone()
        support_b = fly_b.graph_core.edges
        optimizer_b.zero_grad()
        loss_b.backward()
        grad_b = fly_b.graph_core.raw_edge_parameters.grad
        self.assertIsNotNone(grad_b)
        self.assertTrue(torch.all(torch.isfinite(grad_b)))
        self.assertTrue(torch.any(grad_b != 0))
        optimizer_b.step()
        self.assertTrue(torch.any(fly_b.graph_core.raw_edge_parameters.detach() != before_b))
        self.assertEqual(fly_b.graph_core.edges, support_b)
        self.assertTrue(torch.all(fly_b.graph_core.edge_gains.detach() > 0))
        self.assertTrue(all(parameter.grad is None for parameter in fly_a.parameters()))

    def test_changing_a_reachable_edge_changes_logits_without_bypass(self) -> None:
        core = make_core()
        fly_b = FlyB(graph_core=core, label_order=CLASS_ORDER)
        with torch.no_grad():
            fly_b.input_adapter.weight.copy_(torch.eye(32))
            fly_b.input_adapter.bias.zero_()
            fly_b.readout.weight.zero_()
            fly_b.readout.bias.zero_()
            fly_b.readout.weight[0, 0] = 1.0
        inputs = torch.zeros((1, 32))
        inputs[0, 0] = 1.0
        baseline = fly_b(inputs)
        with torch.no_grad():
            # This is the unique path from input coordinate 0 to output coordinate 0.
            fly_b.graph_core.raw_edge_parameters[0] = -20.0
        ablated = fly_b(inputs)
        self.assertNotEqual(float(baseline[0, 0].detach()), float(ablated[0, 0].detach()))
        self.assertAlmostEqual(float(ablated[0, 0].detach()), 0.0, places=5)

    def test_checkpoint_reload_preserves_cpu_logits_and_rejects_mismatch(self) -> None:
        torch.manual_seed(37)
        first = FlyB(graph_core=make_core(), label_order=CLASS_ORDER).eval()
        inputs = torch.randn((2, 32))
        expected = first(inputs).detach()
        metadata = first.checkpoint_metadata()

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fixture.pt"
            save_model_checkpoint(first, path)
            second = FlyB(graph_core=make_core(), label_order=CLASS_ORDER).eval()
            load_model_checkpoint(second, path)
            torch.testing.assert_close(second(inputs), expected, rtol=1e-6, atol=1e-7)

            incompatible = FlyB(graph_core=make_core(steps=4), label_order=CLASS_ORDER)
            with self.assertRaises(GraphCoreError):
                load_model_checkpoint(incompatible, path)
        self.assertEqual(metadata["label_order"], list(CLASS_ORDER))

    def test_forward_and_losses_use_only_in_memory_tensors(self) -> None:
        torch.manual_seed(41)
        embeddings = torch.randn((4, 4))
        fly_a = FlyA(embedding_dim=4, graph_core=make_core())
        z_a = fly_a(embeddings)
        loss_a = distance_preserving_loss(embeddings, z_a)
        fly_b = FlyB(graph_core=make_core(), label_order=CLASS_ORDER)
        logits = fly_b(z_a.detach())
        loss_b = torch.nn.functional.cross_entropy(logits, torch.tensor([0, 1, 2, 3]))
        self.assertTrue(torch.isfinite(loss_a))
        self.assertTrue(torch.isfinite(loss_b))
        self.assertEqual(tuple(logits.shape), (4, 5))


if __name__ == "__main__":
    unittest.main()

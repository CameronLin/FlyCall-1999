from __future__ import annotations

import unittest

from flycall_data.io_reachability import (
    IOReachabilityError,
    check_io_reachability,
    select_io_nodes,
)


class SelectIONodesTests(unittest.TestCase):
    def test_selection_is_repeatable_disjoint_and_respects_requested_counts(self) -> None:
        node_ids = [41, 7, 93, 12, 88, 3, 54, 19, 28, 76]

        first = select_io_nodes(
            node_ids, input_count=3, output_count=2, salt="fixture-salt"
        )
        second = select_io_nodes(
            node_ids, input_count=3, output_count=2, salt="fixture-salt"
        )

        self.assertEqual(first, second)
        self.assertEqual(len(first["input_node_ids"]), 3)
        self.assertEqual(len(first["output_node_ids"]), 2)
        self.assertTrue(
            set(first["input_node_ids"]).isdisjoint(first["output_node_ids"])
        )
        self.assertTrue(
            set(first["input_node_ids"] + first["output_node_ids"]).issubset(
                node_ids
            )
        )

    def test_selection_does_not_depend_on_node_row_order(self) -> None:
        node_ids = [41, 7, 93, 12, 88, 3, 54, 19, 28, 76]
        reversed_ids = list(reversed(node_ids))

        first = select_io_nodes(
            node_ids, input_count=3, output_count=2, salt="fixture-salt"
        )
        second = select_io_nodes(
            reversed_ids, input_count=3, output_count=2, salt="fixture-salt"
        )

        self.assertEqual(first, second)

    def test_selection_rejects_duplicate_demo_node_ids(self) -> None:
        with self.assertRaisesRegex(IOReachabilityError, "node IDs must be unique"):
            select_io_nodes([1, 2, 2, 3], input_count=1, output_count=1)

    def test_selection_rejects_insufficient_demo_nodes(self) -> None:
        with self.assertRaisesRegex(IOReachabilityError, "requires at least"):
            select_io_nodes([1, 2, 3], input_count=2, output_count=2)


class CheckIOReachabilityTests(unittest.TestCase):
    def test_uses_source_to_target_direction_and_ignores_weight_as_cost(self) -> None:
        edges = [(1, 2, 1), (2, 3, 1), (1, 3, 10_000), (3, 4, 0)]

        forward = check_io_reachability(
            edges, [1], [3], max_steps=2, node_ids=[1, 2, 3, 4]
        )
        backward = check_io_reachability(
            edges, [3], [1], max_steps=2, node_ids=[1, 2, 3, 4]
        )

        self.assertEqual(forward["outputs"], [{"node_id": 3, "shortest_hops": 1}])
        self.assertTrue(forward["all_outputs_reachable"])
        self.assertEqual(backward["outputs"], [{"node_id": 1, "shortest_hops": None}])
        self.assertEqual(backward["unreachable_output_ids"], [1])

    def test_multi_source_bfs_returns_shortest_hops_for_each_output(self) -> None:
        edges = [
            (10, 30, 100),
            (20, 30, 1),
            (20, 40, 1),
            (40, 50, 1),
            (30, 50, 1),
        ]

        result = check_io_reachability(
            edges,
            input_ids=[10, 20],
            output_ids=[30, 50],
            max_steps=3,
            node_ids=[10, 20, 30, 40, 50],
        )

        self.assertEqual(
            result["outputs"],
            [
                {"node_id": 30, "shortest_hops": 1},
                {"node_id": 50, "shortest_hops": 2},
            ],
        )
        self.assertEqual(result["unreachable_output_ids"], [])

    def test_reaches_at_step_limit_but_reports_beyond_limit_as_null(self) -> None:
        edges = [(1, 2, 1), (2, 3, 1), (3, 4, 1)]

        result = check_io_reachability(
            edges,
            input_ids=[1],
            output_ids=[3, 4],
            max_steps=2,
            node_ids=[1, 2, 3, 4],
        )

        self.assertEqual(
            result["outputs"],
            [
                {"node_id": 3, "shortest_hops": 2},
                {"node_id": 4, "shortest_hops": None},
            ],
        )
        self.assertEqual(result["unreachable_output_ids"], [4])

    def test_unreachable_output_has_null_distance_and_is_listed(self) -> None:
        result = check_io_reachability(
            [(1, 2, 1), (3, 4, 1)],
            input_ids=[1],
            output_ids=[4],
            max_steps=4,
            node_ids=[1, 2, 3, 4],
        )

        self.assertEqual(result["outputs"], [{"node_id": 4, "shortest_hops": None}])
        self.assertEqual(result["unreachable_output_ids"], [4])

    def test_rejects_overlapping_input_and_output_sets(self) -> None:
        with self.assertRaisesRegex(IOReachabilityError, "must be disjoint"):
            check_io_reachability(
                [(1, 2, 1)],
                input_ids=[1],
                output_ids=[1],
                max_steps=4,
                node_ids=[1, 2],
            )

    def test_rejects_io_ids_missing_from_demo_nodes(self) -> None:
        with self.assertRaisesRegex(IOReachabilityError, "not present in demo nodes"):
            check_io_reachability(
                [(1, 2, 1)],
                input_ids=[1],
                output_ids=[99],
                max_steps=4,
                node_ids=[1, 2],
            )

    def test_rejects_an_edge_endpoint_missing_from_demo_nodes(self) -> None:
        with self.assertRaisesRegex(IOReachabilityError, "edge endpoint.*not present"):
            check_io_reachability(
                [(1, 99, 1)],
                input_ids=[1],
                output_ids=[2],
                max_steps=4,
                node_ids=[1, 2],
            )


if __name__ == "__main__":
    unittest.main()

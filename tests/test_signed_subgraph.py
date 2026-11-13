from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from flycall_data.signed_subgraph import (
    EXCITATORY,
    INHIBITORY,
    SignedSubgraphError,
    induced_edges,
    parquet_neighbor_scanner,
    quota_bfs,
)
from flycall_data.streaming_bfs import _hash_priority


def adjacency_scanner(edges: list[tuple[int, int]]):
    def neighbors_of(frontier: list[int]) -> set[int]:
        found: set[int] = set()
        members = set(frontier)
        for source, target in edges:
            if source in members:
                found.add(target)
            if target in members:
                found.add(source)
        return found

    return neighbors_of


STAR = [(0, node) for node in range(1, 21)]


class QuotaBfsTests(unittest.TestCase):
    def test_fills_quotas_in_hash_priority_order_and_skips_unsigned(self) -> None:
        signs = {0: 1, **{node: (1 if node % 2 else -1) for node in range(1, 17)}}  # 17..20 unsigned
        result = quota_bfs(0, signs, adjacency_scanner(STAR), quotas={EXCITATORY: 3, INHIBITORY: 2})
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.counts, {"excitatory": 3, "inhibitory": 2})
        layer = sorted(range(1, 21), key=_hash_priority)
        expected, need = [], {1: 2, -1: 2}
        for node in layer:
            sign = signs.get(node, 0)
            if sign and need[sign] > 0:
                need[sign] -= 1
                expected.append(node)
            if not any(need.values()):
                break
        self.assertEqual(result.selected, [0, *expected])
        self.assertTrue(all(node in signs for node in result.selected))

    def test_only_admitted_nodes_expand(self) -> None:
        # 0 - 1(unsigned) - 2(+) : 2 must never be reached through the unsigned node.
        edges = [(0, 1), (1, 2), (0, 3)]
        result = quota_bfs(0, {0: 1, 2: 1, 3: -1}, adjacency_scanner(edges), quotas={EXCITATORY: 2, INHIBITORY: 1})
        self.assertEqual(result.status, "stopped")
        self.assertEqual(result.stop_reason, "frontier_exhausted")
        self.assertEqual(sorted(result.selected), [0, 3])

    def test_quota_full_nodes_are_skipped_not_expanded(self) -> None:
        edges = [(0, 1), (1, 2)]
        result = quota_bfs(0, {0: 1, 1: 1, 2: -1}, adjacency_scanner(edges), quotas={EXCITATORY: 1, INHIBITORY: 1})
        self.assertEqual(result.stop_reason, "frontier_exhausted")
        self.assertEqual(result.layers[0]["skipped_quota_full"], 1)
        self.assertEqual(result.selected, [0])

    def test_depth_limit_and_seed_rules(self) -> None:
        chain = [(index, index + 1) for index in range(10)]
        signs = {index: 1 for index in range(11)}
        result = quota_bfs(0, signs, adjacency_scanner(chain), quotas={EXCITATORY: 11, INHIBITORY: 1}, max_depth=3)
        self.assertEqual((result.status, result.stop_reason), ("stopped", "max_depth_reached"))
        self.assertEqual(len(result.selected), 4)
        self.assertEqual(quota_bfs(5, {}, adjacency_scanner(chain)).stop_reason, "seed_has_no_sign")
        with self.assertRaises(SignedSubgraphError):
            quota_bfs(0, signs, adjacency_scanner(chain), quotas={EXCITATORY: 0, INHIBITORY: 1})

    def test_result_is_independent_of_edge_row_order(self) -> None:
        signs = {0: 1, **{node: (1 if node % 3 else -1) for node in range(1, 21)}}
        forward = quota_bfs(0, signs, adjacency_scanner(STAR), quotas={EXCITATORY: 4, INHIBITORY: 3})
        reverse = quota_bfs(0, signs, adjacency_scanner(list(reversed(STAR))), quotas={EXCITATORY: 4, INHIBITORY: 3})
        self.assertEqual(forward.selected, reverse.selected)


class ParquetScanTests(unittest.TestCase):
    def test_scanner_and_induced_edges_on_parquet(self) -> None:
        table = pa.table({
            "source_id": pa.array([0, 2, 1, 3, 4], type=pa.int64()),
            "target_id": pa.array([1, 0, 2, 0, 4], type=pa.int64()),
            "weight": pa.array([5, 6, 7, 8, 9], type=pa.int64()),
        })
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "edges.parquet"
            pq.write_table(table, path)
            counter: dict[str, int] = {}
            self.assertEqual(parquet_neighbor_scanner(path, counter)([0]), {1, 2, 3})
            self.assertEqual(counter["scans"], 1)
            self.assertEqual(induced_edges(path, [0, 1, 2]), [(0, 1, 5), (1, 2, 7), (2, 0, 6)])


if __name__ == "__main__":
    unittest.main()


class ReachableOutputTests(unittest.TestCase):
    def test_outputs_are_reachable_and_follow_hash_priority(self) -> None:
        from flycall_data.io_reachability import _priority
        from flycall_data.signed_subgraph import select_reachable_outputs

        # 1 -> 2 -> 3 -> 4 ; 1 -> 5 ; 6 isolated ; 7 -> 1 (only feeds the input)
        nodes = [1, 2, 3, 4, 5, 6, 7]
        edges = [(1, 2, 1), (2, 3, 1), (3, 4, 1), (1, 5, 1), (7, 1, 1)]
        result = select_reachable_outputs(nodes, edges, [1], count=2, salt="s", max_steps=2)
        self.assertEqual(result["eligible_output_candidates"], 3)  # 2, 5 (1 hop), 3 (2 hops)
        expected = sorted(sorted([2, 3, 5], key=lambda n: (_priority(n, "output", "s"), n))[:2])
        self.assertEqual(result["output_node_ids"], expected)
        with self.assertRaises(SignedSubgraphError):
            select_reachable_outputs(nodes, edges, [1], count=4, salt="s", max_steps=2)
        with self.assertRaises(SignedSubgraphError):
            select_reachable_outputs(nodes, edges, [99], count=1, salt="s", max_steps=2)

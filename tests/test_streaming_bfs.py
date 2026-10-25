from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pyarrow as pa
import pyarrow.parquet as pq

from flycall_data.streaming_bfs import StreamingBfsError
from flycall_data.streaming_bfs import StreamingBfsResourceError
from flycall_data.streaming_bfs import probe_streaming_bfs
from flycall_data.streaming_bfs import select_hash_priority_seed


class StreamingBfsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.edges_path = self.root / "edges.parquet"
        pq.write_table(
            pa.table(
                {
                    "source_id": pa.array([10001, 30, 30, 99, 20], type=pa.int64()),
                    "target_id": pa.array([20, 20, 40, 100, 20], type=pa.int64()),
                    "weight": pa.array([7, 11, 13, 17, 23], type=pa.int64()),
                }
            ),
            self.edges_path,
            row_group_size=2,
        )

    def run_probe(
        self,
        *,
        seed_node_id: int = 10001,
        node_limit: int = 3,
        max_scans: int = 501,
        name: str = "probe",
        min_free_bytes: int = 4 * 1024**3,
    ) -> dict[str, object]:
        return probe_streaming_bfs(
            self.edges_path,
            seed_node_id,
            node_limit,
            self.root / name,
            max_scans=max_scans,
            min_free_bytes=min_free_bytes,
        )

    def test_layer_scans_find_weak_neighbors_and_keep_induced_edge_direction(self) -> None:
        result = self.run_probe()

        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["selected_node_ids"], [20, 30, 10001])
        self.assertEqual(result["bfs_layer_scan_count"], 2)
        self.assertEqual(result["completion_reason"], "node_limit_reached")
        self.assertEqual(result["induced_edge_count"], 3)
        self.assertEqual(
            pq.read_table(Path(str(result["output_dir"])) / "candidate_edges.parquet").to_pylist(),
            [
                {"source_id": 10001, "target_id": 20, "weight": 7},
                {"source_id": 30, "target_id": 20, "weight": 11},
                {"source_id": 20, "target_id": 20, "weight": 23},
            ],
        )

    def test_component_smaller_than_target_finishes_after_exhausting_weak_frontier(self) -> None:
        result = self.run_probe(node_limit=500)

        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["completion_reason"], "component_exhausted")
        self.assertEqual(result["selected_node_ids"], [20, 30, 40, 10001])
        self.assertEqual(result["bfs_layer_scan_count"], 4)
        self.assertEqual(result["scans_completed"], 6)
        self.assertEqual(result["independent_validation"], "pass")

    def test_node_cap_uses_hash_priority_across_all_neighbors_in_a_layer(self) -> None:
        result = self.run_probe(seed_node_id=20, node_limit=2)

        self.assertEqual(result["status"], "complete")
        self.assertEqual(result["completion_reason"], "node_limit_reached")
        self.assertEqual(result["selected_node_ids"], [20, 30])
        self.assertEqual(result["bfs_layer_scan_count"], 1)
        self.assertEqual(result["selection_policy"], "fixed_salt_hash_priority")
        self.assertEqual(result["hash_priority"]["algorithm"], "BLAKE2b-128")

    def test_hash_priority_seed_uses_complete_nodes_and_ignores_row_order(self) -> None:
        nodes = list(range(1, 1025))
        first_path = self.root / "nodes-first.parquet"
        second_path = self.root / "nodes-reversed.parquet"
        pq.write_table(pa.table({"node_id": pa.array(nodes, type=pa.int64())}), first_path, row_group_size=127)
        pq.write_table(
            pa.table({"node_id": pa.array(list(reversed(nodes)), type=pa.int64())}),
            second_path,
            row_group_size=113,
        )

        first = select_hash_priority_seed(first_path)
        second = select_hash_priority_seed(second_path)

        self.assertEqual(first["seed_node_id"], 49)
        self.assertEqual(second["seed_node_id"], first["seed_node_id"])
        self.assertEqual(first["candidate_count"], 1024)
        self.assertEqual(second["candidate_count"], 1024)
        self.assertEqual(first["seed_priority_hex"], second["seed_priority_hex"])

    def test_hash_priority_seed_stops_below_disk_safety_floor(self) -> None:
        nodes_path = self.root / "nodes-for-disk-guard.parquet"
        pq.write_table(pa.table({"node_id": pa.array([1, 2, 3], type=pa.int64())}), nodes_path)

        with patch(
            "flycall_data.streaming_bfs.shutil.disk_usage",
            return_value=SimpleNamespace(free=4 * 1024**3 - 1),
        ):
            with self.assertRaises(StreamingBfsResourceError):
                select_hash_priority_seed(nodes_path)

    def test_hash_priority_is_not_numeric_low_id_order_and_truncation_is_reproducible(self) -> None:
        center = 100_000
        leaves = list(range(1, 1025))
        rows = [
            {"source_id": center, "target_id": leaf, "weight": leaf}
            for leaf in leaves
        ]
        first_edges = self.root / "wide-frontier-first.parquet"
        reversed_edges = self.root / "wide-frontier-reversed.parquet"
        schema = pa.schema(
            [
                ("source_id", pa.int64()),
                ("target_id", pa.int64()),
                ("weight", pa.int64()),
            ]
        )
        pq.write_table(pa.Table.from_pylist(rows, schema=schema), first_edges, row_group_size=71)
        pq.write_table(
            pa.Table.from_pylist(list(reversed(rows)), schema=schema),
            reversed_edges,
            row_group_size=89,
        )

        first = probe_streaming_bfs(first_edges, center, 33, self.root / "wide-first")
        second = probe_streaming_bfs(reversed_edges, center, 33, self.root / "wide-reversed")
        expected_priority_neighbors = [
            49, 594, 470, 225, 248, 998, 455, 634, 685, 567, 298, 134, 142, 394,
            816, 68, 59, 753, 1002, 913, 445, 604, 393, 149, 756, 90, 266, 151,
            58, 287, 252, 653,
        ]
        expected_nodes = {center, *expected_priority_neighbors}

        self.assertEqual(first["selected_node_ids"], second["selected_node_ids"])
        self.assertEqual(set(first["selected_node_ids"]), expected_nodes)
        self.assertGreater(sum(node_id > 512 for node_id in expected_priority_neighbors), 8)
        self.assertGreater(max(expected_priority_neighbors), 900)
        self.assertEqual(first["induced_edge_count"], 32)
        self.assertEqual(second["induced_edge_count"], 32)
        self.assertEqual(first["independent_validation"], "pass")
        self.assertEqual(second["independent_validation"], "pass")

        def induced_edge_set(result: dict[str, object]) -> set[tuple[int, int, int]]:
            table = pq.read_table(Path(str(result["output_dir"])) / "candidate_edges.parquet")
            return {
                (row["source_id"], row["target_id"], row["weight"])
                for row in table.to_pylist()
            }

        expected_edges = {(center, node_id, node_id) for node_id in expected_priority_neighbors}
        self.assertEqual(induced_edge_set(first), expected_edges)
        self.assertEqual(induced_edge_set(second), expected_edges)

        broad_sample = probe_streaming_bfs(
            first_edges,
            center,
            257,
            self.root / "wide-broad-sample",
        )
        broad_leaves = set(broad_sample["selected_node_ids"]) - {center}
        quartile_counts = tuple(
            sum(low <= node_id <= high for node_id in broad_leaves)
            for low, high in ((1, 256), (257, 512), (513, 768), (769, 1024))
        )
        self.assertEqual(quartile_counts, (72, 72, 59, 53))

    def test_selected_nodes_do_not_depend_on_parquet_row_order(self) -> None:
        original_table = pq.read_table(self.edges_path)
        reordered_path = self.root / "edges-reordered.parquet"
        reordered_table = pa.Table.from_pylist(
            list(reversed(original_table.to_pylist())), schema=original_table.schema
        )
        pq.write_table(reordered_table, reordered_path, row_group_size=2)
        self.assertNotEqual(
            pq.read_table(self.edges_path).to_pylist()[0],
            pq.read_table(reordered_path).to_pylist()[0],
        )

        original = self.run_probe(seed_node_id=20, node_limit=2, name="original-order")
        reordered = probe_streaming_bfs(
            reordered_path,
            20,
            2,
            self.root / "reordered-order",
        )

        self.assertEqual(original["selected_node_ids"], [20, 30])
        self.assertEqual(reordered["selected_node_ids"], original["selected_node_ids"])

        def induced_edge_set(result: dict[str, object]) -> set[tuple[int, int, int]]:
            table = pq.read_table(Path(str(result["output_dir"])) / "candidate_edges.parquet")
            return {
                (row["source_id"], row["target_id"], row["weight"])
                for row in table.to_pylist()
            }

        self.assertEqual(induced_edge_set(reordered), induced_edge_set(original))

    def test_scan_budget_exhaustion_never_marks_partial_bfs_complete(self) -> None:
        result = self.run_probe(node_limit=500, max_scans=3)

        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(result["completion_reason"], "scan_budget_exhausted")
        self.assertEqual(result["selected_node_ids"], [20, 10001])
        self.assertEqual(result["bfs_layer_scan_count"], 1)
        self.assertEqual(result["independent_validation"], "not_run")
        self.assertFalse((Path(str(result["output_dir"])) / "candidate_edges.parquet").exists())

    def test_missing_seed_is_distinguished_from_a_small_component(self) -> None:
        result = self.run_probe(seed_node_id=123456)

        self.assertEqual(result["status"], "seed_not_found")
        self.assertEqual(result["selected_node_ids"], [])
        self.assertEqual(result["bfs_layer_scan_count"], 1)
        self.assertEqual(result["induced_edge_count"], 0)
        self.assertEqual(result["independent_validation"], "pass")

    def test_resource_gate_refuses_to_start_below_requested_free_space(self) -> None:
        output_dir = self.root / "blocked"

        with self.assertRaises(StreamingBfsResourceError):
            probe_streaming_bfs(
                self.edges_path,
                10001,
                3,
                output_dir,
                min_free_bytes=1 << 60,
            )

        self.assertFalse(output_dir.exists())

    def test_scan_and_node_caps_cannot_exceed_agreed_limits(self) -> None:
        with self.assertRaisesRegex(StreamingBfsError, "max_scans"):
            self.run_probe(max_scans=502)

        with self.assertRaisesRegex(StreamingBfsError, "node_limit"):
            self.run_probe(node_limit=501)


if __name__ == "__main__":
    unittest.main()

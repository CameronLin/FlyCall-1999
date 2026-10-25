from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from flycall_data.subgraph_probe import probe_induced_subgraph
from flycall_data.subgraph_probe import SubgraphProbeError


class SubgraphProbeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.edges_path = self.root / "edges.parquet"
        pq.write_table(
            pa.table(
                {
                    "source_id": pa.array([10, 30, 30, 99, 20, 20], type=pa.int64()),
                    "target_id": pa.array([20, 20, 40, 100, 20, 30], type=pa.int64()),
                    "weight": pa.array([7, 11, 13, 17, 23, 29], type=pa.int64()),
                }
            ),
            self.edges_path,
        )

    def run_probe(
        self,
        *,
        seed_node_id: int = 10,
        node_limit: int = 3,
        max_scan_edges: int = 20,
        name: str = "probe",
    ) -> dict[str, object]:
        return probe_induced_subgraph(
            self.edges_path,
            seed_node_id,
            node_limit,
            max_scan_edges,
            self.root / name,
        )

    def test_bfs_treats_edges_as_undirected_but_keeps_output_direction_and_weight(self) -> None:
        result = self.run_probe()

        self.assertEqual(result["selected_node_ids"], [10, 20, 30])
        self.assertEqual(
            result["induced_edges"],
            [
                {"source_id": 10, "target_id": 20, "weight": 7},
                {"source_id": 30, "target_id": 20, "weight": 11},
                {"source_id": 20, "target_id": 20, "weight": 23},
                {"source_id": 20, "target_id": 30, "weight": 29},
            ],
        )

    def test_node_limit_is_a_hard_upper_bound(self) -> None:
        result = self.run_probe(node_limit=2)

        self.assertEqual(result["selected_node_ids"], [10, 20])
        self.assertLessEqual(result["selected_node_count"], 2)
        self.assertEqual(result["status"], "node_limit_reached")

    def test_induced_edges_exclude_any_edge_with_an_unselected_endpoint(self) -> None:
        result = self.run_probe()
        induced = result["induced_edges"]

        self.assertTrue(
            all(
                edge["source_id"] in {10, 20, 30}
                and edge["target_id"] in {10, 20, 30}
                for edge in induced
            )
        )
        self.assertNotIn(
            {"source_id": 30, "target_id": 40, "weight": 13}, induced
        )

    def test_missing_seed_is_reported_after_a_complete_fixture_scan(self) -> None:
        result = self.run_probe(seed_node_id=1234)

        self.assertEqual(result["status"], "seed_not_found")
        self.assertTrue(result["scan_complete"])
        self.assertEqual(result["selected_node_ids"], [])

    def test_scan_budget_exhaustion_is_incomplete_with_actual_scan_count(self) -> None:
        result = self.run_probe(max_scan_edges=2)

        self.assertEqual(result["status"], "incomplete")
        self.assertEqual(result["completeness_reason"], "budget_exhausted")
        self.assertFalse(result["scan_complete"])
        self.assertEqual(result["edges_scanned"], 2)
        self.assertEqual(result["max_scan_edges"], 2)

    def test_probe_result_is_marked_non_formal_and_reproducible(self) -> None:
        first = self.run_probe(name="first")
        second = self.run_probe(name="second")
        persisted = json.loads((self.root / "first" / "probe_result.json").read_text())

        self.assertFalse(first["is_formal_subgraph"])
        self.assertEqual(first["selected_node_ids"], second["selected_node_ids"])
        self.assertEqual(first["induced_edges_sha256"], second["induced_edges_sha256"])
        self.assertFalse(persisted["is_formal_subgraph"])
        self.assertNotIn("induced_edges", persisted)

    def test_official_edges_cannot_write_into_the_m1_1_output_directory(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        official_edges = (
            project_root / "data/connectome/derived/malecns_v1.0/edges.parquet"
        )
        official_output = official_edges.parent
        before_names = sorted(path.name for path in official_output.iterdir())

        with self.assertRaisesRegex(SubgraphProbeError, "may write only under"):
            probe_induced_subgraph(official_edges, 10001, 1, 1, official_output)

        self.assertEqual(
            sorted(path.name for path in official_output.iterdir()), before_names
        )


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import pyarrow as pa
import pyarrow.feather as feather
import pyarrow.parquet as pq

from flycall_data.connectome_importer import (
    ConnectomeImportError,
    iter_normalized_edges,
    write_standard_tables,
)


class ConnectomeImporterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.source = self.root / "fixture.feather"
        self.write_fixture(
            [
                (2**53 + 11, 200, 2),
                (200, 2**53 + 11, 1),
                (2**53 + 11, 200, 3),
                (200, 200, 4),
                (300, 200, 5),
            ]
        )

    def write_fixture(self, rows: list[tuple[int, int, int]]) -> None:
        table = pa.table(
            {
                "body_pre": pa.array([row[0] for row in rows], type=pa.int64()),
                "body_post": pa.array([row[1] for row in rows], type=pa.int64()),
                "weight": pa.array([row[2] for row in rows], type=pa.int64()),
            }
        )
        feather.write_feather(table, self.source, compression="uncompressed")

    @staticmethod
    def sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def test_iter_normalized_edges_maps_direction_and_preserves_rows(self) -> None:
        batches = list(iter_normalized_edges(self.source, batch_rows=2))

        self.assertTrue(batches)
        self.assertEqual(
            batches[0].schema,
            pa.schema(
                [
                    ("source_id", pa.int64()),
                    ("target_id", pa.int64()),
                    ("weight", pa.int64()),
                ]
            ),
        )
        rows = pa.Table.from_batches(batches).to_pylist()
        self.assertEqual(
            rows,
            [
                {"source_id": 2**53 + 11, "target_id": 200, "weight": 2},
                {"source_id": 200, "target_id": 2**53 + 11, "weight": 1},
                {"source_id": 2**53 + 11, "target_id": 200, "weight": 3},
                {"source_id": 200, "target_id": 200, "weight": 4},
                {"source_id": 300, "target_id": 200, "weight": 5},
            ],
        )

    def test_writer_aggregates_across_batch_boundary_and_preserves_self_loop(self) -> None:
        output_dir = self.root / "derived"

        result = write_standard_tables(self.source, output_dir, batch_rows=2)

        edges = pq.read_table(output_dir / "edges.parquet")
        self.assertEqual(
            edges.to_pylist(),
            [
                {"source_id": 200, "target_id": 200, "weight": 4},
                {"source_id": 200, "target_id": 2**53 + 11, "weight": 1},
                {"source_id": 300, "target_id": 200, "weight": 5},
                {"source_id": 2**53 + 11, "target_id": 200, "weight": 5},
            ],
        )
        self.assertEqual(result["edge_count"], 4)
        self.assertEqual(result["source_row_count"], 5)
        self.assertEqual(result["input_weight_sum"], result["output_weight_sum"])
        self.assertEqual(result["source_self_loop_rows"], 1)

    def test_writer_deduplicates_nodes_and_writes_exact_schemas(self) -> None:
        output_dir = self.root / "derived"
        write_standard_tables(self.source, output_dir, batch_rows=2)

        edges = pq.read_table(output_dir / "edges.parquet")
        nodes = pq.read_table(output_dir / "nodes.parquet")
        self.assertEqual(
            edges.schema,
            pa.schema(
                [
                    ("source_id", pa.int64()),
                    ("target_id", pa.int64()),
                    ("weight", pa.int64()),
                ]
            ),
        )
        self.assertEqual(nodes.schema, pa.schema([("node_id", pa.int64())]))
        self.assertEqual(
            nodes.column("node_id").to_pylist(), [200, 300, 2**53 + 11]
        )
        self.assertEqual(len(set(nodes.column("node_id").to_pylist())), 3)

    def test_null_values_and_wrong_schema_fail_explicitly_without_output(self) -> None:
        bad_source = self.root / "bad.feather"
        feather.write_feather(
            pa.table(
                {
                    "body_pre": pa.array([1, None], type=pa.int64()),
                    "body_post": pa.array([2, 3], type=pa.int64()),
                    "weight": pa.array([1, 1], type=pa.int64()),
                }
            ),
            bad_source,
        )
        null_output = self.root / "null-output"
        with self.assertRaisesRegex(ConnectomeImportError, "null"):
            write_standard_tables(bad_source, null_output, batch_rows=1)
        self.assertFalse(null_output.exists())

        schema_source = self.root / "wrong-schema.feather"
        feather.write_feather(
            pa.table(
                {
                    "body_pre": pa.array([1], type=pa.int64()),
                    "body_post": pa.array([2], type=pa.int64()),
                    "weight": pa.array([1], type=pa.int64()),
                    "extra": pa.array([9], type=pa.int64()),
                }
            ),
            schema_source,
        )
        with self.assertRaisesRegex(ConnectomeImportError, "schema"):
            list(iter_normalized_edges(schema_source, batch_rows=1))

    def test_nonpositive_weight_fails_explicitly(self) -> None:
        bad_source = self.root / "bad-weight.feather"
        feather.write_feather(
            pa.table(
                {
                    "body_pre": pa.array([1], type=pa.int64()),
                    "body_post": pa.array([2], type=pa.int64()),
                    "weight": pa.array([0], type=pa.int64()),
                }
            ),
            bad_source,
        )

        with self.assertRaisesRegex(ConnectomeImportError, "positive"):
            list(iter_normalized_edges(bad_source, batch_rows=1))

    def test_source_hash_is_unchanged_and_manifest_records_import(self) -> None:
        before = self.sha256(self.source)
        output_dir = self.root / "derived"

        write_standard_tables(self.source, output_dir, batch_rows=2)

        manifest = json.loads((output_dir / "import_manifest.json").read_text())
        self.assertEqual(self.sha256(self.source), before)
        self.assertEqual(manifest["source_sha256"], before)
        self.assertEqual(manifest["source_rows"], 5)
        self.assertEqual(manifest["output_edge_count"], 4)
        self.assertEqual(manifest["output_node_count"], 3)
        self.assertTrue(manifest["pyarrow_version"])
        self.assertEqual(manifest["resource_strategy"]["duckdb_threads"], 2)


if __name__ == "__main__":
    unittest.main()

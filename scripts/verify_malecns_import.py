#!/usr/bin/env python3
"""Stream-verify the M1.1 MaleCNS Parquet outputs and their source manifest."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from flycall_data.connectome_importer import (  # noqa: E402
    SOURCE_FILENAME,
    SOURCE_GENERATION,
    SOURCE_ROW_COUNT,
    SOURCE_SHA256,
    SOURCE_SIZE_BYTES,
)


DATA_DIR = PROJECT_ROOT / "data/connectome/derived/malecns_v1.0"
SOURCE_PATH = PROJECT_ROOT / "data/connectome/malecns_v1.0" / SOURCE_FILENAME
EDGE_SCHEMA = pa.schema(
    [
        ("source_id", pa.int64()),
        ("target_id", pa.int64()),
        ("weight", pa.int64()),
    ]
)
NODE_SCHEMA = pa.schema([("node_id", pa.int64())])


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def any_true(values: pa.Array) -> bool:
    result = pc.any(values).as_py()
    return bool(result) if result is not None else False


def verify() -> dict[str, object]:
    manifest_path = DATA_DIR / "import_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    edges_path = DATA_DIR / "edges.parquet"
    nodes_path = DATA_DIR / "nodes.parquet"
    expected_source = {
        "source_filename": SOURCE_FILENAME,
        "source_generation": SOURCE_GENERATION,
        "source_size_bytes": SOURCE_SIZE_BYTES,
        "source_sha256": SOURCE_SHA256,
        "source_rows": SOURCE_ROW_COUNT,
    }
    for key, value in expected_source.items():
        if manifest.get(key) != value:
            raise ValueError(f"manifest {key} mismatch: {manifest.get(key)!r} != {value!r}")
    if SOURCE_PATH.stat().st_size != SOURCE_SIZE_BYTES or sha256(SOURCE_PATH) != SOURCE_SHA256:
        raise ValueError("source size or SHA-256 does not match the pinned M0.1 object")

    strategy = manifest["resource_strategy"]
    if strategy.get("duckdb_memory_limit") != "2GB" or strategy.get("duckdb_threads") != 2:
        raise ValueError("manifest DuckDB resource settings exceed the approved limit")

    edge_file = pq.ParquetFile(edges_path)
    node_file = pq.ParquetFile(nodes_path)
    if edge_file.schema_arrow != EDGE_SCHEMA:
        raise ValueError(f"unexpected edge schema: {edge_file.schema_arrow}")
    if node_file.schema_arrow != NODE_SCHEMA:
        raise ValueError(f"unexpected node schema: {node_file.schema_arrow}")

    edge_rows = 0
    weight_sum = 0
    self_loop_rows = 0
    self_loop_weight_sum = 0
    previous_pair: tuple[int, int] | None = None
    for batch in edge_file.iter_batches(batch_size=65_536):
        if batch.schema != EDGE_SCHEMA or any(column.null_count for column in batch.columns):
            raise ValueError("edge output has a schema or null-value violation")
        sources = batch.column(0)
        targets = batch.column(1)
        weights = batch.column(2)
        if any_true(pc.less_equal(weights, 0)):
            raise ValueError("edge output contains a nonpositive weight")
        weight_sum += int(pc.sum(weights).as_py() or 0)
        loop_mask = pc.equal(sources, targets)
        self_loop_rows += int(pc.sum(pc.cast(loop_mask, pa.int64())).as_py() or 0)
        self_loop_weight_sum += int(
            pc.sum(pc.if_else(loop_mask, weights, pa.scalar(0, type=pa.int64()))).as_py()
            or 0
        )
        if batch.num_rows > 1:
            previous_sources = sources.slice(0, batch.num_rows - 1)
            next_sources = sources.slice(1)
            previous_targets = targets.slice(0, batch.num_rows - 1)
            next_targets = targets.slice(1)
            bad_order = pc.or_kleene(
                pc.less(next_sources, previous_sources),
                pc.and_kleene(
                    pc.equal(next_sources, previous_sources),
                    pc.less_equal(next_targets, previous_targets),
                ),
            )
            if any_true(bad_order):
                raise ValueError("edge output is unsorted or contains a duplicate pair")
        first_pair = (int(sources[0].as_py()), int(targets[0].as_py())) if batch.num_rows else None
        if previous_pair is not None and first_pair is not None and first_pair <= previous_pair:
            raise ValueError("edge output order or uniqueness fails across row groups")
        if batch.num_rows:
            previous_pair = (int(sources[-1].as_py()), int(targets[-1].as_py()))
        edge_rows += batch.num_rows

    node_rows = 0
    previous_node: int | None = None
    for batch in node_file.iter_batches(batch_size=65_536):
        nodes = batch.column(0)
        if nodes.null_count:
            raise ValueError("node output contains null IDs")
        if batch.num_rows > 1 and any_true(
            pc.less_equal(nodes.slice(1), nodes.slice(0, batch.num_rows - 1))
        ):
            raise ValueError("node output is unsorted or contains duplicate IDs")
        if batch.num_rows:
            first_node = int(nodes[0].as_py())
            last_node = int(nodes[-1].as_py())
            if previous_node is not None and first_node <= previous_node:
                raise ValueError("node order or uniqueness fails across row groups")
            previous_node = last_node
        node_rows += batch.num_rows

    expected_edges = manifest["output_edge_count"]
    expected_nodes = manifest["output_node_count"]
    if edge_rows != expected_edges or edge_file.metadata.num_rows != expected_edges:
        raise ValueError(f"edge count mismatch: streamed {edge_rows}, manifest {expected_edges}")
    if node_rows != expected_nodes or node_file.metadata.num_rows != expected_nodes:
        raise ValueError(f"node count mismatch: streamed {node_rows}, manifest {expected_nodes}")
    if weight_sum != manifest["input_weight_sum"] or weight_sum != manifest["output_weight_sum"]:
        raise ValueError("full Parquet weight sum differs from the manifest")
    if self_loop_rows != manifest["output_self_loop_pairs"]:
        raise ValueError("full Parquet self-loop count differs from the manifest")
    if self_loop_weight_sum != manifest["source_self_loop_weight_sum"]:
        raise ValueError("full Parquet self-loop weight differs from the source scan")
    if edge_rows != manifest["source_rows"] - manifest["output_duplicate_rows_aggregated"]:
        raise ValueError("edge count does not match the global duplicate aggregation record")
    if sha256(edges_path) != manifest["output_edges_sha256"]:
        raise ValueError("edges.parquet SHA-256 differs from the manifest")
    if sha256(nodes_path) != manifest["output_nodes_sha256"]:
        raise ValueError("nodes.parquet SHA-256 differs from the manifest")
    if sha256(SOURCE_PATH) != SOURCE_SHA256:
        raise ValueError("source SHA-256 changed during output verification")

    return {
        "source_rows": SOURCE_ROW_COUNT,
        "edge_rows_verified": edge_rows,
        "node_rows_verified": node_rows,
        "weight_sum_verified": weight_sum,
        "self_loop_pairs_verified": self_loop_rows,
        "self_loop_weight_verified": self_loop_weight_sum,
        "duplicate_rows_aggregated": manifest["output_duplicate_rows_aggregated"],
        "duckdb_memory_limit": strategy["duckdb_memory_limit"],
        "duckdb_threads": strategy["duckdb_threads"],
        "pyarrow_version": manifest["pyarrow_version"],
        "duckdb_version": manifest["duckdb_version"],
        "edges_sha256": manifest["output_edges_sha256"],
        "nodes_sha256": manifest["output_nodes_sha256"],
        "source_sha256": SOURCE_SHA256,
    }


if __name__ == "__main__":
    print(json.dumps(verify(), ensure_ascii=False, indent=2))

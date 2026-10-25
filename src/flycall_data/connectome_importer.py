"""Read-only, bounded-memory import of the selected MaleCNS v1.0 Feather.

``iter_normalized_edges`` maps each source batch to the public edge schema and
preserves every input row. ``write_standard_tables`` performs global pair
aggregation, including pairs repeated in different record batches, then writes
the sorted edge and endpoint-node Parquet tables.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Iterator

import duckdb
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.ipc as ipc
import pyarrow.parquet as pq


SOURCE_FILENAME = "connectome-weights-male-cns-v1.0-minconf-0.5.feather"
SOURCE_GENERATION = 1780494887545976
SOURCE_SIZE_BYTES = 1_051_241_946
SOURCE_SHA256 = "e35da783d1c686b2b58b3b87cd6a403ae43bfcfba8bff28e08ef752c1a56afc1"
SOURCE_ROW_COUNT = 151_856_684

_SOURCE_SCHEMA = pa.schema(
    [
        ("body_pre", pa.int64()),
        ("body_post", pa.int64()),
        ("weight", pa.int64()),
    ]
)
_EDGE_SCHEMA = pa.schema(
    [
        ("source_id", pa.int64()),
        ("target_id", pa.int64()),
        ("weight", pa.int64()),
    ]
)
_NODE_SCHEMA = pa.schema([("node_id", pa.int64())])
_MAX_BATCH_ROWS = 1_000_000
_DUCKDB_MEMORY_LIMIT = "2GB"
_DUCKDB_THREADS = 2
_SAFETY_DISK_BYTES = 1 << 30


class ConnectomeImportError(ValueError):
    """Raised when the source or an import invariant violates the contract."""


def _positive_batch_rows(batch_rows: int) -> int:
    if isinstance(batch_rows, bool) or not isinstance(batch_rows, int):
        raise ConnectomeImportError("batch_rows must be an integer")
    if batch_rows < 1 or batch_rows > _MAX_BATCH_ROWS:
        raise ConnectomeImportError(
            f"batch_rows must be between 1 and {_MAX_BATCH_ROWS}"
        )
    return batch_rows


def _open_feather(path: Path) -> ipc.RecordBatchFileReader:
    try:
        reader = ipc.open_file(path)
    except (OSError, pa.ArrowException) as exc:
        raise ConnectomeImportError(f"could not open Feather source {path}: {exc}") from exc
    if reader.schema != _SOURCE_SCHEMA:
        observed = ", ".join(
            f"{field.name}:{field.type}" for field in reader.schema
        )
        expected = ", ".join(
            f"{field.name}:{field.type}" for field in _SOURCE_SCHEMA
        )
        raise ConnectomeImportError(
            f"source schema mismatch: expected [{expected}], observed [{observed}]"
        )
    return reader


def _validate_batch(batch: pa.RecordBatch, batch_index: int) -> None:
    if batch.schema != _SOURCE_SCHEMA:
        raise ConnectomeImportError(
            f"record batch {batch_index} has an unexpected schema"
        )
    for column_index, field in enumerate(_SOURCE_SCHEMA):
        null_count = batch.column(column_index).null_count
        if null_count:
            raise ConnectomeImportError(
                f"record batch {batch_index} field {field.name} contains "
                f"{null_count} null value(s)"
            )
    if batch.num_rows and pc.any(pc.less_equal(batch.column(2), 0)).as_py():
        raise ConnectomeImportError(
            f"record batch {batch_index} weight values must be positive integers"
        )


def iter_normalized_edges(
    path: str | os.PathLike[str], batch_rows: int
) -> Iterator[pa.RecordBatch]:
    """Yield source rows mapped to ``source_id,target_id,weight`` in int64.

    The mapping is ``body_pre -> source_id`` and ``body_post -> target_id``.
    This function validates but does not combine or discard rows; callers that
    need dataset-wide duplicate-pair aggregation must use
    :func:`write_standard_tables`.
    """

    batch_rows = _positive_batch_rows(batch_rows)
    reader = _open_feather(Path(path))
    for batch_index in range(reader.num_record_batches):
        source_batch = reader.get_batch(batch_index)
        _validate_batch(source_batch, batch_index)
        for offset in range(0, source_batch.num_rows, batch_rows):
            piece = source_batch.slice(offset, batch_rows)
            yield pa.RecordBatch.from_arrays(
                [piece.column(0), piece.column(1), piece.column(2)],
                schema=_EDGE_SCHEMA,
            )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _source_row_count_for_estimate(
    source_path: Path, reader: ipc.RecordBatchFileReader
) -> int:
    if source_path.name == SOURCE_FILENAME:
        return SOURCE_ROW_COUNT
    # Non-production Feather files are accepted for small local fixtures. The
    # production source uses the count already established by M0.1/M1.1.
    return sum(
        reader.get_batch(index).num_rows
        for index in range(reader.num_record_batches)
    )


def _estimated_peak_disk_bytes(source_rows: int) -> int:
    # Covers normalized rows, aggregated rows, worst-case edge Parquet,
    # sorted endpoint spill/output, further DuckDB spill, and 1 GiB of slack.
    return source_rows * 112 + _SAFETY_DISK_BYTES


def _nearest_existing_directory(path: Path) -> Path:
    candidate = path
    while not candidate.exists():
        parent = candidate.parent
        if parent == candidate:
            raise ConnectomeImportError(f"no existing output parent for {path}")
        candidate = parent
    if not candidate.is_dir():
        raise ConnectomeImportError(f"output parent is not a directory: {candidate}")
    return candidate


def _sql_path(path: Path) -> str:
    return "'" + str(path).replace("'", "''") + "'"


def _verify_parquet(path: Path, expected_schema: pa.Schema, expected_rows: int) -> None:
    parquet_file = pq.ParquetFile(path)
    if parquet_file.schema_arrow != expected_schema:
        raise ConnectomeImportError(
            f"output schema mismatch for {path.name}: {parquet_file.schema_arrow}"
        )


def _write_unique_nodes_from_sorted_endpoints(
    sorted_endpoints_path: Path,
    nodes_path: Path,
    batch_rows: int,
) -> int:
    """Deduplicate a disk-sorted endpoint stream with bounded batch memory."""

    node_count = 0
    last_node: int | None = None
    pending: list[int] = []

    def flush(writer: pq.ParquetWriter) -> None:
        nonlocal node_count
        if not pending:
            return
        writer.write_table(
            pa.Table.from_arrays(
                [pa.array(pending, type=pa.int64())], schema=_NODE_SCHEMA
            )
        )
        node_count += len(pending)
        pending.clear()

    with pq.ParquetWriter(
        nodes_path, _NODE_SCHEMA, compression="zstd", use_dictionary=False
    ) as writer:
        parquet_file = pq.ParquetFile(sorted_endpoints_path)
        for batch in parquet_file.iter_batches(
            batch_size=batch_rows, columns=["node_id"]
        ):
            for node_value in batch.column(0).to_pylist():
                node_id = int(node_value)
                if last_node is not None and node_id < last_node:
                    raise ConnectomeImportError(
                        "sorted endpoint stream is not monotonic"
                    )
                if node_id != last_node:
                    pending.append(node_id)
                    last_node = node_id
                    if len(pending) >= batch_rows:
                        flush(writer)
        flush(writer)
    return node_count
    if parquet_file.metadata.num_rows != expected_rows:
        raise ConnectomeImportError(
            f"output row count mismatch for {path.name}: "
            f"expected {expected_rows}, found {parquet_file.metadata.num_rows}"
        )


def _sha256_or_raise(path: Path) -> str:
    try:
        return _sha256(path)
    except OSError as exc:
        raise ConnectomeImportError(f"could not hash {path}: {exc}") from exc


def _directory_size(path: Path) -> int:
    return sum(
        candidate.stat().st_size
        for candidate in path.rglob("*")
        if candidate.is_file()
    )


def write_standard_tables(
    source_path: str | os.PathLike[str],
    output_dir: str | os.PathLike[str],
    batch_rows: int,
) -> dict[str, Any]:
    """Globally aggregate a Feather source and atomically publish three files.

    Input batches are appended to a disk-backed DuckDB table. A global SQL
    ``GROUP BY`` sums duplicate pairs across all batches with a 2 GiB memory
    limit and DuckDB spill files in the staging directory. Endpoints are
    deduplicated from the aggregated edge table, so every retained endpoint is
    represented exactly once in ``nodes.parquet``.
    """

    batch_rows = _positive_batch_rows(batch_rows)
    source = Path(source_path)
    destination = Path(output_dir)
    if not source.is_file():
        raise ConnectomeImportError(f"source file does not exist: {source}")
    if destination.exists():
        raise ConnectomeImportError(
            f"refusing to overwrite existing output: {destination}"
        )

    reader = _open_feather(source)
    source_size_before = source.stat().st_size
    source_hash_before = _sha256_or_raise(source)
    is_official_source = source.name == SOURCE_FILENAME
    if is_official_source:
        if source_size_before != SOURCE_SIZE_BYTES:
            raise ConnectomeImportError(
                f"official source size mismatch: expected {SOURCE_SIZE_BYTES}, "
                f"found {source_size_before}"
            )
        if source_hash_before != SOURCE_SHA256:
            raise ConnectomeImportError(
                f"official source SHA-256 mismatch: expected {SOURCE_SHA256}, "
                f"found {source_hash_before}"
            )

    source_rows_for_estimate = _source_row_count_for_estimate(source, reader)
    estimated_peak_bytes = _estimated_peak_disk_bytes(source_rows_for_estimate)
    disk_check_path = _nearest_existing_directory(destination.parent)
    free_bytes_before = shutil.disk_usage(disk_check_path).free
    if free_bytes_before < estimated_peak_bytes:
        raise ConnectomeImportError(
            "insufficient free disk space before import: "
            f"need an estimated {estimated_peak_bytes} bytes, "
            f"available {free_bytes_before} bytes at {disk_check_path}"
        )

    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(
        tempfile.mkdtemp(
            prefix=f".{destination.name}.staging-", dir=destination.parent
        )
    )
    database_path = staging / "aggregation.duckdb"
    spill_path = staging / "duckdb-spill"
    connection: duckdb.DuckDBPyConnection | None = None
    try:
        spill_path.mkdir()
        connection = duckdb.connect(str(database_path))
        connection.execute(f"SET memory_limit={_sql_path(Path(_DUCKDB_MEMORY_LIMIT))}")
        connection.execute(f"SET temp_directory={_sql_path(spill_path)}")
        connection.execute(f"SET threads={_DUCKDB_THREADS}")
        connection.execute("SET preserve_insertion_order=false")
        connection.execute(
            "CREATE TABLE normalized_input ("
            "source_id BIGINT NOT NULL, target_id BIGINT NOT NULL, weight BIGINT NOT NULL)"
        )

        input_rows = 0
        input_weight_sum = 0
        source_self_loop_rows = 0
        source_self_loop_weight_sum = 0
        for batch_index, batch in enumerate(
            iter_normalized_edges(source, batch_rows)
        ):
            table = pa.Table.from_batches([batch])
            connection.register("_normalized_batch", table)
            try:
                connection.execute(
                    "INSERT INTO normalized_input "
                    "SELECT source_id, target_id, weight FROM _normalized_batch"
                )
            finally:
                connection.unregister("_normalized_batch")
            weight_sum = pc.sum(batch.column(2)).as_py()
            loop_mask = pc.equal(batch.column(0), batch.column(1))
            loop_rows = pc.sum(pc.cast(loop_mask, pa.int64())).as_py()
            loop_weight_sum = pc.sum(
                pc.if_else(loop_mask, batch.column(2), pa.scalar(0, type=pa.int64()))
            ).as_py()
            input_rows += batch.num_rows
            input_weight_sum += int(weight_sum or 0)
            source_self_loop_rows += int(loop_rows or 0)
            source_self_loop_weight_sum += int(loop_weight_sum or 0)

        observed_input_rows = connection.execute(
            "SELECT COUNT(*) FROM normalized_input"
        ).fetchone()[0]
        if observed_input_rows != input_rows:
            raise ConnectomeImportError(
                f"DuckDB input row mismatch: streamed {input_rows}, stored {observed_input_rows}"
            )
        if is_official_source and input_rows != SOURCE_ROW_COUNT:
            raise ConnectomeImportError(
                f"official source row count mismatch: expected {SOURCE_ROW_COUNT}, "
                f"found {input_rows}"
            )
        stored_weight_sum = connection.execute(
            "SELECT COALESCE(SUM(weight), 0) FROM normalized_input"
        ).fetchone()[0]
        if int(stored_weight_sum) != input_weight_sum:
            raise ConnectomeImportError(
                "DuckDB input weight sum differs from streamed weight sum"
            )
        stored_loop_rows, stored_loop_weight = connection.execute(
            "SELECT COUNT(*), COALESCE(SUM(weight), 0) FROM normalized_input "
            "WHERE source_id=target_id"
        ).fetchone()
        if (
            stored_loop_rows != source_self_loop_rows
            or int(stored_loop_weight) != source_self_loop_weight_sum
        ):
            raise ConnectomeImportError(
                "DuckDB input self-loop statistics differ from streamed statistics"
            )

        connection.execute(
            "CREATE TABLE edges AS "
            "SELECT source_id, target_id, SUM(weight) AS weight "
            "FROM normalized_input GROUP BY source_id, target_id"
        )
        edge_count = connection.execute("SELECT COUNT(*) FROM edges").fetchone()[0]
        duplicate_rows_aggregated = input_rows - edge_count
        weight_bounds = connection.execute(
            "SELECT MIN(weight), MAX(weight) FROM edges"
        ).fetchone()
        if edge_count and (
            int(weight_bounds[0]) <= 0
            or int(weight_bounds[1]) > 9_223_372_036_854_775_807
        ):
            raise ConnectomeImportError(
                "aggregated pair weights must fit positive int64 values"
            )
        output_weight_sum = int(
            connection.execute("SELECT COALESCE(SUM(weight), 0) FROM edges").fetchone()[0]
        )
        if output_weight_sum != input_weight_sum:
            raise ConnectomeImportError(
                f"weight conservation failed: input {input_weight_sum}, "
                f"aggregated {output_weight_sum}"
            )
        output_self_loop_pairs, output_self_loop_weight_sum = connection.execute(
            "SELECT COUNT(*), COALESCE(SUM(weight), 0) FROM edges "
            "WHERE source_id=target_id"
        ).fetchone()
        if int(output_self_loop_weight_sum) != source_self_loop_weight_sum:
            raise ConnectomeImportError("self-loop weight was not preserved")

        edges_path = staging / "edges.parquet"
        nodes_path = staging / "nodes.parquet"
        sorted_endpoints_path = staging / "endpoints_sorted.parquet"
        connection.execute(
            "COPY (SELECT source_id::BIGINT AS source_id, "
            "target_id::BIGINT AS target_id, weight::BIGINT AS weight "
            f"FROM edges ORDER BY source_id, target_id) TO {_sql_path(edges_path)} "
            "(FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 65536)"
        )
        connection.execute(
            "COPY (SELECT node_id::BIGINT AS node_id FROM ("
            "SELECT source_id AS node_id FROM edges UNION ALL "
            "SELECT target_id AS node_id FROM edges) endpoints ORDER BY node_id) "
            f"TO {_sql_path(sorted_endpoints_path)} "
            "(FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 65536)"
        )
        _verify_parquet(sorted_endpoints_path, _NODE_SCHEMA, edge_count * 2)
        node_count = _write_unique_nodes_from_sorted_endpoints(
            sorted_endpoints_path, nodes_path, batch_rows
        )
        sorted_endpoints_path.unlink()
        _verify_parquet(edges_path, _EDGE_SCHEMA, edge_count)
        _verify_parquet(nodes_path, _NODE_SCHEMA, node_count)

        source_size_after = source.stat().st_size
        source_hash_after = _sha256_or_raise(source)
        if source_size_after != source_size_before or source_hash_after != source_hash_before:
            raise ConnectomeImportError(
                "source Feather changed during import: "
                f"size {source_size_before}->{source_size_after}, "
                f"SHA-256 {source_hash_before}->{source_hash_after}"
            )

        staging_bytes_before_cleanup = _directory_size(staging)
        manifest: dict[str, Any] = {
            "source_filename": source.name,
            "source_generation": SOURCE_GENERATION if is_official_source else None,
            "source_size_bytes": source_size_before,
            "source_sha256": source_hash_before,
            "source_rows": input_rows,
            "output_edge_count": edge_count,
            "output_node_count": node_count,
            "output_duplicate_rows_aggregated": duplicate_rows_aggregated,
            "input_weight_sum": input_weight_sum,
            "output_weight_sum": output_weight_sum,
            "source_self_loop_rows": source_self_loop_rows,
            "output_self_loop_pairs": int(output_self_loop_pairs),
            "source_self_loop_weight_sum": source_self_loop_weight_sum,
            "output_edges_sha256": _sha256_or_raise(edges_path),
            "output_nodes_sha256": _sha256_or_raise(nodes_path),
            "pyarrow_version": pa.__version__,
            "duckdb_version": duckdb.__version__,
            "import_rules": {
                "source_fields": {
                    "body_pre": "source_id",
                    "body_post": "target_id",
                    "weight": "weight",
                },
                "output_edge_schema": [
                    "source_id:int64",
                    "target_id:int64",
                    "weight:int64",
                ],
                "output_node_schema": ["node_id:int64"],
                "node_ids": "unique union of all source_id and target_id values",
                "duplicate_pairs": "sum weight globally, including across record batches",
                "self_loops": "retain",
                "nulls": "fail explicitly",
                "nonpositive_weights": "fail explicitly",
                "filters": "none; do not infer or add a minconf-0.5 predicate",
                "endpoint_semantics": "node; no neuron, region, or cell_type annotation inferred",
            },
            "resource_strategy": {
                "global_aggregation": "DuckDB GROUP BY with disk spill; node IDs are deduplicated from externally sorted endpoint rows",
                "duckdb_memory_limit": _DUCKDB_MEMORY_LIMIT,
                "duckdb_threads": _DUCKDB_THREADS,
                "read_batch_rows": batch_rows,
                "estimated_peak_extra_disk_bytes": estimated_peak_bytes,
                "free_disk_bytes_before_import": free_bytes_before,
                "staging_bytes_before_database_cleanup": staging_bytes_before_cleanup,
                "source_rows_for_disk_estimate": source_rows_for_estimate,
            },
            "source_sha256_before_import": source_hash_before,
            "source_sha256_after_import": source_hash_after,
            "source_size_bytes_before_import": source_size_before,
            "source_size_bytes_after_import": source_size_after,
        }
        (staging / "import_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        connection.close()
        connection = None
        for transient in (database_path, database_path.with_suffix(".duckdb.wal")):
            if transient.exists():
                transient.unlink()
        shutil.rmtree(spill_path, ignore_errors=True)
        if destination.exists():
            raise ConnectomeImportError(
                f"refusing to overwrite output created during import: {destination}"
            )
        os.rename(staging, destination)
        return {
            "source_row_count": input_rows,
            "edge_count": edge_count,
            "node_count": node_count,
            "input_weight_sum": input_weight_sum,
            "output_weight_sum": output_weight_sum,
            "source_self_loop_rows": source_self_loop_rows,
            "output_self_loop_pairs": int(output_self_loop_pairs),
            "manifest": manifest,
            "output_dir": str(destination),
        }
    except BaseException:
        if connection is not None:
            connection.close()
        shutil.rmtree(staging, ignore_errors=True)
        raise

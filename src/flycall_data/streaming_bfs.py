"""Exact no-index BFS feasibility probe for the M1.1 edge Parquet.

This is an exploratory seam, not a frozen public API. Each BFS level streams
the complete edge table once and treats endpoints as weak/undirected only for
discovery. The final induced-edge table retains the original directed rows.
"""

from __future__ import annotations

import hashlib
import heapq
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from .runtime_resources import peak_rss_bytes


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OFFICIAL_EDGES_PATH = PROJECT_ROOT / "data/connectome/derived/malecns_v1.0/edges.parquet"
PROBE_OUTPUT_ROOT = PROJECT_ROOT / ".scratch/1999-connectome-demo/probes/m1-2"

_EDGE_SCHEMA = pa.schema(
    [
        ("source_id", pa.int64()),
        ("target_id", pa.int64()),
        ("weight", pa.int64()),
    ]
)
_NODE_SCHEMA = pa.schema([("node_id", pa.int64())])
_HASH_SALT = b"FlyCallM12-v1"
_HASH_ALGORITHM = "BLAKE2b-128"
_GIB = 1024**3
_MIN_FREE_BYTES = 4 * _GIB
_MAX_OUTPUT_BYTES = 1 * _GIB
_MAX_RSS_BYTES = 2 * _GIB
_MAX_NODE_LIMIT = 500
_MAX_SCANS = 501
_MAX_WALL_SECONDS = 60 * 60
_BATCH_ROWS = 65_536
_DISK_CHECK_INTERVAL_SECONDS = 0.25


class StreamingBfsError(ValueError):
    """Raised for an invalid or unsafe streaming BFS request."""


class StreamingBfsResourceError(RuntimeError):
    """Raised when initial resources fail the hard safety preflight."""


def _hash_priority(node_id: int) -> tuple[bytes, int]:
    if node_id < -(2**63) or node_id > (2**63 - 1):
        raise StreamingBfsError("node_id must fit signed int64")
    digest = hashlib.blake2b(
        node_id.to_bytes(8, "little", signed=True),
        digest_size=16,
        salt=_HASH_SALT,
    ).digest()
    return digest, node_id


def _hash_priority_metadata() -> dict[str, str]:
    return {
        "algorithm": _HASH_ALGORITHM,
        "digest_bits": "128",
        "salt_ascii": _HASH_SALT.decode("ascii"),
        "salt_hex": _HASH_SALT.hex(),
        "node_id_encoding": "signed int64, 8 bytes, little-endian",
        "rank_order": "digest bytes ascending; node_id ascending only on digest collision",
    }


def select_hash_priority_seed(
    nodes_path: str | Path,
    *,
    min_free_bytes: int = _MIN_FREE_BYTES,
    rss_limit_bytes: int = _MAX_RSS_BYTES,
) -> dict[str, Any]:
    """Select the minimum hash-priority ID by streaming a complete node Parquet.

    This helper never materializes the full node table. It is a proposed M1.2
    policy seam; calling it on official data still requires separate approval.
    """
    path = Path(nodes_path)
    if not path.is_file():
        raise StreamingBfsError(f"nodes_path does not exist: {path}")
    if isinstance(min_free_bytes, bool) or not isinstance(min_free_bytes, int) or min_free_bytes < _MIN_FREE_BYTES:
        raise StreamingBfsError("min_free_bytes cannot be lower than the 4 GiB safety floor")
    if isinstance(rss_limit_bytes, bool) or not isinstance(rss_limit_bytes, int) or not 1 <= rss_limit_bytes <= _MAX_RSS_BYTES:
        raise StreamingBfsError("rss_limit_bytes must be between 1 byte and the 2 GiB limit")
    parquet = pq.ParquetFile(path)
    if not parquet.schema_arrow.equals(_NODE_SCHEMA, check_metadata=False):
        raise StreamingBfsError(f"nodes schema must be exactly node_id:int64; observed {parquet.schema_arrow}")

    started = time.monotonic()
    free_at_start = shutil.disk_usage(path.parent).free
    if free_at_start < min_free_bytes:
        raise StreamingBfsResourceError(
            f"only {free_at_start} free bytes at nodes volume; minimum is {min_free_bytes}"
        )
    lowest_free = free_at_start
    peak_rss_bytes = _current_peak_rss_bytes()

    def guard() -> None:
        nonlocal lowest_free, peak_rss_bytes
        peak_rss_bytes = max(peak_rss_bytes, _current_peak_rss_bytes())
        if peak_rss_bytes > rss_limit_bytes:
            raise StreamingBfsResourceError(
                f"peak RSS {peak_rss_bytes} exceeds the limit {rss_limit_bytes}"
            )
        free = shutil.disk_usage(path.parent).free
        lowest_free = min(lowest_free, free)
        if free < min_free_bytes:
            raise StreamingBfsResourceError(
                f"only {free} free bytes at nodes volume; minimum is {min_free_bytes}"
            )

    best_rank: tuple[bytes, int] | None = None
    rows_scanned = 0
    for batch in parquet.iter_batches(batch_size=_BATCH_ROWS, columns=["node_id"]):
        guard()
        values = batch.column(0)
        if values.null_count:
            raise StreamingBfsError("nodes table contains null node_id values")
        for value in values.to_pylist():
            node_id = int(value)
            rank = _hash_priority(node_id)
            if best_rank is None or rank < best_rank:
                best_rank = rank
            rows_scanned += 1
            if rows_scanned % 4096 == 0:
                guard()
    if best_rank is None:
        raise StreamingBfsError("nodes table contains no node IDs")
    guard()
    return {
        "seed_node_id": best_rank[1],
        "seed_priority_hex": best_rank[0].hex(),
        "candidate_count": rows_scanned,
        "selection_policy": "minimum fixed-salt hash priority over all streamed node rows",
        "hash_priority": _hash_priority_metadata(),
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "peak_rss_bytes": peak_rss_bytes,
        "rss_limit_bytes": rss_limit_bytes,
        "disk_free_bytes_at_start": free_at_start,
        "disk_free_bytes_min_observed": lowest_free,
        "disk_free_bytes_at_result": shutil.disk_usage(path.parent).free,
    }


def _integer(name: str, value: int, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise StreamingBfsError(f"{name} must be an integer")
    if value < minimum or value > maximum:
        raise StreamingBfsError(f"{name} must be between {minimum} and {maximum}")
    return value


def _current_peak_rss_bytes() -> int:
    return peak_rss_bytes()


def _physical_memory_bytes() -> int | None:
    if sys.platform != "darwin":
        return None
    try:
        value = subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True).strip()
        return int(value)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def _directory_size(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def _ordered_edge_digest_state() -> tuple[list[Any], int]:
    # The digest is stable across Arrow batch boundaries, but intentionally
    # preserves source row order; it is not a permutation-invariant set hash.
    return [hashlib.sha256() for _ in range(3)], 0


def _update_edge_digest(state: tuple[list[Any], int], table: pa.Table | pa.RecordBatch) -> tuple[list[Any], int]:
    hashes, row_count = state
    for index, column in enumerate(table.columns):
        if isinstance(column, pa.ChunkedArray):
            column = column.combine_chunks()
        if len(column) == 0:
            continue
        data = column.buffers()[1]
        start = column.offset * 8
        hashes[index].update(memoryview(data)[start : start + len(column) * 8])
    return hashes, row_count + table.num_rows


def _finish_edge_digest(state: tuple[list[Any], int]) -> str:
    hashes, row_count = state
    digest = hashlib.sha256()
    digest.update(row_count.to_bytes(8, "little", signed=False))
    for column_hash in hashes:
        digest.update(column_hash.digest())
    return digest.hexdigest()


class _HashPriorityCandidates:
    """Keep only the lowest hash-priority unseen IDs in a BFS layer."""

    def __init__(self, limit: int, visited: set[int]) -> None:
        self.limit = limit
        self.visited = visited
        self.heap: list[tuple[int, int]] = []
        self.members: set[int] = set()

    def offer(self, node_id: int) -> None:
        if self.limit == 0 or node_id in self.visited or node_id in self.members:
            return
        priority, _ = _hash_priority(node_id)
        priority_value = int.from_bytes(priority, "big", signed=False)
        heap_entry = (-priority_value, -node_id)
        if len(self.heap) < self.limit:
            heapq.heappush(self.heap, heap_entry)
            self.members.add(node_id)
            return
        worst_kept = (-self.heap[0][0], -self.heap[0][1])
        if (priority_value, node_id) < worst_kept:
            removed_entry = heapq.heapreplace(self.heap, heap_entry)
            removed = -removed_entry[1]
            self.members.remove(removed)
            self.members.add(node_id)

    def sorted_ids(self) -> list[int]:
        return sorted(self.members, key=_hash_priority)


def _validate_source(path: Path) -> tuple[pq.ParquetFile, int]:
    if not path.is_file():
        raise StreamingBfsError(f"edges_path does not exist: {path}")
    parquet = pq.ParquetFile(path)
    schema = parquet.schema_arrow
    if not schema.equals(_EDGE_SCHEMA, check_metadata=False):
        raise StreamingBfsError(
            "M1.1 edge schema must be exactly "
            "source_id:int64,target_id:int64,weight:int64; "
            f"observed {schema}"
        )
    return parquet, parquet.metadata.num_rows


def _validate_destination(source: Path, output_dir: Path) -> None:
    source_resolved = source.resolve()
    output_resolved = output_dir.resolve()
    if source_resolved == OFFICIAL_EDGES_PATH.resolve():
        try:
            output_resolved.relative_to(PROBE_OUTPUT_ROOT.resolve())
        except ValueError as exc:
            raise StreamingBfsError(
                "official M1.1 probes may write only under "
                f"{PROBE_OUTPUT_ROOT.resolve()}; refusing {output_resolved}"
            ) from exc
    if output_resolved.exists():
        raise StreamingBfsError(f"output_dir already exists; refusing overwrite: {output_resolved}")
    if output_resolved == source_resolved.parent or output_resolved in source_resolved.parents:
        raise StreamingBfsError("output_dir must not be the M1.1 source directory or one of its parents")


def _write_result(output_dir: Path, result: dict[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / "probe_result.json"
    temporary_path = output_dir / ".probe_result.json.tmp"
    temporary_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary_path.replace(result_path)


def probe_streaming_bfs(
    edges_path: str | Path,
    seed_node_id: int,
    node_limit: int,
    output_dir: str | Path,
    *,
    max_scans: int = _MAX_SCANS,
    wall_clock_seconds: int = _MAX_WALL_SECONDS,
    min_free_bytes: int = _MIN_FREE_BYTES,
    expected_edge_rows: int | None = None,
) -> dict[str, Any]:
    """Run a bounded exact weak-view BFS using one full edge scan per layer.

    If a BFS layer exceeds the remaining node slots, retain the candidates with
    the lowest fixed-salt hash priorities. The API is for feasibility evidence
    only; the hash policy and node cap are not frozen research decisions.
    """
    edge_path = Path(edges_path)
    destination = Path(output_dir)
    if isinstance(seed_node_id, bool) or not isinstance(seed_node_id, int):
        raise StreamingBfsError("seed_node_id must be an integer")
    node_limit = _integer("node_limit", node_limit, 1, _MAX_NODE_LIMIT)
    max_scans = _integer("max_scans", max_scans, 1, _MAX_SCANS)
    wall_clock_seconds = _integer("wall_clock_seconds", wall_clock_seconds, 1, _MAX_WALL_SECONDS)
    if isinstance(min_free_bytes, bool) or not isinstance(min_free_bytes, int) or min_free_bytes < _MIN_FREE_BYTES:
        raise StreamingBfsError("min_free_bytes cannot be lower than the 4 GiB safety floor")
    if expected_edge_rows is not None:
        expected_edge_rows = _integer("expected_edge_rows", expected_edge_rows, 0, 2**63 - 1)

    parquet, metadata_rows = _validate_source(edge_path)
    expected_rows = metadata_rows if expected_edge_rows is None else expected_edge_rows
    if expected_rows != metadata_rows:
        raise StreamingBfsError(
            f"expected_edge_rows={expected_rows} does not match Parquet metadata rows={metadata_rows}"
        )
    _validate_destination(edge_path, destination)
    parent = destination.parent
    parent.mkdir(parents=True, exist_ok=True)
    free_at_start = shutil.disk_usage(parent).free
    if free_at_start < min_free_bytes:
        raise StreamingBfsResourceError(
            f"only {free_at_start} free bytes at output volume; minimum is {min_free_bytes}"
        )

    destination.mkdir()
    started = time.monotonic()
    deadline = started + wall_clock_seconds
    last_disk_check = started
    lowest_free = free_at_start
    scans_completed = 0
    scans_attempted = 0
    rows_scanned_total = 0
    incomplete_scan_rows = 0
    scan_records: list[dict[str, Any]] = []
    layers: list[dict[str, Any]] = []
    selected: set[int] = {seed_node_id}
    frontier: list[int] = [seed_node_id]
    seed_found = False
    status = "incomplete"
    completion_reason = "budget_exhausted"
    stop_reason: str | None = None
    node_limit_reached = False
    depth_reached = 0
    max_rss_bytes = _current_peak_rss_bytes()

    def guard(force_disk_check: bool = False) -> str | None:
        nonlocal last_disk_check, lowest_free, max_rss_bytes
        now = time.monotonic()
        if now >= deadline:
            return "wall_clock_limit"
        max_rss_bytes = max(max_rss_bytes, _current_peak_rss_bytes())
        if max_rss_bytes > _MAX_RSS_BYTES:
            return "rss_limit"
        if force_disk_check or now - last_disk_check >= _DISK_CHECK_INTERVAL_SECONDS:
            free = shutil.disk_usage(destination).free
            last_disk_check = now
            lowest_free = min(lowest_free, free)
            if free < min_free_bytes:
                return "disk_floor"
        return None

    def scan_layer(layer_frontier: list[int], remaining: int) -> tuple[bool, list[int], int, str | None]:
        nonlocal scans_completed, scans_attempted, rows_scanned_total, incomplete_scan_rows
        nonlocal seed_found
        issue = guard(force_disk_check=True)
        if issue:
            return False, [], 0, issue
        scans_attempted += 1
        layer_candidates = _HashPriorityCandidates(remaining, selected)
        frontier_values = pa.array(sorted(layer_frontier), type=pa.int64())
        rows_this_scan = 0
        matched_any = False
        try:
            for batch in parquet.iter_batches(batch_size=_BATCH_ROWS, columns=_EDGE_SCHEMA.names):
                rows_this_scan += batch.num_rows
                rows_scanned_total += batch.num_rows
                issue = guard()
                if issue:
                    incomplete_scan_rows += rows_this_scan
                    return False, [], rows_this_scan, issue
                if any(batch.column(index).null_count for index in range(3)):
                    return False, [], rows_this_scan, "source_null_values"
                source_mask = pc.is_in(batch.column(0), value_set=frontier_values)
                target_mask = pc.is_in(batch.column(1), value_set=frontier_values)
                if pc.any(source_mask).as_py() or pc.any(target_mask).as_py():
                    matched_any = True
                batch_candidate_ids = set(pc.filter(batch.column(1), source_mask).to_pylist())
                batch_candidate_ids.update(pc.filter(batch.column(0), target_mask).to_pylist())
                for candidate_id in batch_candidate_ids:
                    layer_candidates.offer(int(candidate_id))
            issue = guard(force_disk_check=True)
            if issue:
                incomplete_scan_rows += rows_this_scan
                return False, [], rows_this_scan, issue
            if rows_this_scan != expected_rows:
                return False, [], rows_this_scan, "source_row_count_mismatch"
        except (pa.ArrowException, OSError) as exc:
            return False, [], rows_this_scan, f"source_scan_error: {exc}"
        scans_completed += 1
        seed_found = seed_found or matched_any
        return True, layer_candidates.sorted_ids(), rows_this_scan, None

    while frontier:
        # Keep two complete passes available for induced-edge extraction and
        # an independent source-table verification.
        if scans_completed + 3 > max_scans:
            stop_reason = "scan_budget_exhausted"
            break
        remaining = node_limit - len(selected)
        complete, new_nodes, rows_this_scan, issue = scan_layer(frontier, remaining)
        scan_records.append(
            {
                "kind": "bfs_layer",
                "frontier_count": len(frontier),
                "rows": rows_this_scan,
                "complete": complete,
                "depth": depth_reached,
            }
        )
        layers.append(
            {
                "depth": depth_reached,
                "frontier_count": len(frontier),
                "new_node_count": len(new_nodes),
                "selected_count_before": len(selected),
            }
        )
        if not complete:
            stop_reason = issue or "incomplete_scan"
            break
        if not seed_found:
            selected.clear()
            status = "seed_not_found"
            completion_reason = "complete_source_scan"
            frontier = []
            break
        if len(selected) >= node_limit:
            node_limit_reached = True
            status = "complete"
            completion_reason = "node_limit_reached"
            frontier = []
            break
        if not new_nodes:
            status = "complete"
            completion_reason = "component_exhausted"
            frontier = []
            break
        selected.update(new_nodes)
        if len(selected) >= node_limit:
            node_limit_reached = True
            status = "complete"
            completion_reason = "node_limit_reached"
            frontier = []
            depth_reached += 1
            break
        frontier = new_nodes
        depth_reached += 1

    if stop_reason is not None:
        status = "incomplete"
        completion_reason = stop_reason

    # A missing seed produces an empty candidate set; a present seed starts the
    # selected set only after its first full scan confirms it exists.
    if status != "incomplete" and seed_found and not selected:
        selected.add(seed_node_id)

    if status == "incomplete":
        result = _base_result(
            edge_path, destination, seed_node_id, node_limit, expected_rows,
            status, completion_reason, selected, node_limit_reached, depth_reached,
            scans_attempted, scans_completed, rows_scanned_total, incomplete_scan_rows,
            scan_records, layers, started, free_at_start, lowest_free, max_rss_bytes,
        )
        result.update({"seed_found": seed_found, "induced_edge_count": None, "independent_validation": "not_run"})
        _write_result(destination, result)
        return result

    if scans_completed + 2 > max_scans:
        result = _base_result(
            edge_path, destination, seed_node_id, node_limit, expected_rows,
            "incomplete", "scan_budget_exhausted_before_induced_validation", selected,
            node_limit_reached, depth_reached, scans_attempted, scans_completed,
            rows_scanned_total, incomplete_scan_rows, scan_records, layers, started,
            free_at_start, lowest_free, max_rss_bytes,
        )
        result.update({"seed_found": seed_found, "induced_edge_count": None, "independent_validation": "not_run"})
        _write_result(destination, result)
        return result

    selected_ids = sorted(selected)
    selected_values = pa.array(selected_ids, type=pa.int64())
    nodes_path = destination / "candidate_nodes.parquet"
    pq.write_table(pa.table({"node_id": pa.array(selected_ids, type=pa.int64())}), nodes_path)
    output_reason = _output_guard(destination, min_free_bytes)
    if output_reason:
        status, completion_reason = "incomplete", output_reason
        return _persist_final_result(
            edge_path, destination, seed_node_id, node_limit, expected_rows, status,
            completion_reason, selected, node_limit_reached, depth_reached,
            scans_attempted, scans_completed, rows_scanned_total, incomplete_scan_rows,
            scan_records, layers, started, free_at_start, lowest_free, max_rss_bytes,
            seed_found, None, "not_run", None,
        )

    candidate_edges_path = destination / "candidate_edges.parquet"
    edge_writer = pq.ParquetWriter(candidate_edges_path, _EDGE_SCHEMA, compression="zstd")
    extraction_digest = _ordered_edge_digest_state()
    induced_edge_count = 0
    extraction_rows = 0
    extraction_complete = False
    extraction_issue: str | None = None
    scans_attempted += 1
    try:
        for batch in parquet.iter_batches(batch_size=_BATCH_ROWS, columns=_EDGE_SCHEMA.names):
            extraction_rows += batch.num_rows
            rows_scanned_total += batch.num_rows
            extraction_issue = guard()
            if extraction_issue:
                incomplete_scan_rows += extraction_rows
                break
            source_member = pc.is_in(batch.column(0), value_set=selected_values)
            target_member = pc.is_in(batch.column(1), value_set=selected_values)
            induced_mask = pc.and_(source_member, target_member)
            selected_batch = batch.filter(induced_mask)
            if selected_batch.num_rows:
                edge_writer.write_batch(selected_batch, row_group_size=selected_batch.num_rows)
                extraction_digest = _update_edge_digest(extraction_digest, selected_batch)
                induced_edge_count += selected_batch.num_rows
                extraction_issue = _output_guard(destination, min_free_bytes)
                if extraction_issue:
                    break
        if extraction_issue is None:
            extraction_issue = guard(force_disk_check=True)
            if extraction_issue is None and extraction_rows == expected_rows:
                extraction_complete = True
            elif extraction_issue is None:
                extraction_issue = "source_row_count_mismatch"
    except (pa.ArrowException, OSError) as exc:
        extraction_issue = f"induced_edge_scan_error: {exc}"
    finally:
        edge_writer.close()
    if extraction_complete:
        scans_completed += 1
    scan_records.append({"kind": "induced_edge_extraction", "rows": extraction_rows, "complete": extraction_complete})
    extraction_hash = _finish_edge_digest(extraction_digest)
    if not extraction_complete:
        status, completion_reason = "incomplete", extraction_issue or "induced_edge_scan_incomplete"
        return _persist_final_result(
            edge_path, destination, seed_node_id, node_limit, expected_rows, status,
            completion_reason, selected, node_limit_reached, depth_reached,
            scans_attempted, scans_completed, rows_scanned_total, incomplete_scan_rows,
            scan_records, layers, started, free_at_start, lowest_free, max_rss_bytes,
            seed_found, induced_edge_count, "not_run", extraction_hash,
        )

    # Independent source pass plus reading the emitted Parquet validates both
    # completeness and serialized candidate content without a full graph index.
    if scans_completed + 1 > max_scans:
        status, completion_reason = "incomplete", "scan_budget_exhausted_before_independent_validation"
        return _persist_final_result(
            edge_path, destination, seed_node_id, node_limit, expected_rows, status,
            completion_reason, selected, node_limit_reached, depth_reached,
            scans_attempted, scans_completed, rows_scanned_total, incomplete_scan_rows,
            scan_records, layers, started, free_at_start, lowest_free, max_rss_bytes,
            seed_found, induced_edge_count, "not_run", extraction_hash,
        )

    verify_digest = _ordered_edge_digest_state()
    verify_count = 0
    verify_rows = 0
    validation_issue: str | None = None
    scans_attempted += 1
    try:
        for batch in parquet.iter_batches(batch_size=_BATCH_ROWS, columns=_EDGE_SCHEMA.names):
            verify_rows += batch.num_rows
            rows_scanned_total += batch.num_rows
            validation_issue = guard()
            if validation_issue:
                incomplete_scan_rows += verify_rows
                break
            mask = pc.and_(
                pc.is_in(batch.column(0), value_set=selected_values),
                pc.is_in(batch.column(1), value_set=selected_values),
            )
            induced_batch = batch.filter(mask)
            if induced_batch.num_rows:
                verify_digest = _update_edge_digest(verify_digest, induced_batch)
                verify_count += induced_batch.num_rows
        if validation_issue is None:
            validation_issue = guard(force_disk_check=True)
            if validation_issue is None and verify_rows != expected_rows:
                validation_issue = "source_row_count_mismatch"
    except (pa.ArrowException, OSError) as exc:
        validation_issue = f"independent_validation_scan_error: {exc}"
    if validation_issue is None:
        scans_completed += 1
    scan_records.append({"kind": "independent_source_validation", "rows": verify_rows, "complete": validation_issue is None})

    candidate_parquet = pq.ParquetFile(candidate_edges_path)
    candidate_schema_valid = candidate_parquet.schema_arrow.equals(_EDGE_SCHEMA, check_metadata=False)
    candidate_digest = _ordered_edge_digest_state()
    candidate_count = 0
    for candidate_batch in candidate_parquet.iter_batches(batch_size=_BATCH_ROWS, columns=_EDGE_SCHEMA.names):
        candidate_digest = _update_edge_digest(candidate_digest, candidate_batch)
        candidate_count += candidate_batch.num_rows
    output_digest = _finish_edge_digest(candidate_digest)
    output_valid = (
        candidate_schema_valid
        and candidate_count == induced_edge_count == verify_count
        and output_digest == extraction_hash == _finish_edge_digest(verify_digest)
    )
    nodes_table = pq.read_table(nodes_path)
    nodes_valid = nodes_table.schema.equals(pa.schema([("node_id", pa.int64())]), check_metadata=False) and nodes_table.column("node_id").to_pylist() == selected_ids
    independent_validation = "pass" if validation_issue is None and output_valid and nodes_valid else "fail"
    if validation_issue is not None:
        status, completion_reason = "incomplete", validation_issue
    elif not output_valid or not nodes_valid:
        status, completion_reason = "incomplete", "candidate_validation_mismatch"
    else:
        status = "seed_not_found" if not seed_found else "complete"
        completion_reason = "seed_not_found" if not seed_found else completion_reason

    return _persist_final_result(
        edge_path, destination, seed_node_id, node_limit, expected_rows, status,
        completion_reason, selected, node_limit_reached, depth_reached,
        scans_attempted, scans_completed, rows_scanned_total, incomplete_scan_rows,
        scan_records, layers, started, free_at_start, lowest_free, max_rss_bytes,
        seed_found, induced_edge_count, independent_validation, extraction_hash,
        output_valid=output_valid, nodes_valid=nodes_valid,
    )


def _output_guard(destination: Path, min_free_bytes: int) -> str | None:
    if shutil.disk_usage(destination).free < min_free_bytes:
        return "disk_floor"
    if _directory_size(destination) > _MAX_OUTPUT_BYTES:
        return "output_cap_exceeded"
    return None


def _base_result(
    edge_path: Path,
    destination: Path,
    seed_node_id: int,
    node_limit: int,
    expected_rows: int,
    status: str,
    completion_reason: str,
    selected: set[int],
    node_limit_reached: bool,
    depth_reached: int,
    scans_attempted: int,
    scans_completed: int,
    rows_scanned_total: int,
    incomplete_scan_rows: int,
    scan_records: list[dict[str, Any]],
    layers: list[dict[str, Any]],
    started: float,
    free_at_start: int,
    lowest_free: int,
    max_rss_bytes: int,
) -> dict[str, Any]:
    return {
        "artifact_type": "m1.2_streaming_bfs_feasibility_probe",
        "is_formal_subgraph": False,
        "status": status,
        "completion_reason": completion_reason,
        "seed_node_id": seed_node_id,
        "seed_policy": "diagnostic fixed seed only; not representative or official",
        "node_limit": node_limit,
        "selected_node_ids": sorted(selected),
        "selected_node_count": len(selected),
        "node_limit_reached": node_limit_reached,
        "bfs_depth_reached": depth_reached,
        "bfs_layer_scan_count": sum(1 for scan in scan_records if scan["kind"] == "bfs_layer" and scan["complete"]),
        "scans_attempted": scans_attempted,
        "scans_completed": scans_completed,
        "max_scans": _MAX_SCANS,
        "expected_rows_per_full_scan": expected_rows,
        "rows_scanned_total": rows_scanned_total,
        "incomplete_scan_rows": incomplete_scan_rows,
        "scan_records": scan_records,
        "bfs_layers": layers,
        "scan_strategy": "complete sequential PyArrow Parquet scan per BFS layer; no adjacency or degree index",
        "selection_policy": "fixed_salt_hash_priority",
        "hash_priority": _hash_priority_metadata(),
        "neighbor_order": "within each layer, retain lowest fixed-salt hash-priority unseen IDs if node cap would be exceeded; node_id ascending breaks digest collisions only",
        "weak_adjacency": True,
        "induced_edge_direction": "original source_id -> target_id and weight retained",
        "source_path": str(edge_path.resolve()),
        "output_dir": str(destination.resolve()),
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "physical_ram_bytes_observed_by_probe": _physical_memory_bytes(),
        "duckdb_used": False,
        "duckdb_spill_bytes": 0,
        "temporary_index_bytes": 0,
        "output_cap_bytes": _MAX_OUTPUT_BYTES,
        "disk_free_bytes_at_start": free_at_start,
        "disk_free_bytes_min_observed": lowest_free,
        "disk_free_bytes_at_result": shutil.disk_usage(destination).free,
        "peak_rss_bytes": max(max_rss_bytes, _current_peak_rss_bytes()),
        "rss_limit_bytes": _MAX_RSS_BYTES,
    }


def _persist_final_result(
    edge_path: Path,
    destination: Path,
    seed_node_id: int,
    node_limit: int,
    expected_rows: int,
    status: str,
    completion_reason: str,
    selected: set[int],
    node_limit_reached: bool,
    depth_reached: int,
    scans_attempted: int,
    scans_completed: int,
    rows_scanned_total: int,
    incomplete_scan_rows: int,
    scan_records: list[dict[str, Any]],
    layers: list[dict[str, Any]],
    started: float,
    free_at_start: int,
    lowest_free: int,
    max_rss_bytes: int,
    seed_found: bool,
    induced_edge_count: int | None,
    independent_validation: str,
    induced_edges_sha256: str | None,
    *,
    output_valid: bool | None = None,
    nodes_valid: bool | None = None,
) -> dict[str, Any]:
    result = _base_result(
        edge_path, destination, seed_node_id, node_limit, expected_rows, status,
        completion_reason, selected, node_limit_reached, depth_reached,
        scans_attempted, scans_completed, rows_scanned_total, incomplete_scan_rows,
        scan_records, layers, started, free_at_start, lowest_free, max_rss_bytes,
    )
    result.update(
        {
            "seed_found": seed_found,
            "induced_edge_count": induced_edge_count,
            "induced_edges_sha256": induced_edges_sha256,
            "independent_validation": independent_validation,
            "candidate_edges_file_bytes": (destination / "candidate_edges.parquet").stat().st_size if (destination / "candidate_edges.parquet").exists() else 0,
            "candidate_nodes_file_bytes": (destination / "candidate_nodes.parquet").stat().st_size if (destination / "candidate_nodes.parquet").exists() else 0,
            "scratch_directory_bytes": _directory_size(destination),
        }
    )
    if output_valid is not None:
        result["candidate_edges_valid"] = output_valid
    if nodes_valid is not None:
        result["candidate_nodes_valid"] = nodes_valid
    _write_result(destination, result)
    return result

"""Bounded, non-formal feasibility probe for deterministic graph subsetting.

This module intentionally does not publish a production subgraph. Each probe
reads at most ``max_scan_edges`` rows once from the start of the M1.1 Parquet
edge table, builds a sparse undirected adjacency view in memory, and computes
the directed induced edges over the selected nodes from that same bounded
prefix. Hitting the row budget always produces an ``incomplete`` result.
"""

from __future__ import annotations

import hashlib
import json
import random
from collections import deque
from pathlib import Path
from typing import Any

import duckdb
import pyarrow as pa


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OFFICIAL_EDGES_PATH = (
    PROJECT_ROOT / "data/connectome/derived/malecns_v1.0/edges.parquet"
)
PROBE_OUTPUT_ROOT = PROJECT_ROOT / ".scratch/1999-connectome-demo/probes/m1-2"

_EDGE_SCHEMA = pa.schema(
    [
        ("source_id", pa.int64()),
        ("target_id", pa.int64()),
        ("weight", pa.int64()),
    ]
)
_MAX_NODE_LIMIT = 500
_MAX_SCAN_EDGES = 100_000
_DUCKDB_MEMORY_LIMIT = "2GB"
_DUCKDB_THREADS = 2
_CANDIDATE_RNG_SEED = 20261013
_FETCH_BATCH_ROWS = 8_192


class SubgraphProbeError(ValueError):
    """Raised when a bounded M1.2 probe request is invalid."""


def _validate_integer(name: str, value: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SubgraphProbeError(f"{name} must be an integer")
    if value < 1 or value > maximum:
        raise SubgraphProbeError(f"{name} must be between 1 and {maximum}")
    return value


def _ensure_probe_destination(edges_path: Path, output_dir: Path) -> None:
    source = edges_path.resolve()
    destination = output_dir.resolve()
    if source == OFFICIAL_EDGES_PATH.resolve():
        allowed_root = PROBE_OUTPUT_ROOT.resolve()
        try:
            destination.relative_to(allowed_root)
        except ValueError as exc:
            raise SubgraphProbeError(
                "official M1.1 probes may write only under "
                f"{allowed_root}; refusing {destination}"
            ) from exc
    if destination.exists():
        raise SubgraphProbeError(
            f"output_dir already exists; refusing to overwrite: {destination}"
        )
    if destination == source.parent or destination in source.parents:
        raise SubgraphProbeError(
            "output_dir must not be the M1.1 source directory or one of its parents"
        )


def _candidate_seed_strategies(
    adjacency: dict[int, set[int]],
) -> dict[str, dict[str, int]]:
    node_ids = sorted(adjacency)
    if not node_ids:
        return {}

    rng = random.Random(_CANDIDATE_RNG_SEED)
    uniform_id = node_ids[rng.randrange(len(node_ids))]
    by_degree = sorted(node_ids, key=lambda node_id: (len(adjacency[node_id]), node_id))
    median_degree_id = by_degree[(len(by_degree) - 1) // 2]
    highest_degree_id = min(
        node_ids, key=lambda node_id: (-len(adjacency[node_id]), node_id)
    )

    def candidate(node_id: int) -> dict[str, int]:
        return {
            "seed_node_id": node_id,
            "weak_degree_in_bounded_prefix": len(adjacency[node_id]),
        }

    return {
        "uniform_seeded_from_observed_nodes": {
            **candidate(uniform_id),
            "selection_rng_seed": _CANDIDATE_RNG_SEED,
        },
        "median_weak_degree_in_bounded_prefix": candidate(median_degree_id),
        "highest_weak_degree_in_bounded_prefix": candidate(highest_degree_id),
    }


def _edge_digest(edges: list[dict[str, int]]) -> str:
    payload = json.dumps(
        edges, ensure_ascii=False, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def probe_induced_subgraph(
    edges_path: str | Path,
    seed_node_id: int,
    node_limit: int,
    max_scan_edges: int,
    output_dir: str | Path,
) -> dict[str, Any]:
    """Run one bounded BFS feasibility probe and write a non-formal summary.

    The scan is a single ordered ``LIMIT`` query over the Parquet edge table;
    rows are never reread per BFS layer. The undirected adjacency is used only
    to select nodes. Returned ``induced_edges`` preserve the original
    ``source_id -> target_id`` direction and weight for rows within the scanned
    prefix whose two endpoints were selected.
    """

    edge_path = Path(edges_path)
    destination = Path(output_dir)
    if isinstance(seed_node_id, bool) or not isinstance(seed_node_id, int):
        raise SubgraphProbeError("seed_node_id must be an integer")
    node_limit = _validate_integer("node_limit", node_limit, _MAX_NODE_LIMIT)
    max_scan_edges = _validate_integer(
        "max_scan_edges", max_scan_edges, _MAX_SCAN_EDGES
    )
    _ensure_probe_destination(edge_path, destination)
    if not edge_path.is_file():
        raise SubgraphProbeError(f"edges_path does not exist: {edge_path}")

    adjacency: dict[int, set[int]] = {}
    scanned_edges: list[tuple[int, int, int]] = []
    connection = duckdb.connect(database=":memory:")
    try:
        connection.execute(f"SET memory_limit='{_DUCKDB_MEMORY_LIMIT}'")
        connection.execute(f"SET threads={_DUCKDB_THREADS}")
        connection.execute("SET preserve_insertion_order=true")
        reader = connection.execute(
            "SELECT source_id, target_id, weight "
            "FROM read_parquet(?) LIMIT ?",
            [str(edge_path), max_scan_edges],
        ).to_arrow_reader(batch_size=_FETCH_BATCH_ROWS)
        for batch in reader:
            if batch.schema != _EDGE_SCHEMA:
                raise SubgraphProbeError(
                    "M1.1 edge schema must be exactly "
                    "source_id:int64,target_id:int64,weight:int64; "
                    f"observed {batch.schema}"
                )
            if any(batch.column(index).null_count for index in range(3)):
                raise SubgraphProbeError("M1.1 edge rows must not contain nulls")
            sources = batch.column(0).to_pylist()
            targets = batch.column(1).to_pylist()
            weights = batch.column(2).to_pylist()
            for source_id, target_id, weight in zip(sources, targets, weights):
                source_id, target_id, weight = (
                    int(source_id), int(target_id), int(weight)
                )
                scanned_edges.append((source_id, target_id, weight))
                adjacency.setdefault(source_id, set()).add(target_id)
                adjacency.setdefault(target_id, set()).add(source_id)
    except (duckdb.Error, pa.ArrowException) as exc:
        raise SubgraphProbeError(f"could not scan M1.1 edge Parquet: {exc}") from exc
    finally:
        connection.close()

    edges_scanned = len(scanned_edges)
    scan_complete = edges_scanned < max_scan_edges
    seed_found = seed_node_id in adjacency
    selected: set[int] = set()
    node_limit_reached = False

    if seed_found:
        selected.add(seed_node_id)
        queue: deque[int] = deque([seed_node_id])
        if len(selected) >= node_limit:
            node_limit_reached = True
        while queue and len(selected) < node_limit:
            current = queue.popleft()
            for neighbor in sorted(adjacency[current]):
                if neighbor in selected:
                    continue
                selected.add(neighbor)
                queue.append(neighbor)
                if len(selected) >= node_limit:
                    node_limit_reached = True
                    break

    selected_ids = sorted(selected)
    selected_set = set(selected_ids)
    induced_edges = [
        {"source_id": source_id, "target_id": target_id, "weight": weight}
        for source_id, target_id, weight in scanned_edges
        if source_id in selected_set and target_id in selected_set
    ]
    if not scan_complete:
        status = "incomplete"
        completeness_reason = "budget_exhausted"
    elif not seed_found:
        status = "seed_not_found"
        completeness_reason = "scan_complete"
    elif node_limit_reached:
        status = "node_limit_reached"
        completeness_reason = "scan_complete"
    else:
        status = "complete"
        completeness_reason = "scan_complete"

    result: dict[str, Any] = {
        "artifact_type": "m1.2_bounded_feasibility_probe",
        "is_formal_subgraph": False,
        "status": status,
        "completeness_reason": completeness_reason,
        "scan_complete": scan_complete,
        "seed_found_in_scanned_rows": seed_found,
        "seed_node_id": seed_node_id,
        "node_limit": node_limit,
        "selected_node_ids": selected_ids,
        "selected_node_count": len(selected_ids),
        "node_limit_reached": node_limit_reached,
        "max_scan_edges": max_scan_edges,
        "edges_scanned": edges_scanned,
        "scan_strategy": "one ordered DuckDB Parquet scan with LIMIT; no per-layer rescans",
        "scan_scope": "BFS over the sparse graph formed by the scanned prefix only",
        "induced_edge_count": len(induced_edges),
        "induced_edges_sha256": _edge_digest(induced_edges),
        "candidate_seed_strategies": _candidate_seed_strategies(adjacency),
        "duckdb": {
            "version": duckdb.__version__,
            "memory_limit": _DUCKDB_MEMORY_LIMIT,
            "threads": _DUCKDB_THREADS,
        },
    }

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.mkdir()
    result_path = destination / "probe_result.json"
    temporary_result_path = destination / ".probe_result.json.tmp"
    temporary_result_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    temporary_result_path.replace(result_path)
    result["induced_edges"] = induced_edges
    result["result_path"] = str(result_path)
    return result

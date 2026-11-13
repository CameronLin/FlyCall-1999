"""Quota-limited BFS for the signed 300 excitatory + 200 inhibitory subgraph (ticket 21).

Rules (decided 2026-11-13, written before the official run):
- Start from one seed (D3b: minimum hash priority among signed neurons).
- Expand layer by layer over the undirected (weak) view of the directed graph,
  exactly like M1.2. Candidates of one layer are ranked by the M1.2
  hash priority (BLAKE2b-128, salt ``FlyCallM12-v1``).
- A candidate is admitted when its sign quota still has room; otherwise, and
  for unsigned / excluded / absent nodes, it is skipped. Every examined node is
  marked visited and is never reconsidered.
- Only admitted nodes are expanded, so the selection is weakly connected.
- Stop when both quotas are full; stop with a reason when the frontier empties
  or the preregistered depth limit is reached. Never relax quotas.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Mapping

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from .io_reachability import _priority as _io_priority
from .streaming_bfs import _hash_priority

EXCITATORY, INHIBITORY = 1, -1
DEFAULT_QUOTAS = {EXCITATORY: 300, INHIBITORY: 200}
DEFAULT_MAX_DEPTH = 12
READ_BATCH_ROWS = 1 << 20


class SignedSubgraphError(ValueError):
    """Raised when the quota BFS request or its inputs are invalid."""


@dataclass
class QuotaBfsResult:
    status: str
    seed: int
    selected: list[int]
    signs: dict[int, int]
    layers: list[dict[str, int]] = field(default_factory=list)
    stop_reason: str | None = None

    @property
    def counts(self) -> dict[str, int]:
        return {
            "excitatory": sum(1 for node in self.selected if self.signs[node] == EXCITATORY),
            "inhibitory": sum(1 for node in self.selected if self.signs[node] == INHIBITORY),
        }


def quota_bfs(
    seed: int,
    signs: Mapping[int, int],
    neighbors_of: Callable[[list[int]], set[int]],
    *,
    quotas: Mapping[int, int] = DEFAULT_QUOTAS,
    max_depth: int = DEFAULT_MAX_DEPTH,
) -> QuotaBfsResult:
    """Run the preregistered quota BFS; ``neighbors_of`` returns weak neighbors."""

    if set(quotas) != {EXCITATORY, INHIBITORY} or any(value < 1 for value in quotas.values()):
        raise SignedSubgraphError("quotas must give positive counts for +1 and -1.")
    if isinstance(max_depth, bool) or not isinstance(max_depth, int) or max_depth < 1:
        raise SignedSubgraphError("max_depth must be a positive integer.")
    seed_sign = signs.get(seed, 0)
    if seed_sign not in (EXCITATORY, INHIBITORY):
        return QuotaBfsResult("stopped", seed, [], {}, stop_reason="seed_has_no_sign")

    counts = {EXCITATORY: 1 if seed_sign == EXCITATORY else 0, INHIBITORY: 1 if seed_sign == INHIBITORY else 0}
    selected = [seed]
    chosen_signs = {seed: seed_sign}
    visited = {seed}
    frontier = [seed]
    layers: list[dict[str, int]] = []

    def full() -> bool:
        return all(counts[sign] >= quotas[sign] for sign in quotas)

    depth = 0
    while not full():
        if not frontier:
            return QuotaBfsResult("stopped", seed, selected, chosen_signs, layers, "frontier_exhausted")
        if depth >= max_depth:
            return QuotaBfsResult("stopped", seed, selected, chosen_signs, layers, "max_depth_reached")
        depth += 1
        candidates = sorted(neighbors_of(sorted(frontier)) - visited, key=_hash_priority)
        stats = {"depth": depth, "frontier": len(frontier), "candidates": len(candidates),
                 "admitted_excitatory": 0, "admitted_inhibitory": 0,
                 "skipped_unsigned": 0, "skipped_quota_full": 0}
        next_frontier: list[int] = []
        for node in candidates:
            if full():
                break
            visited.add(node)
            sign = signs.get(node, 0)
            if sign not in (EXCITATORY, INHIBITORY):
                stats["skipped_unsigned"] += 1
                continue
            if counts[sign] >= quotas[sign]:
                stats["skipped_quota_full"] += 1
                continue
            counts[sign] += 1
            selected.append(node)
            chosen_signs[node] = sign
            next_frontier.append(node)
            stats["admitted_excitatory" if sign == EXCITATORY else "admitted_inhibitory"] += 1
        layers.append(stats)
        frontier = next_frontier
    return QuotaBfsResult("completed", seed, selected, chosen_signs, layers, None)


def parquet_neighbor_scanner(edges_path: Path, counter: dict[str, int]) -> Callable[[list[int]], set[int]]:
    """Weak neighbors of a frontier by one full streaming scan of edges.parquet."""

    def neighbors_of(frontier: list[int]) -> set[int]:
        values = pa.array(frontier, type=pa.int64())
        found: set[int] = set()
        for batch in pq.ParquetFile(edges_path).iter_batches(batch_size=READ_BATCH_ROWS, columns=["source_id", "target_id"]):
            source, target = batch.column(0), batch.column(1)
            found.update(pc.filter(target, pc.is_in(source, value_set=values)).to_pylist())
            found.update(pc.filter(source, pc.is_in(target, value_set=values)).to_pylist())
        counter["scans"] = counter.get("scans", 0) + 1
        return found

    return neighbors_of


def induced_edges(edges_path: Path, nodes: Iterable[int]) -> list[tuple[int, int, int]]:
    """All original directed edges with both endpoints selected (one full scan)."""

    values = pa.array(sorted(set(nodes)), type=pa.int64())
    rows: list[tuple[int, int, int]] = []
    for batch in pq.ParquetFile(edges_path).iter_batches(batch_size=READ_BATCH_ROWS):
        mask = pc.and_(pc.is_in(batch.column(0), value_set=values), pc.is_in(batch.column(1), value_set=values))
        kept = batch.filter(mask)
        rows.extend(zip(kept.column(0).to_pylist(), kept.column(1).to_pylist(), kept.column(2).to_pylist()))
    return sorted(rows)


def select_reachable_outputs(
    node_ids: Iterable[int],
    edges: Iterable[tuple[int, int, int]],
    input_ids: Iterable[int],
    *,
    count: int,
    salt: str,
    max_steps: int,
) -> dict[str, object]:
    """Decision D5: outputs come only from nodes reachable within ``max_steps``.

    Inputs are chosen beforehand by the unchanged M1.3 rule. Candidates are
    non-input nodes whose shortest directed hop count from any input is
    1..max_steps; they are ranked by the M1.3 keyed hash priority (role
    ``output``, same salt) and the first ``count`` are taken. Reachability then
    holds by construction; this is a fixed rule, not a search over salts.
    """

    nodes = set(node_ids)
    inputs = set(input_ids)
    if not inputs or not inputs <= nodes:
        raise SignedSubgraphError("input_ids must be a non-empty subset of node_ids.")
    outgoing: dict[int, set[int]] = {node: set() for node in nodes}
    for source, target, _ in edges:
        if source not in nodes or target not in nodes:
            raise SignedSubgraphError("edge endpoints must belong to node_ids.")
        outgoing[source].add(target)
    distance = {node: 0 for node in inputs}
    frontier = sorted(inputs)
    for step in range(1, max_steps + 1):
        next_frontier = []
        for node in frontier:
            for target in sorted(outgoing[node]):
                if target not in distance:
                    distance[target] = step
                    next_frontier.append(target)
        frontier = next_frontier
    candidates = sorted(node for node, hops in distance.items() if node not in inputs and 1 <= hops <= max_steps)
    if len(candidates) < count:
        raise SignedSubgraphError(
            f"only {len(candidates)} non-input nodes are reachable within {max_steps} steps; need {count}."
        )
    ranked = sorted(candidates, key=lambda node: (_io_priority(node, "output", salt), node))
    return {
        "rule": "D5: outputs ranked by M1.3 keyed hash priority among non-input nodes reachable within max_steps",
        "max_steps": max_steps,
        "eligible_output_candidates": len(candidates),
        "output_node_ids": sorted(ranked[:count]),
    }

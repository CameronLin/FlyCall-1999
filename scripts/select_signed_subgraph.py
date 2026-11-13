#!/usr/bin/env python3
"""Ticket 21 (M1.4): select the signed 300 + 200 subgraph and check I/O reachability.

Preregistered constants live below and must not be changed after a run.
Outputs (small, committed): G1/G2/G2-glu+ graph definitions and a manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections import Counter, deque
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

import pyarrow.parquet as pq  # noqa: E402

from flycall_data.io_reachability import check_io_reachability, select_io_nodes  # noqa: E402
from flycall_data.signed_subgraph import (  # noqa: E402
    DEFAULT_MAX_DEPTH,
    DEFAULT_QUOTAS,
    induced_edges,
    parquet_neighbor_scanner,
    quota_bfs,
    select_reachable_outputs,
)
from flycall_data.streaming_bfs import _hash_priority, _hash_priority_metadata  # noqa: E402

SEED = 810979  # D3b: minimum M1.2 hash priority among signed neurons
EDGES = "data/connectome/derived/malecns_v1.0/edges.parquet"
EDGES_SHA256 = "d32d5be692b127e8b9132e418bbfc4a13fbc36e2f5fabc90293a1f04d5f133aa"  # M1.1 import manifest
SIGNS = "data/connectome/derived/malecns_v1.0/neuron_signs_v1.0.parquet"
SIGN_SUMMARY = "data/connectome/derived/malecns_v1.0/neuron_signs_v1.0_summary.json"
OUTPUT_DIR = "data/connectome/derived/malecns_v1.0/subgraphs/signed-quota-v1.0"
IO_SALT = "FlyCallM13-IO-v1"  # same rule and salt as M1.3
IO_COUNT = 32
MODEL_STEPS = 2
REPORTED_STEPS = (2, 4)  # T=2 is required; T=4 is reported for comparison with M1.3


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical(value: object) -> str:
    return hashlib.sha256(json.dumps(value, separators=(",", ":"), sort_keys=True).encode("utf-8")).hexdigest()


def _weakly_connected(nodes: list[int], edges: list[tuple[int, int, int]]) -> int:
    adjacency: dict[int, set[int]] = {node: set() for node in nodes}
    for source, target, _ in edges:
        adjacency[source].add(target)
        adjacency[target].add(source)
    seen: set[int] = set()
    components = 0
    for start in nodes:
        if start in seen:
            continue
        components += 1
        queue = deque([start])
        seen.add(start)
        while queue:
            for neighbor in adjacency[queue.popleft()]:
                if neighbor not in seen:
                    seen.add(neighbor)
                    queue.append(neighbor)
    return components


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=OUTPUT_DIR)
    args = parser.parse_args()
    started = time.perf_counter()
    edges_path = PROJECT_ROOT / EDGES
    if _sha256(edges_path) != EDGES_SHA256:
        raise SystemExit("edges.parquet differs from the M1.1 import manifest; rebuild it first.")
    sign_table = pq.read_table(PROJECT_ROOT / SIGNS)
    sign_summary = json.loads((PROJECT_ROOT / SIGN_SUMMARY).read_text(encoding="utf-8"))
    bodies = sign_table["body"].to_pylist()
    primary = dict(zip(bodies, sign_table["sign_glu_inhibitory"].to_pylist()))
    sensitivity = dict(zip(bodies, sign_table["sign_glu_excitatory"].to_pylist()))
    labels = dict(zip(bodies, sign_table["consensus_nt"].to_pylist()))
    cell_types = dict(zip(bodies, sign_table["cell_type"].to_pylist()))
    signed = [body for body, sign in primary.items() if sign != 0]
    if min(signed, key=_hash_priority) != SEED:
        raise SystemExit("SEED is no longer the minimum hash priority among signed neurons.")

    counter: dict[str, int] = {}
    result = quota_bfs(SEED, primary, parquet_neighbor_scanner(edges_path, counter),
                       quotas=DEFAULT_QUOTAS, max_depth=DEFAULT_MAX_DEPTH)
    output_dir = PROJECT_ROOT / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest: dict[str, object] = {
        "schema_version": 1,
        "ticket": "21 M1.4",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": result.status,
        "stop_reason": result.stop_reason,
        "seed": SEED,
        "seed_rule": "minimum M1.2 hash priority among neurons with a +1/-1 sign (D3b)",
        "hash_priority": _hash_priority_metadata(),
        "quotas": {"excitatory": DEFAULT_QUOTAS[1], "inhibitory": DEFAULT_QUOTAS[-1]},
        "max_depth": DEFAULT_MAX_DEPTH,
        "selection_sign_column": "sign_glu_inhibitory",
        "skip_rules": ["unsigned/excluded/absent from sign table", "sign quota full"],
        "expansion": "undirected (weak) view; only admitted nodes expand",
        "layers": result.layers,
        "edge_scans_for_bfs": counter.get("scans", 0),
        "counts": result.counts,
        "sources": {
            "edges_parquet_sha256": EDGES_SHA256,
            "sign_content_sha256": sign_summary["output"]["sign_content_sha256"],
            "neurotransmitter_source_sha256": sign_summary["source"]["sha256"],
        },
        "test": "not applicable (graph construction only)",
    }
    if result.status != "completed":
        (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(manifest, ensure_ascii=False, indent=1))
        print("STOPPED: quotas not filled; rules forbid relaxing them.")
        return 2

    nodes = sorted(result.selected)
    edges = induced_edges(edges_path, nodes)
    components = _weakly_connected(nodes, edges)
    io = select_io_nodes(nodes, IO_COUNT, IO_COUNT, IO_SALT)  # inputs: unchanged M1.3 rule
    io["m1_3_rule_output_node_ids"] = io["output_node_ids"]  # kept for the record (failed T=2 on 2026-11-13)
    d5 = select_reachable_outputs(nodes, edges, io["input_node_ids"], count=IO_COUNT, salt=IO_SALT, max_steps=MODEL_STEPS)
    io["output_node_ids"] = d5["output_node_ids"]
    io["output_rule"] = d5["rule"]
    io["eligible_output_candidates"] = d5["eligible_output_candidates"]
    reach = {
        str(steps): check_io_reachability(edges, io["input_node_ids"], io["output_node_ids"], steps, node_ids=nodes)
        for steps in REPORTED_STEPS
    }
    variants = {"G1_all_positive": {node: 1 for node in nodes},
                "G2_glu_inhibitory": {node: primary[node] for node in nodes},
                "G2_glu_excitatory": {node: sensitivity[node] for node in nodes}}
    graphs = {}
    for name, node_signs in variants.items():
        definition = {
            "node_ids": nodes,
            "input_node_ids": io["input_node_ids"],
            "output_node_ids": io["output_node_ids"],
            "edges": [list(edge) for edge in edges],
            "steps": MODEL_STEPS,
            "node_signs": [[node, node_signs[node]] for node in nodes],
        }
        path = output_dir / f"graph_definition_{name}.json"
        path.write_text(json.dumps(definition, separators=(",", ":")) + "\n", encoding="utf-8")
        out_edges = Counter(node_signs[source] for source, _, _ in edges)
        graphs[name] = {
            "file": path.name,
            "sha256": _sha256(path),
            "node_signs_sha256": _canonical([[node, node_signs[node]] for node in nodes]),
            "excitatory_nodes": sum(1 for v in node_signs.values() if v == 1),
            "inhibitory_nodes": sum(1 for v in node_signs.values() if v == -1),
            "excitatory_edges": out_edges.get(1, 0),
            "inhibitory_edges": out_edges.get(-1, 0),
        }
    prefixes = Counter((cell_types.get(node) or "<none>")[:2] for node in nodes)
    in_degree = Counter(target for _, target, _ in edges)
    manifest.update({
        "node_count": len(nodes),
        "edge_count": len(edges),
        "self_loops": sum(1 for s, t, _ in edges if s == t),
        "weak_components": components,
        "nodes_without_incoming_edges": sum(1 for node in nodes if in_degree[node] == 0),
        "node_set_sha256": _canonical(nodes),
        "edge_set_sha256": _canonical([list(edge) for edge in edges]),
        "consensus_nt_counts": dict(Counter(labels[node] for node in nodes)),
        "cell_type_prefix_counts": dict(prefixes.most_common()),
        "io_selection": io,
        "io_sign_composition": {
            role: dict(Counter(primary[node] for node in io[f"{role}_node_ids"])) for role in ("input", "output")
        },
        "reachability": {
            steps: {"all_outputs_reachable": value["all_outputs_reachable"],
                    "unreachable_output_count": len(value["unreachable_output_ids"]),
                    "hop_counts": dict(Counter(str(row["shortest_hops"]) for row in value["outputs"]))}
            for steps, value in reach.items()
        },
        "model_steps": MODEL_STEPS,
        "required_reachability_steps": MODEL_STEPS,
        "unreachable_policy": "Stop explicitly; do not silently reselect nodes, salts, or change T.",
        "graphs": graphs,
        "elapsed_seconds": time.perf_counter() - started,
        "limitations": [
            "Engineering sample; no biological region or function claim.",
            "Seed differs from G0 (D3b), so G1 - G0 mixes seed, node set and composition differences.",
            "G2_glu_excitatory keeps the same nodes, so it is not a 300/200 split.",
        ],
    })
    if not reach[str(MODEL_STEPS)]["all_outputs_reachable"]:
        manifest["status"] = "stopped_io_unreachable_at_model_steps"
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = {key: manifest[key] for key in ("status", "counts", "node_count", "edge_count", "weak_components",
                                               "layers", "reachability", "io_sign_composition",
                                               "cell_type_prefix_counts", "consensus_nt_counts", "graphs")}
    print(json.dumps(summary, ensure_ascii=False, indent=1))
    return 0 if manifest["status"] == "completed" else 3


if __name__ == "__main__":
    raise SystemExit(main())

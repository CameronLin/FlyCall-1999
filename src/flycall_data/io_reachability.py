"""Deterministic synthetic I/O selection and directed reachability for M1.3.

The public helpers operate on the node and edge rows supplied by the caller.
The archived-demo runner below is the only project entry point: it accepts
only the verified 500-node M1.2 artifact and writes results under M1.3 scratch.
I/O node labels describe engineering endpoints only, not biological roles.
"""

from __future__ import annotations

import hashlib
import json
import platform
import struct
import time
from collections import deque
from pathlib import Path
from typing import Any, Iterable, Sequence

import pyarrow as pa
import pyarrow.parquet as pq

from .runtime_resources import peak_rss_bytes


PROJECT_ROOT = Path(__file__).resolve().parents[2]
ARCHIVED_DEMO_DIR = (
    PROJECT_ROOT
    / "data/connectome/derived/malecns_v1.0/subgraphs/engineering-demo-v1.0"
)
M1_3_SCRATCH_ROOT = PROJECT_ROOT / ".scratch/1999-connectome-demo/m1-3"
DEFAULT_IO_SALT = "FlyCallM13-IO-v1"
DEFAULT_INPUT_COUNT = 32
DEFAULT_OUTPUT_COUNT = 32
DEFAULT_MAX_STEPS = 4
_NODE_SCHEMA = pa.schema([("node_id", pa.int64())])
_EDGE_SCHEMA = pa.schema(
    [
        ("source_id", pa.int64()),
        ("target_id", pa.int64()),
        ("weight", pa.int64()),
    ]
)
_INT64_MIN = -(2**63)
_INT64_MAX = 2**63 - 1


class IOReachabilityError(ValueError):
    """Raised when the archived demo or an I/O request violates its contract."""


def _as_int64(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise IOReachabilityError(f"{name} must contain only int64 values")
    if value < _INT64_MIN or value > _INT64_MAX:
        raise IOReachabilityError(f"{name} contains a value outside int64 range")
    return value


def _unique_ids(name: str, values: Iterable[int]) -> list[int]:
    try:
        result = [_as_int64(name, value) for value in values]
    except TypeError as exc:
        raise IOReachabilityError(f"{name} must be an iterable of int64 IDs") from exc
    if len(result) != len(set(result)):
        raise IOReachabilityError(f"{name} node IDs must be unique")
    if not result:
        raise IOReachabilityError(f"{name} node IDs must not be empty")
    return result


def _positive_integer(name: str, value: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise IOReachabilityError(f"{name} must be a positive integer")
    return value


def _priority(node_id: int, role: str, salt: str) -> bytes:
    message = role.encode("ascii") + b"\x00" + struct.pack("<q", node_id)
    return hashlib.blake2b(
        message,
        digest_size=16,
        key=salt.encode("utf-8"),
    ).digest()


def select_io_nodes(
    node_ids: Iterable[int],
    input_count: int = DEFAULT_INPUT_COUNT,
    output_count: int = DEFAULT_OUTPUT_COUNT,
    salt: str = DEFAULT_IO_SALT,
) -> dict[str, Any]:
    """Select disjoint synthetic I/O IDs by fixed, role-separated hash priority.

    The caller must provide the node set from the verified engineering demo.
    Input and output ranking use BLAKE2b-128 with ``salt`` as the key. Digest
    bytes sort ascending; node ID ascending is used only for digest collisions.
    Returned IDs are sorted numerically for canonical serialization.
    """

    nodes = _unique_ids("node_ids", node_ids)
    input_count = _positive_integer("input_count", input_count)
    output_count = _positive_integer("output_count", output_count)
    if not isinstance(salt, str) or not salt:
        raise IOReachabilityError("salt must be a non-empty string")
    if len(salt.encode("utf-8")) > 64:
        raise IOReachabilityError("salt must encode to at most 64 bytes")
    if input_count + output_count > len(nodes):
        raise IOReachabilityError(
            "selection requires at least input_count + output_count demo nodes"
        )

    input_ids = sorted(
        nodes,
        key=lambda node_id: (_priority(node_id, "input", salt), node_id),
    )[:input_count]
    input_set = set(input_ids)
    remaining_nodes = [node_id for node_id in nodes if node_id not in input_set]
    output_ids = sorted(
        remaining_nodes,
        key=lambda node_id: (_priority(node_id, "output", salt), node_id),
    )[:output_count]

    return {
        "algorithm": "BLAKE2b-128 keyed hash-priority",
        "salt": salt,
        "salt_hex": salt.encode("utf-8").hex(),
        "node_id_encoding": "signed int64, 8 bytes, little-endian",
        "role_domain_separation": "ASCII role name + NUL + encoded node ID",
        "rank_order": "digest bytes ascending; node_id ascending on digest collision",
        "input_node_ids": sorted(input_ids),
        "output_node_ids": sorted(output_ids),
    }


def _edge_triples(
    edges: Iterable[Sequence[int]], node_set: set[int]
) -> list[tuple[int, int, int]]:
    normalized: list[tuple[int, int, int]] = []
    try:
        iterator = iter(edges)
    except TypeError as exc:
        raise IOReachabilityError("edges must be an iterable of triples") from exc
    for index, edge in enumerate(iterator):
        if not isinstance(edge, Sequence) or isinstance(edge, (str, bytes)):
            raise IOReachabilityError(f"edge row {index} must be a 3-value sequence")
        if len(edge) != 3:
            raise IOReachabilityError(f"edge row {index} must have source, target, weight")
        source_id = _as_int64(f"edge row {index} source_id", edge[0])
        target_id = _as_int64(f"edge row {index} target_id", edge[1])
        weight = _as_int64(f"edge row {index} weight", edge[2])
        if source_id not in node_set or target_id not in node_set:
            raise IOReachabilityError(
                f"edge endpoint in row {index} is not present in demo nodes"
            )
        normalized.append((source_id, target_id, weight))
    return normalized


def check_io_reachability(
    edges: Iterable[Sequence[int]],
    input_ids: Iterable[int],
    output_ids: Iterable[int],
    max_steps: int = DEFAULT_MAX_STEPS,
    *,
    node_ids: Iterable[int],
) -> dict[str, Any]:
    """Return shortest directed hop counts from any input to each output.

    ``weight`` is validated as an int64 data field but is not used as a path
    cost. Traversal follows source_id -> target_id only. The node set is
    required so that even isolated nodes can be validated against the demo.
    """

    nodes = _unique_ids("node_ids", node_ids)
    node_set = set(nodes)
    inputs = sorted(_unique_ids("input_ids", input_ids))
    outputs = sorted(_unique_ids("output_ids", output_ids))
    max_steps = _positive_integer("max_steps", max_steps)

    overlap = set(inputs).intersection(outputs)
    if overlap:
        raise IOReachabilityError("input and output node IDs must be disjoint")
    missing_io = (set(inputs) | set(outputs)) - node_set
    if missing_io:
        raise IOReachabilityError(
            "I/O node IDs not present in demo nodes: "
            + ", ".join(str(node_id) for node_id in sorted(missing_io))
        )

    normalized_edges = _edge_triples(edges, node_set)
    outgoing: dict[int, set[int]] = {node_id: set() for node_id in nodes}
    for source_id, target_id, _weight in normalized_edges:
        outgoing[source_id].add(target_id)

    distance: dict[int, int] = {node_id: 0 for node_id in inputs}
    queue: deque[int] = deque(inputs)
    while queue:
        current = queue.popleft()
        current_distance = distance[current]
        if current_distance >= max_steps:
            continue
        for target_id in sorted(outgoing[current]):
            if target_id not in distance:
                distance[target_id] = current_distance + 1
                queue.append(target_id)

    output_rows = [
        {
            "node_id": output_id,
            "shortest_hops": distance.get(output_id),
        }
        for output_id in outputs
    ]
    unreachable = [
        output_id for output_id in outputs if distance.get(output_id) is None
    ]
    return {
        "direction": "source_id -> target_id",
        "path_cost": "unweighted hop count; edge weight is not used",
        "max_steps": max_steps,
        "input_node_ids": inputs,
        "output_node_ids": outputs,
        "outputs": output_rows,
        "unreachable_output_ids": unreachable,
        "all_outputs_reachable": not unreachable,
        "edge_row_count": len(normalized_edges),
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _load_verified_archived_demo(
    demo_dir: Path,
) -> tuple[dict[str, Any], list[int], list[tuple[int, int, int]], dict[str, str]]:
    if demo_dir.resolve() != ARCHIVED_DEMO_DIR.resolve():
        raise IOReachabilityError(
            "M1.3 runner accepts only the archived engineering-demo-v1.0 directory"
        )
    manifest_path = demo_dir / "manifest.json"
    nodes_path = demo_dir / "nodes.parquet"
    edges_path = demo_dir / "edges.parquet"
    for path in (manifest_path, nodes_path, edges_path):
        if not path.is_file():
            raise IOReachabilityError(f"required archived demo file is missing: {path}")

    checksums = {
        "manifest.json": _sha256(manifest_path),
        "nodes.parquet": _sha256(nodes_path),
        "edges.parquet": _sha256(edges_path),
    }
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IOReachabilityError(f"could not read archived demo manifest: {exc}") from exc
    if manifest.get("artifact_type") != "engineering_demo_subgraph":
        raise IOReachabilityError("archived manifest is not an engineering demo subgraph")
    if manifest.get("artifact_status") != "verified_engineering_demo":
        raise IOReachabilityError("archived engineering demo is not marked verified")
    if manifest.get("outputs", {}).get("nodes", {}).get("rows") != 500:
        raise IOReachabilityError("archived engineering demo must contain exactly 500 nodes")

    expected_outputs = {
        "nodes.parquet": ("node_id:int64", 500),
        "edges.parquet": ("source_id:int64,target_id:int64,weight:int64", None),
    }
    for filename, (schema_text, expected_rows) in expected_outputs.items():
        record = manifest.get("outputs", {}).get(filename.removesuffix(".parquet"), {})
        if record.get("path") != filename or record.get("schema") != schema_text:
            raise IOReachabilityError(f"archived manifest schema/path mismatch for {filename}")
        if record.get("sha256") != checksums[filename]:
            raise IOReachabilityError(f"archived manifest checksum mismatch for {filename}")
        if expected_rows is not None and record.get("rows") != expected_rows:
            raise IOReachabilityError(f"archived manifest row-count mismatch for {filename}")

    if manifest.get("edge_semantics", {}).get("output_direction") != (
        "original source_id -> target_id; direction is preserved"
    ):
        raise IOReachabilityError("archived manifest does not confirm source-to-target direction")

    try:
        nodes_table = pq.read_table(nodes_path)
        edges_table = pq.read_table(edges_path)
    except (OSError, pa.ArrowException) as exc:
        raise IOReachabilityError(f"could not read archived demo Parquet: {exc}") from exc
    if nodes_table.schema != _NODE_SCHEMA or edges_table.schema != _EDGE_SCHEMA:
        raise IOReachabilityError(
            "archived Parquet schemas must be node_id:int64 and "
            "source_id:int64,target_id:int64,weight:int64"
        )
    if any(column.null_count for column in nodes_table.columns + edges_table.columns):
        raise IOReachabilityError("archived demo Parquet must not contain nulls")
    if nodes_table.num_rows != 500:
        raise IOReachabilityError("archived nodes.parquet must contain exactly 500 rows")
    if manifest["outputs"]["edges"]["rows"] != edges_table.num_rows:
        raise IOReachabilityError("archived manifest edge row count does not match Parquet")

    node_ids = nodes_table.column("node_id").to_pylist()
    if len(set(node_ids)) != len(node_ids):
        raise IOReachabilityError("archived nodes.parquet contains duplicate node IDs")
    edge_rows = edges_table.to_pylist()
    edges = [
        (row["source_id"], row["target_id"], row["weight"])
        for row in edge_rows
    ]
    _edge_triples(edges, set(node_ids))
    return manifest, node_ids, edges, checksums


def run_archived_demo_io_check(
    output_dir: str | Path,
    *,
    demo_dir: str | Path = ARCHIVED_DEMO_DIR,
    input_count: int = DEFAULT_INPUT_COUNT,
    output_count: int = DEFAULT_OUTPUT_COUNT,
    max_steps: int = DEFAULT_MAX_STEPS,
    salt: str = DEFAULT_IO_SALT,
) -> dict[str, Any]:
    """Validate the archived demo, write a scratch I/O manifest and report.

    This runner refuses any input directory other than the archived v1.0 demo
    and any output directory outside this feature's M1.3 scratch root. It never
    re-reads or modifies M1.1/M1.2 source data beyond hashing the archived files.
    If any output is unreachable, it records the failure and stops without
    retrying with different nodes or silently changing ``max_steps``.
    """

    started = time.perf_counter()
    source_dir = Path(demo_dir).resolve()
    destination = Path(output_dir)
    destination_resolved = destination.resolve()
    scratch_root = M1_3_SCRATCH_ROOT.resolve()
    try:
        destination_resolved.relative_to(scratch_root)
    except ValueError as exc:
        raise IOReachabilityError(
            f"M1.3 output must be under scratch directory {scratch_root}"
        ) from exc
    if destination_resolved == scratch_root:
        raise IOReachabilityError("M1.3 output must use a dedicated child directory")
    if destination.exists():
        raise IOReachabilityError(
            f"M1.3 output directory already exists; refusing to overwrite: {destination}"
        )

    source_manifest, node_ids, edges, source_checksums_before = (
        _load_verified_archived_demo(source_dir)
    )
    selection = select_io_nodes(
        node_ids,
        input_count=input_count,
        output_count=output_count,
        salt=salt,
    )
    reachability = check_io_reachability(
        edges,
        selection["input_node_ids"],
        selection["output_node_ids"],
        max_steps=max_steps,
        node_ids=node_ids,
    )

    result_status = (
        "passed" if reachability["all_outputs_reachable"] else "blocked_unreachable_outputs"
    )
    edge_weight_meaning = source_manifest["edge_semantics"]["weight_meaning"]
    selection_payload = {
        "input_node_ids": selection["input_node_ids"],
        "output_node_ids": selection["output_node_ids"],
    }
    reachability_payload = {
        "outputs": reachability["outputs"],
        "unreachable_output_ids": reachability["unreachable_output_ids"],
    }
    selection_sha256 = _canonical_sha256(selection_payload)
    reachability_sha256 = _canonical_sha256(reachability_payload)
    report = "\n".join(
        [
            "# M1.3 I/O 可達性檢查",
            "",
            f"狀態：`{result_status}`",
            "",
            "輸入只讀自封存的 MaleCNS v1.0 `engineering-demo-v1.0` 子圖。",
            "I/O IDs 是合成工程端點，不代表神經元身分或生物學功能。",
            "",
            f"- Input nodes：{len(selection['input_node_ids'])}",
            f"- Output nodes：{len(selection['output_node_ids'])}",
            f"- T：{max_steps}",
            f"- 方向：`{reachability['direction']}`",
            f"- Weight 語意：{edge_weight_meaning}；本檢查不把 weight 當作路徑成本。",
            f"- 有向邊列數：{reachability['edge_row_count']}",
            f"- 可達 outputs：{len(selection['output_node_ids']) - len(reachability['unreachable_output_ids'])}/{len(selection['output_node_ids'])}",
            f"- 不可達 output IDs：{reachability['unreachable_output_ids']}",
            f"- Selection salt：`{salt}`",
            "- Unreachable policy：不重選、不增加 T，明確停止並記錄結果。",
            "",
            "## Output 最短有向 hop",
            "",
            "| Output node ID | Shortest hops from any input |",
            "|---:|---:|",
            *[
                f"| {row['node_id']} | {row['shortest_hops'] if row['shortest_hops'] is not None else 'null'} |"
                for row in reachability["outputs"]
            ],
            "",
        ]
    )

    destination.mkdir(parents=True, exist_ok=False)
    report_path = destination / "io_report.md"
    report_path.write_text(report, encoding="utf-8")
    report_sha256 = _sha256(report_path)
    source_checksums_after = {
        name: _sha256(source_dir / name)
        for name in ("manifest.json", "nodes.parquet", "edges.parquet")
    }
    if source_checksums_after != source_checksums_before:
        raise IOReachabilityError("archived demo checksums changed during M1.3 run")

    manifest = {
        "manifest_schema_version": "1.0",
        "artifact_type": "m1.3_synthetic_io_reachability_check",
        "artifact_status": result_status,
        "created_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "limitations": [
            "I/O nodes are synthetic engineering endpoints, not biologically typed nodes.",
            "This artifact does not establish biological representativeness or function.",
            "Edge weight is connection metadata and is not used as a path cost.",
        ],
        "source_graph": {
            "path": str(source_dir.relative_to(PROJECT_ROOT)),
            "artifact_name": source_manifest["artifact_name"],
            "manifest_sha256": source_checksums_before["manifest.json"],
            "nodes": {
                "path": "nodes.parquet",
                "rows": len(node_ids),
                "schema": "node_id:int64",
                "sha256": source_checksums_before["nodes.parquet"],
            },
            "edges": {
                "path": "edges.parquet",
                "rows": len(edges),
                "schema": "source_id:int64,target_id:int64,weight:int64",
                "sha256": source_checksums_before["edges.parquet"],
            },
            "upstream_m1_1_source_sha256": source_manifest["source"]["sha256"],
            "upstream_m1_1_edges_sha256": source_manifest["source"]["m1_1_edges_sha256"],
            "upstream_m1_1_nodes_sha256": source_manifest["source"]["m1_1_nodes_sha256"],
        },
        "io_selection": {
            "kind": "synthetic I/O node sets for engineering demo",
            "algorithm": selection["algorithm"],
            "salt": salt,
            "salt_hex": selection["salt_hex"],
            "node_id_encoding": selection["node_id_encoding"],
            "role_domain_separation": selection["role_domain_separation"],
            "rank_order": selection["rank_order"],
            "input_node_ids": selection["input_node_ids"],
            "output_node_ids": selection["output_node_ids"],
            "sets_disjoint": set(selection["input_node_ids"]).isdisjoint(
                selection["output_node_ids"]
            ),
            "selection_sha256": selection_sha256,
        },
        "reachability": {
            "direction": reachability["direction"],
            "max_steps": max_steps,
            "edge_weight_used_as_cost": False,
            "edge_weight_meaning": edge_weight_meaning,
            "path_cost": reachability["path_cost"],
            "per_output": reachability["outputs"],
            "unreachable_output_ids": reachability["unreachable_output_ids"],
            "all_outputs_reachable": reachability["all_outputs_reachable"],
            "reachability_summary_sha256": reachability_sha256,
        },
        "adjustments": [],
        "unreachable_policy": "Stop explicitly; do not silently reselect nodes or change T.",
        "source_checksums_before": source_checksums_before,
        "source_checksums_after": source_checksums_after,
        "outputs": {
            "report": "io_report.md",
            "report_sha256": report_sha256,
            "selection_payload_sha256": selection_sha256,
            "reachability_payload_sha256": reachability_sha256,
        },
        "execution": {
            "elapsed_seconds": round(time.perf_counter() - started, 6),
            "peak_rss_bytes": peak_rss_bytes(),
            "python_version": platform.python_version(),
            "pyarrow_version": pa.__version__,
            "node_count_loaded": len(node_ids),
            "edge_count_loaded": len(edges),
            "dense_adjacency_created": False,
            "full_connectome_read": False,
            "model_loaded": False,
        },
    }
    manifest_path = destination / "io_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest

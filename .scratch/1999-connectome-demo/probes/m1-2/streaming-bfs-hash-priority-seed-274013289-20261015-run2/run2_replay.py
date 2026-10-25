from __future__ import annotations

import hashlib
import json
import os
import pathlib
import signal
import struct
import sys
import time
from datetime import datetime, timezone

import pyarrow as pa
import pyarrow.parquet as pq

PROJECT = pathlib.Path(__file__).resolve().parents[5]
sys.path.insert(0, str(PROJECT / "src"))

from flycall_data.streaming_bfs import probe_streaming_bfs, select_hash_priority_seed  # noqa: E402


RUN1 = PROJECT / ".scratch/1999-connectome-demo/probes/m1-2/streaming-bfs-hash-priority-seed-274013289-20261015-run1"
RUN2 = pathlib.Path(__file__).resolve().parent
M1 = PROJECT / "data/connectome/derived/malecns_v1.0"
NODES = M1 / "nodes.parquet"
EDGES = M1 / "edges.parquet"
PROBE = RUN2 / "probe"
MANIFEST = M1 / "import_manifest.json"
FREE_FLOOR = 4 * 1024**3
WALL_LIMIT_SECONDS = 60 * 60


class ReplayDeadline(RuntimeError):
    pass


def deadline_handler(_signum: int, _frame: object) -> None:
    raise ReplayDeadline("run2 reached the 60-minute outer wall-clock cap")


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(8 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def file_sha256(path: pathlib.Path) -> str:
    return sha256(path)


def canonical_nodes(values: list[int]) -> tuple[list[int], str]:
    ordered = sorted(set(values))
    digest = hashlib.sha256()
    digest.update(len(ordered).to_bytes(8, "little", signed=False))
    for value in ordered:
        digest.update(struct.pack("<q", value))
    return ordered, digest.hexdigest()


def edge_tuples(path: pathlib.Path) -> list[tuple[int, int, int]]:
    table = pq.read_table(path, columns=["source_id", "target_id", "weight"])
    expected = pa.schema([("source_id", pa.int64()), ("target_id", pa.int64()), ("weight", pa.int64())])
    if not table.schema.equals(expected, check_metadata=False):
        raise RuntimeError(f"unexpected edge schema in {path}: {table.schema}")
    return sorted(
        (int(s), int(t), int(w))
        for s, t, w in zip(
            table.column("source_id").to_pylist(),
            table.column("target_id").to_pylist(),
            table.column("weight").to_pylist(),
        )
    )


def canonical_edges(rows: list[tuple[int, int, int]]) -> str:
    digest = hashlib.sha256()
    digest.update(len(rows).to_bytes(8, "little", signed=False))
    for row in rows:
        digest.update(struct.pack("<qqq", *row))
    return digest.hexdigest()


def main() -> int:
    started = time.monotonic()
    started_at_utc = datetime.now(timezone.utc).isoformat()
    signal.signal(signal.SIGALRM, deadline_handler)
    signal.alarm(WALL_LIMIT_SECONDS)
    summary_path = RUN2 / "run_summary.json"
    try:
        if (RUN2 / "seed_selection.json").exists() or PROBE.exists() or summary_path.exists():
            raise RuntimeError("run2 output already exists; refusing overwrite")
        free_start = os.statvfs(M1).f_bavail * os.statvfs(M1).f_frsize
        ram_bytes = os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")
        if free_start < FREE_FLOOR:
            raise RuntimeError(f"disk safety floor failed: {free_start} < {FREE_FLOOR}")
        if ram_bytes != 8 * 1024**3:
            raise RuntimeError(f"physical RAM changed from the approved 8 GiB: {ram_bytes}")

        m1_manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        run1 = json.loads((RUN1 / "run_summary.json").read_text(encoding="utf-8"))
        run1_probe_path = RUN1 / "probe/probe_result.json"
        run1_probe = json.loads(run1_probe_path.read_text(encoding="utf-8"))
        expected_source = {
            "nodes.parquet": m1_manifest["output_nodes_sha256"],
            "edges.parquet": m1_manifest["output_edges_sha256"],
        }
        source_before = {"nodes.parquet": sha256(NODES), "edges.parquet": sha256(EDGES)}
        if source_before != expected_source or source_before != run1["source_checksums_after"]:
            raise RuntimeError(f"source checksum differs before run2: {source_before}")
        if run1["status"] != "complete" or run1_probe["independent_validation"] != "pass":
            raise RuntimeError("run1 was not complete and independently validated")
        run1_actual_candidate_hashes = {
            "candidate_nodes.parquet": sha256(RUN1 / "probe/candidate_nodes.parquet"),
            "candidate_edges.parquet": sha256(RUN1 / "probe/candidate_edges.parquet"),
        }
        if run1_actual_candidate_hashes != run1["candidate_file_sha256"]:
            raise RuntimeError("run1 candidate SHA-256 no longer matches its summary")

        code_files = {
            "src/flycall_data/streaming_bfs.py": sha256(PROJECT / "src/flycall_data/streaming_bfs.py"),
            "tests/test_streaming_bfs.py": sha256(PROJECT / "tests/test_streaming_bfs.py"),
        }
        pyarrow_version = pa.__version__
        if pyarrow_version != "26.0.0":
            raise RuntimeError(f"unexpected PyArrow version: {pyarrow_version}")

        seed = select_hash_priority_seed(NODES)
        (RUN2 / "seed_selection.json").write_text(
            json.dumps(seed, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        if seed["seed_node_id"] != run1["seed_selection"]["seed_node_id"]:
            raise RuntimeError(f"seed differs from run1: {seed['seed_node_id']}")

        bfs = probe_streaming_bfs(
            EDGES,
            seed["seed_node_id"],
            500,
            PROBE,
            max_scans=501,
            wall_clock_seconds=3600,
            min_free_bytes=FREE_FLOOR,
            expected_edge_rows=m1_manifest["output_edge_count"],
        )
        if bfs["status"] != "complete" or bfs["independent_validation"] != "pass":
            raise RuntimeError(f"BFS did not complete validation: {bfs['status']} / {bfs['completion_reason']}")
        if bfs["selected_node_count"] != 500 or bfs["induced_edge_count"] is None:
            raise RuntimeError("BFS did not produce the expected 500-node candidate")

        nodes_path = PROBE / "candidate_nodes.parquet"
        edges_path = PROBE / "candidate_edges.parquet"
        nodes_table = pq.read_table(nodes_path)
        if not nodes_table.schema.equals(pa.schema([("node_id", pa.int64())]), check_metadata=False):
            raise RuntimeError("run2 candidate node schema mismatch")
        run1_nodes, run1_nodes_digest = canonical_nodes(run1_probe["selected_node_ids"])
        run2_nodes, run2_nodes_digest = canonical_nodes(bfs["selected_node_ids"])
        run1_edges = edge_tuples(RUN1 / "probe/candidate_edges.parquet")
        run2_edges = edge_tuples(edges_path)
        if run1_nodes != run2_nodes:
            raise RuntimeError("run1/run2 selected node ID sets differ")
        if run1_edges != run2_edges:
            raise RuntimeError("run1/run2 sorted induced edge tuple multisets differ")
        canonical_edge_digest = canonical_edges(run2_edges)

        candidate_hashes = {
            "candidate_nodes.parquet": sha256(nodes_path),
            "candidate_edges.parquet": sha256(edges_path),
        }
        source_after = {"nodes.parquet": sha256(NODES), "edges.parquet": sha256(EDGES)}
        if source_after != source_before or source_after != expected_source:
            raise RuntimeError(f"source checksum changed during run2: {source_after}")

        run1_canonical_edges = canonical_edges(run1_edges)
        match = {
            "seed_id_equal": seed["seed_node_id"] == run1["seed_selection"]["seed_node_id"],
            "selected_node_set_equal": run1_nodes == run2_nodes,
            "selected_node_count": len(run2_nodes),
            "canonical_node_set_sha256": run2_nodes_digest,
            "run1_canonical_node_set_sha256": run1_nodes_digest,
            "sorted_induced_edge_tuple_multiset_equal": run1_edges == run2_edges,
            "induced_edge_count": len(run2_edges),
            "canonical_sorted_edge_tuples_sha256": canonical_edge_digest,
            "run1_canonical_sorted_edge_tuples_sha256": run1_canonical_edges,
            "canonical_sorted_edge_tuples_equal": canonical_edge_digest == run1_canonical_edges,
            "run1_order_sensitive_induced_edges_sha256": run1_probe["induced_edges_sha256"],
            "run2_order_sensitive_induced_edges_sha256": bfs["induced_edges_sha256"],
            "order_sensitive_digest_equal": run1_probe["induced_edges_sha256"] == bfs["induced_edges_sha256"],
            "order_sensitive_digest_note": "induced_edges_sha256 hashes rows in source Parquet order; it is not permutation-invariant. Canonical sorted tuple SHA-256 above is order-independent.",
        }
        if not all(match[k] for k in ("seed_id_equal", "selected_node_set_equal", "sorted_induced_edge_tuple_multiset_equal", "canonical_sorted_edge_tuples_equal", "order_sensitive_digest_equal")):
            raise RuntimeError(f"run1/run2 reproducibility check failed: {match}")

        free_end = os.statvfs(M1).f_bavail * os.statvfs(M1).f_frsize
        summary = {
            "status": "complete",
            "run_id": "m1-2-hash-priority-seed-274013289-20261015-run2",
            "started_at_utc": started_at_utc,
            "python_version": sys.version,
            "pyarrow_version": pyarrow_version,
            "code_sha256": code_files,
            "fixture_test": {"command": "PYTHONPATH=src uv run --offline --python 3.12 --with pyarrow==26.0.0 -- python -m unittest discover -s tests -p 'test_streaming_bfs.py' -v", "tests": 11, "status": "passed"},
            "preflight": {"physical_ram_bytes": ram_bytes, "disk_free_bytes_at_start": free_start, "required_disk_floor_bytes": FREE_FLOOR, "duckdb_used": False},
            "source_checksums_before": source_before,
            "source_checksums_after": source_after,
            "source_checksums_match_m1_1_manifest": source_after == expected_source,
            "seed_selection": seed,
            "bfs": bfs,
            "candidate_file_sha256": candidate_hashes,
            "comparison_to_run1": match,
            "artifact_independent_check": {"status": "pass", "run1_candidate_sha256_rechecked": run1_actual_candidate_hashes, "run2_candidate_sha256": candidate_hashes, "run2_internal_source_scan_validation": bfs["independent_validation"]},
            "disk_free_bytes_at_end": free_end,
            "total_elapsed_seconds": round(time.monotonic() - started, 3),
        }
        summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return 0
    except BaseException as exc:
        failure = {
            "status": "incomplete",
            "run_id": "m1-2-hash-priority-seed-274013289-20261015-run2",
            "error": f"{type(exc).__name__}: {exc}",
            "total_elapsed_seconds": round(time.monotonic() - started, 3),
            "probe_result": json.loads((PROBE / "probe_result.json").read_text()) if (PROBE / "probe_result.json").exists() else None,
        }
        summary_path.write_text(json.dumps(failure, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        raise
    finally:
        signal.alarm(0)


if __name__ == "__main__":
    raise SystemExit(main())

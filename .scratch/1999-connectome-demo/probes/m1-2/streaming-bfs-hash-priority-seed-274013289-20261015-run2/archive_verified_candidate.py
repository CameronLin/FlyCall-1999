from __future__ import annotations

import hashlib
import json
import os
import pathlib
import shutil
import struct
from datetime import datetime, timezone

import pyarrow as pa
import pyarrow.parquet as pq


PROJECT = pathlib.Path(__file__).resolve().parents[5]
RUN1 = PROJECT / ".scratch/1999-connectome-demo/probes/m1-2/streaming-bfs-hash-priority-seed-274013289-20261015-run1"
RUN2 = pathlib.Path(__file__).resolve().parent
M1 = PROJECT / "data/connectome/derived/malecns_v1.0"
ARCHIVE = M1 / "subgraphs/engineering-demo-v1.0"
STAGE = M1 / "subgraphs/.engineering-demo-v1.0.staging"


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while block := stream.read(8 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def edge_rows(path: pathlib.Path) -> list[tuple[int, int, int]]:
    table = pq.read_table(path)
    schema = pa.schema([("source_id", pa.int64()), ("target_id", pa.int64()), ("weight", pa.int64())])
    if not table.schema.equals(schema, check_metadata=False):
        raise RuntimeError(f"unexpected edge schema {table.schema}")
    return sorted((int(s), int(t), int(w)) for s, t, w in zip(table["source_id"].to_pylist(), table["target_id"].to_pylist(), table["weight"].to_pylist()))


def canonical_edges(rows: list[tuple[int, int, int]]) -> str:
    digest = hashlib.sha256()
    digest.update(len(rows).to_bytes(8, "little", signed=False))
    for row in rows:
        digest.update(struct.pack("<qqq", *row))
    return digest.hexdigest()


def main() -> None:
    summary = json.loads((RUN2 / "run_summary.json").read_text(encoding="utf-8"))
    run1_summary = json.loads((RUN1 / "run_summary.json").read_text(encoding="utf-8"))
    run1_result = json.loads((RUN1 / "probe/probe_result.json").read_text(encoding="utf-8"))
    run2_result = json.loads((RUN2 / "probe/probe_result.json").read_text(encoding="utf-8"))
    m1_manifest = json.loads((M1 / "import_manifest.json").read_text(encoding="utf-8"))
    if summary.get("status") != "complete" or summary.get("artifact_independent_check", {}).get("status") != "pass":
        raise RuntimeError("run2 summary or independent validation is not complete/pass")
    if run1_summary.get("status") != "complete" or run1_result.get("independent_validation") != "pass":
        raise RuntimeError("run1 is not complete and independently validated")
    comparison = summary.get("comparison_to_run1", {})
    required_true = ("seed_id_equal", "selected_node_set_equal", "sorted_induced_edge_tuple_multiset_equal", "canonical_sorted_edge_tuples_equal", "order_sensitive_digest_equal")
    if not all(comparison.get(key) is True for key in required_true):
        raise RuntimeError(f"run1/run2 reproducibility checks did not all pass: {comparison}")
    if run2_result.get("status") != "complete" or run2_result.get("selected_node_count") != 500 or run2_result.get("induced_edge_count") != 2216:
        raise RuntimeError("run2 candidate counts/status do not meet the adopted engineering-demo configuration")
    if run2_result.get("is_formal_subgraph") is not False:
        raise RuntimeError("scratch probe has an unexpected formal status")
    expected_source_hashes = {
        "nodes.parquet": m1_manifest["output_nodes_sha256"],
        "edges.parquet": m1_manifest["output_edges_sha256"],
    }
    if summary.get("source_checksums_before") != expected_source_hashes or summary.get("source_checksums_after") != expected_source_hashes:
        raise RuntimeError("run2 source checksums do not match M1.1 manifest")
    if summary.get("source_checksums_match_m1_1_manifest") is not True:
        raise RuntimeError("run2 source checksum stability check did not pass")
    if ARCHIVE.exists() or STAGE.exists():
        raise RuntimeError(f"refusing to overwrite existing archive/stage: {ARCHIVE if ARCHIVE.exists() else STAGE}")
    free_before_archive = shutil.disk_usage(M1).free
    if free_before_archive < 4 * 1024**3:
        raise RuntimeError(f"archive disk safety floor failed: {free_before_archive} free bytes")

    src_nodes = RUN2 / "probe/candidate_nodes.parquet"
    src_edges = RUN2 / "probe/candidate_edges.parquet"
    actual_candidate_hashes = {"candidate_nodes.parquet": sha256(src_nodes), "candidate_edges.parquet": sha256(src_edges)}
    if actual_candidate_hashes != summary["candidate_file_sha256"]:
        raise RuntimeError("run2 candidate output SHA-256 differs from run summary")
    src_nodes_table = pq.read_table(src_nodes)
    node_schema = pa.schema([("node_id", pa.int64())])
    if not src_nodes_table.schema.equals(node_schema, check_metadata=False):
        raise RuntimeError(f"unexpected node schema: {src_nodes_table.schema}")
    node_ids = src_nodes_table["node_id"].to_pylist()
    if len(node_ids) != 500 or len(set(node_ids)) != 500 or run2_result["seed_node_id"] not in set(node_ids):
        raise RuntimeError("candidate nodes are not 500 unique IDs including the seed")
    source_edges = edge_rows(src_edges)
    if len(source_edges) != 2216 or canonical_edges(source_edges) != comparison["canonical_sorted_edge_tuples_sha256"]:
        raise RuntimeError("candidate edge rows do not match canonical reproducibility digest")
    if any(source not in set(node_ids) or target not in set(node_ids) for source, target, _weight in source_edges):
        raise RuntimeError("candidate edge endpoint is outside the selected node set")

    STAGE.parent.mkdir(parents=True, exist_ok=True)
    STAGE.mkdir()
    shutil.copy2(src_nodes, STAGE / "nodes.parquet")
    shutil.copy2(src_edges, STAGE / "edges.parquet")
    staged_hashes = {name: sha256(STAGE / name) for name in ("nodes.parquet", "edges.parquet")}
    if staged_hashes != {"nodes.parquet": actual_candidate_hashes["candidate_nodes.parquet"], "edges.parquet": actual_candidate_hashes["candidate_edges.parquet"]}:
        raise RuntimeError("staged file checksum differs from run2 scratch candidate")

    manifest = {
        "manifest_schema_version": "1.0",
        "artifact_type": "engineering_demo_subgraph",
        "artifact_name": "MaleCNS v1.0 M1.2 hash-priority 500-node engineering demo",
        "artifact_status": "verified_engineering_demo",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "limitations": [
            "Engineering demo artifact only; not a biologically representative sample.",
            "The 500-node cap is an adopted demo size, not an optimal or biologically justified scale.",
            "M1.1 node IDs are endpoint IDs; no neuron, cell-type, or brain-region semantics are inferred.",
            "M1.2 feasibility completion does not approve a research seed policy or support population-level biological claims.",
        ],
        "source": {
            "dataset": "MaleCNS v1.0",
            "official_bulk_filename": m1_manifest["source_filename"],
            "generation": m1_manifest["source_generation"],
            "size_bytes": m1_manifest["source_size_bytes"],
            "sha256": m1_manifest["source_sha256"],
            "source_rows": m1_manifest["source_rows"],
            "m1_1_import_manifest": "data/connectome/derived/malecns_v1.0/import_manifest.json",
            "m1_1_edges_path": "data/connectome/derived/malecns_v1.0/edges.parquet",
            "m1_1_edges_sha256": expected_source_hashes["edges.parquet"],
            "m1_1_edge_rows": m1_manifest["output_edge_count"],
            "m1_1_nodes_path": "data/connectome/derived/malecns_v1.0/nodes.parquet",
        "m1_1_nodes_sha256": expected_source_hashes["nodes.parquet"],
        "m1_1_node_rows": m1_manifest["output_node_count"],
        "selected_release_filter": "Official minconf-0.5 artifact used as published; exact upstream comparator is not specified, and no additional project filter was applied.",
            "source_checksums_before_run2": summary["source_checksums_before"],
            "source_checksums_after_run2": summary["source_checksums_after"],
            "m1_1_outputs_read_only": True,
        },
        "selection": {
            "algorithm": "BLAKE2b-128",
            "salt_ascii": "FlyCallM12-v1",
            "salt_hex": "466c7943616c6c4d31322d7631",
            "node_id_encoding": "signed int64, 8 bytes, little-endian",
            "rank_order": "digest bytes ascending; node_id ascending only on digest collision",
            "seed_node_id": run2_result["seed_node_id"],
            "seed_priority_hex": summary["seed_selection"]["seed_priority_hex"],
            "seed_candidate_count": summary["seed_selection"]["candidate_count"],
            "node_limit": 500,
            "selected_node_count": run2_result["selected_node_count"],
            "selected_node_ids_file": "nodes.parquet",
            "bfs_adjacency_for_selection": "weak/undirected view of source_id and target_id",
            "bfs_depth_reached": run2_result["bfs_depth_reached"],
            "completion_reason": run2_result["completion_reason"],
            "layer_candidate_order": run2_result["neighbor_order"],
        },
        "edge_semantics": {
            "output_direction": "original source_id -> target_id; direction is preserved",
            "weight_type": "int64",
            "weight_meaning": "Published segment-to-segment connection weight; source documentation describes it as the number of connections/postsynaptic densities, not calibrated synaptic efficacy. M1.1 retains int64 and globally sums duplicate directed pairs.",
            "induced_edge_rule": "retain every M1.1 directed edge row whose source_id and target_id are both selected",
            "self_loop_policy": "retain according to M1.1; no M1.2 filter added",
            "edge_count": run2_result["induced_edge_count"],
        },
        "execution": {
            "run1_scratch": str(RUN1.relative_to(PROJECT)),
            "run2_scratch": str(RUN2.relative_to(PROJECT)),
            "run2_summary": str((RUN2 / "run_summary.json").relative_to(PROJECT)),
            "run2_probe_result": str((RUN2 / "probe/probe_result.json").relative_to(PROJECT)),
            "run2_code_sha256": summary["code_sha256"],
            "python_version": summary["python_version"],
            "pyarrow_version": summary["pyarrow_version"],
            "fixture_tests": summary["fixture_test"],
            "seed_selection_elapsed_seconds": summary["seed_selection"]["elapsed_seconds"],
            "bfs_elapsed_seconds": run2_result["elapsed_seconds"],
            "total_elapsed_seconds_including_checksum_and_comparison": summary["total_elapsed_seconds"],
            "edge_scans_completed": run2_result["scans_completed"],
            "edge_rows_scanned_total": run2_result["rows_scanned_total"],
            "peak_rss_bytes": run2_result["peak_rss_bytes"],
            "physical_ram_bytes": summary["preflight"]["physical_ram_bytes"],
            "minimum_free_disk_bytes_during_bfs": run2_result["disk_free_bytes_min_observed"],
            "duckdb_used": run2_result["duckdb_used"],
            "duckdb_spill_bytes": run2_result["duckdb_spill_bytes"],
            "temporary_index_bytes": run2_result["temporary_index_bytes"],
            "scratch_output_bytes": run2_result["scratch_directory_bytes"],
        },
        "reproducibility_and_validation": {
            "run1_run2_seed_equal": comparison["seed_id_equal"],
            "run1_run2_selected_node_set_equal": comparison["selected_node_set_equal"],
            "run1_run2_sorted_induced_edge_tuple_multiset_equal": comparison["sorted_induced_edge_tuple_multiset_equal"],
            "canonical_node_set_sha256": comparison["canonical_node_set_sha256"],
            "canonical_sorted_induced_edge_tuples_sha256": comparison["canonical_sorted_edge_tuples_sha256"],
            "run1_order_sensitive_induced_edges_sha256": comparison["run1_order_sensitive_induced_edges_sha256"],
            "run2_order_sensitive_induced_edges_sha256": comparison["run2_order_sensitive_induced_edges_sha256"],
            "order_sensitive_digest_explanation": comparison["order_sensitive_digest_note"],
            "run2_independent_validation": run2_result["independent_validation"],
            "run2_candidate_nodes_sha256": staged_hashes["nodes.parquet"],
            "run2_candidate_edges_sha256": staged_hashes["edges.parquet"],
            "run2_canonical_edges_sha256": comparison["canonical_sorted_edge_tuples_sha256"],
        },
        "outputs": {
            "nodes": {"path": "nodes.parquet", "schema": "node_id:int64", "rows": 500, "sha256": staged_hashes["nodes.parquet"]},
            "edges": {"path": "edges.parquet", "schema": "source_id:int64,target_id:int64,weight:int64", "rows": 2216, "sha256": staged_hashes["edges.parquet"]},
        },
    }
    manifest_path = STAGE / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    # Verify the staged archive content before making the final directory visible.
    staged_nodes = pq.read_table(STAGE / "nodes.parquet")
    staged_edges = edge_rows(STAGE / "edges.parquet")
    selected = set(staged_nodes["node_id"].to_pylist())
    if len(selected) != 500 or len(staged_edges) != 2216 or any(s not in selected or t not in selected for s, t, _ in staged_edges):
        raise RuntimeError("staged archive failed content validation")
    if canonical_edges(staged_edges) != comparison["canonical_sorted_edge_tuples_sha256"]:
        raise RuntimeError("staged archive sorted-edge checksum differs from run1/run2")
    if {name: sha256(STAGE / name) for name in ("nodes.parquet", "edges.parquet")} != staged_hashes:
        raise RuntimeError("staged archive checksum changed during validation")
    if ARCHIVE.exists():
        raise RuntimeError("archive destination appeared during verification; refusing overwrite")
    STAGE.rename(ARCHIVE)
    print(json.dumps({
        "archive": str(ARCHIVE.relative_to(PROJECT)),
        "manifest": str((ARCHIVE / "manifest.json").relative_to(PROJECT)),
        "manifest_sha256": sha256(ARCHIVE / "manifest.json"),
        "output_sha256": {name: sha256(ARCHIVE / name) for name in ("nodes.parquet", "edges.parquet")},
        "scratch_candidate_sha256": actual_candidate_hashes,
        "all_checks_passed": True,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

"""Fail-closed graph and embedding inputs for the M3.2 provisional runner."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch

from .e5_runtime import E5_MODEL_FILE_SHA256
from .embedding_pipeline import EmbeddingCache, EmbeddingSettings
from .evaluation import LABEL_ORDER
from .fly_ab_training import EmbeddingSplit, GraphDefinition, validate_engineering_graph
from .loader import DatasetBundle
from .model_config import E5_SMALL_CONFIG


PINNED_M12_MANIFEST_SHA256 = "5300c6cefdc6b84a854545e64f4131baa3fc42f0bde97a83f68fcc1c3769cf40"
PINNED_M13_IO_MANIFEST_SHA256 = "48148a1d64cc5402b17db99dff61ad42a3c29bef8d422ebfa6a25e375e07f585"


class M32InputGateError(RuntimeError):
    """Raised when graph or cache inputs do not match the pinned M3.2 contract."""


@dataclass(frozen=True)
class M32GraphPaths:
    graph_dir: Path
    io_manifest_path: Path

    @property
    def graph_manifest_path(self) -> Path:
        return self.graph_dir / "manifest.json"

    @property
    def nodes_path(self) -> Path:
        return self.graph_dir / "nodes.parquet"

    @property
    def edges_path(self) -> Path:
        return self.graph_dir / "edges.parquet"


@dataclass(frozen=True)
class M32EmbeddingSplits:
    train_for_a: EmbeddingSplit
    validation_for_a: EmbeddingSplit
    train_for_b: EmbeddingSplit
    validation_for_b: EmbeddingSplit
    source_sha256: dict[str, str]
    cache_manifest_sha256: str


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha256_manifest(path: Path) -> str:
    """Hash UTF-8 manifest content with Git-independent LF line endings."""

    try:
        content = Path(path).read_bytes()
    except OSError as error:
        raise M32InputGateError(f"unable to read manifest bytes: {path}") from error
    normalized = content.replace(b"\r\n", b"\n")
    if b"\r" in normalized:
        raise M32InputGateError(f"manifest contains unsupported bare carriage returns: {path}")
    return hashlib.sha256(normalized).hexdigest()


def _sha256_json(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def verify_m32_graph_provenance(paths: M32GraphPaths) -> dict[str, Any]:
    """Verify manifest pins and raw artifact hashes without importing a Parquet reader."""

    required = (
        paths.graph_manifest_path,
        paths.io_manifest_path,
        paths.nodes_path,
        paths.edges_path,
    )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise M32InputGateError(f"M3.2 graph artifacts are missing: {missing}")

    graph_manifest_sha256 = _sha256_manifest(paths.graph_manifest_path)
    io_manifest_sha256 = _sha256_manifest(paths.io_manifest_path)
    mismatches = []
    if graph_manifest_sha256 != PINNED_M12_MANIFEST_SHA256:
        mismatches.append(
            f"M1.2 manifest current={graph_manifest_sha256}, pinned={PINNED_M12_MANIFEST_SHA256}"
        )
    if io_manifest_sha256 != PINNED_M13_IO_MANIFEST_SHA256:
        mismatches.append(
            f"M1.3 I/O manifest current={io_manifest_sha256}, pinned={PINNED_M13_IO_MANIFEST_SHA256}"
        )
    if mismatches:
        raise M32InputGateError(
            "graph provenance pin mismatch; Parquet files have not been opened: " + "; ".join(mismatches)
        )

    try:
        graph_manifest = json.loads(paths.graph_manifest_path.read_text(encoding="utf-8"))
        io_manifest = json.loads(paths.io_manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise M32InputGateError(f"graph manifest is unreadable or invalid: {error}") from error
    source_graph = io_manifest.get("source_graph")
    if not isinstance(source_graph, dict) or source_graph.get("manifest_sha256") != graph_manifest_sha256:
        raise M32InputGateError("M1.3 I/O manifest does not reference the current pinned M1.2 manifest.")

    output_specs = graph_manifest.get("outputs")
    if not isinstance(output_specs, dict):
        raise M32InputGateError("M1.2 graph manifest is missing output checksums.")
    observed = {
        "nodes": _sha256_file(paths.nodes_path),
        "edges": _sha256_file(paths.edges_path),
    }
    for name, path in (("nodes", paths.nodes_path), ("edges", paths.edges_path)):
        spec = output_specs.get(name)
        if not isinstance(spec, dict) or spec.get("sha256") != observed[name]:
            raise M32InputGateError(f"{name} Parquet raw SHA-256 differs from the M1.2 manifest.")
        io_spec = source_graph.get(name)
        if not isinstance(io_spec, dict) or io_spec.get("sha256") != observed[name]:
            raise M32InputGateError(f"{name} Parquet raw SHA-256 differs from the M1.3 I/O manifest.")
        if path.name != spec.get("path"):
            raise M32InputGateError(f"{name} Parquet path differs from the M1.2 manifest.")
    return {
        "graph_manifest": graph_manifest,
        "io_manifest": io_manifest,
        "graph_manifest_sha256": graph_manifest_sha256,
        "io_manifest_sha256": io_manifest_sha256,
        "nodes_sha256": observed["nodes"],
        "edges_sha256": observed["edges"],
    }


def load_m32_graph(paths: M32GraphPaths) -> tuple[GraphDefinition, dict[str, str]]:
    """Load only the fixed small subgraph after every provenance gate passes."""

    verified = verify_m32_graph_provenance(paths)
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except Exception as error:
        raise M32InputGateError(
            "approved PyArrow Parquet runtime is unavailable; graph rows were not read."
        ) from error

    try:
        node_table = pq.read_table(paths.nodes_path)
        edge_table = pq.read_table(paths.edges_path)
    except Exception as error:
        raise M32InputGateError(f"unable to read the pinned M1.2 Parquet graph: {error}") from error
    if node_table.schema.names != ["node_id"] or node_table.schema.field("node_id").type != pa.int64():
        raise M32InputGateError("M1.2 nodes schema must be exactly node_id:int64.")
    if edge_table.schema.names != ["source_id", "target_id", "weight"]:
        raise M32InputGateError("M1.2 edges schema must be source_id,target_id,weight.")
    if any(edge_table.schema.field(name).type != pa.int64() for name in edge_table.schema.names):
        raise M32InputGateError("M1.2 edge fields must all be int64.")

    node_ids = tuple(int(value) for value in node_table.column("node_id").to_pylist())
    edges = tuple(
        (int(row["source_id"]), int(row["target_id"]), int(row["weight"]))
        for row in edge_table.to_pylist()
    )
    graph_manifest = verified["graph_manifest"]
    io_manifest = verified["io_manifest"]
    expected_nodes = graph_manifest.get("selection", {}).get("selected_node_count")
    expected_edges = graph_manifest.get("edge_semantics", {}).get("edge_count")
    if len(node_ids) != expected_nodes or len(set(node_ids)) != len(node_ids):
        raise M32InputGateError("M1.2 nodes row count or uniqueness does not match the manifest.")
    if len(edges) != expected_edges:
        raise M32InputGateError("M1.2 edge row count does not match the manifest.")
    node_set = set(node_ids)
    if any(source not in node_set or target not in node_set for source, target, _weight in edges):
        raise M32InputGateError("M1.2 contains an edge endpoint outside its selected node table.")
    if any(weight <= 0 for _source, _target, weight in edges):
        raise M32InputGateError("M1.2 edge weights must be positive for the fixed log1p prior.")

    selection = io_manifest.get("io_selection")
    if not isinstance(selection, dict):
        raise M32InputGateError("M1.3 I/O manifest is missing io_selection.")
    input_ids = tuple(selection.get("input_node_ids", ()))
    output_ids = tuple(selection.get("output_node_ids", ()))
    graph = GraphDefinition(node_ids, input_ids, output_ids, edges, steps=2)
    try:
        validate_engineering_graph(graph)
    except ValueError as error:
        raise M32InputGateError(f"M1.2/M1.3 topology violates the M3.0 contract: {error}") from error

    after_hashes = {
        "nodes_sha256": _sha256_file(paths.nodes_path),
        "edges_sha256": _sha256_file(paths.edges_path),
        "graph_manifest_sha256": _sha256_manifest(paths.graph_manifest_path),
        "io_manifest_sha256": _sha256_manifest(paths.io_manifest_path),
    }
    if (
        after_hashes["nodes_sha256"] != verified["nodes_sha256"]
        or after_hashes["edges_sha256"] != verified["edges_sha256"]
        or after_hashes["graph_manifest_sha256"] != verified["graph_manifest_sha256"]
        or after_hashes["io_manifest_sha256"] != verified["io_manifest_sha256"]
    ):
        raise M32InputGateError("a pinned graph input changed while it was being read.")
    source_hashes = {
        "graph_manifest": verified["graph_manifest_sha256"],
        "io_manifest": verified["io_manifest_sha256"],
        "nodes_parquet": verified["nodes_sha256"],
        "edges_parquet": verified["edges_sha256"],
    }
    return graph, source_hashes


def load_m32_embedding_splits(
    bundle: DatasetBundle,
    *,
    embedding_manifest_path: Path,
    cache_root: Path,
) -> M32EmbeddingSplits:
    """Resolve train/validation vectors by exact text and cache hashes only."""

    manifest_path = Path(embedding_manifest_path)
    try:
        embedding_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise M32InputGateError(f"E5 embedding manifest is unreadable or invalid: {error}") from error
    if (
        embedding_manifest.get("evaluation_status") != "smoke_test/provisional"
        or embedding_manifest.get("data_status") != "synthetic"
        or embedding_manifest.get("review_status") != "pending_manual_review"
    ):
        raise M32InputGateError("E5 embedding manifest is not the expected pending provisional artifact.")
    dataset_hashes = bundle.audit_summary.get("source_sha256")
    if not isinstance(dataset_hashes, dict) or embedding_manifest.get("source_sha256") != dataset_hashes:
        raise M32InputGateError("E5 cache data source hashes differ from the frozen dataset loader audit.")

    settings_data = embedding_manifest.get("cache_settings")
    if not isinstance(settings_data, dict):
        raise M32InputGateError("E5 cache settings are missing from the embedding manifest.")
    settings_values = dict(settings_data)
    try:
        settings_values["model_file_sha256"] = tuple(
            (str(name), str(digest)) for name, digest in settings_values["model_file_sha256"]
        )
        settings = EmbeddingSettings(**settings_values)
    except (KeyError, TypeError, ValueError) as error:
        raise M32InputGateError(f"E5 cache settings are invalid: {error}") from error
    if (
        settings.model_id != E5_SMALL_CONFIG.model_id
        or settings.revision != E5_SMALL_CONFIG.revision
        or settings.tokenizer_revision != E5_SMALL_CONFIG.revision
        or settings.output_dimension != 384
        or settings.normalize_embeddings is not True
        or settings.model_file_sha256 != E5_MODEL_FILE_SHA256
    ):
        raise M32InputGateError("E5 cache model revision, normalization, dimension, or file hashes are not pinned.")

    expected_rows: dict[str, dict[str, Any]] = {}
    for row in bundle.records:
        if row.get("split") in {"train", "validation"}:
            record_id = row.get("id")
            if not isinstance(record_id, str) or record_id in expected_rows:
                raise M32InputGateError("frozen train/validation records contain missing or duplicate IDs.")
            expected_rows[record_id] = row

    entries = embedding_manifest.get("entries")
    if not isinstance(entries, list) or len(entries) != 850:
        raise M32InputGateError("E5 manifest must contain exactly 850 train/validation cache entries.")
    entries_by_id: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise M32InputGateError("E5 embedding manifest contains an invalid entry.")
        record_id = entry.get("record_id")
        if not isinstance(record_id, str) or record_id in entries_by_id:
            raise M32InputGateError("E5 embedding manifest has a missing or duplicate record ID.")
        if entry.get("split") not in {"train", "validation"}:
            raise M32InputGateError("E5 cache manifest must not contain test or other split vectors.")
        entries_by_id[record_id] = entry
    if set(entries_by_id) != set(expected_rows):
        raise M32InputGateError("E5 cache entries do not exactly cover frozen train and validation IDs.")

    cache = EmbeddingCache(Path(cache_root))
    features: dict[str, tuple[float, ...]] = {}
    for record_id, row in expected_rows.items():
        entry = entries_by_id[record_id]
        text = row.get("transcript")
        if not isinstance(text, str):
            raise M32InputGateError(f"train/validation transcript {record_id} is invalid.")
        transcript_sha256 = hashlib.sha256(text.encode("utf-8", errors="strict")).hexdigest()
        if entry.get("transcript_sha256") != transcript_sha256:
            raise M32InputGateError(f"E5 manifest transcript hash differs for {record_id}.")
        cache_key = cache.key_for(text, settings)
        if entry.get("cache_key") != cache_key:
            raise M32InputGateError(f"E5 cache key differs from text/model settings for {record_id}.")
        vector = cache.get(cache_key)
        if vector is None:
            raise M32InputGateError(f"E5 cache entry is missing for {record_id}.")
        if len(vector) != 384 or entry.get("dimension") != 384:
            raise M32InputGateError(f"E5 cache dimension differs from the pinned output for {record_id}.")
        if any(not math.isfinite(value) for value in vector):
            raise M32InputGateError(f"E5 cache vector is non-finite for {record_id}.")
        norm = math.sqrt(sum(value * value for value in vector))
        if not math.isclose(norm, 1.0, rel_tol=1e-6, abs_tol=1e-6):
            raise M32InputGateError(f"E5 cache vector is not unit-normalized for {record_id}.")
        if _sha256_json([float(value) for value in vector]) != entry.get("embedding_sha256"):
            raise M32InputGateError(f"E5 cache vector SHA-256 differs from its manifest for {record_id}.")
        features[record_id] = vector

    result: dict[str, EmbeddingSplit] = {}
    for split in ("train", "validation"):
        rows = [row for row in bundle.records if row.get("split") == split]
        rows.sort(key=lambda row: row["id"])
        ids = tuple(row["id"] for row in rows)
        families = tuple(row["scenario_family_id"] for row in rows)
        tensor = torch.tensor([features[record_id] for record_id in ids], dtype=torch.float32, device="cpu")
        result[split] = EmbeddingSplit(split, ids, families, tensor)
        labeled = EmbeddingSplit(
            split,
            ids,
            families,
            tensor,
            tuple(row["label_id"] for row in rows),
        )
        result[f"{split}_labeled"] = labeled

    counts = embedding_manifest.get("splits")
    if counts != {"train": 700, "validation": 150}:
        raise M32InputGateError("E5 embedding manifest split counts are not 700/150.")
    if any(row.get("split") == "test" for row in entries):
        raise M32InputGateError("test embeddings are prohibited in the M3.2 input manifest.")

    source_hashes = dict(dataset_hashes)
    source_hashes["embedding_manifest"] = _sha256_file(manifest_path)
    source_hashes["e5_model_files"] = _sha256_json([list(item) for item in settings.model_file_sha256])
    return M32EmbeddingSplits(
        train_for_a=result["train"],
        validation_for_a=result["validation"],
        train_for_b=result["train_labeled"],
        validation_for_b=result["validation_labeled"],
        source_sha256=source_hashes,
        cache_manifest_sha256=source_hashes["embedding_manifest"],
    )

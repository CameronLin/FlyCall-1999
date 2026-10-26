#!/usr/bin/env python3
"""Run the fixed, provisional E5 train/validation comparison on Windows CPU."""

from __future__ import annotations

import argparse
import csv
import ctypes
import hashlib
import json
import os
import platform
import re
import shutil
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from flycall_data.embedding_pipeline import (  # noqa: E402
    EmbeddingCache,
    SplitTexts,
    embed_texts,
    run_baseline,
)
from flycall_data.e5_runtime import (  # noqa: E402
    E5_MODEL_FILE_SHA256,
    load_e5_encoder,
    verify_e5_snapshot,
)
from flycall_data.evaluation import (  # noqa: E402
    LABEL_ORDER,
    PredictionBatch,
    evaluate_predictions,
    render_markdown_report,
)
from flycall_data.lda_baseline import run_lda_logistic_baseline  # noqa: E402
from flycall_data.loader import DatasetPaths, load_frozen_dataset  # noqa: E402
from flycall_data.model_config import E5_SMALL_CONFIG  # noqa: E402


DATASET_PATHS = DatasetPaths(
    jsonl_path=PROJECT_ROOT / "data/1999_synthetic/formal/v1.0.0/formal_dataset_v1.0.0.jsonl",
    csv_path=PROJECT_ROOT / "data/1999_synthetic/formal/v1.0.0/formal_dataset_v1.0.0.csv",
    taxonomy_path=PROJECT_ROOT / "data/1999_synthetic/taxonomy/current/taxonomy_v1.3.yaml",
    frozen_manifest_path=PROJECT_ROOT
    / "data/1999_synthetic/taxonomy/current/formal_split_manifest_frozen_v1.0.yaml",
)
OUTPUT_PARENT = PROJECT_ROOT / ".scratch/1999-connectome-demo/runs"
CACHE_ROOT = PROJECT_ROOT / ".scratch/1999-connectome-demo/caches/m2-2b-e5-small"
MIN_FREE_DISK_BYTES = 4 * 1024**3
MIN_AVAILABLE_RAM_BYTES = 1 * 1024**3
MAX_PROCESS_RSS_BYTES = int(3.5 * 1024**3)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _source_paths() -> dict[str, Path]:
    return {
        "jsonl": DATASET_PATHS.jsonl_path,
        "csv": DATASET_PATHS.csv_path,
        "taxonomy": DATASET_PATHS.taxonomy_path,
        "manifest": DATASET_PATHS.frozen_manifest_path,
    }


def _source_hashes() -> dict[str, str]:
    return {name: _sha256_file(path) for name, path in _source_paths().items()}


def _package_versions() -> dict[str, str]:
    packages = (
        "numpy",
        "scikit-learn",
        "scipy",
        "sentence-transformers",
        "sentencepiece",
        "tokenizers",
        "torch",
        "transformers",
    )
    result: dict[str, str] = {}
    for package in packages:
        try:
            result[package] = version(package)
        except PackageNotFoundError as error:
            raise RuntimeError(f"required package {package} is not installed in this environment.") from error
    return result


def _windows_resources() -> dict[str, int | float]:
    if os.name != "nt":
        raise RuntimeError("this resource-gated runner is intended for Windows.")

    from ctypes import wintypes

    class MemoryStatus(ctypes.Structure):
        _fields_ = [
            ("dwLength", wintypes.DWORD),
            ("dwMemoryLoad", wintypes.DWORD),
            ("ullTotalPhys", ctypes.c_ulonglong),
            ("ullAvailPhys", ctypes.c_ulonglong),
            ("ullTotalPageFile", ctypes.c_ulonglong),
            ("ullAvailPageFile", ctypes.c_ulonglong),
            ("ullTotalVirtual", ctypes.c_ulonglong),
            ("ullAvailVirtual", ctypes.c_ulonglong),
            ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
        ]

    status = MemoryStatus()
    status.dwLength = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise OSError(ctypes.get_last_error(), "GlobalMemoryStatusEx failed")

    class ProcessMemoryCounters(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
            ("PrivateUsage", ctypes.c_size_t),
        ]

    counters = ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel32.GetCurrentProcess.argtypes = []
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    psapi.GetProcessMemoryInfo.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(ProcessMemoryCounters),
        wintypes.DWORD,
    ]
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
    if not psapi.GetProcessMemoryInfo(kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
        raise OSError(ctypes.get_last_error(), "GetProcessMemoryInfo failed")

    return {
        "total_physical_ram_bytes": int(status.ullTotalPhys),
        "available_ram_bytes": int(status.ullAvailPhys),
        "available_commit_bytes": int(status.ullAvailPageFile),
        "memory_load_percent": int(status.dwMemoryLoad),
        "process_peak_working_set_bytes": int(counters.PeakWorkingSetSize),
        "process_peak_pagefile_bytes": int(counters.PeakPagefileUsage),
    }


def _resource_gate(snapshot: Path) -> dict[str, Any]:
    resources = _windows_resources()
    free_disk = shutil.disk_usage(PROJECT_ROOT).free
    resources["project_disk_free_bytes"] = free_disk
    resources["model_snapshot_bytes"] = sum(path.stat().st_size for path in snapshot.rglob("*") if path.is_file())
    if int(resources["available_ram_bytes"]) < MIN_AVAILABLE_RAM_BYTES:
        raise RuntimeError("E5 run stopped: available physical RAM fell below 1 GiB.")
    if int(resources["available_commit_bytes"]) < MIN_AVAILABLE_RAM_BYTES:
        raise RuntimeError("E5 run stopped: available commit fell below 1 GiB.")
    if int(resources["memory_load_percent"]) >= 90:
        raise RuntimeError("E5 run stopped: Windows memory load reached 90%.")
    if int(resources["process_peak_working_set_bytes"]) > MAX_PROCESS_RSS_BYTES:
        raise RuntimeError("E5 run stopped: process peak working set exceeded the 3.5 GiB ceiling.")
    if free_disk < MIN_FREE_DISK_BYTES:
        raise RuntimeError("E5 run stopped: project disk free space fell below the 4 GiB reserve.")
    return resources


def _candidate_registration(seed: int = 42) -> dict[str, Any]:
    if isinstance(seed, bool) or not isinstance(seed, int) or seed < 1:
        raise ValueError("training seed must be a positive integer.")
    return {
        "schema_version": 1,
        "locked_before_dataset_load": True,
        "status": "pre_registered",
        "seed": seed,
        "label_order": list(LABEL_ORDER),
        "embedding": {
            "model_id": E5_SMALL_CONFIG.model_id,
            "revision": E5_SMALL_CONFIG.revision,
            "prefix": E5_SMALL_CONFIG.prefix,
            "max_seq_length": E5_SMALL_CONFIG.max_seq_length,
            "truncation_policy": "right-truncate; report per-text token counts before embedding",
            "pooling": E5_SMALL_CONFIG.pooling,
            "normalize_embeddings": E5_SMALL_CONFIG.normalize_embeddings,
            "device": "cpu",
            "batch_size": 1,
            "model_file_sha256": [list(item) for item in E5_MODEL_FILE_SHA256],
        },
        "candidates": {
            "logistic_regression": {
                "classifier": "sklearn.linear_model.LogisticRegression",
                "C": 1.0,
                "max_iter": 1000,
                "solver": "lbfgs",
                "random_state": seed,
            },
            "mlp": {
                "hidden_size": 16,
                "epochs": 80,
                "learning_rate": 0.02,
                "seed": seed,
            },
            "pca_mlp": {
                "pca_components": 32,
                "pca_fit_split": "train",
                "hidden_size": 16,
                "epochs": 80,
                "learning_rate": 0.02,
                "seed": seed,
            },
            "lda_logistic_regression": {
                "lda_solver": "svd",
                "lda_components": 4,
                "classifier": "sklearn.linear_model.LogisticRegression",
                "classifier_C": 1.0,
                "classifier_max_iter": 1000,
                "classifier_solver": "lbfgs",
                "seed": seed,
            },
        },
        "test": "not_run; no test text, embeddings, predictions, or metrics",
        "selection_rule": "Compare only the predeclared train/validation candidates; do not tune after seeing validation metrics.",
    }


def _split_texts(rows: Sequence[dict[str, Any]], split: str) -> SplitTexts:
    return SplitTexts(
        split=split,
        record_ids=tuple(row["id"] for row in rows),
        family_ids=tuple(row["scenario_family_id"] for row in rows),
        texts=tuple(row["transcript"] for row in rows),
        labels=tuple(row["label_id"] for row in rows),
    )


def _prediction_batch(
    split: str,
    rows: Sequence[dict[str, Any]],
    predictions: Sequence[str],
) -> PredictionBatch:
    return PredictionBatch(
        split=split,
        record_ids=tuple(row["id"] for row in rows),
        family_ids=tuple(row["scenario_family_id"] for row in rows),
        expected=tuple(row["label_id"] for row in rows),
        predicted=tuple(predictions),
    )


def _vector_sha256(vector: Sequence[float]) -> str:
    return _sha256_bytes(_json_bytes([float(value) for value in vector]))


def _write_predictions(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=(
                "candidate",
                "split",
                "record_id",
                "expected",
                "predicted",
                *(f"logit_{label}" for label in LABEL_ORDER),
            ),
        )
        writer.writeheader()
        writer.writerows(rows)


def _package_version_or_error(package: str) -> str:
    try:
        return version(package)
    except PackageNotFoundError as error:
        raise RuntimeError(f"required package {package} is missing.") from error


def _write_lda_checkpoint(
    path: Path,
    result: Any,
    validation: Any,
    registration: dict[str, Any],
    source_hashes: dict[str, str],
) -> dict[str, Any]:
    import joblib
    import numpy as np

    checkpoint = {
        "schema_version": 1,
        "artifact_type": "flycall_e5_baseline",
        "candidate": result.candidate,
        "seed": result.seed,
        "label_order": list(result.label_order),
        "embedding_model": E5_SMALL_CONFIG.model_id,
        "embedding_revision": E5_SMALL_CONFIG.revision,
        "embedding_dimension": E5_SMALL_CONFIG.output_dimension,
        "embedding_model_files_sha256": [list(item) for item in E5_MODEL_FILE_SHA256],
        "configuration": dict(result.parameters),
        "configuration_fingerprint": registration["configuration_fingerprint"],
        "source_sha256": source_hashes,
        "train_record_ids_sha256": _sha256_bytes(_json_bytes(list(result.lda_fit_record_ids))),
        "validation_record_ids_sha256": _sha256_bytes(_json_bytes(list(result.validation_record_ids))),
        "lda": result.lda_model,
        "classifier": result.classifier,
    }
    joblib.dump(checkpoint, path, compress=3)
    reloaded = joblib.load(path)
    reduced = reloaded["lda"].transform(np.asarray(validation.features, dtype=np.float64))
    reloaded_predictions = tuple(str(value) for value in reloaded["classifier"].predict(reduced))
    raw_reloaded_scores = np.asarray(reloaded["classifier"].decision_function(reduced))
    class_index = {str(label): index for index, label in enumerate(reloaded["classifier"].classes_)}
    reloaded_scores = raw_reloaded_scores[:, [class_index[label] for label in result.label_order]]
    original_scores = np.asarray(result.validation_logits)
    if reloaded_predictions != result.validation_predictions or not np.array_equal(reloaded_scores, original_scores):
        raise RuntimeError("reloaded M2.3 checkpoint did not reproduce validation predictions and scores exactly.")
    return {
        "path": path.relative_to(PROJECT_ROOT).as_posix(),
        "sha256": _sha256_file(path),
        "bytes": path.stat().st_size,
        "format": "joblib",
        "reload_prediction_match": True,
        "reload_score_array_exact_match": True,
        "joblib_version": version("joblib"),
        "scikit_learn_version": version("scikit-learn"),
        "numpy_version": version("numpy"),
    }


def _baseline_scores(model: Any, preprocessor: Any, candidate: str, features: Any) -> Any:
    import numpy as np

    transformed = preprocessor.transform(features) if preprocessor is not None else features
    if candidate == "logistic_regression":
        raw = np.asarray(model.decision_function(transformed), dtype=np.float64)
        class_index = {str(label): index for index, label in enumerate(model.classes_)}
        scores = raw[:, [class_index[label] for label in LABEL_ORDER]]
    elif candidate in {"mlp", "pca_mlp"}:
        import torch

        with torch.no_grad():
            scores = model(torch.tensor(transformed, dtype=torch.float32, device="cpu")).cpu().numpy()
        scores = np.asarray(scores, dtype=np.float64)
    else:
        raise ValueError(f"unsupported E5 checkpoint candidate {candidate!r}.")
    if scores.ndim != 2 or scores.shape[1] != len(LABEL_ORDER) or not np.isfinite(scores).all():
        raise RuntimeError("checkpoint returned invalid fixed-order classification scores.")
    return scores


def _write_baseline_checkpoint(
    path: Path,
    result: Any,
    train: Any,
    validation: Any,
    registration: dict[str, Any],
    source_hashes: dict[str, str],
) -> dict[str, Any]:
    import joblib
    import numpy as np

    checkpoint = {
        "schema_version": 1,
        "artifact_type": "flycall_e5_baseline",
        "candidate": result.candidate,
        "seed": result.seed,
        "label_order": list(result.label_order),
        "embedding_model": E5_SMALL_CONFIG.model_id,
        "embedding_revision": E5_SMALL_CONFIG.revision,
        "embedding_dimension": E5_SMALL_CONFIG.output_dimension,
        "embedding_model_files_sha256": [list(item) for item in E5_MODEL_FILE_SHA256],
        "output_dimension": len(LABEL_ORDER),
        "configuration": dict(result.parameters),
        "configuration_fingerprint": registration["configuration_fingerprint"],
        "source_sha256": source_hashes,
        "train_record_ids_sha256": _sha256_bytes(_json_bytes(list(result.train_record_ids))),
        "validation_record_ids_sha256": _sha256_bytes(_json_bytes(list(result.validation_record_ids))),
        "transform_fit_record_ids_sha256": _sha256_bytes(_json_bytes(list(result.transform_fit_record_ids))),
        "model": result.model,
        "preprocessor": result.preprocessor,
    }
    joblib.dump(checkpoint, path, compress=3)
    reloaded = joblib.load(path)
    if (
        reloaded.get("schema_version") != 1
        or reloaded.get("artifact_type") != "flycall_e5_baseline"
        or reloaded.get("candidate") != result.candidate
        or reloaded.get("label_order") != list(LABEL_ORDER)
        or reloaded.get("embedding_dimension") != E5_SMALL_CONFIG.output_dimension
        or reloaded.get("configuration_fingerprint") != registration["configuration_fingerprint"]
        or reloaded.get("source_sha256") != source_hashes
    ):
        raise RuntimeError(f"reloaded {result.candidate} checkpoint metadata differs from its locked contract.")
    train_scores = _baseline_scores(reloaded["model"], reloaded["preprocessor"], result.candidate, train.features)
    validation_scores = _baseline_scores(
        reloaded["model"], reloaded["preprocessor"], result.candidate, validation.features
    )
    if result.candidate == "logistic_regression":
        train_predictions = tuple(str(value) for value in reloaded["model"].predict(train.features))
        validation_predictions = tuple(str(value) for value in reloaded["model"].predict(validation.features))
    else:
        train_predictions = tuple(LABEL_ORDER[index] for index in train_scores.argmax(axis=1).tolist())
        validation_predictions = tuple(LABEL_ORDER[index] for index in validation_scores.argmax(axis=1).tolist())
    if (
        train_predictions != result.train_predictions
        or validation_predictions != result.validation_predictions
        or not np.array_equal(train_scores, np.asarray(result.train_logits, dtype=np.float64))
        or not np.array_equal(validation_scores, np.asarray(result.validation_logits, dtype=np.float64))
    ):
        raise RuntimeError(f"reloaded {result.candidate} checkpoint did not reproduce scores and predictions exactly.")
    return {
        "path": path.relative_to(PROJECT_ROOT).as_posix(),
        "sha256": _sha256_file(path),
        "bytes": path.stat().st_size,
        "format": "joblib",
        "reload_prediction_match": True,
        "reload_score_array_exact_match": True,
        "joblib_version": version("joblib"),
        "scikit_learn_version": version("scikit-learn"),
        "numpy_version": version("numpy"),
    }


def run(snapshot_dir: Path, run_dir: Path, *, seed: int = 42) -> None:
    snapshot = Path(snapshot_dir).resolve(strict=True)
    run_dir = Path(run_dir).resolve()
    try:
        run_dir.relative_to(PROJECT_ROOT.resolve())
    except ValueError as error:
        raise ValueError("run output must stay under the project workspace.") from error
    run_dir.mkdir(parents=True, exist_ok=False)
    registration = _candidate_registration(seed)
    registration["configuration_fingerprint"] = _sha256_bytes(_json_bytes(registration))
    _write_json(run_dir / "pre_registered_candidates.json", registration)

    preflight_resources = _resource_gate(snapshot)
    model_manifest = verify_e5_snapshot(snapshot)
    packages = _package_versions()
    source_before = _source_hashes()
    started = time.perf_counter()
    bundle = load_frozen_dataset(DATASET_PATHS)
    loader_seconds = time.perf_counter() - started
    if bundle.audit_summary["source_sha256"] != source_before:
        raise RuntimeError("M2.1 loader source checksums do not match pre-run file hashes.")

    train_rows: list[dict[str, Any]] = []
    validation_rows: list[dict[str, Any]] = []
    for row in bundle.records:
        split = row["split"]
        if split == "train":
            train_rows.append(row)
        elif split == "validation":
            validation_rows.append(row)
    if len(train_rows) != 700 or len(validation_rows) != 150:
        raise RuntimeError("frozen train/validation counts differ from the v0.2 dataset contract.")

    cache_settings = E5_SMALL_CONFIG.embedding_settings(
        preprocessing_version="transcript-only-v1",
        truncation_policy="audited-right-truncate",
        dtype="float32",
        model_file_sha256=E5_MODEL_FILE_SHA256,
    )
    cache = EmbeddingCache(CACHE_ROOT)
    cache_before_bytes = sum(path.stat().st_size for path in CACHE_ROOT.rglob("*") if path.is_file()) if CACHE_ROOT.exists() else 0

    started = time.perf_counter()
    encoder = load_e5_encoder(snapshot)
    model_load_seconds = time.perf_counter() - started
    model_loaded_resources = _resource_gate(snapshot)

    permitted_rows = train_rows + validation_rows
    prefixed_texts: list[str] = []
    for row in permitted_rows:
        transcript = row["transcript"]
        if not isinstance(transcript, str):
            raise ValueError("permitted transcript must be text.")
        transcript.encode("utf-8", errors="strict")
        prefixed_texts.append(E5_SMALL_CONFIG.prefix + transcript)
    tokenization_started = time.perf_counter()
    diagnostics = encoder.inspect(prefixed_texts)
    tokenization_seconds = time.perf_counter() - tokenization_started
    if len(diagnostics) != len(permitted_rows):
        raise RuntimeError("tokenizer diagnostics do not align with permitted records.")

    train_texts = _split_texts(train_rows, "train")
    validation_texts = _split_texts(validation_rows, "validation")
    started = time.perf_counter()
    train_embeddings = embed_texts(train_texts, encoder, cache_settings, cache)
    validation_embeddings = embed_texts(validation_texts, encoder, cache_settings, cache)
    embedding_seconds = time.perf_counter() - started
    after_embedding_resources = _resource_gate(snapshot)

    diagnostic_by_id: dict[str, dict[str, Any]] = {}
    for row, diagnostic in zip(permitted_rows, diagnostics, strict=True):
        diagnostic_by_id[row["id"]] = {
            "record_id": row["id"],
            "split": row["split"],
            **diagnostic.as_dict(),
        }
    tokenization_path = run_dir / "tokenization_diagnostics.csv"
    tokenization_path.parent.mkdir(parents=True, exist_ok=True)
    with tokenization_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=(
                "record_id",
                "split",
                "input_index",
                "raw_token_count",
                "effective_token_count",
                "truncated",
                "truncated_token_count",
            ),
        )
        writer.writeheader()
        writer.writerows(diagnostic_by_id.values())

    embedding_entries: list[dict[str, Any]] = []
    for rows, embeddings in (
        (train_rows, train_embeddings),
        (validation_rows, validation_embeddings),
    ):
        for row, vector in zip(rows, embeddings.features, strict=True):
            raw_text = row["transcript"]
            cache_key = cache.key_for(raw_text, cache_settings)
            embedding_entries.append(
                {
                    "record_id": row["id"],
                    "split": row["split"],
                    "transcript_sha256": _sha256_bytes(raw_text.encode("utf-8", errors="strict")),
                    "cache_key": cache_key,
                    "embedding_sha256": _vector_sha256(vector),
                    "dimension": len(vector),
                    "tokenization": diagnostic_by_id[row["id"]],
                }
            )
    truncation_count = sum(bool(item["tokenization"]["truncated"]) for item in embedding_entries)
    embedding_manifest = {
        "schema_version": 1,
        "evaluation_status": "smoke_test/provisional",
        "data_status": "synthetic",
        "review_status": "pending_manual_review",
        "source_sha256": source_before,
        "model": encoder.model_manifest,
        "preprocessing": {
            "text_field": "transcript",
            "preprocessing_version": "transcript-only-v1",
            "unicode_policy": "strict UTF-8; preserve source code points; no Unicode normalization or translation",
            "prefix": E5_SMALL_CONFIG.prefix,
            "max_seq_length": E5_SMALL_CONFIG.max_seq_length,
            "truncation_policy": "right-truncate; per-text counts recorded before encoding",
            "truncated_record_count": truncation_count,
            "truncated_record_fraction": truncation_count / len(embedding_entries),
        },
        "package_versions": packages,
        "dependency_inputs": {
            "requirements": {
                "path": ".scratch/1999-connectome-demo/requirements-m2-2b-e5-windows.in",
                "sha256": _sha256_file(PROJECT_ROOT / ".scratch/1999-connectome-demo/requirements-m2-2b-e5-windows.in"),
            },
            "lock": {
                "path": ".scratch/1999-connectome-demo/requirements-m2-2b-e5-windows.lock",
                "sha256": _sha256_file(PROJECT_ROOT / ".scratch/1999-connectome-demo/requirements-m2-2b-e5-windows.lock"),
            },
        },
        "cache_settings": {
            "model_id": cache_settings.model_id,
            "revision": cache_settings.revision,
            "tokenizer_revision": cache_settings.tokenizer_revision,
            "model_file_sha256": [list(item) for item in cache_settings.model_file_sha256],
            "prefix": cache_settings.prefix,
            "preprocessing_version": cache_settings.preprocessing_version,
            "max_seq_length": cache_settings.max_seq_length,
            "truncation_policy": cache_settings.truncation_policy,
            "pooling": cache_settings.pooling,
            "normalize_embeddings": cache_settings.normalize_embeddings,
            "dtype": cache_settings.dtype,
            "output_dimension": cache_settings.output_dimension,
            "device": cache_settings.device,
            "batch_size": cache_settings.batch_size,
        },
        "splits": {"train": len(train_embeddings.features), "validation": len(validation_embeddings.features)},
        "test_text_count_processed": 0,
        "test_embedding_count": 0,
        "entries": embedding_entries,
    }
    _write_json(run_dir / "embedding_manifest.json", embedding_manifest)

    candidate_outputs: dict[str, dict[str, Any]] = {}
    prediction_rows: list[dict[str, Any]] = []
    candidate_report_paths: list[Path] = []
    candidate_checkpoint_paths: list[Path] = []

    for candidate in ("logistic_regression", "mlp", "pca_mlp"):
        started = time.perf_counter()
        if candidate == "pca_mlp":
            result = run_baseline(
                candidate,
                train_embeddings,
                validation_embeddings,
                label_order=LABEL_ORDER,
                seed=seed,
                pca_components=32,
                hidden_size=16,
                epochs=80,
                learning_rate=0.02,
            )
        elif candidate == "mlp":
            result = run_baseline(
                candidate,
                train_embeddings,
                validation_embeddings,
                label_order=LABEL_ORDER,
                seed=seed,
                hidden_size=16,
                epochs=80,
                learning_rate=0.02,
            )
        else:
            result = run_baseline(
                candidate,
                train_embeddings,
                validation_embeddings,
                label_order=LABEL_ORDER,
                seed=seed,
            )
        elapsed = time.perf_counter() - started
        checkpoint_path = run_dir / f"m2-{candidate}-checkpoint.joblib"
        checkpoint_manifest = _write_baseline_checkpoint(
            checkpoint_path,
            result,
            train_embeddings,
            validation_embeddings,
            registration,
            source_before,
        )
        candidate_checkpoint_paths.append(checkpoint_path)
        candidate_outputs[candidate] = _record_candidate(
            run_dir,
            candidate,
            train_rows,
            validation_rows,
            result.train_predictions,
            result.validation_predictions,
            result.train_logits,
            result.validation_logits,
            {
                "fit_transform_predict_wall_seconds": elapsed,
                "parameters": result.parameters,
                "checkpoint": checkpoint_manifest,
            },
            prediction_rows,
            candidate_report_paths,
        )

    started = time.perf_counter()
    lda_result = run_lda_logistic_baseline(train_embeddings, validation_embeddings, seed=seed)
    lda_elapsed = time.perf_counter() - started
    checkpoint_manifest = _write_lda_checkpoint(
        run_dir / "m2-3-lda-logistic-checkpoint.joblib",
        lda_result,
        validation_embeddings,
        registration,
        source_before,
    )
    candidate_outputs["lda_logistic_regression"] = _record_candidate(
        run_dir,
        "lda_logistic_regression",
        train_rows,
        validation_rows,
        lda_result.train_predictions,
        lda_result.validation_predictions,
        lda_result.train_logits,
        lda_result.validation_logits,
        {
            "wall_seconds": lda_elapsed,
            "timings_seconds": lda_result.timings_seconds,
            "parameters": lda_result.parameters,
            "checkpoint": checkpoint_manifest,
        },
        prediction_rows,
        candidate_report_paths,
    )

    _write_predictions(run_dir / "predictions.csv", prediction_rows)
    result_metrics = {
        "schema_version": 1,
        "evaluation_status": "smoke_test/provisional",
        "data_status": "synthetic",
        "review_status": "pending_manual_review",
        "label_order": list(LABEL_ORDER),
        "candidate_settings_fingerprint": registration["configuration_fingerprint"],
        "candidates": candidate_outputs,
        "test": {"status": "not_run", "input_count": 0, "prediction_count": 0, "metrics": None},
    }
    _write_json(run_dir / "metrics.json", result_metrics)

    final_source_hashes = _source_hashes()
    if source_before != final_source_hashes:
        raise RuntimeError("formal source files changed during the train/validation run.")
    post_run_resources = _resource_gate(snapshot)
    cache_after_bytes = sum(path.stat().st_size for path in CACHE_ROOT.rglob("*") if path.is_file())
    cache_output_bytes = max(0, cache_after_bytes - cache_before_bytes)
    environment = {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "packages": packages,
        "device": "cpu",
        "torch_cuda_available": False,
    }
    resource_record = {
        "before_model_load": preflight_resources,
        "after_model_load": model_loaded_resources,
        "after_embedding": after_embedding_resources,
        "after_run": post_run_resources,
        "model_load_seconds": model_load_seconds,
        "tokenization_diagnostics_seconds": tokenization_seconds,
        "embedding_seconds": embedding_seconds,
        "loader_seconds": loader_seconds,
        "peak_working_set_bytes": post_run_resources["process_peak_working_set_bytes"],
        "peak_pagefile_bytes": post_run_resources["process_peak_pagefile_bytes"],
        "cache_bytes_added": cache_output_bytes,
        "cache_bytes_total": cache_after_bytes,
        "project_disk_free_before_bytes": preflight_resources["project_disk_free_bytes"],
        "project_disk_free_after_bytes": post_run_resources["project_disk_free_bytes"],
        "disk_reserve_bytes": MIN_FREE_DISK_BYTES,
        "rss_stop_threshold_bytes": MAX_PROCESS_RSS_BYTES,
    }
    report = _render_overall_report(run_dir, candidate_outputs, resource_record, bundle.audit_summary)
    (run_dir / "report.md").write_text(report, encoding="utf-8")

    output_paths = [
        run_dir / "pre_registered_candidates.json",
        run_dir / "embedding_manifest.json",
        run_dir / "tokenization_diagnostics.csv",
        run_dir / "metrics.json",
        run_dir / "predictions.csv",
        run_dir / "report.md",
        run_dir / "m2-3-lda-logistic-checkpoint.joblib",
        *candidate_report_paths,
        *candidate_checkpoint_paths,
    ]
    output_checksums = {
        path.relative_to(PROJECT_ROOT).as_posix(): {
            "sha256": _sha256_file(path),
            "bytes": path.stat().st_size,
        }
        for path in output_paths
    }
    manifest = {
        "run_id": run_dir.name,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "evaluation_status": "smoke_test",
        "result_status": "provisional",
        "data_status": "synthetic",
        "review_status": "pending_manual_review",
        "dataset_source": "formal_dataset_v1.0.0",
        "dataset_source_paths": {key: value.relative_to(PROJECT_ROOT).as_posix() for key, value in _source_paths().items()},
        "source_sha256_before": source_before,
        "source_sha256_after": final_source_hashes,
        "source_checksums_unchanged": source_before == final_source_hashes,
        "dataset_audit": bundle.audit_summary,
        "model_manifest": encoder.model_manifest,
        "package_versions": packages,
        "dependency_inputs": {
            "requirements": {
                "path": ".scratch/1999-connectome-demo/requirements-m2-2b-e5-windows.in",
                "sha256": _sha256_file(PROJECT_ROOT / ".scratch/1999-connectome-demo/requirements-m2-2b-e5-windows.in"),
            },
            "lock": {
                "path": ".scratch/1999-connectome-demo/requirements-m2-2b-e5-windows.lock",
                "sha256": _sha256_file(PROJECT_ROOT / ".scratch/1999-connectome-demo/requirements-m2-2b-e5-windows.lock"),
            },
        },
        "environment": environment,
        "resource_measurements": resource_record,
        "split_inputs": {"train": len(train_rows), "validation": len(validation_rows)},
        "family_overlap_count": 0,
        "test": {
            "status": "not_run",
            "transcript_count_passed_to_tokenizer": 0,
            "embedding_count": 0,
            "prediction_count": 0,
            "metrics": None,
        },
        "candidate_settings_fingerprint": registration["configuration_fingerprint"],
        "checkpoint_reload_verified": all(
            entry.get("checkpoint", {}).get("reload_prediction_match") is True
            and entry.get("checkpoint", {}).get("reload_score_array_exact_match") is True
            for entry in candidate_outputs.values()
        ),
        "code_sha256": {
            "runner": _sha256_file(Path(__file__)),
            "e5_runtime": _sha256_file(SRC_ROOT / "flycall_data/e5_runtime.py"),
            "embedding_pipeline": _sha256_file(SRC_ROOT / "flycall_data/embedding_pipeline.py"),
            "lda_baseline": _sha256_file(SRC_ROOT / "flycall_data/lda_baseline.py"),
            "evaluation": _sha256_file(SRC_ROOT / "flycall_data/evaluation.py"),
        },
        "outputs": output_checksums,
    }
    _write_json(run_dir / "run_manifest.json", manifest)
    print(json.dumps({"run_dir": str(run_dir), "metrics": result_metrics, "resources": resource_record}, ensure_ascii=True, indent=2))


def _record_candidate(
    run_dir: Path,
    candidate: str,
    train_rows: list[dict[str, Any]],
    validation_rows: list[dict[str, Any]],
    train_predictions: Sequence[str],
    validation_predictions: Sequence[str],
    train_logits: Sequence[Sequence[float]],
    validation_logits: Sequence[Sequence[float]],
    details: dict[str, Any],
    prediction_rows: list[dict[str, Any]],
    candidate_report_paths: list[Path],
) -> dict[str, Any]:
    train_batch = _prediction_batch("train", train_rows, train_predictions)
    validation_batch = _prediction_batch("validation", validation_rows, validation_predictions)
    report = evaluate_predictions(
        train_batch,
        validation_batch,
        candidate_name=candidate,
        label_order=LABEL_ORDER,
        data_status="synthetic",
    )
    report["splits"]["train"]["fit_record_count"] = len(train_batch.record_ids)
    report["splits"]["validation"]["transform_record_count"] = len(validation_batch.record_ids)
    candidate_report = run_dir / "candidate_reports" / f"{candidate}.md"
    candidate_report.parent.mkdir(parents=True, exist_ok=True)
    candidate_report.write_text(render_markdown_report(report), encoding="utf-8")
    candidate_report_paths.append(candidate_report)

    for split, rows, predictions, logits_by_row in (
        ("train", train_rows, train_predictions, train_logits),
        ("validation", validation_rows, validation_predictions, validation_logits),
    ):
        for row, prediction, logits in zip(rows, predictions, logits_by_row, strict=True):
            record = {
                "candidate": candidate,
                "split": split,
                "record_id": row["id"],
                "expected": row["label_id"],
                "predicted": prediction,
            }
            record.update({f"logit_{label}": float(value) for label, value in zip(LABEL_ORDER, logits, strict=True)})
            prediction_rows.append(record)
    return {"report": report, **details}


def _render_overall_report(
    run_dir: Path,
    candidates: dict[str, dict[str, Any]],
    resources: dict[str, Any],
    audit: dict[str, Any],
) -> str:
    lines = [
        "# M2.2b / M2.3 E5 provisional train/validation run",
        "",
        "- Status: `smoke_test` / `provisional`",
        "- Dataset: synthetic; `review_status=pending_manual_review`",
        "- E5: `intfloat/multilingual-e5-small` at the pinned revision; frozen CPU inference, batch size 1.",
        "- Split: frozen manifest train/validation only; no re-split.",
        "- Test: `not_run`; no test transcript entered tokenizer, encoder, cache, fit, transform, predict, or metrics.",
        "- Model candidates and settings were registered before the dataset was loaded; no validation tuning was performed.",
        "",
        "## Split audit",
        "",
        f"- Records: {audit['record_count']}",
        f"- Train: {audit['split_counts']['train']}; validation: {audit['split_counts']['validation']}; test audit count: {audit['split_counts']['test']}.",
        "- Model inputs: 700 train and 150 validation records; 0 test records.",
        "- Family split isolation: verified by the frozen loader and model batch contracts.",
        "",
        "## Candidate comparison",
        "",
        "| Candidate | Train accuracy | Train Macro-F1 | Validation accuracy | Validation Macro-F1 | Fit/transform timing |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for candidate, entry in candidates.items():
        report = entry["report"]
        train_metrics = report["splits"]["train"]["metrics"]
        validation_metrics = report["splits"]["validation"]["metrics"]
        timings = entry.get("timings_seconds") or {
            "fit_transform_predict_wall_seconds": entry.get("fit_transform_predict_wall_seconds", entry.get("wall_seconds"))
        }
        timing_text = ", ".join(f"{name}={value:.4f}s" for name, value in timings.items() if isinstance(value, (int, float)))
        lines.append(
            f"| {candidate} | {train_metrics['accuracy']:.4f} | {train_metrics['macro_f1']:.4f} | "
            f"{validation_metrics['accuracy']:.4f} | {validation_metrics['macro_f1']:.4f} | {timing_text} |"
        )
    lines.extend(
        [
            "",
            "Full fixed-order logits and predictions are in `predictions.csv`; per-class metrics, supports, confusion matrices, and error record IDs are in `metrics.json` and `candidate_reports/`.",
            "",
            "## Runtime and resource measurements",
            "",
            f"- Model load: {resources['model_load_seconds']:.2f}s; tokenization diagnostics: {resources['tokenization_diagnostics_seconds']:.2f}s; embeddings: {resources['embedding_seconds']:.2f}s.",
            f"- Peak process working set: {resources['peak_working_set_bytes'] / 1024**3:.3f} GiB; peak pagefile: {resources['peak_pagefile_bytes'] / 1024**3:.3f} GiB.",
            f"- Cache added: {resources['cache_bytes_added']} bytes; cache total: {resources['cache_bytes_total']} bytes.",
            f"- Project disk free: {resources['project_disk_free_before_bytes']} bytes before and {resources['project_disk_free_after_bytes']} bytes after; 4 GiB reserve preserved.",
            "",
            "## Limits",
            "",
            "The dataset is synthetic and has not passed manual review. These train/validation values are workflow smoke results, not formal model performance. Do not use them to claim real 1999 service outcomes or to unlock the test set.",
            "",
            "## Artifacts",
            "",
            "- `pre_registered_candidates.json` — fixed candidate settings and configuration fingerprint.",
            "- `embedding_manifest.json` — model/checksum/package contract, source hashes, per-record cache/output hashes and token counts.",
            "- `tokenization_diagnostics.csv` — train/validation token counts and explicit truncation flags.",
            "- `predictions.csv` — train/validation predictions and fixed-order logits only.",
            "- Four `m2-<candidate>-checkpoint.joblib` artifacts — model settings, source/configuration fingerprints, and reload-verified predictor objects.",
            "- `m2-3-lda-logistic-checkpoint.joblib` — reloaded and checked against saved validation predictions and scores.",
            "- `run_manifest.json` — resource data, source checksums, environment and output checksums.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--snapshot-dir",
        type=Path,
        default=Path(os.environ["E5_SNAPSHOT"]) if os.environ.get("E5_SNAPSHOT") else None,
        required=os.environ.get("E5_SNAPSHOT") is None,
        help="Local directory for the exact pinned E5 snapshot; network access is not used.",
    )
    parser.add_argument("--output-parent", type=Path, default=OUTPUT_PARENT)
    parser.add_argument("--run-id", help="unique run directory name; defaults to a UTC timestamp")
    parser.add_argument("--seed", type=int, default=42, help="positive training seed registered before data loading")
    args = parser.parse_args()
    if args.seed < 1:
        parser.error("--seed must be a positive integer")
    run_id = args.run_id or (
        f"m2-2b-e5-provisional-seed-{args.seed}-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    )
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", run_id):
        parser.error("--run-id may contain only letters, numbers, dot, underscore, and hyphen")
    run_dir = Path(args.output_parent) / run_id
    try:
        run(Path(args.snapshot_dir), run_dir, seed=args.seed)
    except Exception as error:
        if run_dir.exists() and not (run_dir / "run_manifest.json").exists():
            _write_json(
                run_dir / "execution_failure.json",
                {
                    "run_id": run_id,
                    "status": "failed",
                    "created_at_utc": datetime.now(timezone.utc).isoformat(),
                    "error_type": type(error).__name__,
                    "error": str(error),
                },
            )
        raise


if __name__ == "__main__":
    main()

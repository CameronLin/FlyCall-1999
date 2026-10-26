#!/usr/bin/env python3
"""Run the pre-registered, CPU-only, train/validation Fly A/B experiment."""

from __future__ import annotations

import argparse
import csv
import ctypes
import hashlib
import json
import math
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from dataclasses import replace
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from flycall_data.evaluation import LABEL_ORDER  # noqa: E402
from flycall_data.e5_runtime import E5_MODEL_FILE_SHA256  # noqa: E402
from flycall_data.fly_ab_training import (  # noqa: E402
    TrainingConfig,
    load_fly_a_checkpoint,
    load_fly_b_checkpoint,
    train_fly_a,
    train_fly_b,
)
from flycall_data.loader import DatasetPaths, load_frozen_dataset  # noqa: E402
from flycall_data.m32_inputs import (  # noqa: E402
    M32GraphPaths,
    M32InputGateError,
    _sha256_manifest,
    load_m32_embedding_splits,
    load_m32_graph,
    verify_m32_graph_provenance,
)
from flycall_data.model_config import E5_SMALL_CONFIG  # noqa: E402


DATASET_PATHS = DatasetPaths(
    jsonl_path=PROJECT_ROOT / "data/1999_synthetic/formal/v1.0.0/formal_dataset_v1.0.0.jsonl",
    csv_path=PROJECT_ROOT / "data/1999_synthetic/formal/v1.0.0/formal_dataset_v1.0.0.csv",
    taxonomy_path=PROJECT_ROOT / "data/1999_synthetic/taxonomy/current/taxonomy_v1.3.yaml",
    frozen_manifest_path=PROJECT_ROOT
    / "data/1999_synthetic/taxonomy/current/formal_split_manifest_frozen_v1.0.yaml",
)
GRAPH_PATHS = M32GraphPaths(
    graph_dir=PROJECT_ROOT / "data/connectome/derived/malecns_v1.0/subgraphs/engineering-demo-v1.0",
    io_manifest_path=PROJECT_ROOT
    / ".scratch/1999-connectome-demo/m1-3/engineering-demo-io-v1.0-20261016/io_manifest.json",
)
E5_RUN_DIR = PROJECT_ROOT / ".scratch/1999-connectome-demo/runs/m2-2b-e5-provisional-20261026T015843Z"
E5_EMBEDDING_MANIFEST = E5_RUN_DIR / "embedding_manifest.json"
E5_CACHE_ROOT = PROJECT_ROOT / ".scratch/1999-connectome-demo/caches/m2-2b-e5-small"
LOCK_PATH = PROJECT_ROOT / ".scratch/1999-connectome-demo/requirements-m3-2-fly-ab-windows.lock"
REQUIREMENTS_PATH = PROJECT_ROOT / ".scratch/1999-connectome-demo/requirements-m3-2-fly-ab-windows.in"
OUTPUT_PARENT = PROJECT_ROOT / ".scratch/1999-connectome-demo/runs"

MIN_FREE_DISK_BYTES = 4 * 1024**3
MIN_AVAILABLE_RAM_BYTES = 1 * 1024**3
MAX_PROCESS_RSS_BYTES = int(3.5 * 1024**3)
TRAINING_CONFIG = TrainingConfig(
    seed=42,
    batch_size=32,
    max_epochs=100,
    patience=10,
    learning_rate=1e-3,
    gradient_clip_norm=1.0,
    torch_threads=1,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _display_path(path: Path) -> str:
    try:
        display = Path(path).resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        display = str(path)
    return display.encode("ascii", errors="backslashreplace").decode("ascii")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha256_json(value: Any) -> str:
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _dataset_paths() -> dict[str, Path]:
    return {
        "jsonl": DATASET_PATHS.jsonl_path,
        "csv": DATASET_PATHS.csv_path,
        "taxonomy": DATASET_PATHS.taxonomy_path,
        "manifest": DATASET_PATHS.frozen_manifest_path,
    }


def _code_hashes() -> dict[str, str]:
    paths = {
        "runner": Path(__file__).resolve(),
        "inputs": SRC_ROOT / "flycall_data/m32_inputs.py",
        "trainer": SRC_ROOT / "flycall_data/fly_ab_training.py",
        "graph_core": SRC_ROOT / "flycall_data/graph_core.py",
        "loader": SRC_ROOT / "flycall_data/loader.py",
        "evaluation": SRC_ROOT / "flycall_data/evaluation.py",
    }
    return {name: _sha256_file(path) for name, path in paths.items()}


def _candidate_registration(training_config: TrainingConfig = TRAINING_CONFIG) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "status": "pre_registered",
        "locked_before_dataset_load": True,
        "data_status": "synthetic",
        "review_status": "pending_manual_review",
        "evaluation_status": "smoke_test/provisional",
        "graph": {
            "node_count": 500,
            "edge_count": 2216,
            "ordered_input_count": 32,
            "ordered_output_count": 32,
            "steps": 2,
            "pinned_m12_manifest_sha256": "5300c6cefdc6b84a854545e64f4131baa3fc42f0bde97a83f68fcc1c3769cf40",
            "pinned_m13_io_manifest_sha256": "48148a1d64cc5402b17db99dff61ad42a3c29bef8d422ebfa6a25e375e07f585",
            "aggregation": "source_to_target; fixed indegree normalization including self loops",
            "edge_prior": "per-target-mean-one-log1p inverse-softplus; epsilon=1e-6",
        },
        "embedding": {
            "run_id": E5_RUN_DIR.name,
            "manifest": str(E5_EMBEDDING_MANIFEST.relative_to(PROJECT_ROOT)),
            "cache_root": str(E5_CACHE_ROOT.relative_to(PROJECT_ROOT)),
            "model_id": E5_SMALL_CONFIG.model_id,
            "revision": E5_SMALL_CONFIG.revision,
            "tokenizer_revision": E5_SMALL_CONFIG.revision,
            "prefix": E5_SMALL_CONFIG.prefix,
            "max_seq_length": E5_SMALL_CONFIG.max_seq_length,
            "pooling": E5_SMALL_CONFIG.pooling,
            "normalize_embeddings": E5_SMALL_CONFIG.normalize_embeddings,
            "model_file_sha256": [list(item) for item in E5_MODEL_FILE_SHA256],
            "train_count": 700,
            "validation_count": 150,
            "dimension": 384,
            "test_embeddings": "prohibited",
        },
        "training": {
            "candidate_name": f"fly_a_to_fly_b_m3_2_seed_{training_config.seed}",
            "seed": training_config.seed,
            "batch_size": training_config.batch_size,
            "max_epochs": training_config.max_epochs,
            "patience": training_config.patience,
            "optimizer": "Adam",
            "learning_rate": training_config.learning_rate,
            "gradient_clip_norm": training_config.gradient_clip_norm,
            "device": "cpu",
            "torch_threads": training_config.torch_threads,
            "fly_a_objective": "train-only pairwise distance preserving loss",
            "fly_a_selection": "minimum full-validation distance stress; earliest epoch wins exact tie",
            "fly_b_objective": "train-only cross entropy with frozen selected Fly A",
            "fly_b_selection": "validation macro-F1, then lower validation loss, then earliest epoch",
            "label_order": list(LABEL_ORDER),
        },
        "test": "not_run; no test transcript, embedding, prediction, or metric",
        "selection_rule": "No setting may be changed after this registration based on validation results.",
    }


def _package_versions() -> dict[str, str]:
    result: dict[str, str] = {}
    for package in ("numpy", "pyarrow", "torch"):
        try:
            result[package] = version(package)
        except PackageNotFoundError:
            result[package] = "not-installed"
    return result


def _windows_resources() -> dict[str, int]:
    if os.name != "nt":
        raise RuntimeError("M3.2 resource-gated runner requires Windows.")

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

    memory = MemoryStatus()
    memory.dwLength = ctypes.sizeof(memory)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(memory)):
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
        "total_physical_ram_bytes": int(memory.ullTotalPhys),
        "available_ram_bytes": int(memory.ullAvailPhys),
        "available_commit_bytes": int(memory.ullAvailPageFile),
        "memory_load_percent": int(memory.dwMemoryLoad),
        "process_peak_working_set_bytes": int(counters.PeakWorkingSetSize),
        "process_peak_pagefile_bytes": int(counters.PeakPagefileUsage),
    }


def _resource_gate() -> dict[str, int]:
    resources = _windows_resources()
    free_disk = shutil.disk_usage(PROJECT_ROOT).free
    resources["project_disk_free_bytes"] = int(free_disk)
    if resources["available_ram_bytes"] < MIN_AVAILABLE_RAM_BYTES:
        raise RuntimeError("M3.2 stopped: available physical RAM is below 1 GiB.")
    if resources["available_commit_bytes"] < MIN_AVAILABLE_RAM_BYTES:
        raise RuntimeError("M3.2 stopped: available commit is below 1 GiB.")
    if resources["memory_load_percent"] >= 90:
        raise RuntimeError("M3.2 stopped: Windows memory load reached 90%.")
    if resources["process_peak_working_set_bytes"] > MAX_PROCESS_RSS_BYTES:
        raise RuntimeError("M3.2 stopped: process peak working set exceeded 3.5 GiB.")
    if free_disk < MIN_FREE_DISK_BYTES:
        raise RuntimeError("M3.2 stopped: less than 4 GiB of project disk space remains.")
    return resources


def _current_git_commit() -> str | None:
    git_executable = shutil.which("git")
    if git_executable is None and os.name == "nt":
        candidates = (
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "Git/cmd/git.exe",
            Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Git/cmd/git.exe",
        )
        git_executable = next((str(path) for path in candidates if path.is_file()), None)
    if git_executable is None:
        return None
    try:
        completed = subprocess.run(
            [git_executable, "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            check=True,
            text=True,
            encoding="utf-8",
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return completed.stdout.strip()


def _write_report(path: Path, manifest: dict[str, Any], *, error: str | None = None) -> None:
    lines = [
        "# M3.2 Fly A/B provisional train-validation run",
        "",
        f"- Run ID: `{manifest['run_id']}`",
        f"- Status: `{manifest['status']}`",
        "- Data: synthetic; manual review pending; provisional only.",
        "- Test: `not_run`; no test transcript, embedding, prediction, or metric.",
    ]
    if error:
        lines.extend(["", "## Stopped at gate", "", error])
    else:
        summary = manifest["summary"]
        lines.extend(
            [
                "",
                "## Selected checkpoints",
                "",
                f"- Fly A epoch: {summary['fly_a']['selected_epoch']}; validation distance stress: "
                f"{summary['fly_a']['validation_distance_stress']:.8f}.",
                f"- Fly B epoch: {summary['fly_b']['selected_epoch']}; validation Macro-F1: "
                f"{summary['fly_b']['validation_macro_f1']:.6f}.",
                f"- Fly A parameters: {summary['fly_a']['parameter_counts']}; "
                f"Fly B parameters: {summary['fly_b']['parameter_counts']}.",
                "- Checkpoint reload comparison: validation representations/logits match within `1e-6`.",
                "",
                "## Classification metrics",
                "",
            ]
        )
        split_reports = manifest["classification_metrics"]["splits"]
        for split_name in ("train", "validation"):
            split_report = split_reports[split_name]
            metrics = split_report["metrics"]
            lines.extend(
                [
                    f"### {split_name.title()} (n={split_report['n_records']})",
                    "",
                    f"Accuracy: {metrics['accuracy']:.4f}; Macro-F1: {metrics['macro_f1']:.4f}.",
                    "",
                    "| Label | Precision | Recall | F1 | Support |",
                    "|---|---:|---:|---:|---:|",
                ]
            )
            for label in LABEL_ORDER:
                item = metrics["per_class"][label]
                lines.append(
                    f"| `{label}` | {item['precision']:.4f} | {item['recall']:.4f} | "
                    f"{item['f1']:.4f} | {item['support']} |"
                )
            matrix_rows = ["| Actual / Predicted | " + " | ".join(f"`{label}`" for label in LABEL_ORDER) + " |", "|---|" + "---:|" * len(LABEL_ORDER)]
            for label, row in zip(LABEL_ORDER, metrics["confusion_matrix"], strict=True):
                matrix_rows.append("| `" + label + "` | " + " | ".join(str(value) for value in row) + " |")
            lines.extend(["", "Confusion matrix (rows: actual; columns: predicted):", "", *matrix_rows, ""])
        lines.extend(["Classification details are also saved in `metrics.json`."])
    lines.extend(["", "## Provenance and limits", "", "See `run_manifest.json` for source hashes, resource readings, timings, dependency versions and locked configuration."])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _verify_e5_run_bundle() -> tuple[dict[str, Any], dict[str, Any], str]:
    try:
        run_manifest = json.loads((E5_RUN_DIR / "run_manifest.json").read_text(encoding="utf-8"))
        embedding_manifest = json.loads(E5_EMBEDDING_MANIFEST.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise M32InputGateError(f"the pinned M2.2b E5 run bundle is unreadable: {error}") from error
    expected_run = "m2-2b-e5-provisional-20261026T015843Z"
    if run_manifest.get("run_id") != expected_run:
        raise M32InputGateError("the selected E5 cache is not the corrected pinned M2.2b run.")
    if (
        run_manifest.get("data_status") != "synthetic"
        or run_manifest.get("review_status") != "pending_manual_review"
        or run_manifest.get("result_status") != "provisional"
        or run_manifest.get("evaluation_status") != "smoke_test"
        or run_manifest.get("checkpoint_reload_verified") is not True
        or run_manifest.get("source_checksums_unchanged") is not True
    ):
        raise M32InputGateError("the pinned E5 run manifest is incomplete or has an unexpected status.")
    test = run_manifest.get("test")
    if not isinstance(test, dict) or test.get("status") != "not_run" or any(
        test.get(key) not in (0, None)
        for key in ("transcript_count_passed_to_tokenizer", "embedding_count", "prediction_count")
    ):
        raise M32InputGateError("the pinned E5 run manifest does not prove that test remained unused.")
    artifact_key = E5_EMBEDDING_MANIFEST.relative_to(PROJECT_ROOT).as_posix()
    file_records = run_manifest.get("outputs")
    artifact_record = file_records.get(artifact_key) if isinstance(file_records, dict) else None
    embedding_manifest_sha256 = _sha256_file(E5_EMBEDDING_MANIFEST)
    if not isinstance(artifact_record, dict) or artifact_record.get("sha256") != embedding_manifest_sha256:
        raise M32InputGateError("the corrected E5 run manifest checksum does not match its embedding manifest.")
    if embedding_manifest.get("evaluation_status") != "smoke_test/provisional":
        raise M32InputGateError("the pinned E5 embedding manifest is not provisional.")
    return run_manifest, embedding_manifest, embedding_manifest_sha256


def _failure(
    run_dir: Path,
    run_manifest: dict[str, Any],
    *,
    phase: str,
    error: Exception,
) -> int:
    blocked = isinstance(error, (M32InputGateError, ImportError, ModuleNotFoundError))
    run_manifest.update(
        {
            "status": "blocked" if blocked else "failed",
            "stopped_at_phase": phase,
            "error_type": type(error).__name__,
            "error": str(error),
            "finished_at_utc": _now(),
            "test": {"status": "not_run", "model_inputs": 0, "metrics": "not_run"},
        }
    )
    _write_json(run_dir / "run_manifest.json", run_manifest)
    _write_report(run_dir / "report.md", run_manifest, error=f"`{phase}`: {error}")
    print(f"M3.2 {run_manifest['status']} at {phase}: {error}", file=sys.stderr)
    print(f"Run artifacts: {_display_path(run_dir)}", file=sys.stderr)
    return 2 if blocked else 1


def _write_predictions(
    path: Path,
    *,
    model_a: Any,
    model_b: Any,
    splits: Sequence[Any],
) -> None:
    fields = ["split", "record_id", "family_id", "expected_label", "predicted_label"]
    fields.extend(f"logit_{label}" for label in LABEL_ORDER)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        import torch

        model_a.eval()
        model_b.eval()
        with torch.no_grad():
            for split in splits:
                if split.split not in {"train", "validation"}:
                    raise ValueError("prediction export accepts train and validation only.")
                logits = model_b(model_a(split.embeddings))
                predictions = logits.argmax(dim=1).tolist()
                for index, predicted in enumerate(predictions):
                    row: dict[str, Any] = {
                        "split": split.split,
                        "record_id": split.record_ids[index],
                        "family_id": split.family_ids[index],
                        "expected_label": split.labels[index],
                        "predicted_label": LABEL_ORDER[predicted],
                    }
                    row.update(
                        {f"logit_{label}": float(logits[index, label_index]) for label_index, label in enumerate(LABEL_ORDER)}
                    )
                    writer.writerow(row)


def _validate_inputs_unchanged(graph_hashes: dict[str, str], dataset_hashes: dict[str, str]) -> None:
    graph_paths = {
        "graph_manifest": GRAPH_PATHS.graph_manifest_path,
        "io_manifest": GRAPH_PATHS.io_manifest_path,
        "nodes_parquet": GRAPH_PATHS.nodes_path,
        "edges_parquet": GRAPH_PATHS.edges_path,
    }
    for name, path in graph_paths.items():
        observed = _sha256_file(path) if name in {"nodes_parquet", "edges_parquet"} else _sha256_manifest(path)
        if observed != graph_hashes[name]:
            raise M32InputGateError(f"pinned graph input changed during the M3.2 run: {name}.")
    for name, path in _dataset_paths().items():
        if _sha256_file(path) != dataset_hashes[name]:
            raise RuntimeError(f"frozen dataset source changed during the M3.2 run: {name}.")


def _run(run_dir: Path, run_id: str, training_config: TrainingConfig = TRAINING_CONFIG) -> int:
    run_dir.mkdir(parents=True, exist_ok=False)
    registration = _candidate_registration(training_config)
    registration["configuration_fingerprint"] = _sha256_json(registration)
    _write_json(run_dir / "pre_registered_candidates.json", registration)
    run_manifest: dict[str, Any] = {
        "schema_version": 1,
        "run_id": run_id,
        "status": "pre_registered",
        "created_at_utc": _now(),
        "git_commit": _current_git_commit(),
        "configuration_fingerprint": registration["configuration_fingerprint"],
        "candidate_registration": "pre_registered_candidates.json",
        "code_sha256": _code_hashes(),
        "dependency_inputs": {
            "requirements": {"path": str(REQUIREMENTS_PATH.relative_to(PROJECT_ROOT)), "sha256": _sha256_file(REQUIREMENTS_PATH)},
            "lock": {"path": str(LOCK_PATH.relative_to(PROJECT_ROOT)), "sha256": _sha256_file(LOCK_PATH)},
        },
        "environment": {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "machine": platform.machine(),
            "packages": _package_versions(),
            "device": "cpu",
        },
        "test": {"status": "not_run", "model_inputs": 0, "metrics": "not_run"},
    }
    _write_json(run_dir / "run_manifest.json", run_manifest)

    phase = "graph-provenance-preflight"
    started = time.perf_counter()
    try:
        graph_provenance = verify_m32_graph_provenance(GRAPH_PATHS)
        e5_run_manifest, e5_embedding_manifest, embedding_manifest_sha256 = _verify_e5_run_bundle()
        resources_before = _resource_gate()

        phase = "pinned-Parquet-read"
        graph, graph_hashes = load_m32_graph(GRAPH_PATHS)
        if graph_hashes != {
            "graph_manifest": graph_provenance["graph_manifest_sha256"],
            "io_manifest": graph_provenance["io_manifest_sha256"],
            "nodes_parquet": graph_provenance["nodes_sha256"],
            "edges_parquet": graph_provenance["edges_sha256"],
        }:
            raise M32InputGateError("graph checksums changed between provenance preflight and Parquet read.")

        phase = "frozen-dataset-contract"
        bundle = load_frozen_dataset(DATASET_PATHS)
        dataset_hashes = dict(bundle.audit_summary["source_sha256"])
        if e5_run_manifest.get("source_sha256_after") != dataset_hashes:
            raise M32InputGateError("the pinned M2.2b E5 run used different frozen dataset source checksums.")

        phase = "E5-cache-provenance"
        embedding_splits = load_m32_embedding_splits(
            bundle,
            embedding_manifest_path=E5_EMBEDDING_MANIFEST,
            cache_root=E5_CACHE_ROOT,
        )

        source_hashes = {
            **dataset_hashes,
            **graph_hashes,
            "embedding_manifest": embedding_manifest_sha256,
            "e5_model_files": _sha256_json(
                [list(item) for item in json.loads(E5_EMBEDDING_MANIFEST.read_text(encoding="utf-8"))["cache_settings"]["model_file_sha256"]]
            ),
            "e5_run_manifest": _sha256_file(E5_RUN_DIR / "run_manifest.json"),
            "m32_requirements": _sha256_file(REQUIREMENTS_PATH),
            "m32_lock": _sha256_file(LOCK_PATH),
        }
        source_hashes = dict(sorted(source_hashes.items()))
        run_manifest.update(
            {
                "status": "running",
                "source_sha256": source_hashes,
                "graph": {
                    "nodes": len(graph.node_ids),
                    "edges": len(graph.edges),
                    "input_node_ids": list(graph.input_node_ids),
                    "output_node_ids": list(graph.output_node_ids),
                    "steps": graph.steps,
                },
                "dataset_audit": {
                    "split_counts": dict(bundle.split_counts),
                    "label_split_counts": bundle.label_split_counts,
                    "family_overlap_count": 0,
                    "data_status": "synthetic",
                    "review_status": "pending_manual_review",
                },
                "embedding_counts": {"train": 700, "validation": 150, "test": 0},
                "embedding_settings": e5_embedding_manifest["cache_settings"],
                "resources_before_training": resources_before,
                "started_training_at_utc": _now(),
            }
        )
        _write_json(run_dir / "run_manifest.json", run_manifest)

        phase = "Fly-A-training"
        fly_a_path = run_dir / "fly-a-checkpoint.pt"
        fly_a = train_fly_a(
            graph,
            embedding_splits.train_for_a,
            embedding_splits.validation_for_a,
            checkpoint_path=fly_a_path,
            source_sha256=source_hashes,
            config=training_config,
        )

        phase = "Fly-B-training"
        source_hashes_b = dict(source_hashes)
        source_hashes_b["fly_a_checkpoint"] = fly_a.checkpoint_sha256
        fly_b_path = run_dir / "fly-b-checkpoint.pt"
        fly_b = train_fly_b(
            graph,
            embedding_splits.train_for_b,
            embedding_splits.validation_for_b,
            fly_a_checkpoint_path=fly_a_path,
            fly_a_source_sha256=source_hashes,
            source_sha256=source_hashes_b,
            checkpoint_path=fly_b_path,
            config=training_config,
            candidate_name=f"fly_a_to_fly_b_m3_2_seed_{training_config.seed}",
        )

        phase = "checkpoint-reload-comparison"
        fly_a_reloaded = load_fly_a_checkpoint(
            graph,
            int(embedding_splits.train_for_a.embeddings.shape[1]),
            fly_a_path,
            expected_source_sha256=source_hashes,
        )
        fly_b_reloaded = load_fly_b_checkpoint(
            graph,
            fly_b_path,
            expected_source_sha256=source_hashes_b,
        )
        import torch

        with torch.no_grad():
            validation_a_expected = fly_a.model(embedding_splits.validation_for_a.embeddings)
            validation_a_actual = fly_a_reloaded(embedding_splits.validation_for_a.embeddings)
            validation_b_expected = fly_b.model(validation_a_expected)
            validation_b_actual = fly_b_reloaded(validation_a_actual)
        if not torch.allclose(validation_a_expected, validation_a_actual, rtol=1e-6, atol=1e-6):
            raise RuntimeError("reloaded Fly A validation representation differs beyond 1e-6.")
        if not torch.allclose(validation_b_expected, validation_b_actual, rtol=1e-6, atol=1e-6):
            raise RuntimeError("reloaded Fly B validation logits differ beyond 1e-6.")

        phase = "artifact-finalization"
        graph_definition_path = run_dir / "graph_definition.json"
        _write_json(
            graph_definition_path,
            {
                "schema_version": 1,
                "node_ids": list(graph.node_ids),
                "input_node_ids": list(graph.input_node_ids),
                "output_node_ids": list(graph.output_node_ids),
                "edges": [list(edge) for edge in graph.edges],
                "steps": graph.steps,
                "source_sha256": source_hashes,
            },
        )
        _write_json(
            run_dir / "training_history.json",
            {"fly_a": list(fly_a.history), "fly_b": list(fly_b.history)},
        )
        _write_json(run_dir / "metrics.json", fly_b.evaluation)
        _write_predictions(
            run_dir / "predictions.csv",
            model_a=fly_a_reloaded,
            model_b=fly_b_reloaded,
            splits=(embedding_splits.train_for_b, embedding_splits.validation_for_b),
        )
        _validate_inputs_unchanged(graph_hashes, dataset_hashes)
        resources_after = _resource_gate()
        elapsed_seconds = time.perf_counter() - started
        summary = {
            "fly_a": {
                "selected_epoch": fly_a.selected_epoch,
                "validation_distance_stress": fly_a.best_validation_metric,
                "checkpoint": fly_a_path.name,
                "checkpoint_sha256": fly_a.checkpoint_sha256,
                "parameter_counts": fly_a.model.parameter_counts,
            },
            "fly_b": {
                "selected_epoch": fly_b.selected_epoch,
                "validation_macro_f1": fly_b.best_validation_metric,
                "checkpoint": fly_b_path.name,
                "checkpoint_sha256": fly_b.checkpoint_sha256,
                "parameter_counts": fly_b.model.parameter_counts,
            },
            "checkpoint_reload": {
                "status": "passed",
                "validation_representation_max_abs_diff": float(
                    torch.max(torch.abs(validation_a_expected - validation_a_actual))
                ),
                "validation_logits_max_abs_diff": float(
                    torch.max(torch.abs(validation_b_expected - validation_b_actual))
                ),
                "tolerance": {"rtol": 1e-6, "atol": 1e-6},
            },
        }
        output_paths = (
            run_dir / "pre_registered_candidates.json",
            graph_definition_path,
            fly_a_path,
            fly_b_path,
            run_dir / "training_history.json",
            run_dir / "metrics.json",
            run_dir / "predictions.csv",
        )
        output_records: dict[str, dict[str, Any]] = {}
        for output_path in output_paths:
            try:
                output_name = output_path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
            except ValueError:
                output_name = str(output_path.resolve())
            output_records[output_name] = {
                "bytes": output_path.stat().st_size,
                "sha256": _sha256_file(output_path),
            }
        run_manifest.update(
            {
                "status": "completed_provisional",
                "summary": summary,
                "classification_metrics": fly_b.evaluation,
                "outputs": output_records,
                "resources_after_training": resources_after,
                "elapsed_seconds": elapsed_seconds,
                "finished_at_utc": _now(),
                "test": {"status": "not_run", "model_inputs": 0, "metrics": "not_run"},
            }
        )
        _write_json(run_dir / "run_manifest.json", run_manifest)
        _write_report(run_dir / "report.md", run_manifest)
        print(f"M3.2 provisional run completed: {_display_path(run_dir)}")
        print(f"Fly A selected epoch {fly_a.selected_epoch}; Fly B selected epoch {fly_b.selected_epoch}.")
        return 0
    except Exception as error:
        run_manifest["elapsed_seconds"] = time.perf_counter() - started
        return _failure(run_dir, run_manifest, phase=phase, error=error)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", help="unique output directory name; defaults to a UTC timestamp")
    parser.add_argument("--output-parent", type=Path, default=OUTPUT_PARENT)
    parser.add_argument("--seed", type=int, default=42, help="positive training seed registered before data loading")
    args = parser.parse_args(argv)
    if args.seed < 1:
        parser.error("--seed must be a positive integer")
    run_id = args.run_id or f"m3-2-fly-ab-provisional-seed-{args.seed}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", run_id):
        parser.error("--run-id must be a simple directory name (letters, digits, dot, underscore, hyphen).")
    output_parent = args.output_parent.resolve()
    run_dir = output_parent / run_id
    try:
        return _run(run_dir, run_id, replace(TRAINING_CONFIG, seed=args.seed))
    except FileExistsError:
        print(f"Refusing to overwrite an existing run directory: {_display_path(run_dir)}", file=sys.stderr)
        return 2
    except OSError as error:
        print(f"Could not create M3.2 run directory {_display_path(run_dir)}: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

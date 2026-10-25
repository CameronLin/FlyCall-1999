#!/usr/bin/env python3
"""Run the M2.2a train/validation-only text baseline smoke test."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import resource
import shutil
import sys
import time
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from flycall_data.loader import DatasetPaths, load_frozen_dataset  # noqa: E402
from flycall_data.text_baseline import LABEL_ORDER, run_baselines, split_for_smoke  # noqa: E402


DATASET_PATHS = DatasetPaths(
    jsonl_path=PROJECT_ROOT / "data/1999_synthetic/formal/v1.0.0/formal_dataset_v1.0.0.jsonl",
    csv_path=PROJECT_ROOT / "data/1999_synthetic/formal/v1.0.0/formal_dataset_v1.0.0.csv",
    taxonomy_path=PROJECT_ROOT / "data/1999_synthetic/taxonomy/current/taxonomy_v1.3.yaml",
    frozen_manifest_path=PROJECT_ROOT
    / "data/1999_synthetic/taxonomy/current/formal_split_manifest_frozen_v1.0.yaml",
)
MIN_FREE_DISK_BYTES = 4 * 1024**3
DEFAULT_OUTPUT_PARENT = PROJECT_ROOT / ".scratch/1999-connectome-demo/runs"


def _physical_ram_bytes() -> int:
    return int(os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE"))


def _peak_rss_bytes() -> int:
    value = int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    return value if platform.system() == "Darwin" else value * 1024


def _sha256_json(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _require_disk_reserve(path: Path) -> int:
    free_bytes = shutil.disk_usage(path).free
    if free_bytes < MIN_FREE_DISK_BYTES:
        raise RuntimeError(
            f"Free disk fell below the 4 GiB reserve: {free_bytes} bytes available."
        )
    return free_bytes


def _metrics_table(results: list[Any]) -> str:
    lines = [
        "| 特徵 | 分類器 | split | 筆數 | Accuracy | Macro-F1 |",
        "|---|---|---|---:|---:|---:|",
    ]
    for result in results:
        for split_name, metrics in (
            ("train", result.train_metrics),
            ("validation", result.validation_metrics),
        ):
            lines.append(
                f"| {result.feature_kind} | {result.classifier_name} | {split_name} | "
                f"{sum(item['support'] for item in metrics['per_class'].values())} | "
                f"{metrics['accuracy']:.4f} | {metrics['macro_f1']:.4f} |"
            )
    return "\n".join(lines)


def _detailed_metrics(results: list[Any], label_names: dict[str, str]) -> str:
    sections: list[str] = []
    for result in results:
        sections.append(f"### {result.feature_kind} + {result.classifier_name}\n")
        sections.append(
            f"固定設定：`{json.dumps({'features': result.feature_parameters, 'classifier': result.classifier_parameters}, ensure_ascii=False, sort_keys=True)}`  "
        )
        sections.append(f"特徵數：{result.feature_count}。\n")
        for split_name, metrics in (
            ("Train", result.train_metrics),
            ("Validation", result.validation_metrics),
        ):
            sections.append(f"#### {split_name}\n")
            sections.append(
                "| label_id | label_name | Precision | Recall | F1 | Support |\n"
                "|---|---|---:|---:|---:|---:|"
            )
            for label_id in LABEL_ORDER:
                item = metrics["per_class"][label_id]
                sections.append(
                    f"| `{label_id}` | {label_names[label_id]} | {item['precision']:.4f} | {item['recall']:.4f} | "
                    f"{item['f1']:.4f} | {item['support']} |"
                )
            sections.append(
                "\nConfusion matrix（rows=actual, columns=predicted; label order follows the frozen taxonomy）:\n\n"
            )
            sections.append(
                "Labels: `" + "`, `".join(f"{key}={label_names[key]}" for key in LABEL_ORDER) + "`\n\n"
            )
            sections.append("```text\n")
            sections.extend(" ".join(str(value) for value in row) + "\n" for row in metrics["confusion_matrix"])
            sections.append("```\n")
    return "\n".join(sections)


def _write_predictions(
    path: Path,
    results: list[Any],
    label_by_id: dict[str, str],
) -> int:
    count = 0
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=(
                "candidate",
                "feature_kind",
                "classifier",
                "split",
                "record_id",
                "actual_label_id",
                "predicted_label_id",
                "dataset_status",
                "review_status",
                "result_status",
            ),
            lineterminator="\n",
        )
        writer.writeheader()
        for result in results:
            candidate = f"{result.feature_kind}+{result.classifier_name}"
            for split_name, record_ids, predictions in (
                ("train", result.train_record_ids, result.train_predictions),
                ("validation", result.validation_record_ids, result.validation_predictions),
            ):
                raise_if_missing = set(record_ids) - set(label_by_id)
                if raise_if_missing:
                    raise RuntimeError("Prediction labels missing for IDs: " + ", ".join(sorted(raise_if_missing)))
                for record_id, predicted in zip(record_ids, predictions, strict=True):
                    writer.writerow(
                        {
                            "candidate": candidate,
                            "feature_kind": result.feature_kind,
                            "classifier": result.classifier_name,
                            "split": split_name,
                            "record_id": record_id,
                            "actual_label_id": label_by_id[record_id],
                            "predicted_label_id": predicted,
                            "dataset_status": "synthetic",
                            "review_status": "pending_manual_review",
                            "result_status": "smoke_test/provisional",
                        }
                    )
                    count += 1
    return count


def _render_report(manifest: dict[str, Any], results: list[Any]) -> str:
    audit = manifest["dataset_audit"]
    return f"""# M2.2a 輕量文字分類基線 smoke test

狀態：`smoke_test`／`provisional`  
日期：{manifest['created_at_utc']}  
資料：正式合成資料 v1.0.0；全部 `review_status=pending_manual_review`。本報告不是正式效能結論。

## 使用界線

M2.1 `load_frozen_dataset()` 為契約稽核完整讀取 JSONL／CSV、taxonomy 與 frozen manifest，包含 test 列；本次再次載入僅用於前後契約／checksum 核對。模型流程只接收 train 與 validation 列。Test 列沒有進入 TF-IDF fit／transform、分類器 fit／predict、特徵比較、調參、指標或預測輸出；test 指標為 `not_run`。

模型輸入只有 `transcript`，保留逐字稿中的 `R:`／`L:` 標記。ID、label 名稱、scenario、scenario_family_id、split、review_status 及其他 metadata 不作為特徵。`scenario_family_id` 只用來稽核既有切分隔離。

## 資料契約與 split 核對

- M2.1 loader audit：{audit['record_count']} 筆、{audit['label_count']} 類、{audit['family_count']} 個 scenario families；taxonomy `{audit['taxonomy_version']}`、manifest `{audit['manifest_version']}`。
- 全體 split 配額（loader 契約稽核）：`{json.dumps(audit['split_counts'], ensure_ascii=False, sort_keys=True)}`。這是資料契約計數，不是 test 分類指標。
- 各 split 家族數（契約稽核）：`{json.dumps(manifest['family_counts_by_split_from_loader_audit'], ensure_ascii=False, sort_keys=True)}`。
- 模型輸入：train {manifest['model_splits']['train']['records']} 筆／{manifest['model_splits']['train']['family_count']} 家族；validation {manifest['model_splits']['validation']['records']} 筆／{manifest['model_splits']['validation']['family_count']} 家族。
- Train／validation 家族交集：{manifest['model_splits']['family_intersection_count']}；`scenario_family_id` 不跨 split。
- Test 模型輸入列、預測列、指標計算：均為 0／`not_run`。

## 固定實驗設定

- Label 順序與名稱：`{json.dumps(manifest['label_names'], ensure_ascii=False, sort_keys=True)}`。
- TF-IDF：字符 n-gram `(2, 5)` 與短字符片語 n-gram `(2, 4)`；`min_df=2`、`max_features=50000`、`sublinear_tf=true`、不轉小寫。片語候選以連續字符片段實作，未引入分詞套件。
- Classifiers：Logistic Regression (`C=1`, `lbfgs`, `max_iter=1000`) 與 Linear SVM (`C=1`, `dual=auto`, `max_iter=5000`)；固定 seed 42。候選組預先固定，無超參數搜尋。
- 向量器 vocabulary／IDF 只以 train fit；validation 僅 transform 與比較。
- 隔離環境：`{manifest['environment']['venv_path']}`；安裝方式 `{manifest['environment']['install_command']}`；僅 CPU wheel，沒有 GPU 套件或模型。
- 依賴版本：Python {manifest['environment']['python']}；scikit-learn {manifest['environment']['scikit_learn']}；NumPy {manifest['environment']['numpy']}；SciPy {manifest['environment']['scipy']}；joblib {manifest['environment']['joblib']}；threadpoolctl {manifest['environment']['threadpoolctl']}；narwhals {manifest['environment']['narwhals']}；cloudpickle {manifest['environment']['cloudpickle']}。
- 下載量上限 500 MiB；實際安裝時約下載 {manifest['environment']['downloaded_mib']} MiB；環境目錄大小 {manifest['environment']['venv_size_mib']} MiB。安裝前的 wheel 相容性檢查與套件版本詳列於鎖定檔及 ticket。
- CPU；實測實體 RAM {manifest['resources']['physical_ram_bytes']} bytes。

## Train／validation 摘要

{_metrics_table(results)}

## 分類指標與混淆矩陣

{_detailed_metrics(results, manifest['label_names'])}

## 執行資源與資料完整性

- M2.1 loader 稽核時間：{manifest['resources']['loader_elapsed_seconds']:.3f} 秒（含全資料契約檢查）。
- TF-IDF／模型 fit 與 train／validation 評估時間：{manifest['resources']['model_elapsed_seconds']:.3f} 秒。
- 程序峰值 RSS：{manifest['resources']['peak_rss_bytes']} bytes。
- 可用磁碟：執行前 {manifest['resources']['free_disk_before_bytes']} bytes；輸出後 {manifest['resources']['free_disk_after_bytes']} bytes；4 GiB 保留線通過：{manifest['resources']['disk_reserve_preserved']}。
- 正式 JSONL／CSV／taxonomy／frozen manifest 的 M2.1 audit SHA-256 前後一致：{manifest['source_checksums_unchanged']}。
- 完整設定及 source SHA-256 見 `run_manifest.json`；只含 train／validation 的預測見 `predictions.csv`。
- 依賴鎖定檔：`requirements-m2-2a-smoke.txt`；實際環境套件版本記錄於 manifest。

## 限制

資料仍未完成逐筆人工複核；分數只能用來確認低資源 pipeline 可運作與輸出形狀。不得解讀為正式模型效能、真實案件表現或可部署分類能力。Test split 僅被 M2.1 loader 用於 frozen data contract 稽核，沒有被模型流程讀取或評估。
"""


def run(output_dir: Path) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    if DEFAULT_OUTPUT_PARENT.resolve() not in output_dir.parents:
        raise ValueError(f"Smoke outputs must remain under {DEFAULT_OUTPUT_PARENT}.")
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite existing smoke-run output: {output_dir}")
    if _physical_ram_bytes() < 8 * 1024**3:
        raise RuntimeError("Physical RAM is below the ticket's 8 GiB execution baseline.")
    free_disk_before = _require_disk_reserve(PROJECT_ROOT)

    loader_started = time.perf_counter()
    bundle = load_frozen_dataset(DATASET_PATHS)
    loader_elapsed = time.perf_counter() - loader_started
    audit_summary = bundle.audit_summary
    pre_run_source_sha256 = dict(audit_summary["source_sha256"])
    review_status_counts = dict(Counter(str(row["review_status"]) for row in bundle.records))
    label_names = dict(bundle.label_names)
    family_counts_by_split = dict(Counter(bundle.family_splits.values()))
    train_records, validation_records = split_for_smoke(bundle.records)
    del bundle

    expected_source_paths = {
        "jsonl": DATASET_PATHS.jsonl_path,
        "csv": DATASET_PATHS.csv_path,
        "taxonomy": DATASET_PATHS.taxonomy_path,
        "manifest": DATASET_PATHS.frozen_manifest_path,
    }
    source_paths = {
        name: path.relative_to(PROJECT_ROOT).as_posix()
        for name, path in expected_source_paths.items()
    }
    source_sha256_before = pre_run_source_sha256
    if set(label_names) != set(LABEL_ORDER):
        raise RuntimeError("Frozen taxonomy label IDs differ from the fixed model class order.")
    if set(review_status_counts) != {"pending_manual_review"}:
        raise RuntimeError(f"Expected all records to remain pending_manual_review: {review_status_counts}")

    # The classifier seam receives only these two collections; no test argument
    # or test transcript is passed to vectorizer or estimator code.
    model_started = time.perf_counter()
    results = run_baselines(train_records, validation_records, random_state=42)
    model_elapsed = time.perf_counter() - model_started

    # Repeat the M2.1 contract audit after modeling. It reads all frozen source
    # files, including test rows, only to prove the source contract stayed fixed.
    post_bundle = load_frozen_dataset(DATASET_PATHS)
    source_checksums_unchanged = (
        pre_run_source_sha256 == post_bundle.audit_summary["source_sha256"]
    )
    if not source_checksums_unchanged:
        raise RuntimeError("One or more frozen data source checksums changed during the smoke test.")
    source_sha256_after = dict(post_bundle.audit_summary["source_sha256"])
    del post_bundle

    free_disk_before_output = _require_disk_reserve(PROJECT_ROOT)
    output_dir.mkdir(parents=True, exist_ok=False)

    label_by_id = {
        str(row["id"]): str(row["label_id"])
        for row in (*train_records, *validation_records)
    }
    prediction_count = _write_predictions(output_dir / "predictions.csv", results, label_by_id)

    train_family_ids = {str(row["scenario_family_id"]) for row in train_records}
    validation_family_ids = {str(row["scenario_family_id"]) for row in validation_records}
    if train_family_ids & validation_family_ids:
        raise RuntimeError("scenario_family_id leakage detected between train and validation.")
    if prediction_count != len(results) * (len(train_records) + len(validation_records)):
        raise RuntimeError("Prediction count does not match train+validation records for each candidate.")
    model_record_counts = {
        "train": {
            "records": len(train_records),
            "family_count": len(train_family_ids),
            "record_id_sha256": _sha256_json([row["id"] for row in train_records]),
        },
        "validation": {
            "records": len(validation_records),
            "family_count": len(validation_family_ids),
            "record_id_sha256": _sha256_json([row["id"] for row in validation_records]),
        },
        "family_intersection_count": 0,
    }
    manifest: dict[str, Any] = {
        "run_id": output_dir.name,
        "created_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "smoke_test",
        "result_status": "provisional",
        "dataset_source": "formal_dataset_v1.0.0",
        "dataset_source_paths": source_paths,
        "source_sha256_before": source_sha256_before,
        "source_sha256_after": source_sha256_after,
        "code_sha256": {
            "runner": _sha256_file(Path(__file__).resolve()),
            "baseline_module": _sha256_file(PROJECT_ROOT / "src/flycall_data/text_baseline.py"),
            "tests": _sha256_file(PROJECT_ROOT / "tests/test_text_baseline.py"),
            "requirements": _sha256_file(PROJECT_ROOT / ".scratch/1999-connectome-demo/requirements-m2-2a-smoke.txt"),
        },
        "pilot_included": False,
        "review_status_counts": review_status_counts,
        "loader_audit_reads_full_files": True,
        "loader_audit_includes_test_split": True,
        "model_uses_only": ["train", "validation"],
        "test_model_input_count": 0,
        "test_prediction_count": 0,
        "test_metrics": "not_run",
        "model_splits": model_record_counts,
        "split_counts_from_loader_audit": audit_summary["split_counts"],
        "family_counts_by_split_from_loader_audit": family_counts_by_split,
        "label_counts_from_loader_audit": audit_summary["label_counts"],
        "label_split_counts_from_loader_audit": audit_summary["label_split_counts"],
        "family_isolation_from_loader_audit": True,
        "label_order": list(LABEL_ORDER),
        "label_names": label_names,
        "feature_input": "transcript only; preserve R:/L: markers; management metadata excluded",
        "vectorizer_fit_split": "train only",
        "validation_vectorizer_operation": "transform only",
        "feature_candidates": {
            "char": {"analyzer": "char", "ngram_range": [2, 5]},
            "phrase_char": {"analyzer": "char", "ngram_range": [2, 4], "note": "short contiguous character phrases; no external tokenizer"},
            "shared": {"min_df": 2, "max_features": 50000, "sublinear_tf": True, "lowercase": False, "dtype": "float64 default"},
        },
        "classifier_candidates": [
            {"name": "logistic_regression", "C": 1.0, "max_iter": 1000, "solver": "lbfgs", "random_state": 42},
            {"name": "linear_svm", "C": 1.0, "dual": "auto", "max_iter": 5000, "random_state": 42},
        ],
        "candidate_count": len(results),
        "predictions_written": prediction_count,
        "dataset_audit": audit_summary,
        "source_checksums_unchanged": source_checksums_unchanged,
        "source_sha256_after": source_sha256_after,
        "environment": {
            "python": platform.python_version(),
            "scikit_learn": version("scikit-learn"),
            "numpy": version("numpy"),
            "scipy": version("scipy"),
            "joblib": version("joblib"),
            "narwhals": version("narwhals"),
            "threadpoolctl": version("threadpoolctl"),
            "cloudpickle": version("cloudpickle"),
            "implementation": platform.python_implementation(),
            "machine": platform.machine(),
            "venv_path": ".scratch/1999-connectome-demo/env/m2-2a-smoke",
            "install_command": "uv pip install --python <isolated-venv-python> --only-binary=:all: -r requirements-m2-2a-smoke.txt",
            "downloaded_mib": 32.6,
            "download_limit_mib": 500,
            "venv_size_mib": 147,
            "device": "CPU",
        },
        "resources": {
            "physical_ram_bytes": _physical_ram_bytes(),
            "free_disk_before_bytes": free_disk_before,
            "free_disk_before_output_bytes": free_disk_before_output,
            "free_disk_after_bytes": None,
            "disk_reserve_bytes": MIN_FREE_DISK_BYTES,
            "disk_reserve_preserved": None,
            "loader_elapsed_seconds": loader_elapsed,
            "model_elapsed_seconds": model_elapsed,
            "peak_rss_bytes": _peak_rss_bytes(),
            "device": "CPU",
        },
        "artifacts": {
            "metrics": "metrics.json",
            "predictions": "predictions.csv",
            "report": "report.md",
        },
    }

    payload = {
        "run_manifest": manifest,
        "candidates": [asdict(result) for result in results],
    }
    (output_dir / "metrics.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "report.md").write_text(_render_report(manifest, results), encoding="utf-8")
    free_disk_after = _require_disk_reserve(PROJECT_ROOT)
    manifest["resources"]["free_disk_after_bytes"] = free_disk_after
    manifest["resources"]["disk_reserve_preserved"] = free_disk_after >= MIN_FREE_DISK_BYTES
    payload["run_manifest"] = manifest
    (output_dir / "metrics.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "report.md").write_text(_render_report(manifest, results), encoding="utf-8")
    _require_disk_reserve(PROJECT_ROOT)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="New scratch directory; defaults to a timestamped path under the project scratch tree.",
    )
    args = parser.parse_args()
    run_id = "m2-2a-smoke-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = args.output_dir or (DEFAULT_OUTPUT_PARENT / run_id)
    result = run(output_dir)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

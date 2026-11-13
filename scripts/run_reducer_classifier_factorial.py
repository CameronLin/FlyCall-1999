#!/usr/bin/env python3
"""Reducer × classifier factorial: {E5, LDA, Fly A} × {SVM, Fly B}.

Separates how much of the Fly A→Fly B score comes from the reduction stage and
how much from the classification stage. Train/validation only: inputs are the
checksummed M2.2b E5 cache and the three M3.2 Fly A checkpoints, loaded through
``diagnose_fly_a_b.load_train_validation_inputs``. Test is never read.
Preregistration: .scratch/1999-connectome-demo/research/
reducer-classifier-factorial-preregistration-20261113.md
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for extra in (PROJECT_ROOT / "src", PROJECT_ROOT / "scripts"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import numpy as np  # noqa: E402
import torch  # noqa: E402

from diagnose_fly_a_b import (  # noqa: E402
    DEFAULT_CACHE_ROOT,
    DEFAULT_EMBEDDING_MANIFEST,
    DEFAULT_RUNS,
    EXPECTED_SEEDS,
    load_train_validation_inputs,
)
from flycall_data.evaluation import LABEL_ORDER  # noqa: E402
from flycall_data.fly_ab_training import (  # noqa: E402
    EmbeddingSplit,
    TrainingConfig,
    load_fly_b_checkpoint,
    train_fly_b,
    train_fly_b_on_features,
)
from flycall_data.reducer_classifier_factorial import (  # noqa: E402
    CLASSIFIERS,
    FLY_B_SCHEDULES,
    REDUCERS,
    FactorialError,
    fit_lda_reducer,
    paired_delta,
    run_svm,
    summarize,
)

DEFAULT_OUTPUT = ".scratch/1999-connectome-demo/runs/reducer-classifier-factorial-20261113"
PREREGISTRATION = ".scratch/1999-connectome-demo/research/reducer-classifier-factorial-preregistration-20261113.md"
REDUCER_LABELS = {"e5": "E5 384-D（無降維）", "lda": "LDA 4-D", "fly_a": "Fly A 32-D"}
CLASSIFIER_LABELS = {"svm": "SVM", "fly_b": "Fly B"}
RELOAD_TOLERANCE = 1e-6


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _features(item: dict[str, Any]) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    train_e5 = item["train"].embeddings.numpy().astype(np.float64)
    validation_e5 = item["validation"].embeddings.numpy().astype(np.float64)
    lda = fit_lda_reducer(train_e5, item["train"].labels, validation_e5)
    fly_a_train = np.asarray(item["fly_a_train_features"].features, dtype=np.float64)
    fly_a_validation = np.asarray(item["fly_a_validation_features"].features, dtype=np.float64)
    return {
        "e5": (train_e5, validation_e5),
        "lda": (lda.train, lda.validation),
        "fly_a": (fly_a_train, fly_a_validation),
    }


def _as_split(template: EmbeddingSplit, values: np.ndarray) -> EmbeddingSplit:
    return EmbeddingSplit(
        template.split,
        template.record_ids,
        template.family_ids,
        torch.tensor(values, dtype=torch.float32),
        template.labels,
    )


def _fly_b_cell(
    item: dict[str, Any],
    reducer: str,
    features: tuple[np.ndarray, np.ndarray],
    schedule: dict[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    seed = item["seed"]
    config = TrainingConfig(
        seed=seed,
        batch_size=32,
        max_epochs=schedule["max_epochs"],
        patience=schedule["patience"],
        learning_rate=schedule["learning_rate"],
        gradient_clip_norm=1.0,
        torch_threads=1,
    )
    path = output_dir / "checkpoints" / schedule["name"] / f"{reducer}-to-fly-b" / f"seed-{seed}" / "fly-b-checkpoint.pt"
    candidate = f"{reducer}_to_fly_b_{schedule['name']}_seed_{seed}"
    source_hashes = dict(item["source_sha256"])
    if reducer == "fly_a":
        # Original M3.3 path: same RNG order as M3.2, so s1 should reproduce it.
        source_hashes["fly_a_checkpoint"] = item["fly_a_checkpoint_sha256"]
        result = train_fly_b(
            item["graph"], item["train"], item["validation"],
            fly_a_checkpoint_path=item["fly_a_checkpoint"],
            fly_a_source_sha256=item["fly_a_source_sha256"],
            source_sha256=source_hashes,
            checkpoint_path=path,
            config=config,
            candidate_name=candidate,
        )
    else:
        result = train_fly_b_on_features(
            item["graph"],
            _as_split(item["train"], features[0]),
            _as_split(item["validation"], features[1]),
            source_sha256=source_hashes,
            checkpoint_path=path,
            config=config,
            candidate_name=candidate,
        )
    validation_inputs = torch.tensor(features[1], dtype=torch.float32)
    reloaded = load_fly_b_checkpoint(
        item["graph"], path, expected_source_sha256=source_hashes, input_width=int(features[1].shape[1])
    )
    with torch.no_grad():
        before = result.model(validation_inputs)
        after = reloaded(validation_inputs)
    reload_diff = float((before - after).abs().max())
    if reload_diff > RELOAD_TOLERANCE:
        raise FactorialError(f"{candidate} reload changed validation logits by {reload_diff}.")
    assert result.evaluation is not None
    validation = result.evaluation["splits"]["validation"]
    return {
        "selected_epoch": result.selected_epoch,
        "epochs_run": len(result.history),
        "parameter_counts": result.model.parameter_counts,
        "checkpoint": path.relative_to(output_dir).as_posix(),
        "checkpoint_sha256": result.checkpoint_sha256,
        "checkpoint_reload_max_abs_diff": reload_diff,
        "train_metrics": result.evaluation["splits"]["train"]["metrics"],
        "validation_metrics": validation["metrics"],
        "validation_predictions": list(_predictions(result.model, validation_inputs)),
        "configuration": {**{k: v for k, v in schedule.items() if k != "name"}, "batch_size": 32, "gradient_clip_norm": 1.0},
    }


def _predictions(model: torch.nn.Module, inputs: torch.Tensor) -> tuple[str, ...]:
    with torch.no_grad():
        logits = model(inputs)
    return tuple(LABEL_ORDER[index] for index in logits.argmax(dim=1).tolist())


def run_factorial(
    inputs: list[dict[str, Any]], output_dir: Path
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    cells: dict[str, dict[str, dict[str, Any]]] = {}
    sanity: list[dict[str, Any]] = []
    started = time.perf_counter()

    def store(key: str, seed: int, value: dict[str, Any]) -> None:
        cells.setdefault(key, {})[str(seed)] = value

    for item in inputs:
        seed = item["seed"]
        features = _features(item)
        for reducer in REDUCERS:
            train_x, validation_x = features[reducer]
            svm = run_svm(train_x, item["train"].labels, validation_x, item["validation"].labels)
            store(f"{reducer}|svm|-", seed, {
                "input_width": int(train_x.shape[1]),
                "train_metrics": svm.train_metrics,
                "validation_metrics": svm.validation_metrics,
                "validation_predictions": list(svm.validation_predictions),
                "configuration": svm.parameters,
            })
            for schedule in FLY_B_SCHEDULES:
                cell = _fly_b_cell(item, reducer, features[reducer], schedule, output_dir)
                cell["input_width"] = int(train_x.shape[1])
                store(f"{reducer}|fly_b|{schedule['name']}", seed, cell)
                print(
                    f"seed {seed} {reducer}->fly_b {schedule['name']}: "
                    f"F1 {cell['validation_metrics']['macro_f1']:.4f} (epoch {cell['selected_epoch']})",
                    flush=True,
                )
            print(f"seed {seed} {reducer}->svm: F1 {svm.validation_metrics['macro_f1']:.4f}", flush=True)
        reproduced = cells["fly_a|fly_b|s1_m3_2_default"][str(seed)]["validation_metrics"]["macro_f1"]
        sanity.append({
            "seed": seed,
            "m3_2_saved_validation_macro_f1": float(item["old_validation"]["macro_f1"]),
            "rerun_validation_macro_f1": float(reproduced),
            "abs_diff": abs(float(item["old_validation"]["macro_f1"]) - float(reproduced)),
        })

    summary: dict[str, Any] = {}
    for key, by_seed in cells.items():
        ordered = [by_seed[str(seed)] for seed in EXPECTED_SEEDS]
        summary[key] = {
            metric: summarize([row["validation_metrics"][metric] for row in ordered])
            for metric in ("macro_f1", "accuracy")
        }
        summary[key]["train_macro_f1"] = summarize([row["train_metrics"]["macro_f1"] for row in ordered])

    def per_seed(key: str) -> list[float]:
        return [float(cells[key][str(seed)]["validation_metrics"]["macro_f1"]) for seed in EXPECTED_SEEDS]

    deltas: dict[str, Any] = {}
    for schedule in ("s1_m3_2_default", "s2_long"):
        fly_b = lambda reducer: f"{reducer}|fly_b|{schedule}"  # noqa: E731
        deltas[schedule] = {
            "reducer_effect_lda_minus_fly_a__svm": paired_delta(per_seed("lda|svm|-"), per_seed("fly_a|svm|-")),
            "reducer_effect_lda_minus_fly_a__fly_b": paired_delta(per_seed(fly_b("lda")), per_seed(fly_b("fly_a"))),
            "reducer_effect_e5_minus_fly_a__svm": paired_delta(per_seed("e5|svm|-"), per_seed("fly_a|svm|-")),
            "reducer_effect_e5_minus_fly_a__fly_b": paired_delta(per_seed(fly_b("e5")), per_seed(fly_b("fly_a"))),
            **{
                f"classifier_effect_svm_minus_fly_b__{reducer}": paired_delta(
                    per_seed(f"{reducer}|svm|-"), per_seed(fly_b(reducer))
                )
                for reducer in REDUCERS
            },
        }
    deltas["fly_b_training_budget_s2_minus_s1"] = {
        reducer: paired_delta(per_seed(f"{reducer}|fly_b|s2_long"), per_seed(f"{reducer}|fly_b|s1_m3_2_default"))
        for reducer in REDUCERS
    }

    return {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "validation_only_factorial_complete_pending_manual_review",
        "preregistration": PREREGISTRATION,
        "data_status": "synthetic",
        "review_status": "pending_manual_review",
        "label_order": list(LABEL_ORDER),
        "seeds": list(EXPECTED_SEEDS),
        "reducers": list(REDUCERS),
        "classifiers": list(CLASSIFIERS),
        "fly_b_schedules": [dict(item) for item in FLY_B_SCHEDULES],
        "split_counts": {"train": 700, "validation": 150, "test": 0},
        "test": {"status": "not_run", "model_inputs": 0, "metrics": None},
        "formal_test_eligible": False,
        "elapsed_seconds": time.perf_counter() - started,
        "source_sha256_by_seed": {str(item["seed"]): item["source_sha256"] for item in inputs},
        "fly_a_checkpoint_sha256_by_seed": {str(item["seed"]): item["fly_a_checkpoint_sha256"] for item in inputs},
        "source_code_sha256": {
            relative: _sha256_file(PROJECT_ROOT / relative)
            for relative in (
                "src/flycall_data/reducer_classifier_factorial.py",
                "src/flycall_data/fly_ab_training.py",
                "src/flycall_data/graph_core.py",
                "scripts/run_reducer_classifier_factorial.py",
                "scripts/diagnose_fly_a_b.py",
            )
        },
        "sanity_fly_a_to_fly_b_reproduces_m3_2": sanity,
        "summary": summary,
        "deltas": deltas,
        "cells": cells,
    }, inputs


def _write_predictions(path: Path, results: dict[str, Any], inputs: list[dict[str, Any]]) -> None:
    by_seed = {item["seed"]: item for item in inputs}
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["reducer", "classifier", "schedule", "seed", "record_id", "family_id", "expected_label", "predicted_label"])
        for key, cell_by_seed in results["cells"].items():
            reducer, classifier, schedule = key.split("|")
            for seed in EXPECTED_SEEDS:
                validation = by_seed[seed]["validation"]
                predictions = cell_by_seed[str(seed)]["validation_predictions"]
                for record_id, family_id, label, predicted in zip(
                    validation.record_ids, validation.family_ids, validation.labels or (), predictions
                ):
                    writer.writerow([reducer, classifier, schedule, seed, record_id, family_id, label, predicted])


def _fmt(summary: dict[str, float]) -> str:
    return f"{summary['mean']:.4f} ± {summary['sample_std']:.4f}"


def _markdown(results: dict[str, Any]) -> str:
    s = results["summary"]
    d = results["deltas"]
    s1, s2 = "s1_m3_2_default", "s2_long"
    lines = [
        "# 降維器 × 分類器 交叉實驗（validation only）",
        "",
        "- 狀態：`validation_only_factorial_complete_pending_manual_review`",
        "- 資料：`synthetic`；複核：`pending_manual_review`；test：`not_run`（0 model inputs）",
        f"- 預註冊：`{results['preregistration']}`",
        f"- Seeds：{', '.join(str(seed) for seed in results['seeds'])}；數值為 validation Macro-F1 平均 ± 樣本標準差",
        "",
        "## 主要結果：使用者指定的 2×2（Fly B 用 s1＝M3.2 訓練預算）",
        "",
        "| 降維器 ＼ 分類器 | SVM | Fly B |",
        "|---|---:|---:|",
    ]
    for reducer in ("lda", "fly_a"):
        lines.append(
            f"| {REDUCER_LABELS[reducer]} | {_fmt(s[f'{reducer}|svm|-']['macro_f1'])} | "
            f"{_fmt(s[f'{reducer}|fly_b|{s1}']['macro_f1'])} |"
        )
    lines += [
        "",
        "## 完整表格",
        "",
        "| 降維器 | 輸入寬度 | SVM | Fly B s1（LR 0.001／100 ep） | Fly B s2（LR 0.003／200 ep） |",
        "|---|---:|---:|---:|---:|",
    ]
    widths = {"e5": 384, "lda": 4, "fly_a": 32}
    for reducer in REDUCERS:
        lines.append(
            f"| {REDUCER_LABELS[reducer]} | {widths[reducer]} | {_fmt(s[f'{reducer}|svm|-']['macro_f1'])} | "
            f"{_fmt(s[f'{reducer}|fly_b|{s1}']['macro_f1'])} | {_fmt(s[f'{reducer}|fly_b|{s2}']['macro_f1'])} |"
        )
    lines += [
        "",
        "Accuracy（平均）：",
        "",
        "| 降維器 | SVM | Fly B s1 | Fly B s2 |",
        "|---|---:|---:|---:|",
    ]
    for reducer in REDUCERS:
        lines.append(
            f"| {REDUCER_LABELS[reducer]} | {s[f'{reducer}|svm|-']['accuracy']['mean']:.4f} | "
            f"{s[f'{reducer}|fly_b|{s1}']['accuracy']['mean']:.4f} | {s[f'{reducer}|fly_b|{s2}']['accuracy']['mean']:.4f} |"
        )
    lines += ["", "## 各 seed validation Macro-F1", "", "| 組合 | 42 | 1337 | 2026 | 選用 epoch |", "|---|---:|---:|---:|---|"]
    for key, by_seed in results["cells"].items():
        reducer, classifier, schedule = key.split("|")
        name = f"{REDUCER_LABELS[reducer]} → {CLASSIFIER_LABELS[classifier]}" + ("" if schedule == "-" else f" {schedule.split('_')[0]}")
        epochs = "—" if classifier == "svm" else ", ".join(str(by_seed[str(seed)]["selected_epoch"]) for seed in EXPECTED_SEEDS)
        values = " | ".join(f"{by_seed[str(seed)]['validation_metrics']['macro_f1']:.4f}" for seed in EXPECTED_SEEDS)
        lines.append(f"| {name} | {values} | {epochs} |")

    def delta_row(label: str, value: dict[str, Any]) -> str:
        per_seed = ", ".join(f"{x:+.4f}" for x in value["per_seed"])
        verdict = "一致" if value["consistent"] else "不明確"
        return f"| {label} | {value['mean']:+.4f} | {per_seed} | {verdict} |"

    lines += [
        "",
        "## 差異拆解（s1；判讀規則：三個 seed 同號且 |平均 Δ| ≥ 0.02 才算一致）",
        "",
        "| 比較 | 平均 Δ Macro-F1 | 各 seed Δ | 判讀 |",
        "|---|---:|---|---|",
        delta_row("降維器效果，分類器固定 SVM：LDA − Fly A", d[s1]["reducer_effect_lda_minus_fly_a__svm"]),
        delta_row("降維器效果，分類器固定 Fly B：LDA − Fly A", d[s1]["reducer_effect_lda_minus_fly_a__fly_b"]),
        delta_row("降維器效果，分類器固定 SVM：E5 − Fly A", d[s1]["reducer_effect_e5_minus_fly_a__svm"]),
        delta_row("降維器效果，分類器固定 Fly B：E5 − Fly A", d[s1]["reducer_effect_e5_minus_fly_a__fly_b"]),
        delta_row("分類器效果，降維器固定 E5：SVM − Fly B", d[s1]["classifier_effect_svm_minus_fly_b__e5"]),
        delta_row("分類器效果，降維器固定 LDA：SVM − Fly B", d[s1]["classifier_effect_svm_minus_fly_b__lda"]),
        delta_row("分類器效果，降維器固定 Fly A：SVM − Fly B", d[s1]["classifier_effect_svm_minus_fly_b__fly_a"]),
        "",
        "### Fly B 訓練預算（s2 − s1）",
        "",
        "| 輸入 | 平均 Δ Macro-F1 | 各 seed Δ | 判讀 |",
        "|---|---:|---|---|",
    ]
    for reducer in REDUCERS:
        lines.append(delta_row(REDUCER_LABELS[reducer], d["fly_b_training_budget_s2_minus_s1"][reducer]))
    lines += [
        "",
        "### s2 下的差異拆解",
        "",
        "| 比較 | 平均 Δ Macro-F1 | 各 seed Δ | 判讀 |",
        "|---|---:|---|---|",
        delta_row("降維器效果，分類器固定 Fly B：LDA − Fly A", d[s2]["reducer_effect_lda_minus_fly_a__fly_b"]),
        delta_row("分類器效果，降維器固定 LDA：SVM − Fly B", d[s2]["classifier_effect_svm_minus_fly_b__lda"]),
        delta_row("分類器效果，降維器固定 Fly A：SVM − Fly B", d[s2]["classifier_effect_svm_minus_fly_b__fly_a"]),
        "",
        "## 健全性檢查",
        "",
        "| Seed | M3.2 存檔 Fly A→Fly B F1 | 本次重跑 s1 | 差異 |",
        "|---:|---:|---:|---:|",
    ]
    for row in results["sanity_fly_a_to_fly_b_reproduces_m3_2"]:
        lines.append(
            f"| {row['seed']} | {row['m3_2_saved_validation_macro_f1']:.4f} | {row['rerun_validation_macro_f1']:.4f} | {row['abs_diff']:.2e} |"
        )
    max_reload = max(
        cell["checkpoint_reload_max_abs_diff"]
        for key, by_seed in results["cells"].items() if "|fly_b|" in key
        for cell in by_seed.values()
    )
    lines += [
        "",
        f"所有 Fly B checkpoint 重載後 validation logits 最大差異：{max_reload:.2e}（容差 {RELOAD_TOLERANCE:g}）。",
        "",
        "## 限制",
        "",
        "- 全部是 validation 結果；設定在同一 validation set 上比較，不是無偏的最終估計，不取代 M3.4 暫定 winner 或 M4 鎖定模型。",
        "- LDA 與 SVM 不含隨機性；LDA→SVM 與 E5→SVM 的標準差為 0。Fly A→SVM 的變異只來自三個 Fly A checkpoint。",
        "- 資料為合成資料、待人工複核；不代表真實 1999 案件表現。未讀取 test。",
        "",
        "完整數值、各類別指標、checkpoint 雜湊見 `results.json`；逐筆 validation 預測見 `validation_predictions.csv`。",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", action="append", default=None)
    parser.add_argument("--embedding-manifest", default=DEFAULT_EMBEDDING_MANIFEST)
    parser.add_argument("--cache-root", default=DEFAULT_CACHE_ROOT)
    parser.add_argument("--output-dir", default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output_dir = PROJECT_ROOT / args.output_dir
    if output_dir.exists() and any(output_dir.iterdir()):
        raise SystemExit(f"Refusing to overwrite non-empty output directory {output_dir}.")
    output_dir.mkdir(parents=True, exist_ok=True)
    inputs = load_train_validation_inputs(
        run_dirs=[PROJECT_ROOT / value for value in (args.run_dir or DEFAULT_RUNS)],
        embedding_manifest_path=PROJECT_ROOT / args.embedding_manifest,
        cache_root=PROJECT_ROOT / args.cache_root,
    )
    results, inputs = run_factorial(inputs, output_dir)
    _write_predictions(output_dir / "validation_predictions.csv", results, inputs)
    (output_dir / "results.json").write_text(
        json.dumps(results, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    (output_dir / "report.md").write_text(_markdown(results), encoding="utf-8")
    print(f"Wrote factorial results to {output_dir.relative_to(PROJECT_ROOT).as_posix()}")
    print("Test status: not_run; test model inputs: 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

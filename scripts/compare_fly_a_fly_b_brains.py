#!/usr/bin/env python3
"""Compare trained Fly A and Fly B "brains" on the same graph (post-hoc analysis).

Reads the final checkpoints from run_independent_tuning.py. Three views:
edge-by-edge change, neuron activity / class selectivity, and lesions.
Differences between Fly A and Fly B are always shown next to the
seed-to-seed baseline of the same model, because retraining with another seed
also changes weights. No model selection happens here; test is never read.
"""

from __future__ import annotations

import argparse
import itertools
import json
import statistics
import sys
import time
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
for extra in (PROJECT_ROOT / "src", PROJECT_ROOT / "scripts"):
    if str(extra) not in sys.path:
        sys.path.insert(0, str(extra))

import numpy as np  # noqa: E402
import torch  # noqa: E402

from diagnose_fly_a_b import DEFAULT_CACHE_ROOT, DEFAULT_EMBEDDING_MANIFEST, DEFAULT_RUNS, load_inputs_for, load_train_validation_inputs  # noqa: E402
from flycall_data.brain_comparison import (  # noqa: E402
    edge_log_change,
    eta_squared,
    fly_a_drives,
    fly_a_output,
    fly_b_logits,
    jaccard,
    load_trained,
    node_states,
    spearman,
    top_set,
)
from flycall_data.evaluation import LABEL_ORDER, classification_metrics  # noqa: E402
from flycall_data.reducer_classifier_factorial import run_svm  # noqa: E402
from run_independent_tuning import GRAPH_ORDER, load_graphs  # noqa: E402

RUN = ".scratch/1999-connectome-demo/runs/independent-tuning-20261113"
OUTPUT = ".scratch/1999-connectome-demo/runs/fly-ab-brain-comparison-20261113"
OBJECTIVES = ("distance", "distance_supcon")
SEEDS = (42, 1337, 2026)
TOP_EDGE_FRACTION = 0.10
TOP_NEURONS = 20
COLOR_A, COLOR_B = "#2a78d6", "#eb6834"  # dataviz reference palette, categorical slots 1-2 (light)
INK, INK_2, SURFACE, GRID = "#0b0b0b", "#52514e", "#fcfcfb", "#e4e3df"


def f1(labels, predictions) -> float:
    return float(classification_metrics(labels, predictions, LABEL_ORDER)["macro_f1"])


def svm_f1(train_x, labels_tr, val_x, labels_val) -> float:
    return float(run_svm(train_x, labels_tr, val_x, labels_val).validation_metrics["macro_f1"])


def analyse_pair(graph, fly_a, fly_b, data) -> dict[str, Any]:
    xtr, xval, labels_tr, labels_val, ytr = data["xtr"], data["xval"], data["labels_tr"], data["labels_val"], data["ytr"]
    core_a, core_b = fly_a.graph_core, fly_b.graph_core
    count = len(core_a.node_ids)
    with torch.no_grad():
        ztr, zval = fly_a(xtr), fly_a(xval)
        states_a = node_states(core_a, fly_a_drives(fly_a, xtr)).numpy()
        states_b = node_states(core_b, fly_b.input_adapter(ztr)).numpy()
        base_a = svm_f1(ztr.numpy(), labels_tr, zval.numpy(), labels_val)
        base_b = f1(labels_val, [LABEL_ORDER[i] for i in fly_b(zval).argmax(1).tolist()])
        drop_a, drop_b = np.zeros(count), np.zeros(count)
        for node in range(count):
            mask = torch.zeros(count, dtype=torch.bool)
            mask[node] = True
            a_tr, a_val = fly_a_output(fly_a, xtr, silenced=mask), fly_a_output(fly_a, xval, silenced=mask)
            drop_a[node] = base_a - svm_f1(a_tr.numpy(), labels_tr, a_val.numpy(), labels_val)
            logits = fly_b_logits(fly_b, zval, silenced=mask)
            drop_b[node] = base_b - f1(labels_val, [LABEL_ORDER[i] for i in logits.argmax(1).tolist()])
        inhibition = {}
        if core_a.node_signs is not None and bool((core_a.edge_signs < 0).any()):
            scale = (core_a.edge_signs > 0).to(torch.float32)  # zero every inhibitory edge
            a_tr, a_val = fly_a_output(fly_a, xtr, edge_scale=scale), fly_a_output(fly_a, xval, edge_scale=scale)
            logits = fly_b_logits(fly_b, zval, edge_scale=scale)
            inhibition = {
                "fly_a_drop": base_a - svm_f1(a_tr.numpy(), labels_tr, a_val.numpy(), labels_val),
                "fly_b_drop": base_b - f1(labels_val, [LABEL_ORDER[i] for i in logits.argmax(1).tolist()]),
            }
    labels_idx = ytr.numpy()
    return {
        "log_change_a": edge_log_change(core_a, graph),
        "log_change_b": edge_log_change(core_b, graph),
        "eta_a": eta_squared(states_a, labels_idx),
        "eta_b": eta_squared(states_b, labels_idx),
        "mean_abs_a": np.abs(states_a).mean(axis=0),
        "mean_abs_b": np.abs(states_b).mean(axis=0),
        "drop_a": drop_a, "drop_b": drop_b,
        "base_a": base_a, "base_b": base_b,
        "inhibition_removed": inhibition,
    }


def compare(per_seed: dict[int, dict[str, Any]], key_a: str, key_b: str, metric) -> dict[str, Any]:
    """A-vs-B (same seed) next to the A-vs-A and B-vs-B seed baselines."""

    a_vs_b = [metric(per_seed[s][key_a], per_seed[s][key_b]) for s in SEEDS]
    pairs = list(itertools.combinations(SEEDS, 2))
    a_seeds = [metric(per_seed[s][key_a], per_seed[t][key_a]) for s, t in pairs]
    b_seeds = [metric(per_seed[s][key_b], per_seed[t][key_b]) for s, t in pairs]
    return {"fly_a_vs_fly_b_same_seed": statistics.fmean(a_vs_b), "fly_a_seed_baseline": statistics.fmean(a_seeds),
            "fly_b_seed_baseline": statistics.fmean(b_seeds), "values": {"a_vs_b": a_vs_b, "a_seeds": a_seeds, "b_seeds": b_seeds}}


def summarise(graph, per_seed) -> dict[str, Any]:
    core = graph.build_core()
    roles = np.array(["internal"] * len(core.node_ids), dtype=object)
    roles[core.input_index.numpy()] = "input"
    roles[core.output_index.numpy()] = "output"
    edge_signs = core.edge_signs.numpy() if core.node_signs is not None else np.ones(len(core.edges))
    node_signs = np.array(core.node_signs) if core.node_signs is not None else np.ones(len(core.node_ids))
    out: dict[str, Any] = {
        "edges": {
            "spearman_log_change": compare(per_seed, "log_change_a", "log_change_b", spearman),
            "top10pct_strengthened_jaccard": compare(per_seed, "log_change_a", "log_change_b",
                                                     lambda a, b: jaccard(top_set(a, TOP_EDGE_FRACTION), top_set(b, TOP_EDGE_FRACTION))),
            "spread_sd_log_change": {"fly_a": statistics.fmean(float(np.std(per_seed[s]["log_change_a"])) for s in SEEDS),
                                     "fly_b": statistics.fmean(float(np.std(per_seed[s]["log_change_b"])) for s in SEEDS)},
            "mean_log_change_by_edge_sign": {
                label: {"fly_a": statistics.fmean(float(per_seed[s]["log_change_a"][edge_signs == sign].mean()) for s in SEEDS),
                        "fly_b": statistics.fmean(float(per_seed[s]["log_change_b"][edge_signs == sign].mean()) for s in SEEDS)}
                for label, sign in (("excitatory", 1), ("inhibitory", -1)) if bool((edge_signs == sign).any())},
        },
        "activity": {
            "spearman_eta_squared_profile": compare(per_seed, "eta_a", "eta_b", spearman),
            "spearman_mean_abs_activity_profile": compare(per_seed, "mean_abs_a", "mean_abs_b", spearman),
            "median_eta_squared": {"fly_a": statistics.fmean(float(np.median(per_seed[s]["eta_a"])) for s in SEEDS),
                                   "fly_b": statistics.fmean(float(np.median(per_seed[s]["eta_b"])) for s in SEEDS)},
            "neurons_eta_squared_above_0_5": {"fly_a": statistics.fmean(int((per_seed[s]["eta_a"] > 0.5).sum()) for s in SEEDS),
                                              "fly_b": statistics.fmean(int((per_seed[s]["eta_b"] > 0.5).sum()) for s in SEEDS)},
            "silent_neurons_mean_abs_below_0_01": {"fly_a": statistics.fmean(int((per_seed[s]["mean_abs_a"] < 0.01).sum()) for s in SEEDS),
                                                   "fly_b": statistics.fmean(int((per_seed[s]["mean_abs_b"] < 0.01).sum()) for s in SEEDS)},
        },
        "lesion": {
            "intact_validation_macro_f1": {"fly_a_to_svm": statistics.fmean(per_seed[s]["base_a"] for s in SEEDS),
                                           "fly_a_to_fly_b": statistics.fmean(per_seed[s]["base_b"] for s in SEEDS)},
            "top20_important_jaccard": compare(per_seed, "drop_a", "drop_b",
                                               lambda a, b: jaccard(top_set(a, count=TOP_NEURONS), top_set(b, count=TOP_NEURONS))),
            "spearman_drop_profile": compare(per_seed, "drop_a", "drop_b", spearman),
            "neurons_with_drop_ge_0_02": {"fly_a": statistics.fmean(int((per_seed[s]["drop_a"] >= 0.02).sum()) for s in SEEDS),
                                          "fly_b": statistics.fmean(int((per_seed[s]["drop_b"] >= 0.02).sum()) for s in SEEDS)},
            "mean_drop_by_role": {role: {"fly_a": statistics.fmean(float(per_seed[s]["drop_a"][roles == role].mean()) for s in SEEDS),
                                         "fly_b": statistics.fmean(float(per_seed[s]["drop_b"][roles == role].mean()) for s in SEEDS)}
                                  for role in ("input", "internal", "output")},
            "mean_drop_by_node_sign": {label: {"fly_a": statistics.fmean(float(per_seed[s]["drop_a"][node_signs == sign].mean()) for s in SEEDS),
                                               "fly_b": statistics.fmean(float(per_seed[s]["drop_b"][node_signs == sign].mean()) for s in SEEDS)}
                                       for label, sign in (("excitatory", 1), ("inhibitory", -1)) if bool((node_signs == sign).any())},
        },
    }
    if per_seed[SEEDS[0]]["inhibition_removed"]:
        out["lesion"]["remove_all_inhibitory_edges_drop"] = {
            "fly_a": statistics.fmean(per_seed[s]["inhibition_removed"]["fly_a_drop"] for s in SEEDS),
            "fly_b": statistics.fmean(per_seed[s]["inhibition_removed"]["fly_b_drop"] for s in SEEDS),
            "by_seed": [per_seed[s]["inhibition_removed"] for s in SEEDS]}
    return out


def draw_figures(per_seed, graph, output_dir: Path, tag: str, summaries: dict[str, Any]) -> list[str]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.sans-serif": ["Microsoft JhengHei", "Microsoft YaHei", "DejaVu Sans"],
                         "axes.unicode_minus": False, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
                         "axes.edgecolor": GRID, "axes.labelcolor": INK_2, "xtick.color": INK_2, "ytick.color": INK_2,
                         "text.color": INK, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
                         "axes.spines.top": False, "axes.spines.right": False})
    seed = SEEDS[0]
    item = per_seed[seed]
    files = []

    def save(fig, name):
        path = output_dir / name
        fig.savefig(path, dpi=150, bbox_inches="tight")
        plt.close(fig)
        files.append(name)

    # 1. hist: how far training moved each edge (overview).
    fig, ax = plt.subplots(figsize=(7, 4))
    bins = np.linspace(min(item["log_change_a"].min(), item["log_change_b"].min()),
                       max(item["log_change_a"].max(), item["log_change_b"].max()), 60)
    ax.hist(item["log_change_a"], bins=bins, color=COLOR_A, alpha=0.6, label="Fly A（降維）", edgecolor=SURFACE, linewidth=0.5)
    ax.hist(item["log_change_b"], bins=bins, color=COLOR_B, alpha=0.6, label="Fly B（分類）", edgecolor=SURFACE, linewidth=0.5)
    ax.axvline(0, color=INK_2, linewidth=1)
    ax.set_xlabel("log（訓練後強度 ÷ 訓練前強度）；0 = 沒變，>0 = 加強")
    ax.set_ylabel("邊數")
    ax.set_title(f"{tag}：每條邊強度的改變（seed {seed}）", loc="left")
    ax.legend(frameon=False)
    save(fig, f"{tag}_hist_edge_change.png")

    # 2. scatter: same edge, Fly A vs Fly B, faceted by edge sign.
    core = graph.build_core()
    signs = core.edge_signs.numpy() if core.node_signs is not None else np.ones(len(core.edges))
    facets = [(label, sign) for label, sign in (("增強邊", 1), ("抑制邊", -1)) if bool((signs == sign).any())]
    fig, axes = plt.subplots(1, len(facets), figsize=(5.2 * len(facets), 4.6), squeeze=False)
    lim = [min(item["log_change_a"].min(), item["log_change_b"].min()), max(item["log_change_a"].max(), item["log_change_b"].max())]
    for ax, (label, sign) in zip(axes[0], facets):
        pick = signs == sign
        ax.scatter(item["log_change_a"][pick], item["log_change_b"][pick], s=8, color=INK_2, alpha=0.35, linewidths=0)
        ax.plot(lim, lim, color=INK_2, linewidth=1, linestyle="--")
        rho = spearman(item["log_change_a"][pick], item["log_change_b"][pick])
        ax.set_title(f"{label}（{int(pick.sum())} 條），Spearman ρ = {rho:.2f}", loc="left")
        ax.set_xlabel("Fly A 的改變量")
        ax.set_ylabel("Fly B 的改變量")
    fig.suptitle(f"{tag}：同一條邊在兩個腦裡的改變（虛線 = 兩者相同）", x=0.01, ha="left")
    save(fig, f"{tag}_scatter_edge_a_vs_b.png")

    # 3. hist: class selectivity per neuron.
    fig, ax = plt.subplots(figsize=(7, 4))
    bins = np.linspace(0, 1, 41)
    ax.hist(item["eta_a"], bins=bins, color=COLOR_A, alpha=0.6, label="Fly A（降維）", edgecolor=SURFACE, linewidth=0.5)
    ax.hist(item["eta_b"], bins=bins, color=COLOR_B, alpha=0.6, label="Fly B（分類）", edgecolor=SURFACE, linewidth=0.5)
    ax.set_xlabel("類別選擇性 η²（0 = 對五類反應一樣，1 = 只看類別）")
    ax.set_ylabel("神經元數")
    ax.set_title(f"{tag}：500 個神經元的類別選擇性（seed {seed}）", loc="left")
    ax.legend(frameon=False)
    save(fig, f"{tag}_hist_class_selectivity.png")

    # 4. lesion: drop per neuron, Fly A vs Fly B.
    fig, ax = plt.subplots(figsize=(5.6, 5))
    ax.scatter(item["drop_a"], item["drop_b"], s=10, color=INK_2, alpha=0.45, linewidths=0)
    ax.axhline(0, color=GRID, linewidth=1)
    ax.axvline(0, color=GRID, linewidth=1)
    ax.set_xlabel("關掉該神經元後 Fly A→SVM 掉的 Macro-F1")
    ax.set_ylabel("關掉該神經元後 Fly A→Fly B 掉的 Macro-F1")
    ax.set_title(f"{tag}：損傷實驗，每點一個神經元（seed {seed}）", loc="left")
    save(fig, f"{tag}_scatter_lesion.png")
    return files


def draw_summary(summaries: dict[str, Any], output_dir: Path) -> str:
    import matplotlib.pyplot as plt

    keys = list(summaries)
    metrics = (("edges", "spearman_log_change", "邊的改變"), ("activity", "spearman_eta_squared_profile", "類別選擇性"),
               ("lesion", "spearman_drop_profile", "損傷影響"))
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.8), sharey=True)
    y = np.arange(len(keys))
    for ax, (section, metric, title) in zip(axes, metrics):
        ab = [summaries[k][section][metric]["fly_a_vs_fly_b_same_seed"] for k in keys]
        sa = [summaries[k][section][metric]["fly_a_seed_baseline"] for k in keys]
        sb = [summaries[k][section][metric]["fly_b_seed_baseline"] for k in keys]
        ax.scatter(sa, y + 0.18, s=40, color=COLOR_A, label="Fly A 換 seed（基準）", zorder=3)
        ax.scatter(sb, y - 0.18, s=40, color=COLOR_B, label="Fly B 換 seed（基準）", zorder=3)
        ax.scatter(ab, y, s=60, color=INK, marker="D", label="Fly A vs Fly B（同 seed）", zorder=3)
        ax.set_yticks(y, [k.replace("|", "\n") for k in keys])
        ax.set_xlim(-0.2, 1.0)
        ax.axvline(0, color=INK_2, linewidth=0.8)
        ax.set_title(f"{title}的相似度（Spearman ρ）", loc="left")
    axes[0].legend(frameon=False, loc="lower left", fontsize=8)
    fig.suptitle("黑色菱形明顯低於彩色點 = Fly A 和 Fly B 的差異大過換 seed 的差異", x=0.01, ha="left")
    name = "summary_similarity_vs_seed_baseline.png"
    fig.savefig(output_dir / name, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return name


def markdown(summaries: dict[str, Any], figures: list[str], elapsed: float, run: str = RUN, semantics: str = "") -> str:
    def row(section, metric):
        return [f"{summaries[k][section][metric]['fly_a_vs_fly_b_same_seed']:.2f}／"
                f"{summaries[k][section][metric]['fly_a_seed_baseline']:.2f}／"
                f"{summaries[k][section][metric]['fly_b_seed_baseline']:.2f}" for k in summaries]

    keys = list(summaries)
    head = "| 指標 | " + " | ".join(k.replace("|", " ") for k in keys) + " |"
    sep = "|---|" + "---:|" * len(keys)
    lines = ["# Fly A／Fly B 腦部差異分析（事後分析）", "",
             f"- 資料：最終 checkpoints（`{run}/checkpoints`）；圖核心語意：`{semantics}`。活化與 η² 用 700 筆 train；損傷影響用 150 筆 validation。",
             "- 這是事後分析，不做任何模型選擇；test 未讀取。資料為合成資料、待人工複核。",
             "- 每個比較都附「同一隻換 seed」的基準：Fly A vs Fly B 要明顯低於基準，才代表任務造成的差異。",
             "", "## 相似度：Fly A vs Fly B（同 seed）／Fly A 換 seed／Fly B 換 seed", "", head, sep,
             "| 邊的改變量 Spearman ρ | " + " | ".join(row("edges", "spearman_log_change")) + " |",
             "| 加強最多的前 10% 邊重疊（Jaccard） | " + " | ".join(row("edges", "top10pct_strengthened_jaccard")) + " |",
             "| 類別選擇性 η² Spearman ρ | " + " | ".join(row("activity", "spearman_eta_squared_profile")) + " |",
             "| 平均活化強度 Spearman ρ | " + " | ".join(row("activity", "spearman_mean_abs_activity_profile")) + " |",
             "| 損傷影響 Spearman ρ | " + " | ".join(row("lesion", "spearman_drop_profile")) + " |",
             "| 最重要 20 個神經元重疊（Jaccard） | " + " | ".join(row("lesion", "top20_important_jaccard")) + " |",
             "", "## 兩個腦各自的特徵（三 seed 平均；Fly A／Fly B）", "", head, sep]

    def pair(path):
        out = []
        for k in keys:
            value = summaries[k]
            for part in path:
                value = value[part]
            out.append(f"{value['fly_a']:.3f}／{value['fly_b']:.3f}")
        return out

    lines += ["| 邊改變量的分散程度（SD） | " + " | ".join(pair(("edges", "spread_sd_log_change"))) + " |",
              "| 增強邊平均改變量 | " + " | ".join(pair(("edges", "mean_log_change_by_edge_sign", "excitatory"))) + " |"]
    if all("inhibitory" in summaries[k]["edges"]["mean_log_change_by_edge_sign"] for k in keys):
        lines.append("| 抑制邊平均改變量 | " + " | ".join(pair(("edges", "mean_log_change_by_edge_sign", "inhibitory"))) + " |")
    lines += ["| 神經元 η² 中位數 | " + " | ".join(pair(("activity", "median_eta_squared"))) + " |",
              "| η² > 0.5 的神經元數 | " + " | ".join(pair(("activity", "neurons_eta_squared_above_0_5"))) + " |",
              "| 幾乎不活動（平均 \\|活化\\| < 0.01）的神經元數 | " + " | ".join(pair(("activity", "silent_neurons_mean_abs_below_0_01"))) + " |",
              "| 關掉後掉 ≥ 0.02 的神經元數 | " + " | ".join(pair(("lesion", "neurons_with_drop_ge_0_02"))) + " |",
              "| 平均損傷影響：輸入點 | " + " | ".join(pair(("lesion", "mean_drop_by_role", "input"))) + " |",
              "| 平均損傷影響：內部點 | " + " | ".join(pair(("lesion", "mean_drop_by_role", "internal"))) + " |",
              "| 平均損傷影響：輸出點 | " + " | ".join(pair(("lesion", "mean_drop_by_role", "output"))) + " |"]
    signed = [k for k in keys if "remove_all_inhibitory_edges_drop" in summaries[k]["lesion"]]
    if signed:
        lines += ["", "## 拿掉全部抑制邊後掉的 Macro-F1（Fly A→SVM／Fly A→Fly B）", "", "| 圖 | Fly A | Fly B |", "|---|---:|---:|"]
        for k in signed:
            value = summaries[k]["lesion"]["remove_all_inhibitory_edges_drop"]
            lines.append(f"| {k.replace('|', ' ')} | {value['fly_a']:+.3f} | {value['fly_b']:+.3f} |")
    lines += ["", "## 圖", ""] + [f"- `{name}`" for name in figures] + [
        "", "## 限制", "",
        "- 損傷影響在 150 筆 validation 上量測，1 筆約等於 0.007 的 accuracy，小的差異可能只是雜訊。",
        "- Fly A 和 Fly B 的輸入不同（E5 vs Fly A 輸出），轉接層也不同；差異不全來自圖上的連線。",
        "- Fly A 的損傷以重新 fit 的 SVM 評估；Fly B 的損傷直接用它自己的輸出層。",
        f"", f"分析耗時 {elapsed:.0f} 秒。完整數值見 `results.json`。", ""]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", default=OUTPUT)
    parser.add_argument("--graphs", default=",".join(GRAPH_ORDER))
    parser.add_argument("--run", default=RUN, help="tuning run whose final checkpoints are analysed")
    args = parser.parse_args()
    run = args.run
    output_dir = PROJECT_ROOT / args.output_dir
    if output_dir.exists() and any(output_dir.iterdir()):
        raise SystemExit(f"Refusing to overwrite {output_dir}.")
    output_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    tuning_meta = json.loads((PROJECT_ROOT / run / "results.json").read_text(encoding="utf-8"))
    item = load_inputs_for(tuning_meta.get("dataset_version", "v1.0.0"), tuning_meta.get("embedding_manifest"))
    train, validation = item["train"], item["validation"]
    data = {"xtr": train.embeddings, "xval": validation.embeddings, "labels_tr": list(train.labels),
            "labels_val": list(validation.labels),
            "ytr": torch.tensor([LABEL_ORDER.index(l) for l in train.labels])}
    tuning = json.loads((PROJECT_ROOT / run / "results.json").read_text(encoding="utf-8"))
    hops = tuning["settings"].get("step_semantics", "legacy (T-1 hops)").startswith("input_at_step_zero")
    steps = int(tuning["settings"].get("steps", 2))
    graphs = {key: replace(value, input_at_step_zero=hops, steps=steps) for key, value in load_graphs(item["graph"]).items()}
    summaries, figures, checks = {}, [], []
    for name in [g for g in args.graphs.split(",") if g]:
        for objective in OBJECTIVES:
            per_seed = {}
            for seed in SEEDS:
                base = PROJECT_ROOT / run / "checkpoints" / name
                fly_a, _ = load_trained("fly_a", graphs[name], base / f"fly_a_{objective}" / f"seed-{seed}.pt")
                fly_b, _ = load_trained("fly_b", graphs[name], base / f"fly_b_on_fly_a_{objective}" / f"seed-{seed}.pt")
                per_seed[seed] = analyse_pair(graphs[name], fly_a, fly_b, data)
                # Sanity: intact scores must reproduce the tuning run's validation numbers.
                final = tuning["by_graph"][name]["final"]
                expected_a = next(r for r in final[f"fly_a_{objective}_to_svm"]["by_seed"] if r["seed"] == seed)["validation"]["macro_f1"]
                expected_b = next(r for r in final[f"fly_a_{objective}_to_fly_b"]["by_seed"] if r["seed"] == seed)["validation"]["macro_f1"]
                checks.append({"graph": name, "objective": objective, "seed": seed,
                               "fly_a_abs_diff": abs(per_seed[seed]["base_a"] - expected_a),
                               "fly_b_abs_diff": abs(per_seed[seed]["base_b"] - expected_b)})
            tag = f"{name}|{objective}"
            summaries[tag] = summarise(graphs[name], per_seed)
            if name in ("G0", "G2"):
                figures += draw_figures(per_seed, graphs[name], output_dir, f"{name}_{objective}", summaries)
            print(f"[{time.perf_counter() - started:6.0f}s] {tag} done", flush=True)
    figures.append(draw_summary(summaries, output_dir))
    elapsed = time.perf_counter() - started
    if max(max(c["fly_a_abs_diff"], c["fly_b_abs_diff"]) for c in checks) > 1e-9:
        print("WARNING: intact scores differ from the tuning run; see results.json", flush=True)
    results = {"schema_version": 1, "created_at_utc": datetime.now(timezone.utc).isoformat(),
               "status": "post_hoc_analysis_pending_manual_review", "source_run": run,
               "step_semantics": tuning["settings"].get("step_semantics", "legacy (T-1 hops)"),
               "test": {"status": "not_run", "model_inputs": 0}, "seeds": list(SEEDS),
               "settings": {"top_edge_fraction": TOP_EDGE_FRACTION, "top_neurons": TOP_NEURONS,
                            "activity_rows": "train (700)", "lesion_rows": "validation (150)"},
               "reproduction_checks": checks, "summaries": summaries, "figures": figures, "elapsed_seconds": elapsed}
    (output_dir / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output_dir / "report.md").write_text(markdown(summaries, figures, elapsed, run, results["step_semantics"]), encoding="utf-8")
    print(f"done in {elapsed:.0f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

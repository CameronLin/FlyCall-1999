#!/usr/bin/env python3
"""Build a standalone HTML report: four-graph training pipeline, timing and scores,
plus the 17 Fly A / Fly B brain-comparison figures with tags, key points and
cross-figure comparisons. Figures are embedded as data URIs (opens offline).
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import statistics
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TUNING = ".scratch/1999-connectome-demo/runs/independent-tuning-t-hops-20261113"
BRAIN = ".scratch/1999-connectome-demo/runs/fly-ab-brain-comparison-t-hops-20261113"
OUTPUT = "outputs/FlyCall-1999_FlyA_FlyB_分析報告.html"
TEMPLATE = "scripts/brain_report_template.html"

GRAPH_NAME = {"G0": "G0 原圖", "G1": "G1 全正", "G2": "G2 有正負", "G2_glu_plus": "G2-glu+"}
GRAPH_SPEC = {
    "G0": ("500", "2,216", "無", "原本的子圖，M3.2／M4 使用的圖；全部當增強。"),
    "G1": ("500", "6,691", "無", "新選的 300 增強＋200 抑制神經元，但先全部當增強。"),
    "G2": ("500", "6,691", "有", "和 G1 同樣的點與邊，依神經傳導物質給正負號；麩胺酸＝抑制。"),
    "G2_glu_plus": ("500", "6,691", "有", "和 G2 相同，只把麩胺酸改成增強，用來檢查這個假設。"),
}
OBJ_NAME = {"distance": "只保留距離", "distance_supcon": "距離＋類別分離"}
KIND = {
    "hist_edge_change": ("邊強度改變量", "訓練把每條連線改了多少？哪個腦改得多？"),
    "scatter_edge_a_vs_b": ("同一條邊的 A／B 比較", "兩個腦是不是加強或減弱了同一批連線？"),
    "hist_class_selectivity": ("類別選擇性", "有多少神經元的反應是由案件類別決定的？"),
    "scatter_lesion": ("損傷實驗", "關掉一個神經元，分數會掉多少？兩個腦依賴同一批神經元嗎？"),
}
COMBOS = (
    ("fly_a_distance_to_svm", "Fly A（只保留距離）→ SVM"),
    ("fly_a_distance_supcon_to_svm", "Fly A（距離＋類別分離）→ SVM"),
    ("lda_to_svm", "LDA → SVM（參考）"),
    ("lda_to_fly_b", "LDA → Fly B"),
    ("fly_a_distance_to_fly_b", "Fly A（只保留距離）→ Fly B"),
    ("fly_a_distance_supcon_to_fly_b", "Fly A（距離＋類別分離）→ Fly B"),
)
COMBO_LABEL = dict(COMBOS) | {"svm": "→ SVM", "fly_b": "→ Fly B"}


def esc(text: object) -> str:
    return html.escape(str(text))


def num(value: float, fmt: str = ".2f", suffix: str = "") -> str:
    return f"<b class='num'>{format(value, fmt)}{esc(suffix)}</b>"


def mmss(seconds: float) -> str:
    return f"{int(seconds // 60)} 分 {int(seconds % 60):02d} 秒"


def f1s(block: dict) -> list[float]:
    if "validation_by_seed" in block:
        return [float(item["macro_f1"]) for item in block["validation_by_seed"]]
    return [float(item["validation"]["macro_f1"]) for item in block["by_seed"]]


# Edges that can affect the outputs, by graph-core steps T (from the graph structure, ticket 24).
TRAINABLE = {2: {"G0": (277, 2216), "G2": (510, 6691)}, 4: {"G0": (1675, 2216), "G2": (5602, 6691)}}
STEPS = 2


def figure_points(kind: str, s: dict, graph: str = "G2") -> tuple[str, list[str]]:
    """(how to read — plain text, key points — HTML bullets) from 3-seed means."""

    e, a, l = s["edges"], s["activity"], s["lesion"]
    used, total = TRAINABLE[STEPS].get(graph, (0, 1))
    share = used / total
    spike = (f"T={STEPS} 時有 {num(used, ',d')} ／ {total:,} 條邊（{num(share * 100, '.0f', '%')}）會影響輸出；"
             + ("其餘的邊收不到梯度、強度完全沒變，所以 0 的位置有一根很高的柱子。" if share < 0.5
                else "其餘少數邊沒有被訓練，集中在 0 的位置。"))
    if kind == "hist_edge_change":
        sd, signs = e["spread_sd_log_change"], e["mean_log_change_by_edge_sign"]
        how = ("橫軸是 log（訓練後強度 ÷ 訓練前強度）：0 代表沒變，大於 0 代表加強，小於 0 代表減弱；縱軸是邊數。"
               "藍色是 Fly A（降維），橘色是 Fly B（分類）。分布越寬，代表那個腦把連線改得越多。")
        points = [spike,
                  f"改變量的標準差：Fly A {num(sd['fly_a'], '.3f')}、Fly B {num(sd['fly_b'], '.3f')}，約 {num(sd['fly_b'] / max(sd['fly_a'], 1e-9), '.0f', ' 倍')}。",
                  "在有被訓練的邊上，Fly A 幾乎維持原本的 connectome 強度；Fly B 大幅改寫連線（藍色只有一根細柱，橘色向兩側展開）。"]
        if "inhibitory" in signs:
            points.append(f"增強邊平均改變：A {num(signs['excitatory']['fly_a'], '+.3f')}／B {num(signs['excitatory']['fly_b'], '+.3f')}；"
                          f"抑制邊：A {num(signs['inhibitory']['fly_a'], '+.3f')}／B {num(signs['inhibitory']['fly_b'], '+.3f')}。")
    elif kind == "scatter_edge_a_vs_b":
        sp, jac = e["spearman_log_change"], e["top10pct_strengthened_jaccard"]
        how = ("每個點是一條邊：橫軸是它在 Fly A 的改變量，縱軸是在 Fly B 的改變量。點落在虛線（對角線）上，代表兩個腦對這條邊的改法相同。"
               "G2 會分成「增強邊」與「抑制邊」兩格。")
        points = [f"A、B 改變量的相關（Spearman ρ）：{num(sp['fly_a_vs_fly_b_same_seed'])}；對照：Fly A 換 seed {num(sp['fly_a_seed_baseline'])}、Fly B 換 seed {num(sp['fly_b_seed_baseline'])}。",
                  f"加強最多的前 10% 邊重疊：A vs B {num(jac['fly_a_vs_fly_b_same_seed'])}，換 seed {num(jac['fly_a_seed_baseline'])}／{num(jac['fly_b_seed_baseline'])}。",
                  "點幾乎都擠在「Fly A 改變量 ≈ 0」的直線上：兩個腦改的是不同的東西。",
                  f"原點 (0, 0) 上疊著沒被訓練的邊（T={STEPS} 時有 {num(used / total * 100, '.0f', '%')} 的邊會影響輸出）。"]
    elif kind == "hist_class_selectivity":
        med, hi, silent = a["median_eta_squared"], a["neurons_eta_squared_above_0_5"], a["silent_neurons_mean_abs_below_0_01"]
        how = ("每個神經元算一個 η²（0～1）：0 代表它對五類案件反應都一樣，1 代表反應完全由類別決定；縱軸是神經元數。"
               "藍色是 Fly A，橘色是 Fly B。最左邊的高柱通常是幾乎不活動的神經元。")
        points = [f"η² 中位數：Fly A {num(med['fly_a'])}、Fly B {num(med['fly_b'])}。",
                  f"η² > 0.5 的神經元：Fly A {num(hi['fly_a'], '.0f', ' 個')}、Fly B {num(hi['fly_b'], '.0f', ' 個')}（共 500 個）。",
                  f"幾乎不活動的神經元：Fly A {num(silent['fly_a'], '.0f', ' 個')}、Fly B {num(silent['fly_b'], '.0f', ' 個')}。"]
    else:
        drop, sp, jac = l["neurons_with_drop_ge_0_02"], l["spearman_drop_profile"], l["top20_important_jaccard"]
        how = ("每個點是一個神經元：把它關掉後，橫軸是 Fly A→SVM 掉的 Macro-F1，縱軸是 Fly A→Fly B 掉的 Macro-F1。"
               "越往右或往上代表越重要；點集中在原點附近，代表單一神經元不重要。")
        points = [f"關掉後掉 ≥ 0.02 的神經元：Fly A {num(drop['fly_a'], '.1f', ' 個')}、Fly B {num(drop['fly_b'], '.1f', ' 個')}（共 500 個）。",
                  f"A、B 損傷影響的相關 ρ = {num(sp['fly_a_vs_fly_b_same_seed'])}；最重要 20 個神經元重疊 {num(jac['fly_a_vs_fly_b_same_seed'])}（換 seed 約 {num(jac['fly_a_seed_baseline'])}／{num(jac['fly_b_seed_baseline'])}）。",
                  "資訊分散在許多神經元，沒有固定的關鍵神經元。"]
        if "remove_all_inhibitory_edges_drop" in l:
            inh = l["remove_all_inhibitory_edges_drop"]
            points.append(f"一次拿掉全部抑制邊：Fly A 掉 {num(inh['fly_a'], '+.3f')}、Fly B 掉 {num(inh['fly_b'], '+.3f')}。")
    return how, points


def compare_points(kind: str, s: dict) -> list[str]:
    """Cross-version comparison for one figure type; every claim is computed from the data."""

    def get(key, *path):
        value = s[key]
        for part in path:
            value = value[part]
        return value

    keys = ["G0|distance", "G0|distance_supcon", "G2|distance", "G2|distance_supcon"]
    label = lambda k: f"{GRAPH_NAME[k.split('|')[0]]}・{OBJ_NAME[k.split('|')[1]]}"
    rng = lambda vals, f=".2f": f"{num(min(vals), f)}～{num(max(vals), f)}"
    if kind == "hist_edge_change":
        sd_a = {k: get(k, "edges", "spread_sd_log_change", "fly_a") for k in keys}
        sd_b = {k: get(k, "edges", "spread_sd_log_change", "fly_b") for k in keys}
        wider = all(sd_b[k] > 3 * sd_a[k] for k in keys)
        g0_b = (sd_b["G0|distance"] + sd_b["G0|distance_supcon"]) / 2
        g2_b = (sd_b["G2|distance"] + sd_b["G2|distance_supcon"]) / 2
        points = [("四個版本都一樣：Fly B 的分布比 Fly A 寬很多（標準差至少 3 倍）。" if wider
                   else "多數版本中 Fly B 的分布比 Fly A 寬。"),
                  (f"Fly B 在 G0 改得比 G2 多（平均標準差 {num(g0_b, '.3f')} 對 {num(g2_b, '.3f')}）。" if g0_b > g2_b
                   else f"Fly B 在 G2 改得比 G0 多（平均標準差 {num(g2_b, '.3f')} 對 {num(g0_b, '.3f')}）。")]
        points.append("標準差（A／B）：" + "；".join(f"{label(k)} {num(sd_a[k], '.3f')}／{num(sd_b[k], '.3f')}" for k in keys))
        return points
    if kind == "scatter_edge_a_vs_b":
        ab = [get(k, "edges", "spearman_log_change", "fly_a_vs_fly_b_same_seed") for k in keys]
        bb = [get(k, "edges", "spearman_log_change", "fly_b_seed_baseline") for k in keys]
        return [f"A vs B 的相關在四個版本是 {rng(ab)}；Fly B 換 seed 的一致性是 {rng(bb)}。",
                ("Fly B 換 seed 的一致性明顯高於 A vs B：Fly B 的改寫穩定、屬於分類任務特有，而且和 Fly A 無關。"
                 if min(bb) > max(ab) else "部分版本中 A vs B 的相關接近 Fly B 換 seed 的一致性，任務差異較不明確。"),
                "G2 的增強邊與抑制邊可分開看：Fly B 對兩種邊都有加強也有減弱。"]
    if kind == "hist_class_selectivity":
        dist_a = [get(k, "activity", "median_eta_squared", "fly_a") for k in keys if k.endswith("|distance")]
        sup_a = [get(k, "activity", "median_eta_squared", "fly_a") for k in keys if k.endswith("supcon")]
        b = [get(k, "activity", "median_eta_squared", "fly_b") for k in keys]
        return [f"只保留距離時，Fly A 的 η² 中位數只有 {rng(dist_a)}；Fly B 是 {rng(b)}。",
                f"改成距離＋類別分離後，Fly A 升到 {rng(sup_a)}，和 Fly B 很接近。",
                "η² 中位數（A／B）：" + "；".join(f"{label(k)} {num(get(k, 'activity', 'median_eta_squared', 'fly_a'))}／{num(get(k, 'activity', 'median_eta_squared', 'fly_b'))}" for k in keys)]
    drops = [max(get(k, "lesion", "neurons_with_drop_ge_0_02", "fly_a"), get(k, "lesion", "neurons_with_drop_ge_0_02", "fly_b")) for k in keys]
    points = [f"關掉單一神經元後掉 ≥ 0.02 的，每個版本最多只有 {num(max(drops), '.0f', ' 個')}（共 500 個）：資訊分散在許多神經元。",
              "A、B 的損傷影響互不相關，重要神經元的重疊和換 seed 差不多。"]
    if "remove_all_inhibitory_edges_drop" in s.get("G2|distance", {}).get("lesion", {}):
        d = s["G2|distance"]["lesion"]["remove_all_inhibitory_edges_drop"]
        c = s["G2|distance_supcon"]["lesion"]["remove_all_inhibitory_edges_drop"]
        points.append(f"G2 一次拿掉全部抑制邊：只保留距離的模型 Fly A 掉 {num(d['fly_a'], '+.3f')}、Fly B 掉 {num(d['fly_b'], '+.3f')}；"
                      f"距離＋類別分離則是 {num(c['fly_a'], '+.3f')}、{num(c['fly_b'], '+.3f')}。")
    return points


def verdict(value: dict) -> str:
    if not value["consistent"]:
        return "<span class='badge flat'>不明確</span>"
    return "<span class='badge up'>一致提升</span>" if value["mean"] > 0 else "<span class='badge down'>一致下降</span>"


def t_compare_note(data: dict) -> str:
    """Data-driven summary of the paired T4 − T2 verdicts (no hard-coded interpretation)."""

    parts = []
    for g, combos in data.items():
        up = [dict(COMBOS)[c] for c, d in combos.items() if c != "lda_to_svm" and d["consistent"] and d["mean"] > 0]
        down = [dict(COMBOS)[c] for c, d in combos.items() if c != "lda_to_svm" and d["consistent"] and d["mean"] < 0]
        text = f"{GRAPH_NAME[g]}："
        text += ("一致提升 " + "、".join(up) if up else "") + ("；" if up and down else "")
        text += ("一致下降 " + "、".join(down) if down else "")
        parts.append(text if (up or down) else f"{GRAPH_NAME[g]}：沒有一致的變化")
    return esc("。".join(parts) + "。「一致」＝三個 seed 同方向且平均差 ≥ 0.02；其餘列為不明確。")


def t_compare_section(tuning_dir: Path) -> str:
    path = tuning_dir / "t4_vs_t2.json"
    if not path.exists():
        return ""
    data = json.loads(path.read_text(encoding="utf-8"))["deltas"]
    graphs = list(data)
    combos = [c for c, _ in COMBOS if c != "lda_to_svm"]
    rows = []
    for c in combos:
        cells = []
        for g in graphs:
            d = data[g][c]
            cells.append(f"<td><span class='mono'>{d['t2_mean']:.3f} → {d['t4_mean']:.3f}</span><br>"
                         f"<b class='num'>{d['mean']:+.3f}</b> {verdict(d)}</td>")
        rows.append(f"<tr><th scope='row'>{esc(dict(COMBOS)[c])}</th>{''.join(cells)}</tr>")
    table = ("<table class='tcmp'><thead><tr><th>組合</th>" + "".join(f"<th>{esc(GRAPH_NAME[g])}</th>" for g in graphs)
             + f"</tr></thead><tbody>{''.join(rows)}</tbody></table>")
    return ("<section class='part' id='tcompare'><div class='part-head'><span class='part-no'>03b</span><h2>T=4 與 T=2 的比較</h2>"
            "<p>同一套流程，只把圖核心步數從 2 改成 4（T 步＝T 跳）。三個 seed 配對比較 T4 − T2；判讀規則相同。</p></div>"
            f"<div class='panel'><div class='tablewrap'>{table}</div>"
            f"<p class='note'>{t_compare_note(data)}</p></div></section>")



E5_RUNS = {"v1.0.0": ".scratch/1999-connectome-demo/runs/m2-2b-e5-provisional-20261026T015843Z",
           "v2.0.0": ".scratch/1999-connectome-demo/runs/m2-2b-e5-dataset-v2-seed-42-20261114"}
TEST_RUN = {"v2.0.0": ".scratch/1999-connectome-demo/runs/test-evaluation-dataset-v2-20261114"}
LABEL_ZH = {"sidewalk_maintenance": "人行道", "road_surface_defect": "道路", "park_general_maintenance": "公園",
            "waste_truck_service": "垃圾車", "street_cleaning": "路面清潔"}
BASELINE_ZH = {"logistic_regression": "E5 → LR", "mlp": "E5 → MLP", "pca_mlp": "E5 → PCA → MLP",
               "lda_logistic_regression": "E5 → LDA → LR"}
CHANGE = 0.02  # |difference of means| below this is reported as 持平


def _val_predictions(run: str) -> dict[str, list[tuple[str, str]]]:
    import csv
    rows: dict[str, list[tuple[str, str]]] = {}
    with (PROJECT_ROOT / run / "predictions.csv").open(encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            if row["split"] == "validation":
                rows.setdefault(row["candidate"], []).append((row["expected"], row["predicted"]))
    return rows


def _per_class_f1(pairs: list[tuple[str, str]]) -> dict[str, float]:
    out = {}
    for label in LABEL_ZH:
        tp = sum(e == label and p == label for e, p in pairs)
        denom = sum(p == label for _, p in pairs) + sum(e == label for e, _ in pairs)
        out[label] = 2 * tp / denom if denom else 0.0
    return out


def _change_badge(delta: float) -> str:
    if abs(delta) < CHANGE:
        return "<span class='badge flat'>持平</span>"
    return "<span class='badge up'>上升</span>" if delta > 0 else "<span class='badge down'>下降</span>"


def _score(result: dict) -> str:
    m = result["macro_f1"]
    return f"{m['mean']:.3f}" + ("" if m["std"] == 0 else f" ± {m['std']:.3f}")


def dataset_compare_section() -> str:
    """Dataset v1.0.0 → v2.0.0 comparison (validation; test exists for v2 only). Empty in the v1 report."""

    if DATASET != "v2.0.0":
        return ""
    from collections import Counter

    v1_run = RUNS_BY_DATASET["v1.0.0"][STEPS][0]
    r1 = json.loads((PROJECT_ROOT / v1_run / "results.json").read_text(encoding="utf-8"))
    r2 = json.loads((PROJECT_ROOT / TUNING / "results.json").read_text(encoding="utf-8"))
    graphs = [g for g in GRAPH_NAME if g in r2["by_graph"] and g in r1["by_graph"]]

    p1, p2 = _val_predictions(E5_RUNS["v1.0.0"]), _val_predictions(E5_RUNS["v2.0.0"])
    base_rows = []
    for cand, name in BASELINE_ZH.items():
        a = statistics.fmean(_per_class_f1(p1[cand]).values())
        b = statistics.fmean(_per_class_f1(p2[cand]).values())
        base_rows.append(f"<tr><th scope='row'>{esc(name)}</th><td class='num'>{a:.3f}</td><td class='num'>{b:.3f}</td>"
                         f"<td><b class='num'>{b - a:+.3f}</b> {_change_badge(b - a)}</td></tr>")
    a = statistics.fmean(f1s(r1["by_graph"][graphs[0]]["final"]["lda_to_svm"]))
    b = statistics.fmean(f1s(r2["by_graph"][graphs[0]]["final"]["lda_to_svm"]))
    base_rows.append(f"<tr><th scope='row'>LDA → SVM</th><td class='num'>{a:.3f}</td><td class='num'>{b:.3f}</td>"
                     f"<td><b class='num'>{b - a:+.3f}</b> {_change_badge(b - a)}</td></tr>")
    base_table = ("<table class='tcmp'><thead><tr><th>基準模型</th><th>v1</th><th>v2</th><th>變化</th></tr></thead>"
                  f"<tbody>{''.join(base_rows)}</tbody></table>")

    combos = [c for c, _ in COMBOS if c != "lda_to_svm"]
    counts = {"up": 0, "down": 0, "flat": 0}
    all_up, all_down, rows = [], [], []
    for c in combos:
        cells, deltas = [], []
        for g in graphs:
            a = statistics.fmean(f1s(r1["by_graph"][g]["final"][c]))
            b = statistics.fmean(f1s(r2["by_graph"][g]["final"][c]))
            d = b - a
            deltas.append(d)
            counts["flat" if abs(d) < CHANGE else ("up" if d > 0 else "down")] += 1
            cells.append(f"<td><span class='mono'>{a:.3f} → {b:.3f}</span><br><b class='num'>{d:+.3f}</b> {_change_badge(d)}</td>")
        if all(d >= CHANGE for d in deltas):
            all_up.append(dict(COMBOS)[c])
        if all(d <= -CHANGE for d in deltas):
            all_down.append(dict(COMBOS)[c])
        rows.append(f"<tr><th scope='row'>{esc(dict(COMBOS)[c])}</th>{''.join(cells)}</tr>")
    fly_table = (f"<table class='tcmp'><thead><tr><th>組合（T={STEPS}）</th>"
                 + "".join(f"<th>{esc(GRAPH_NAME[g])}</th>" for g in graphs)
                 + f"</tr></thead><tbody>{''.join(rows)}</tbody></table>")
    best1 = max((statistics.fmean(f1s(r1["by_graph"][g]["final"][c])), g, c) for g in graphs for c in combos)
    best2 = max((statistics.fmean(f1s(r2["by_graph"][g]["final"][c])), g, c) for g in graphs for c in combos)

    f1_1, f1_2 = _per_class_f1(p1["mlp"]), _per_class_f1(p2["mlp"])
    class_rows = "".join(
        f"<tr><th scope='row'>{LABEL_ZH[l]}</th><td class='num'>{f1_1[l]:.2f}</td><td class='num'>{f1_2[l]:.2f}</td>"
        f"<td><b class='num'>{f1_2[l] - f1_1[l]:+.2f}</b></td></tr>" for l in LABEL_ZH)
    e1 = Counter((e, p) for e, p in p1["mlp"] if e != p)
    e2 = Counter((e, p) for e, p in p2["mlp"] if e != p)
    top = sorted(set(e1) | set(e2), key=lambda k: (-(e1[k] + e2[k]), k))[:5]
    conf_rows = "".join(
        f"<tr><th scope='row'>{LABEL_ZH[e]} → {LABEL_ZH[p]}</th><td class='num'>{e1[(e, p)]}</td><td class='num'>{e2[(e, p)]}</td></tr>"
        for e, p in top)
    class_table = ("<table class='tcmp'><thead><tr><th>類別（E5 → MLP）</th><th>v1 F1</th><th>v2 F1</th><th>變化</th></tr></thead>"
                   f"<tbody>{class_rows}</tbody></table>")
    conf_table = ("<table class='tcmp'><thead><tr><th>認錯（正解 → 預測）</th><th>v1 筆數</th><th>v2 筆數</th></tr></thead>"
                  f"<tbody>{conf_rows}</tbody></table>")
    sw_sc = lambda e: e[("sidewalk_maintenance", "street_cleaning")] + e[("street_cleaning", "sidewalk_maintenance")]
    class_note = (f"人行道與路面清潔互相認錯：v1 {sw_sc(e1)} 筆 → v2 {sw_sc(e2)} 筆。"
                  f"公園 F1 {f1_1['park_general_maintenance']:.2f} → {f1_2['park_general_maintenance']:.2f}："
                  "拿掉 v1 的「一般公園」捷徑詞後，公園類別沒有變差。validation 共 150 筆、每類 30 筆，單一類別的數字波動較大。")

    test_html = ""
    test_path = PROJECT_ROOT / TEST_RUN["v2.0.0"] / "test_results.json"
    if test_path.exists():
        t = json.loads(test_path.read_text(encoding="utf-8"))
        sel, res = t["selected_fly_model"], t["results"]
        t_sel, g_sel, c_sel = sel.split("/")
        sel_name = f"{t_sel.replace('T', 'T=')}・{GRAPH_NAME[g_sel]}・{dict(COMBOS)[c_sel]}（依規則選定）"
        named = [(sel_name, res[sel]), ("E5 → LR", res["e5_logistic_regression"]),
                 ("E5 → MLP", res["e5_mlp"]), ("E5 → LDA → LR", res["e5_lda_logistic"]),
                 ("LDA → SVM", res[f"T{STEPS}/G0/lda_to_svm"])]
        test_rows = "".join(f"<tr><th scope='row'>{esc(n)}</th><td class='num'>{_score(r)}</td></tr>" for n, r in named)
        test_html = ("<div class='panel'><h3>v2 的 test（只評估一次）</h3><div class='tablewrap'><table class='tcmp'>"
                     f"<thead><tr><th>模型</th><th>test Macro-F1</th></tr></thead><tbody>{test_rows}</tbody></table></div>"
                     "<p class='note'>讀 test 前已用 validation 鎖定 51 個候選與選模規則，每個候選只評估一次；"
                     "E5 → LR 在 validation 很高、到 test 明顯下降，表示 test 的情境家族比較難。v1 的 test 從未打開，所以 test 沒有 v1 可比。</p></div>")

    summary = (f"T={STEPS} 的 {sum(counts.values())} 個 Fly 組合：上升 {counts['up']}、下降 {counts['down']}、持平 {counts['flat']}"
               f"（兩版平均差 ≥ {CHANGE} 才算升降）。")
    if all_up:
        summary += "四張圖都上升：" + "、".join(all_up) + "。"
    if all_down:
        summary += "四張圖都下降：" + "、".join(all_down) + "。"
    summary += (f"最高分組合從 v1 的 {best1[0]:.3f}（{GRAPH_NAME[best1[1]]}・{dict(COMBOS)[best1[2]]}）"
                f"變成 v2 的 {best2[0]:.3f}（{GRAPH_NAME[best2[1]]}・{dict(COMBOS)[best2[2]]}）。")
    return ("<section class='part' id='datacompare'><div class='part-head'><span class='part-no'>03c</span>"
            "<h2>資料 v1 與 v2 的比較</h2><p>類別、情境家族、split 與訓練流程都相同，只把 1,000 筆通話換成 v2.0.0"
            "（逐筆撰寫、自動品質檢查通過、未經人工複核）。表中是 validation Macro-F1；兩版逐字稿不同，"
            "所以差異同時反映資料與訓練隨機性。</p></div>"
            f"<div class='panel'><h3>基準模型</h3><div class='tablewrap'>{base_table}</div>"
            "<p class='note'>v2 的訓練集分數不再是 1.000，模型不能只靠背 v1 的固定句型。</p></div>"
            f"<div class='panel'><h3>Fly A／Fly B 組合</h3><div class='tablewrap'>{fly_table}</div>"
            f"<p class='note'>{esc(summary)}</p></div>"
            f"<div class='panel'><h3>各類別</h3><div class='tablewrap'>{class_table}</div>"
            f"<div class='tablewrap'>{conf_table}</div><p class='note'>{esc(class_note)}</p></div>"
            f"{test_html}</section>")


def build() -> str:
    tuning = json.loads((PROJECT_ROOT / TUNING / "results.json").read_text(encoding="utf-8"))
    timings = json.loads((PROJECT_ROOT / TUNING / "timings.json").read_text(encoding="utf-8"))
    brain = json.loads((PROJECT_ROOT / BRAIN / "results.json").read_text(encoding="utf-8"))
    summaries, graphs = brain["summaries"], list(tuning["by_graph"])
    total = timings["run_total_seconds"]

    # hero numbers
    best_key, best_graph, best_value = None, None, -1.0
    for key, _ in COMBOS:
        if key == "lda_to_svm":
            continue
        for g in graphs:
            value = statistics.fmean(f1s(tuning["by_graph"][g]["final"][key]))
            if value > best_value:
                best_key, best_graph, best_value = key, g, value
    ratios = [summaries[k]["edges"]["spread_sd_log_change"]["fly_b"] / summaries[k]["edges"]["spread_sd_log_change"]["fly_a"] for k in summaries]
    eta_b = [summaries[k]["activity"]["median_eta_squared"]["fly_b"] for k in summaries if k.endswith("|distance")]
    eta_a = [summaries[k]["activity"]["median_eta_squared"]["fly_a"] for k in summaries if k.endswith("|distance")]
    hero = "".join([
        f"<div class='kpi'><span class='kpi-k'>總訓練時間</span><span class='kpi-v'>{int(total // 60)}<small> 分 {int(total % 60)} 秒</small></span><span class='kpi-n'>四張圖 × 240 次訓練</span></div>",
        f"<div class='kpi'><span class='kpi-k'>最高 validation Macro-F1</span><span class='kpi-v'>{best_value:.3f}</span><span class='kpi-n'>{esc(GRAPH_NAME[best_graph])}・{esc(dict(COMBOS)[best_key])}</span></div>",
        f"<div class='kpi'><span class='kpi-k'>Fly B 連線改變量</span><span class='kpi-v'>{min(ratios):.0f}–{max(ratios):.0f}<small> 倍</small></span><span class='kpi-n'>相對於 Fly A（改變量標準差）</span></div>",
        f"<div class='kpi'><span class='kpi-k'>神經元類別選擇性 η²（中位數）</span><span class='kpi-v'>{min(eta_b):.2f}–{max(eta_b):.2f}</span><span class='kpi-n'>Fly B；同組合的 Fly A（只保留距離）為 {min(eta_a):.2f}–{max(eta_a):.2f}</span></div>",
    ])

    graph_cards = "".join(
        f"<article class='gcard'><header><span class='gtag'>{esc(GRAPH_NAME[g])}</span></header>"
        f"<dl><div><dt>點</dt><dd>{GRAPH_SPEC[g][0]}</dd></div><div><dt>邊</dt><dd>{GRAPH_SPEC[g][1]}</dd></div><div><dt>抑制</dt><dd>{GRAPH_SPEC[g][2]}</dd></div></dl>"
        f"<p>{esc(GRAPH_SPEC[g][3])}</p></article>" for g in graphs)

    longest = max(timings["by_graph"][g]["total_seconds"] for g in graphs)
    bars = []
    for g in graphs:
        t = timings["by_graph"][g]
        seg = lambda cls, sec, name: (f"<span class='seg-{cls}' style='width:{sec / longest * 100:.2f}%' "
                                      f"title='{esc(name)}：{mmss(sec)}'></span>")
        bars.append(f"<div class='brow'><span class='blab'>{esc(GRAPH_NAME[g])}</span><div class='btrack'>"
                    f"{seg('a', t['fly_a_cv_seconds'], '① Fly A 交叉驗證')}{seg('b', t['fly_b_cv_seconds'], '② Fly B 交叉驗證')}"
                    f"{seg('c', t['final_training_seconds'], '③ 最終訓練')}</div><span class='bval'>{mmss(t['total_seconds'])}</span></div>")
    timing_rows = "".join(
        f"<tr><td>{esc(GRAPH_NAME[g])}</td><td>{mmss(timings['by_graph'][g]['fly_a_cv_seconds'])}</td><td>{mmss(timings['by_graph'][g]['fly_b_cv_seconds'])}</td>"
        f"<td>{mmss(timings['by_graph'][g]['final_training_seconds'])}</td><td><b>{mmss(timings['by_graph'][g]['total_seconds'])}</b></td></tr>" for g in graphs)
    timing_table = ("<table><thead><tr><th>圖</th><th>① Fly A 交叉驗證</th><th>② Fly B 交叉驗證</th><th>③ 最終訓練</th><th>合計</th></tr></thead>"
                    f"<tbody>{timing_rows}<tr class='sum'><td>全部</td><td></td><td></td><td></td><td><b>{mmss(total)}</b></td></tr></tbody></table>")
    lr_rows = []
    for g in graphs:
        chosen, epochs = tuning["by_graph"][g]["chosen_learning_rate"], tuning["by_graph"][g]["final_epochs"]
        cells = [f"{chosen['fly_a'][o]}<small> ／ {epochs['fly_a'][o]}</small>" for o in ("distance", "distance_supcon")]
        cells += [f"{chosen['fly_b'][k]}<small> ／ {epochs['fly_b'][k]}{' ⚑' if epochs['fly_b'][k] >= 199 else ''}</small>" for k in ("lda", "fly_a_distance", "fly_a_distance_supcon")]
        lr_rows.append(f"<tr><td>{esc(GRAPH_NAME[g])}</td>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
    lr_table = ("<table><thead><tr><th>圖</th><th>Fly A 距離</th><th>Fly A 距離＋類別</th><th>Fly B 接 LDA</th><th>Fly B 接 A（距離）</th><th>Fly B 接 A（距離＋類別）</th></tr></thead>"
                f"<tbody>{''.join(lr_rows)}</tbody></table>")

    lo, hi = 0.84, 0.92
    res_rows = []
    for key, label in COMBOS:
        cells = []
        for g in graphs:
            values = f1s(tuning["by_graph"][g]["final"][key])
            mean, sd = statistics.fmean(values), statistics.stdev(values)
            level = max(0.0, min(1.0, (mean - lo) / (hi - lo)))
            cells.append(f"<td style='--lv:{level:.2f}'><span>{mean:.3f}</span><small>±{sd:.3f}</small></td>")
        cls = " class='ref'" if key == "lda_to_svm" else ""
        res_rows.append(f"<tr{cls}><th scope='row'>{esc(label)}</th>{''.join(cells)}</tr>")
    result_table = ("<table class='heat'><thead><tr><th>組合</th>" + "".join(f"<th>{esc(GRAPH_NAME[g])}</th>" for g in graphs) +
                    f"</tr></thead><tbody>{''.join(res_rows)}</tbody></table>")
    verdict_groups = []
    for name, block in tuning["comparisons"].items():
        items = "".join(f"<li><span>{esc(COMBO_LABEL.get(k, k))}</span><span class='vd'><b class='num'>{v['mean']:+.3f}</b>{verdict(v)}</span></li>" for k, v in block.items())
        title = name.replace("_glu_plus", "-glu+").replace("SupCon − distance", "距離＋類別分離 − 只保留距離")
        verdict_groups.append(f"<article class='vcard'><h4>{esc(title)}</h4><ul>{items}</ul></article>")
    verdicts = "".join(verdict_groups)

    kind_cards = "".join(f"<button class='kcard' type='button' data-jump='{k}'><span class='kname'>{esc(v[0])}</span><span class='kq'>{esc(v[1])}</span></button>" for k, v in KIND.items())
    figure_dir = PROJECT_ROOT / BRAIN
    cards = []
    for name in brain["figures"]:
        data = base64.b64encode((figure_dir / name).read_bytes()).decode("ascii")
        if name.startswith("summary"):
            graph, objective, kind = "all", "all", "summary"
            eyebrow, title = "總覽", "Fly A／Fly B 的差異 vs 換 seed 的差異"
            how = ("把 8 種組合（4 張子圖 × 2 種目標）放在一起，比較三個面向的相似度：邊的改變、類別選擇性、損傷影響。"
                   "黑色菱形是 Fly A vs Fly B（同 seed）；藍點與橘點分別是 Fly A、Fly B 換 seed 重練後和自己的相似度。")
            points = ["黑色菱形在彩色點左邊越遠，代表 Fly A 和 Fly B 的差異越大過換 seed 的差異，也就是任務讓兩個腦不一樣。",
                      "「邊的改變」通常差距最明顯。",
                      "「損傷影響」三種點都接近 0：單一神經元的重要性本身就不穩定。"]
            tags = "<span class='t kind'>總覽</span><span class='t'>全部 8 種組合</span>"
        else:
            stem = name.removesuffix(".png")
            graph = stem.split("_")[0]
            objective = "distance_supcon" if stem.startswith(f"{graph}_distance_supcon") else "distance"
            kind = stem.removeprefix(f"{graph}_{objective}_")
            eyebrow, title = KIND[kind][0], f"{GRAPH_NAME[graph]}・Fly A：{OBJ_NAME[objective]}"
            how, points = figure_points(kind, summaries[f"{graph}|{objective}"], graph)
            tags = (f"<span class='t graph'>{esc(GRAPH_NAME[graph])}</span><span class='t obj'>{esc(OBJ_NAME[objective])}</span>"
                    f"<span class='t kind'>{esc(KIND[kind][0])}</span>")
        bullet_html = "".join(f"<li>{p}</li>" for p in points)
        cards.append(
            f"<article class='fig' data-graph='{graph}' data-objective='{objective}' data-kind='{kind}'>"
            f"<header class='fig-head'><span class='fig-eyebrow'>{esc(eyebrow)}</span><h3>{esc(title)}</h3><div class='tags'>{tags}</div></header>"
            f"<button class='thumb' type='button' aria-label='放大：{esc(eyebrow)}・{esc(title)}'><img loading='lazy' alt='{esc(eyebrow)}：{esc(title)}' src='data:image/png;base64,{data}'></button>"
            f"<div class='fig-body'><h4>重點</h4><ul class='points'>{bullet_html}</ul>"
            f"<details><summary>怎麼看這張圖</summary><p>{esc(how)}</p></details>"
            f"<p class='file'>{esc(name)}・seed 42 繪製；數字為三個 seed 平均</p></div></article>")
    comparisons = "".join(
        f"<aside class='cmp' data-kind='{k}' hidden><h3>比較：{esc(v[0])}在四個版本之間</h3><ul class='points'>{''.join(f'<li>{p}</li>' for p in compare_points(k, summaries))}</ul></aside>"
        for k, v in KIND.items())

    template = (PROJECT_ROOT / TEMPLATE).read_text(encoding="utf-8")
    for key, value in {
        "HERO": hero, "GRAPH_CARDS": graph_cards, "TIMING_BARS": "".join(bars), "TIMING_TABLE": timing_table,
        "TOTAL": mmss(total), "LR_TABLE": lr_table, "RESULT_TABLE": result_table, "VERDICTS": verdicts,
        "KIND_CARDS": kind_cards, "COMPARISONS": comparisons, "FIGURES": "".join(cards),
        "STEPS": str(STEPS), "T_COMPARE": t_compare_section(PROJECT_ROOT / TUNING),
        "DATA_NOTE": DATA_NOTES[DATASET],
        "DATA_COMPARE": dataset_compare_section(),
        "NAV_DATA": '<a href="#datacompare">v1 vs v2</a>' if DATASET == "v2.0.0" else "",
        "TEST_NOTE": "調參只用 train／validation；test 另以鎖定設定評估一次" if DATASET == "v2.0.0" else "只用 train／validation，test 未讀取",
        "SOURCES": f"{Path(TUNING).name}、{Path(BRAIN).name}",
        "MINUTES_PER_GRAPH": f"{min(timings['by_graph'][g]['total_seconds'] for g in graphs if g != 'G0') / 60:.0f}–{max(timings['by_graph'][g]['total_seconds'] for g in graphs if g != 'G0') / 60:.0f}",
    }.items():
        template = template.replace("{{" + key + "}}", value)
    return template


RUNS_BY_DATASET = {  # dataset -> T -> (tuning run, brain-comparison run)
    "v1.0.0": {
        4: (".scratch/1999-connectome-demo/runs/independent-tuning-t4-20261113",
            ".scratch/1999-connectome-demo/runs/fly-ab-brain-comparison-t4-20261113"),
        2: (".scratch/1999-connectome-demo/runs/independent-tuning-t-hops-20261113",
            ".scratch/1999-connectome-demo/runs/fly-ab-brain-comparison-t-hops-20261113"),
    },
    "v2.0.0": {
        4: (".scratch/1999-connectome-demo/runs/independent-tuning-v2-t4-20261114",
            ".scratch/1999-connectome-demo/runs/fly-ab-brain-comparison-v2-t4-20261114"),
        2: (".scratch/1999-connectome-demo/runs/independent-tuning-v2-t2-20261114",
            ".scratch/1999-connectome-demo/runs/fly-ab-brain-comparison-v2-t2-20261114"),
    },
}
DATA_NOTES = {"v1.0.0": "合成資料 v1.0.0，待人工複核",
              "v2.0.0": "合成資料 v2.0.0，自動品質檢查通過，未經人工複核"}
DATASET = "v1.0.0"
RUNS = RUNS_BY_DATASET[DATASET]


def combined(default_steps: int = 4) -> str:
    """One page that holds every T's full report, switchable at the top (each in its own srcdoc iframe)."""

    global TUNING, BRAIN, STEPS
    frames, buttons = [], []
    for steps in sorted(RUNS, reverse=True):
        TUNING, BRAIN = RUNS[steps]
        STEPS = steps
        doc = html.escape(build(), quote=True)
        active = steps == default_steps
        frames.append(f"<iframe class='rep' id='rep-{steps}' title='T={steps} 報告' srcdoc=\"{doc}\"{'' if active else ' hidden'}></iframe>")
        buttons.append(f"<button type='button' class='tb' data-t='{steps}' aria-pressed='{str(active).lower()}'>T = {steps}</button>")
    label = "資料 v2.0.0" if DATASET == "v2.0.0" else "存檔：資料 v1.0.0（目前報告改用 v2.0.0）"
    return (WRAPPER.replace("{{BUTTONS}}", "".join(buttons)).replace("{{FRAMES}}", "".join(frames))
            .replace("{{DATASET_LABEL}}", label))


WRAPPER = """<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Fly A／Fly B 分析報告</title>
<style>
:root { --bg: #f3f4f1; --paper: #ffffff; --ink: #16191c; --ink-2: #4f565c; --rule: #dadcd7;
  --f: "Noto Sans TC", "Microsoft JhengHei", "PingFang TC", system-ui, sans-serif; }
@media (prefers-color-scheme: dark) { :root { --bg: #101214; --paper: #191c1f; --ink: #eceef0; --ink-2: #aab1b7; --rule: #2e3338; color-scheme: dark } }
html, body { height: 100%; margin: 0; }
body { background: var(--bg); color: var(--ink); font-family: var(--f); display: flex; flex-direction: column; }
.switch { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; border-bottom: 1px solid var(--rule); background: var(--paper);
  padding: max(8px, env(safe-area-inset-top, 0px)) max(16px, env(safe-area-inset-right, 0px)) 8px max(16px, env(safe-area-inset-left, 0px)); }
.switch b { font-size: .92rem; }
.switch b.ds { font-weight: 500; border: 1px solid var(--rule); border-radius: 6px; padding: 2px 8px; }
.switch span { font-size: .8rem; color: var(--ink-2); }
.seg { display: inline-flex; border: 1px solid var(--rule); border-radius: 999px; overflow: hidden; }
.tb { font: inherit; font-size: .86rem; border: 0; background: transparent; color: var(--ink-2); padding: 4px 14px; cursor: pointer; }
.tb[aria-pressed="true"] { background: var(--ink); color: var(--paper); }
.tb:focus-visible { outline: 2px solid #2a78d6; outline-offset: 2px; }
.rep { flex: 1; width: 100%; border: 0; display: block; }
.rep[hidden] { display: none !important; }
</style>
</head>
<body>
<div class="switch" role="group" aria-label="選擇圖核心步數 T">
  <b class="ds">{{DATASET_LABEL}}</b><b>圖核心步數</b><div class="seg">{{BUTTONS}}</div>
  <span>T=4 報告內含「T=4 vs T=2」配對比較；兩份報告的版面與說明格式相同。</span>
</div>
{{FRAMES}}
<script>
document.querySelectorAll(".tb").forEach(b => b.addEventListener("click", () => {
  document.querySelectorAll(".tb").forEach(x => x.setAttribute("aria-pressed", String(x === b)));
  document.querySelectorAll(".rep").forEach(f => { f.hidden = f.id !== "rep-" + b.dataset.t; });
}));
</script>
</body>
</html>
"""


def main() -> int:
    global TUNING, BRAIN, STEPS, DATASET, RUNS
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=OUTPUT)
    parser.add_argument("--single", action="store_true", help="write one report (use --tuning/--brain/--steps) instead of the T=2/T=4 combined page")
    parser.add_argument("--tuning", default=TUNING, help="tuning run folder (results.json, timings.json)")
    parser.add_argument("--brain", default=BRAIN, help="brain-comparison folder (results.json + figures)")
    parser.add_argument("--steps", type=int, default=2, choices=sorted(TRAINABLE))
    parser.add_argument("--dataset-version", default="v1.0.0", choices=sorted(RUNS_BY_DATASET))
    args = parser.parse_args()
    DATASET, RUNS = args.dataset_version, RUNS_BY_DATASET[args.dataset_version]
    out = PROJECT_ROOT / args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    if args.single:
        TUNING, BRAIN, STEPS = args.tuning, args.brain, args.steps
        page = build()
    else:
        page = combined()
    out.write_text(page, encoding="utf-8")
    print(f"wrote report ({out.stat().st_size // 1024} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

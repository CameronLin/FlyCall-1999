"""Write the Fly A／Fly B brain-comparison parts of the intro page for all four versions.

Outputs (then run scripts/build_intro_html.py):
    docs/intro/sections/brain_table.html   3.2 summary table, one pane per version
    docs/intro/sections/brain_figs.html    3.3 figure cards, one set of 17 per version

The figure images themselves are embedded by build_intro_html.py from the same run folders.
Card text reuses figure_points() from build_brain_report_html.py so it matches the analysis report.
"""
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_brain_report_html as report  # noqa: E402

RUNS = ROOT / ".scratch/1999-connectome-demo/runs"
OUT = ROOT / "docs/intro/sections"
# version id -> (label, T, brain-comparison run folder); the order is the order of the buttons
VERSIONS = {
    "v1-t2": ("資料 v1・T=2", 2, "fly-ab-brain-comparison-t-hops-20261113"),
    "v1-t4": ("資料 v1・T=4", 4, "fly-ab-brain-comparison-t4-20261113"),
    "v2-t2": ("資料 v2・T=2", 2, "fly-ab-brain-comparison-v2-t2-20261114"),
    "v2-t4": ("資料 v2・T=4", 4, "fly-ab-brain-comparison-v2-t4-20261114"),
}
DEFAULT = "v1-t4"
GRAPHS = ["G0", "G1", "G2", "G2_glu_plus"]
FIG_GRAPHS = ["G0", "G2"]
OBJS = ["distance", "distance_supcon"]
KINDS = list(report.KIND)
SUMMARY_HOW = ("把 8 種組合（4 張子圖 × 2 種目標）放在一起，比較三個面向的相似度：邊的改變、類別選擇性、損傷影響。"
               "黑色菱形是 Fly A vs Fly B（同 seed）；藍點與橘點分別是 Fly A、Fly B 換 seed 重練後和自己的相似度。")
SUMMARY_POINTS = ["黑色菱形在彩色點左邊越遠，代表 Fly A 和 Fly B 的差異越大過換 seed 的差異，也就是任務讓兩個腦不一樣。",
                  "「邊的改變」通常差距最明顯。",
                  "「損傷影響」三種點都接近 0：單一神經元的重要性本身就不穩定。"]


def esc(x):
    return html.escape(str(x), quote=True)


def n2(x):
    return f"{x:.2f}".replace("-", "−")


def rng(values, fmt="{:.2f}"):
    lo, hi = min(values), max(values)
    return (fmt.format(lo) + "–" + fmt.format(hi)).replace("-0", "−0") if lo != hi else fmt.format(lo)


def summaries(folder):
    return json.loads((RUNS / folder / "results.json").read_text(encoding="utf-8"))["summaries"]


def table(vid):
    s = summaries(VERSIONS[vid][2])
    rows, ratios = [], {}
    for g in GRAPHS:
        for o in OBJS:
            sd = s[f"{g}|{o}"]["edges"]["spread_sd_log_change"]
            ratios[g, o] = sd["fly_b"] / sd["fly_a"]
    top = max(ratios, key=ratios.get)
    for g in GRAPHS:
        for o in OBJS:
            x = s[f"{g}|{o}"]
            sd, sp = x["edges"]["spread_sd_log_change"], x["edges"]["spearman_log_change"]
            eta, silent = x["activity"]["median_eta_squared"], x["activity"]["silent_neurons_mean_abs_below_0_01"]
            cells = [n2(sd["fly_a"]), n2(sd["fly_b"]), f"{ratios[g, o]:.0f}×", n2(sp["fly_a_vs_fly_b_same_seed"]),
                     n2(sp["fly_a_seed_baseline"]), n2(eta["fly_a"]), n2(eta["fly_b"]), f"{silent['fly_a']:.0f}", f"{silent['fly_b']:.0f}"]
            hl = ' class="hl"' if (g, o) == top else ""
            rows.append(f'        <tr{hl}><td>{esc(report.GRAPH_NAME[g])}</td><td>{esc(report.OBJ_NAME[o])}</td>'
                        + "".join(f'<td class="num">{c}</td>' for c in cells) + "</tr>")
    keys = [f"{g}|{o}" for g in GRAPHS for o in OBJS]
    dist = [f"{g}|distance" for g in GRAPHS]
    rho = [s[k]["edges"]["spearman_log_change"]["fly_a_vs_fly_b_same_seed"] for k in keys]
    rho_seed = [s[k]["edges"]["spearman_log_change"]["fly_a_seed_baseline"] for k in keys]
    facts = (f"這個版本：Fly B 的連線改變量是 Fly A 的 <b>{rng(list(ratios.values()), '{:.0f}')} 倍</b>；"
             f"A 對 B 的相關 {rng(rho)}（A 換 seed {rng(rho_seed)}）；"
             f"Fly B 的 η² {rng([s[k]['activity']['median_eta_squared']['fly_b'] for k in keys])}；"
             f"Fly A（只保留距離）的 η² {rng([s[k]['activity']['median_eta_squared']['fly_a'] for k in dist])}，"
             f"幾乎沒反應的神經元 {rng([s[k]['activity']['silent_neurons_mean_abs_below_0_01']['fly_a'] for k in dist], '{:.0f}')} 個。")
    hidden = "" if vid == DEFAULT else " hidden"
    return (f'    <div class="ab-pane" data-set="{vid}"{hidden}>\n'
            '    <div class="tablewrap"><table class="abt">\n'
            '      <thead>\n'
            '        <tr><th rowspan="2">圖</th><th rowspan="2">Fly A 目標</th><th colspan="3">① 連線改變量（標準差）</th><th colspan="2">② 同一條邊</th><th colspan="2">③ 類別選擇性 η²</th><th colspan="2">③ 幾乎沒反應的神經元</th></tr>\n'
            '        <tr><th class="num">A</th><th class="num">B</th><th class="num">B／A</th><th class="num">A 對 B</th><th class="num">A 換 seed</th><th class="num">A</th><th class="num">B</th><th class="num">A</th><th class="num">B</th></tr>\n'
            '      </thead>\n'
            '      <tbody>\n' + "\n".join(rows) + "\n      </tbody>\n"
            f'    </table></div>\n    <p class="ab-facts">{facts}</p>\n    </div>\n')


def cards(vid):
    label, steps, folder = VERSIONS[vid]
    report.STEPS = steps  # figure_points() reads the module-level T
    s = summaries(folder)
    hidden = "" if vid == DEFAULT else " hidden"
    out = []
    for g in FIG_GRAPHS:
        for o in OBJS:
            for k in KINDS:
                how, points = report.figure_points(k, s[f"{g}|{o}"], g)
                eyebrow, title = report.KIND[k][0], f"{report.GRAPH_NAME[g]}・Fly A：{report.OBJ_NAME[o]}"
                out.append((g, o, k, f"{vid}/{g}_{o}_{k}", eyebrow, title, points, how))
    out.append(("summary", "all", "summary", f"{vid}/all_all_summary", "總覽", "Fly A／Fly B 的差異 vs 換 seed 的差異",
                SUMMARY_POINTS, SUMMARY_HOW))
    lines = []
    for g, o, k, key, eyebrow, title, points, how in out:
        pts = "".join(f"<li>{p}</li>" for p in points)
        lines.append(
            f'      <article class="fig" data-set="{vid}" data-graph="{g}" data-objective="{o}" data-kind="{k}"{hidden}>\n'
            f'        <button type="button" class="thumb" aria-label="放大：{esc(eyebrow)}・{esc(title)}（{label}）">'
            f'<img data-fig="{key}" alt="{esc(eyebrow)}：{esc(title)}（{label}）"></button>\n'
            f'        <div class="fig-body"><span class="fig-eyebrow">{esc(eyebrow)}・{label}</span><h4>{esc(title)}</h4><ul>{pts}</ul>'
            f'<details><summary>怎麼看這張圖</summary><p>{esc(how)}</p></details></div>\n'
            f'      </article>')
    return "\n".join(lines) + "\n"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "brain_table.html").write_text("".join(table(v) for v in VERSIONS), encoding="utf-8", newline="\n")
    (OUT / "brain_figs.html").write_text("".join(cards(v) for v in VERSIONS), encoding="utf-8", newline="\n")
    print("wrote", ", ".join(str((OUT / f).relative_to(ROOT)) for f in ("brain_table.html", "brain_figs.html")))


if __name__ == "__main__":
    main()

"""Write the result charts of the intro page from the run records (then run build_intro_html.py).

    docs/intro/sections/chart_retrain.html    §11  validation, data v1 vs v2 (T toggle for the Fly rows)
    docs/intro/sections/chart_t_compare.html  §10  validation, T=2 vs T=4 per graph (data toggle)
    docs/intro/sections/chart_test.html       §11  one-time test vs validation for the locked candidates

Each chart is a dot plot on one shared Macro-F1 axis: two dots per row joined by a line, the value
pair and the change printed on the right, a hover title on every row, and a table view underneath.
Styles: docs/intro/css/charts.css; toggles: docs/intro/js/charts.js.
"""
import html
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from build_brain_report_html import GRAPH_NAME, f1s  # noqa: E402

RUNS = ROOT / ".scratch/1999-connectome-demo/runs"
OUT = ROOT / "docs/intro/sections"
TUNING = {("v1", 2): "independent-tuning-t-hops-20261113", ("v1", 4): "independent-tuning-t4-20261113",
          ("v2", 2): "independent-tuning-v2-t2-20261114", ("v2", 4): "independent-tuning-v2-t4-20261114"}
E5 = {"v1": "m2-2b-e5-seed-42-current-runner-20261026", "v2": "m2-2b-e5-dataset-v2-seed-42-20261114"}
TEST = "test-evaluation-dataset-v2-20261114/test_results.json"
GRAPHS = ["G0", "G1", "G2", "G2_glu_plus"]
COMBO = {"lda_to_svm": "LDA → SVM", "fly_a_distance_supcon_to_svm": "Fly A（距離＋類別分離）→ SVM",
         "lda_to_fly_b": "LDA → Fly B", "fly_a_distance_to_fly_b": "Fly A（只保留距離）→ Fly B",
         "fly_a_distance_supcon_to_fly_b": "Fly A（距離＋類別分離）→ Fly B"}
E5_NAME = {"logistic_regression": "E5 → LR", "mlp": "E5 → MLP", "lda_logistic_regression": "E5 → LDA → LR"}
LO, HI, STEP = 0.70, 1.00, 0.05


def esc(x):
    return html.escape(str(x), quote=True)


def tuning(data, t):
    return json.loads((RUNS / TUNING[data, t] / "results.json").read_text(encoding="utf-8"))["by_graph"]


def fly(data, t, g, combo):
    return statistics.fmean(f1s(tuning(data, t)[g]["final"][combo]))


def e5(data, cand):
    m = json.loads((RUNS / E5[data] / "metrics.json").read_text(encoding="utf-8"))["candidates"][cand]
    return m["report"]["splits"]["validation"]["metrics"]["macro_f1"]


def pos(v):
    return max(0.0, min(100.0, (v - LO) / (HI - LO) * 100))


def axis():
    ticks = [LO + i * STEP for i in range(round((HI - LO) / STEP) + 1)]
    marks = "".join(f'<span style="left:{pos(t):.2f}%">{t:.2f}</span>' for t in ticks)
    return f'<div class="ch-row ch-axisrow" aria-hidden="true"><span></span><div class="ch-axis">{marks}</div><span></span></div>'


def rows_html(rows, names):
    """rows: (group or None, label, a, b, sd_b or None, highlight)."""
    out, group = [], None
    for g, label, a, b, sd, hl in rows:
        if g and g != group:
            out.append(f'<div class="ch-group">{esc(g)}</div>')
            group = g
        d = b - a
        cls = "up" if d > 0.0005 else ("down" if d < -0.0005 else "flat")
        lo, hi = sorted((pos(a), pos(b)))
        whisk = ""
        if sd:
            wl, wr = pos(b - sd), pos(b + sd)
            whisk = f'<span class="ch-sd" style="left:{wl:.2f}%;width:{wr - wl:.2f}%"></span>'
        sd_txt = f" ± {sd:.3f}" if sd else ""
        tip = f"{label}｜{names[0]} {a:.3f}；{names[1]} {b:.3f}{sd_txt}；變化 {d:+.3f}"
        out.append(
            f'<div class="ch-row{" ch-hl" if hl else ""}" title="{esc(tip)}">'
            f'<span class="ch-lab">{label}</span>'
            f'<div class="ch-track"><span class="ch-line" style="left:{lo:.2f}%;width:{hi - lo:.2f}%"></span>{whisk}'
            f'<span class="ch-dot ch-s1" style="left:{pos(a):.2f}%"></span><span class="ch-dot ch-s2" style="left:{pos(b):.2f}%"></span></div>'
            f'<span class="ch-val">{a:.3f} → <b>{b:.3f}</b><em class="{cls}">{d:+.3f}</em></span></div>')
    return "".join(out)


def table_html(rows, names):
    body = "".join(
        f'<tr{" class=hl" if hl else ""}><td>{esc(g or "")}</td><td>{label}</td><td class="num">{a:.3f}</td>'
        f'<td class="num">{b:.3f}{f" ± {sd:.3f}" if sd else ""}</td><td class="num">{b - a:+.3f}</td></tr>'
        for g, label, a, b, sd, hl in rows)
    return (f'<div class="tablewrap"><table><thead><tr><th>組別</th><th>模型</th><th class="num">{names[0]}</th>'
            f'<th class="num">{names[1]}</th><th class="num">變化</th></tr></thead><tbody>{body}</tbody></table></div>')


def chart(cid, title, names, colors, panes, toggle_label=None, note=""):
    """panes: list of (pane id, button label, rows); the first pane is shown."""
    legend = (f'<span><i class="ch-key ch-s1" style="--c:var({colors[0]})"></i>{names[0]}</span>'
              f'<span><i class="ch-key ch-s2" style="--c:var({colors[1]})"></i>{names[1]}</span>')
    seg = ""
    if len(panes) > 1:
        seg = (f'<div class="ch-seg" role="group" aria-label="{esc(toggle_label)}">'
               + "".join(f'<button type="button" data-pane="{p}" aria-pressed="{str(i == 0).lower()}">{lab}</button>'
                         for i, (p, lab, _) in enumerate(panes)) + "</div>")
    body = "".join(
        f'<div class="ch-pane" data-pane="{p}"{"" if i == 0 else " hidden"}>'
        f'<div class="ch-plot">{axis()}{rows_html(rows, names)}</div>'
        f'<details class="ch-more"><summary>以表格檢視</summary>{table_html(rows, names)}</details></div>'
        for i, (p, _, rows) in enumerate(panes))
    step = STEP / (HI - LO) * 100
    return (f'<figure class="ch" id="{cid}" style="--s1:var({colors[0]});--s2:var({colors[1]});--ch-step:{step:.4f}%">\n'
            f'  <div class="ch-head"><figcaption class="ch-title">{title}</figcaption>{seg}</div>\n'
            f'  <div class="ch-legend">{legend}<span class="ch-axisname">Macro-F1（{LO:.2f}–{HI:.2f}）</span></div>\n'
            f'  {body}\n'
            + (f'  <p class="ch-note">{note}</p>\n' if note else "") + "</figure>\n")


def retrain():
    base = [("基準（E5，seed 42）", E5_NAME[c], e5("v1", c), e5("v2", c), None, False) for c in E5_NAME]
    panes = []
    for t in (2, 4):
        rows = list(base)
        rows.append(("基準（三個 seed 平均）", COMBO["lda_to_svm"], fly("v1", t, "G0", "lda_to_svm"),
                     fly("v2", t, "G0", "lda_to_svm"), None, False))
        for combo in ("fly_a_distance_supcon_to_svm", "fly_a_distance_supcon_to_fly_b", "lda_to_fly_b"):
            for g in GRAPHS:
                rows.append((COMBO[combo] + f"・T={t}", GRAPH_NAME[g], fly("v1", t, g, combo), fly("v2", t, g, combo), None, False))
        panes.append((f"t{t}", f"果蠅模型 T={t}", rows))
    return chart("ch-retrain", "換成資料 v2 後，validation Macro-F1 怎麼變", ("資料 v1", "資料 v2"), ("--ch-old", "--ch-new"),
                 panes, "果蠅模型的步數",
                 "E5 基準只跑 seed 42，其餘為三個 seed 平均。兩版資料的 validation 是不同的 150 筆，只看方向，不宜逐筆比較。")


def t_compare():
    panes = []
    for data in ("v1", "v2"):
        rows = []
        for combo in ("fly_a_distance_supcon_to_svm", "fly_a_distance_supcon_to_fly_b", "lda_to_fly_b", "fly_a_distance_to_fly_b"):
            for g in GRAPHS:
                rows.append((COMBO[combo], GRAPH_NAME[g], fly(data, 2, g, combo), fly(data, 4, g, combo), None, False))
        panes.append((data, f"資料 {data}", rows))
    return chart("ch-tcompare", "T=2 改成 T=4，validation Macro-F1 怎麼變", ("T=2", "T=4"), ("--ch-t2", "--ch-t4"),
                 panes, "資料版本", "三個 seed 平均。右側數字是 T=4 減 T=2；差距在 ±0.01 左右時，大致在不同 seed 的波動範圍內。")


def test():
    r = json.loads((RUNS / TEST).read_text(encoding="utf-8"))
    res = r["results"]
    sel = r["selected_fly_model"]  # e.g. T2/G2/fly_a_distance_supcon_to_fly_b
    t_sel, g_sel, c_sel = sel.split("/")
    fly_keys = [k for k in res if not k.startswith("e5_")]
    best = max(fly_keys, key=lambda k: res[k]["macro_f1"]["mean"])
    t_b, g_b, c_b = best.split("/")

    def tv(key):
        t, g, c = key.split("/")
        return fly("v2", int(t[1:]), g, c)
    rows = [
        ("依規則選定的果蠅模型", f"{COMBO[c_sel]}（T={t_sel[1:]}・{GRAPH_NAME[g_sel]}）", tv(sel),
         r["selected_fly_model_test"]["macro_f1"]["mean"], r["selected_fly_model_test"]["macro_f1"]["std"], True),
        ("對照方法", "LDA → SVM", tv("T2/G0/lda_to_svm"), res["T2/G0/lda_to_svm"]["macro_f1"]["mean"], None, False),
        ("對照方法", "E5 → LDA → LR", e5("v2", "lda_logistic_regression"), res["e5_lda_logistic"]["macro_f1"]["mean"], None, False),
        ("對照方法", "E5 → MLP", e5("v2", "mlp"), res["e5_mlp"]["macro_f1"]["mean"], None, False),
        ("對照方法", "E5 → LR", e5("v2", "logistic_regression"), res["e5_logistic_regression"]["macro_f1"]["mean"], None, False),
        ("僅參考（不改變選擇）", f"全部候選最高：{COMBO[c_b]}（T={t_b[1:]}・{GRAPH_NAME[g_b]}）", tv(best),
         res[best]["macro_f1"]["mean"], res[best]["macro_f1"]["std"], False),
    ]
    return chart("ch-test", "一次性 test：和 validation 比，分數掉了多少", ("validation", "test"), ("--ch-old", "--ch-new"),
                 [("test", "", rows)], None,
                 "test 只評估一次。果蠅模型為三個 seed 平均，橫線是 ± 標準差；E5 與 LDA 基準為固定 seed。"
                 "實心點在空心點左邊越遠，代表從 validation 到 test 掉得越多。")


def main():
    for name, fn in (("chart_retrain.html", retrain), ("chart_t_compare.html", t_compare), ("chart_test.html", test)):
        (OUT / name).write_text(fn(), encoding="utf-8", newline="\n")
        print("wrote", (OUT / name).relative_to(ROOT))


if __name__ == "__main__":
    main()

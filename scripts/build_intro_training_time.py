"""Write docs/intro/sections/training_time.html (v1 vs v2 training time) from the run records.

Then rebuild the page with scripts/build_intro_html.py. Styles and the T toggle live in
docs/intro/css/training_time.css and docs/intro/js/training_time.js.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / ".scratch/1999-connectome-demo/runs"
OUT = ROOT / "docs/intro/sections/training_time.html"
RUN = {("v1", 2): "independent-tuning-t-hops-20261113", ("v2", 2): "independent-tuning-v2-t2-20261114",
       ("v1", 4): "independent-tuning-t4-20261113", ("v2", 4): "independent-tuning-v2-t4-20261114"}
BRAIN = {("v1", 2): "fly-ab-brain-comparison-t-hops-20261113", ("v2", 2): "fly-ab-brain-comparison-v2-t2-20261114",
         ("v1", 4): "fly-ab-brain-comparison-t4-20261113", ("v2", 4): "fly-ab-brain-comparison-v2-t4-20261114"}
GRAPHS = [("G0", "G0 原圖"), ("G1", "G1 全正"), ("G2", "G2 有正負"), ("G2_glu_plus", "G2-glu+")]
COLS = [("fly_a", "distance", "Fly A 距離"), ("fly_a", "distance_supcon", "Fly A 距離＋類別"),
        ("fly_b", "lda", "Fly B 接 LDA"), ("fly_b", "fly_a_distance", "Fly B 接 A（距離）"),
        ("fly_b", "fly_a_distance_supcon", "Fly B 接 A（距離＋類別）")]


def mmss(s):
    s = round(s)
    return f"{s // 60} 分 {s % 60:02d} 秒"


def stop_epochs(o, acc):
    if isinstance(o, dict):
        for k, v in o.items():
            if k == "selected_epochs":
                acc.extend(v)
            else:
                stop_epochs(v, acc)


D = {}
for key, name in RUN.items():
    res = json.loads((RUNS / name / "results.json").read_text(encoding="utf-8"))
    tim = json.loads((RUNS / name / "timings.json").read_text(encoding="utf-8"))
    a, b = [], []
    for g in res["by_graph"].values():
        stop_epochs(g["cv_fly_a"], a)
        stop_epochs(g["cv_fly_b"], b)
    brain = json.loads((RUNS / BRAIN[key] / "results.json").read_text(encoding="utf-8"))["elapsed_seconds"]
    D[key] = {"total": tim["run_total_seconds"], "graphs": tim["by_graph"], "res": res["by_graph"],
              "stopA": sum(a) / len(a), "stopB": sum(b) / len(b), "nA": len(a), "nB": len(b), "brain": brain}


def pct(v1, v2):
    return round((v2 - v1) / v1 * 100)


def kpis():
    t2, t4 = (D["v1", 2], D["v2", 2]), (D["v1", 4], D["v2", 4])
    g2v1 = D["v1", 2]["res"]["G2"]["final_epochs"]["fly_b"]["fly_a_distance_supcon"]
    g2v2 = D["v2", 2]["res"]["G2"]["final_epochs"]["fly_b"]["fly_a_distance_supcon"]
    tiles = [
        ("獨立調參總時間・T=2", f"{round(t2[1]['total'] / 60)}<small> 分</small>",
         f"v1 為 {mmss(t2[0]['total'])}；v2 {mmss(t2[1]['total'])}，<b>{pct(t2[0]['total'], t2[1]['total'])}%</b>"),
        ("獨立調參總時間・T=4", f"{round(t4[1]['total'] / 60)}<small> 分</small>",
         f"v1 為 {mmss(t4[0]['total'])}；v2 {mmss(t4[1]['total'])}，<b>{pct(t4[0]['total'], t4[1]['total'])}%</b>"),
        ("Fly B 平均停止 epoch・T=2", f"{t2[0]['stopB']:.0f}<small> → </small>{t2[1]['stopB']:.0f}",
         f"T=4：{t4[0]['stopB']:.0f} → {t4[1]['stopB']:.0f}；Fly A 兩版都約 {min(D[k]['stopA'] for k in D):.0f}–{max(D[k]['stopA'] for k in D):.0f}"),
        ("最終訓練長度（最明顯的一格）", f"{g2v1}<small> → </small>{g2v2}<small> epoch</small>",
         "G2・T=2・Fly B 接 Fly A（距離＋類別）；v1 碰到 200 上限"),
    ]
    return "".join(f'<div class="tt-kpi"><div class="tt-k">{k}</div><div class="tt-v">{v}</div><div class="tt-n">{n}</div></div>'
                   for k, v, n in tiles)


def bars(t):
    segs = [("fly_a_cv_seconds", "a", "① Fly A 交叉驗證"), ("fly_b_cv_seconds", "b", "② Fly B 交叉驗證"),
            ("final_training_seconds", "c", "③ 最終訓練")]
    mx = max(D[v, t]["graphs"][g]["total_seconds"] for v in ("v1", "v2") for g, _ in GRAPHS)
    rows = []
    for g, label in GRAPHS:
        rows.append(f'<div class="tt-glab">{label}</div>')
        for v in ("v1", "v2"):
            x = D[v, t]["graphs"][g]
            spans = "".join(
                f'<span class="tt-s{c}" style="width:{x[k] / mx * 100:.2f}%" title="{label}・{v}・{name}：{mmss(x[k])}"></span>'
                for k, c, name in segs)
            delta = ""
            if v == "v2":
                p = pct(D["v1", t]["graphs"][g]["total_seconds"], x["total_seconds"])
                delta = f' <em class="{"tt-dn" if p < 0 else ("tt-up" if p > 0 else "tt-flat")}">{p:+d}%</em>'
            rows.append(f'<div class="tt-brow"><span class="tt-ver tt-{v}">{v}</span><div class="tt-track">{spans}</div>'
                        f'<span class="tt-bval">{mmss(x["total_seconds"])}{delta}</span></div>')
    return "".join(rows)


def detail_table(t):
    head = "<tr><th>圖</th><th>資料</th><th>① Fly A 交叉驗證</th><th>② Fly B 交叉驗證</th><th>③ 最終訓練</th><th>合計</th></tr>"
    body = []
    for g, label in GRAPHS:
        for v in ("v1", "v2"):
            x = D[v, t]["graphs"][g]
            body.append(f'<tr{" class=tt-v2row" if v == "v2" else ""}><td>{label if v == "v1" else ""}</td><td>{v}</td>'
                        f'<td class="num">{mmss(x["fly_a_cv_seconds"])}</td><td class="num">{mmss(x["fly_b_cv_seconds"])}</td>'
                        f'<td class="num">{mmss(x["final_training_seconds"])}</td><td class="num"><b>{mmss(x["total_seconds"])}</b></td></tr>')
    for v in ("v1", "v2"):
        body.append(f'<tr class="tt-sum"><td>全部</td><td>{v}</td><td></td><td></td><td></td>'
                    f'<td class="num"><b>{mmss(D[v, t]["total"])}</b></td></tr>')
    return f'<div class="tablewrap"><table><thead>{head}</thead><tbody>{"".join(body)}</tbody></table></div>'


def settings_table(t):
    head = "<tr><th>圖</th>" + "".join(f"<th>{c}</th>" for *_, c in COLS) + "</tr>"
    body = []
    for g, label in GRAPHS:
        cells = []
        for part, key, _ in COLS:
            ep = [D[v, t]["res"][g]["final_epochs"][part][key] for v in ("v1", "v2")]
            lr = [D[v, t]["res"][g]["chosen_learning_rate"][part][key] for v in ("v1", "v2")]
            flag = lambda e: '<i class="tt-flag" title="碰到 200 epoch 上限">⚑</i>' if e >= 199 else ""
            cls = " tt-big" if ep[0] - ep[1] >= 50 else ""
            cells.append(f'<td class="num{cls}" title="學習率 v1 {lr[0]}／v2 {lr[1]}"><span class="tt-old">{ep[0]}{flag(ep[0])}</span>'
                         f' → <b>{ep[1]}</b>{flag(ep[1])}<small>lr {lr[0]}→{lr[1]}</small></td>')
        body.append(f"<tr><td>{label}</td>{''.join(cells)}</tr>")
    return f'<div class="tablewrap"><table class="tt-set"><thead>{head}</thead><tbody>{"".join(body)}</tbody></table></div>'


def stop_bars():
    mx = max(max(D[k]["stopA"], D[k]["stopB"]) for k in D)
    out = []
    for part, name in (("stopA", "Fly A"), ("stopB", "Fly B")):
        for t in (2, 4):
            v1, v2 = D["v1", t][part], D["v2", t][part]
            out.append(f'<div class="tt-erow"><span class="tt-elab">{name}・T={t}</span><div class="tt-etracks">'
                       f'<div class="tt-etrack"><span class="tt-ver tt-v1">v1</span><span class="tt-ebar tt-ebar1" style="width:{v1 / mx * 100:.1f}%"></span><b>{v1:.1f}</b></div>'
                       f'<div class="tt-etrack"><span class="tt-ver tt-v2">v2</span><span class="tt-ebar tt-ebar2" style="width:{v2 / mx * 100:.1f}%"></span><b>{v2:.1f}</b></div>'
                       f'</div></div>')
    return "".join(out)


def by_t(fn):
    return "".join(f'<div class="tt-pane" data-tt="{t}"{"" if t == 2 else " hidden"}>{fn(t)}</div>' for t in (2, 4))


seg = ('<div class="tt-seg" role="group" aria-label="選擇圖核心步數 T">'
       '<button type="button" class="tt-tb" data-tt="2" aria-pressed="true">T = 2</button>'
       '<button type="button" class="tt-tb" data-tt="4" aria-pressed="false">T = 4</button></div>')
legend = ('<div class="tt-legend"><span><i class="tt-sa"></i>① Fly A 交叉驗證</span><span><i class="tt-sb"></i>② Fly B 交叉驗證</span>'
          '<span><i class="tt-sc"></i>③ 最終訓練</span></div>')
brain_rows = "".join(f'<td class="num">{mmss(D[v, t]["brain"])}</td>' for t in (2, 4) for v in ("v1", "v2"))

BLOCK = f'''<div class="block what tt" id="training-time"><span class="tag">紀錄：訓練時間（v1 vs v2）</span>
      <p>換成 v2 資料後，同一套調參流程<b>整體快了 1–2 成</b>，省下的時間幾乎都在 Fly B：v2 上 Fly B 比較早達到最佳點、提早停止。下面依序是摘要、流程、每張圖的時間，以及原因。</p>
      <div class="tt-kpis">{kpis()}</div>

      <h4 class="tt-h">① 一次「獨立調參」做了什麼（每張圖都相同）</h4>
      <div class="tt-flow">
        <div class="tt-stage tt-s1"><div class="tt-sn">階段 ①</div><h5>Fly A 交叉驗證：選 Fly A 的學習率</h5>
          <ul><li>700 筆 train 依情境家族分成 5 份，每次 4 份訓練、1 份驗證。</li><li>兩種目標（只保留距離／距離＋類別分離）各試 3 個學習率。</li><li>每次訓練用 early stopping：連續 25 個 epoch 沒進步就停。</li></ul>
          <div class="tt-formula">2 目標 × 3 學習率 × 3 seed × 5 份 = 90 次</div></div>
        <div class="tt-arrow" aria-hidden="true">→</div>
        <div class="tt-stage tt-s2"><div class="tt-sn">階段 ②</div><h5>Fly B 交叉驗證：選 Fly B 的學習率</h5>
          <ul><li>三種輸入：LDA 4 維、兩種 Fly A 的 32 維輸出。</li><li>多了 5 類輸出層、每份資料都要重新產生輸入，是最花時間的階段。</li><li><b>v1 與 v2 的差距主要在這裡。</b></li></ul>
          <div class="tt-formula">3 輸入 × 3 學習率 × 3 seed × 5 份 = 135 次</div></div>
        <div class="tt-arrow" aria-hidden="true">→</div>
        <div class="tt-stage tt-s3"><div class="tt-sn">階段 ③</div><h5>最終訓練：在全部 train 上重訓</h5>
          <ul><li>用選定的學習率，固定訓練「交叉驗證選出的 epoch 中位數」。</li><li>Fly A 先訓練好並凍結，再訓練 Fly B。</li></ul>
          <div class="tt-formula">2 Fly A × 3 seed ＋ 3 Fly B × 3 seed = 15 次</div></div>
      </div>

      <div class="tt-head"><h4 class="tt-h">② 每張圖的訓練時間</h4>{seg}</div>
      <div class="tt-panel">
        {legend}
        {by_t(lambda t: '<div class="tt-bars">' + bars(t) + '</div><details class="tt-more"><summary>看詳細數字</summary>' + detail_table(t) + '</details>')}
        <p class="tt-note">同一個 T 之下，所有長條用同一個比例尺。G0 只有 2,216 條邊所以最快；另外三張有 6,691 條邊。</p>
      </div>

      <div class="tt-head"><h4 class="tt-h">③ 為什麼 v2 比較快：Fly B 提早停止</h4></div>
      <div class="tt-grid2">
        <div class="tt-panel"><h5>交叉驗證中每次訓練的平均停止 epoch</h5>
          <div class="tt-ebars">{stop_bars()}</div>
          <p class="tt-note">Fly A 每版 {D["v1", 2]["nA"]} 次、Fly B 每版 {D["v1", 2]["nB"]} 次訓練的平均。兩版每個 epoch 的計算量相同（筆數、E5 維度、圖與模型大小都一樣），所以跑幾個 epoch 就決定了時間。</p></div>
        <div class="tt-panel"><h5>重點</h5>
          <ul class="tt-points">
            <li><b>Fly A 沒有變</b>：平均都停在約 44–48 個 epoch，所以階段 ① 的時間兩版差不多。</li>
            <li><b>Fly B 少了約 35 個 epoch</b>：推測是 v2 的類別在 Fly A／LDA 表徵上分得比較開，較快達到最佳點（這點沒有另外驗證）。</li>
            <li><b>總時間只少 1–2 成</b>：每次訓練都要多跑 25 個 epoch 才能確認沒有再進步，而且 Fly A 沒有變快。</li>
            <li><b>最終訓練也跟著變短</b>：v1 有幾格碰到 200 上限（⚑），v2 沒有任何一格碰到上限。</li>
          </ul></div>
      </div>

      <div class="tt-head"><h4 class="tt-h">④ 交叉驗證選出的最終訓練長度（epoch，v1 → v2）</h4></div>
      <div class="tt-panel">
        {by_t(settings_table)}
        <p class="tt-note">⚑ 表示碰到 200 epoch 上限，可能還沒完全收斂；深色底的格子少了 50 個 epoch 以上。每格下方小字是選出的學習率（v1 → v2）。</p>
      </div>

      <details class="tt-more"><summary>其他步驟的時間</summary>
        <div class="tablewrap"><table><thead><tr><th>步驟</th><th class="num">v1 T=2</th><th class="num">v2 T=2</th><th class="num">v1 T=4</th><th class="num">v2 T=4</th></tr></thead>
        <tbody><tr><td>訓練後的腦部分析（活動、重要連線、移除測試；不訓練）</td>{brain_rows}</tr></tbody></table></div>
        <ul>
          <li>腦部分析兩版計算內容相同，但 v2 多花約 6 分鐘，原因沒有查明（可能是當時電腦負載）。</li>
          <li>v2 的 1,000 筆 E5 編碼約 1.8 分鐘（另載入模型約 0.5 分鐘）；E5 基準分類器每個不到 1 秒；第一代固定預算的 Fly A／B（G0）每個 seed 約 6–9 秒。</li>
        </ul>
      </details>
      <p class="tt-note">以上為 Windows x64 CPU、單一程序的實際經過時間，由 <code>progress.log</code> 時間戳記算出（各 run 資料夾的 <code>timings.json</code>），會受當時電腦負載影響，不是精確的效能測量。</p>
    </div>
'''

OUT.write_text(BLOCK + "    ", encoding="utf-8", newline="\n")
print("wrote", OUT.relative_to(ROOT))

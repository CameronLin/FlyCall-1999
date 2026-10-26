"""Project guide for the FlyCall-1999 Streamlit research demo."""

from __future__ import annotations

import html
import json
from pathlib import Path

import streamlit as st


FORMAL_DATASET_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "1999_synthetic"
    / "formal"
    / "v1.0.0"
    / "formal_dataset_v1.0.0.jsonl"
)
FORMAL_EXAMPLE_SPECS = (
    ("TPE1999-FORMAL-SW-0031", "sidewalk_maintenance", "#167c80"),
    ("TPE1999-FORMAL-RD-0076", "road_surface_defect", "#426fb3"),
    ("TPE1999-FORMAL-PK-0008", "park_general_maintenance", "#36805b"),
    ("TPE1999-FORMAL-WT-0001", "waste_truck_service", "#7655a6"),
    ("TPE1999-FORMAL-SC-0105", "street_cleaning", "#bd7029"),
)


def _table_markup(headers: tuple[str, ...], rows: tuple[tuple[str, ...], ...]) -> str:
    header_cells = "".join(f"<th scope='col'>{html.escape(value)}</th>" for value in headers)
    body_rows = "".join(
        "<tr>" + "".join(f"<td>{html.escape(value)}</td>" for value in row) + "</tr>"
        for row in rows
    )
    return (
        '<div class="guide-table-wrap"><table class="guide-table">'
        f"<thead><tr>{header_cells}</tr></thead><tbody>{body_rows}</tbody>"
        "</table></div>"
    )


def _select_guide_section(section: str) -> None:
    st.session_state["guide_section"] = section


@st.cache_data(show_spinner=False)
def _load_formal_examples(dataset_path: str, record_ids: tuple[str, ...]) -> tuple[dict, ...]:
    wanted_ids = set(record_ids)
    found: dict[str, dict] = {}
    with Path(dataset_path).open("r", encoding="utf-8") as dataset_file:
        for line in dataset_file:
            record = json.loads(line)
            record_id = record.get("id")
            if record_id in wanted_ids:
                found[record_id] = record
                if len(found) == len(wanted_ids):
                    break
    missing = wanted_ids.difference(found)
    if missing:
        raise ValueError(f"資料集缺少範例 ID：{', '.join(sorted(missing))}")
    return tuple(found[record_id] for record_id in record_ids)


st.set_page_config(
    page_title="FlyCall-1999 專案說明",
    page_icon="📘",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.html(
    """
    <style>
      :root { color-scheme: light; }
      [data-testid="stAppViewContainer"], [data-testid="stMain"] {
        background: #f2f6f8 !important; color: #183247 !important;
      }
      [data-testid="stSidebar"],
      [data-testid="stExpandSidebarButton"],
      [data-testid="stSidebarCollapseButton"] { display: none !important; }
      .guide-page-switcher-label {
        color: #526977; font-size: .72rem; font-weight: 850; letter-spacing: .1em;
        margin: 0 0 .35rem .1rem;
      }
      .st-key-page-switcher { margin: 0 0 1rem; }
      .st-key-page-switcher-current [data-testid="stPageLink"] a,
      .st-key-page-switcher-item [data-testid="stPageLink"] a {
        display: flex; justify-content: flex-start; width: 100%;
        color: #183247 !important; background: #ffffff !important;
        border: 1px solid #cbd9e0 !important; border-radius: 12px !important;
        padding: .5rem .72rem !important; text-decoration: none !important; font-weight: 800 !important;
      }
      .st-key-page-switcher-current [data-testid="stPageLink"] a {
        background: #e2f2ef !important; border: 2px solid #167c80 !important;
        box-shadow: 0 2px 0 #167c8024;
      }
      .st-key-page-switcher-current [data-testid="stPageLink"] a *,
      .st-key-page-switcher-item [data-testid="stPageLink"] a * { color: #183247 !important; }
      .st-key-page-switcher-current [data-testid="stPageLink"] a:hover,
      .st-key-page-switcher-item [data-testid="stPageLink"] a:hover { background: #dcefeb !important; }
      [data-testid="stAppViewContainer"] :is(p, h1, h2, h3, h4, h5, h6, li, label, span, small, summary, a, button),
      [data-testid="stMetricLabel"] *, [data-testid="stMetricValue"] *,
      [data-testid="stCaptionContainer"] *, [data-testid="stMarkdownContainer"] * {
        color: #183247 !important;
      }
      .block-container { max-width: 1180px; padding-top: 1.7rem; padding-bottom: 4rem; }
      .guide-hero {
        padding: 1.7rem 2rem; margin: .6rem 0 1rem; border: 1px solid #d5e4e8; border-radius: 20px;
        color: #183247; background: linear-gradient(120deg, #e5f1f2, #e6eef6 65%, #e3f0ed);
        box-shadow: 0 10px 28px #17364e0c;
      }
      .guide-hero .eyebrow { color: #167c80 !important; font-size: .74rem; font-weight: 800; letter-spacing: .13em; }
      .guide-hero h1 { color: #183247 !important; margin: .4rem 0; font-size: clamp(1.8rem, 3vw, 2.4rem); }
      .guide-hero p { color: #405d6d !important; margin: 0; line-height: 1.6; }
      .guide-flow-card {
        min-height: 125px; padding: 1rem; border: 1px solid #dce6eb; border-top: 4px solid #167c80;
        border-radius: 14px; background: #fff; box-shadow: 0 5px 16px #193b5208;
      }
      .guide-flow-step { color: #167c80 !important; font-size: .7rem; font-weight: 850; letter-spacing: .08em; }
      .guide-flow-title { color: #183247 !important; font-size: .95rem; font-weight: 850; margin: .3rem 0; }
      .guide-flow-copy { color: #526977 !important; font-size: .78rem; line-height: 1.5; }
      .guide-note, .guide-warning, .guide-callout {
        color: #405969 !important; padding: .85rem 1rem; border-radius: 11px; line-height: 1.6;
      }
      .guide-note { border: 1px solid #d5e5df; border-left: 4px solid #4b9b7d; background: #edf7f2; }
      .guide-warning { margin: .7rem 0 1.2rem; border: 1px solid #eadbb9; border-left: 4px solid #d28a37; background: #fff8e9; }
      .guide-callout { border: 1px solid #cfe1e5; border-left: 4px solid #43899a; background: #edf6f8; }
      .guide-layer { min-height: 110px; padding: .9rem; border-radius: 13px; text-align: center; background: #fff; border: 1px solid #dce6eb; box-shadow: 0 5px 16px #193b5208; }
      .guide-layer-title { font-size: .72rem; font-weight: 850; letter-spacing: .08em; }
      .guide-layer-value { color: #183247 !important; font-size: 1.15rem; font-weight: 850; margin: .3rem 0; }
      .guide-layer-copy { color: #617587 !important; font-size: .74rem; }
      .guide-layer-input { border-top: 4px solid #3f76a8; }
      .guide-layer-input .guide-layer-title { color: #3f76a8 !important; }
      .guide-layer-hidden { border-top: 4px solid #7655a6; }
      .guide-layer-hidden .guide-layer-title { color: #7655a6 !important; }
      .guide-layer-output { border-top: 4px solid #3b805c; }
      .guide-layer-output .guide-layer-title { color: #3b805c !important; }
      .guide-code-chip, .guide-transcript {
        color: #244354 !important; background: #edf3f5; border: 1px solid #dce6eb;
        border-radius: 10px; font-family: ui-monospace, Consolas, monospace;
      }
      .guide-code-chip { padding: .65rem .75rem; text-align: center; font-weight: 750; }
      .guide-transcript { padding: .9rem 1rem; white-space: pre-wrap; overflow-wrap: anywhere; line-height: 1.65; }
      .st-key-guide_bookmark_row {
        padding: .6rem; margin: 1rem 0 1.25rem; border: 1px solid #d5e1e6;
        border-radius: 17px; background: linear-gradient(135deg, #fbfdfe, #edf3f5);
        box-shadow: 0 7px 20px #193b520a;
      }
      .st-key-guide_nav_overview { --bookmark-border: #167c80; --bookmark-fill: #e5f3f1; }
      .st-key-guide_nav_data { --bookmark-border: #36805b; --bookmark-fill: #e9f4eb; }
      .st-key-guide_nav_architecture { --bookmark-border: #426fb3; --bookmark-fill: #eaf0fb; }
      .st-key-guide_nav_experiments { --bookmark-border: #7655a6; --bookmark-fill: #f0eafb; }
      .st-key-guide_nav_examples { --bookmark-border: #a95c1c; --bookmark-fill: #fff0df; }
      .st-key-guide_nav_overview button,
      .st-key-guide_nav_data button,
      .st-key-guide_nav_architecture button,
      .st-key-guide_nav_experiments button,
      .st-key-guide_nav_examples button {
        box-sizing: border-box; min-height: 46px; padding: .24rem .78rem;
        border: 1px solid var(--bookmark-border) !important;
        border-top: 4px solid var(--bookmark-border) !important; border-radius: 12px !important;
        color: #183247 !important; background: #ffffff !important;
        font-size: .83rem !important; font-weight: 800 !important; white-space: nowrap;
        box-shadow: 0 2px 6px #18324712 !important;
        transition: transform .15s ease, box-shadow .15s ease, background .15s ease;
      }
      .st-key-guide_nav_overview button:hover,
      .st-key-guide_nav_data button:hover,
      .st-key-guide_nav_architecture button:hover,
      .st-key-guide_nav_experiments button:hover,
      .st-key-guide_nav_examples button:hover {
        color: #183247 !important; background: var(--bookmark-fill) !important;
        transform: translateY(-1px); box-shadow: 0 5px 12px #18324718 !important;
      }
      .st-key-guide_nav_overview button[kind="primary"],
      .st-key-guide_nav_data button[kind="primary"],
      .st-key-guide_nav_architecture button[kind="primary"],
      .st-key-guide_nav_experiments button[kind="primary"],
      .st-key-guide_nav_examples button[kind="primary"] {
        border-width: 2px !important; border-top-width: 4px !important;
        color: #183247 !important; background: var(--bookmark-fill) !important;
        box-shadow: 0 0 0 2px color-mix(in srgb, var(--bookmark-border) 18%, transparent),
          0 5px 14px color-mix(in srgb, var(--bookmark-border) 18%, transparent) !important;
        font-weight: 900 !important; transform: translateY(-1px);
      }
      .st-key-guide_nav_overview button:focus-visible,
      .st-key-guide_nav_data button:focus-visible,
      .st-key-guide_nav_architecture button:focus-visible,
      .st-key-guide_nav_experiments button:focus-visible,
      .st-key-guide_nav_examples button:focus-visible {
        outline: 3px solid #183247 !important; outline-offset: 2px;
      }
      .guide-example-card {
        min-width: 0; padding: .9rem 1rem; border: 1px solid #dce6eb;
        border-left: 4px solid var(--example-accent); border-radius: 14px;
        background: #fff; box-shadow: 0 5px 15px #193b5208;
      }
      .guide-example-card-title {
        color: #183247; font-size: .96rem; font-weight: 850;
        line-height: 1.45; margin: 0 0 .45rem;
      }
      .guide-example-meta { display: flex; flex-wrap: wrap; gap: .35rem; margin-bottom: .5rem; }
      .guide-example-chip {
        display: inline-block; padding: .18rem .5rem; border: 1px solid #dce6eb;
        border-radius: 999px; color: #29495a; background: #f3f7f8;
        font-size: .68rem; font-weight: 750;
      }
      .guide-example-record-id {
        color: #526977; font: .7rem ui-monospace, Consolas, monospace; margin: .25rem 0 .6rem;
        overflow-wrap: anywhere;
      }
      .guide-transcript-turns { display: flex; flex-direction: column; gap: .45rem; }
      .guide-transcript-turn {
        display: grid; grid-template-columns: 94px minmax(0, 1fr); align-items: start;
        gap: .65rem; padding: .62rem .7rem; border: 1px solid #e2eaed;
        border-radius: 10px; background: #fff;
      }
      .guide-transcript-speaker {
        display: inline-block; padding: .18rem .45rem; border-radius: 7px;
        color: #183247 !important; background: #e7eff5; font-size: .75rem;
        font-weight: 850; text-align: center; white-space: nowrap;
      }
      .guide-turn-l .guide-transcript-speaker { background: #e8f3ec; }
      .guide-transcript-utterance {
        color: #294354 !important; line-height: 1.7; overflow-wrap: anywhere;
      }
      .guide-table-wrap { width: 100%; overflow-x: auto; margin: .5rem 0 1rem; border: 1px solid #dce6eb; border-radius: 12px; background: #fff; box-shadow: 0 4px 14px #193b5207; }
      .guide-table { width: 100%; border-collapse: collapse; color: #183247 !important; background: #fff; font-size: .86rem; }
      .guide-table th { color: #183247 !important; background: #e8f0f2; text-align: left; font-weight: 800; white-space: nowrap; }
      .guide-table td { color: #405969 !important; background: #fff; vertical-align: top; }
      .guide-table th, .guide-table td { padding: .65rem .8rem; border-bottom: 1px solid #e5ecef; }
      .guide-table tbody tr:nth-child(even) td { background: #f7fafb; }
      .guide-table tbody tr:last-child td { border-bottom: 0; }
      [data-testid="stMarkdownContainer"] code {
        color: #285b66 !important; background: #e7f0f2 !important;
        border: 1px solid #d6e4e7; border-radius: 5px; padding: .08rem .3rem;
      }
      .guide-source-link { color: #176d79 !important; font-weight: 750; text-decoration: none; }
      .guide-source-link:hover { text-decoration: underline; }
      [data-testid="stPageLink"] a {
        color: #176d79 !important; background: #fff !important; border: 1px solid #d2e1e5;
        border-radius: 10px; padding: .45rem .75rem; text-decoration: none;
      }
      [data-testid="stPageLink"] a:hover { background: #edf5f6 !important; }
      [data-testid="stMetric"] { padding: .8rem .9rem; border: 1px solid #dce6eb; border-radius: 13px; background: #fff; box-shadow: 0 4px 14px #193b5207; }
      [data-testid="stExpander"] { border: 1px solid #cbd9e0 !important; border-radius: 12px !important; background: #fff !important; overflow: hidden; }
      [data-testid="stExpander"] summary { color: #183247 !important; background: #eaf1f3 !important; font-weight: 750; }
      [data-testid="stExpander"] summary:hover { background: #e1ecee !important; }
      [data-testid="stExpander"] [data-testid="stExpanderDetails"] { background: #fff !important; }
      [data-testid="stExpander"] * { color: #183247 !important; }
      [data-testid="stAppViewContainer"] a { color: #176d79 !important; }
      @media (max-width: 760px) {
        .block-container { padding: 1rem .8rem 3rem; }
        .guide-hero { padding: 1.35rem 1.15rem; border-radius: 16px; }
        .guide-flow-card { min-height: 135px; padding: .75rem; }
        .st-key-guide_bookmark_row { row-gap: .35rem; }
        .st-key-guide_nav_overview button,
        .st-key-guide_nav_data button,
        .st-key-guide_nav_architecture button,
        .st-key-guide_nav_experiments button,
        .st-key-guide_nav_examples button {
          min-height: 44px; padding: .22rem .55rem; font-size: .78rem !important;
        }
        .guide-example-card { padding: .75rem .8rem; }
        .guide-transcript-turn { grid-template-columns: 78px minmax(0, 1fr); gap: .5rem; padding: .55rem; }
        .guide-table { min-width: 620px; }
      }
    </style>
    """,
)

with st.container(key="page-switcher"):
    st.markdown('<div class="guide-page-switcher-label">頁面導覽</div>', unsafe_allow_html=True)
    switcher_columns = st.columns([1.3, 1.3, 7.4], gap="small")
    with switcher_columns[0]:
        with st.container(key="page-switcher-item"):
            st.page_link("app.py", label="通話分類", icon=":material/home:", width="stretch")
    with switcher_columns[1]:
        with st.container(key="page-switcher-current"):
            st.page_link(
                "pages/1_專案說明.py",
                label="專案說明",
                icon=":material/menu_book:",
                width="stretch",
            )
st.markdown(
    """
    <div class="guide-hero">
      <div class="eyebrow">FLYCALL-1999 · PROJECT GUIDE</div>
      <h1>專案流程、模型架構與實驗紀錄</h1>
      <p>用一頁看懂資料如何建立與切分、目前展示模型怎麼分類，以及開發中比較過哪些方法。</p>
    </div>
    """,
    unsafe_allow_html=True,
)

summary = st.columns(4, gap="medium")
for column, label, value, detail in zip(
    summary,
    ("正式合成通話", "服務分類", "情境家族", "資料切分"),
    ("1,000 筆", "5 類", "66 個", "700 / 150 / 150"),
    ("Pilot 50 筆另存", "每類 200 筆", "同一家族不跨 split", "Train / Validation / Test"),
    strict=True,
):
    with column:
        st.metric(label, value)
        st.caption(detail)

st.markdown(
    '<div class="guide-warning"><strong>研究限制</strong>：資料是合成逐字稿，目前仍待人工複核；'
    '所有模型分數都來自 validation。正式 test 尚未執行，這些數字不能當成真實 1999 服務成效。</div>',
    unsafe_allow_html=True,
)

guide_sections = (
    ('overview', '專案流程', '#167c80', '#f0f8f7'),
    ('data', '資料生成與切分', '#36805b', '#f1f8f3'),
    ('architecture', '模型架構', '#426fb3', '#f3f7fd'),
    ('experiments', '中途測試與分類比較', '#7655a6', '#f6f2fb'),
    ('examples', '分類範例', '#bd7029', '#fff7ef'),
)
valid_sections = {section for section, *_ in guide_sections}
if "guide_section" not in st.session_state:
    st.session_state["guide_section"] = "overview"
selected_section = st.session_state.get("guide_section", "overview")
if selected_section not in valid_sections:
    selected_section = "overview"
    st.session_state["guide_section"] = selected_section

with st.container(horizontal=True, wrap=True, gap="xsmall", key="guide_bookmark_row"):
    for index, (section, label, _, _) in enumerate(guide_sections, start=1):
        st.button(
            f"{index:02d}  {label}",
            key=f"guide_nav_{section}",
            type="primary" if selected_section == section else "secondary",
            width="content",
            on_click=_select_guide_section,
            args=(section,),
        )


if selected_section == "overview":
    st.subheader("研究要做什麼？")
    st.markdown(
        "這個專案把 1999 客服和民眾之間的多輪對話，分類到五種市政服務類別。"
        "一般文字分類器提供比較基準；另一條研究路徑把 MaleCNS 雄性果蠅連結圖作為稀疏拓樸，"
        "測試 Fly A 壓縮文字表示、Fly B 再分類的可行性。"
    )

    st.subheader("從來電文字到人工確認")
    flow = st.columns([1, 0.12, 1, 0.12, 1, 0.12, 1], gap="small")
    flow_cards = (
        ("01 · INPUT", "通話逐字稿", "R: 客服、L: 來電民眾的多輪文字"),
        ("02 · ENCODE", "E5 語意編碼", "把文字轉為 384 維向量"),
        ("03 · CLASSIFY", "鎖定 MLP", "384 → 16 → 5 類 logits"),
        ("04 · REVIEW", "人工確認", "介面只作研究展示，不會真實派工"),
    )
    for index, (step, title, copy) in enumerate(flow_cards):
        with flow[index * 2]:
            st.markdown(
                f'<div class="guide-flow-card"><div class="guide-flow-step">{step}</div>'
                f'<div class="guide-flow-title">{title}</div><div class="guide-flow-copy">{copy}</div></div>',
                unsafe_allow_html=True,
            )
        if index < len(flow_cards) - 1:
            with flow[index * 2 + 1]:
                st.markdown("<div style='text-align:center;padding-top:2.5rem;color:#78909a;font-size:1.4rem'>→</div>", unsafe_allow_html=True)

    st.subheader("目前完成狀態")
    left, right = st.columns(2, gap="large")
    with left:
        st.markdown("**已完成的技術部分**")
        st.markdown(
            "- E5 本機推論與固定模型 checkpoint\n"
            "- MLP 開發／展示模型及共用 predictor\n"
            "- Fly A/B 圖模型的 train/validation 訓練流程\n"
            "- CLI、API 與 Streamlit 對同一 checkpoint 的輸出一致性驗收"
        )
    with right:
        st.markdown("**仍需完成的研究關卡**")
        st.markdown(
            "- 人工複核正式合成逐字稿並記錄決定\n"
            "- 核准候選模型與設定\n"
            "- 通過前兩項後，才依一次性流程執行正式 test 評估"
        )

elif selected_section == "data":

    st.subheader("資料從哪裡來？")
    st.markdown(
        "正式資料不是實際市民通話，也沒有生成音訊。類別名稱與範圍依專案 taxonomy 整理，"
        "並參照臺北市 1999 案件類別資料核對；每類 200 筆是為了建立平衡的研究資料集，"
        "不是照真實案件比例抽樣。"
    )
    st.markdown(
        '<a class="guide-source-link" href="https://data.taipei/dataset/detail?id=cb423c17-88eb-4231-a725-f1b93247d1bf" target="_blank" rel="noopener noreferrer">'
        '查看臺北市資料大平台的類別資料 ↗</a>',
        unsafe_allow_html=True,
    )

    st.markdown(
        _table_markup(
            ("類別代碼", "服務類別", "情境例子"),
            (
                ("sidewalk_maintenance", "人行道維護", "地磚翹起、路面高低差"),
                ("road_surface_defect", "道路凹陷、不平、有高低差", "路面凹洞、局部隆起"),
                ("park_general_maintenance", "一般公園綠地管理及設施維護（含車輛違規進入）", "遊具、座椅、綠地設施"),
                ("waste_truck_service", "垃圾車清運及服務事項", "漏收、停靠與清運時段"),
                ("street_cleaning", "路面清潔（含行人果皮箱、菸蒂、狗便）", "菸蒂、散落垃圾、果皮箱"),
            ),
        ),
        unsafe_allow_html=True,
    )

    st.subheader("如何生成正式逐字稿？")
    gen_columns = st.columns(3, gap="medium")
    generation_cards = (
        ("情境家族", "66 個家族", "先定義不同案件情境，再用變化庫避免每筆只換地名。"),
        ("分批組裝", "20 批 × 50 筆", "以確定性模板組裝對話並保留生成紀錄，正式版共 1,000 筆。"),
        ("對話規格", "9、11 或 13 行", "R 為客服、L 為民眾；每筆至少 200 個中文字，只保留一個主要問題。"),
    )
    for column, (title, value, copy) in zip(gen_columns, generation_cards, strict=True):
        with column:
            st.markdown(f"**{title}**")
            st.markdown(f"### {value}")
            st.caption(copy)

    st.markdown(
        '<div class="guide-note">正式資料使用行政區與公共空間類型描述位置，避免姓名、電話、門牌或精確地址。'
        '自動格式檢查通過不等於逐筆人工核准；正式資料目前仍待人工複核。</div>',
        unsafe_allow_html=True,
    )

    st.subheader("如何切分，避免相似情境洩漏？")
    split_columns = st.columns(3, gap="medium")
    split_cards = (
        ("訓練 Train", "700 筆", "70% · 33 個情境家族"),
        ("驗證 Validation", "150 筆", "15% · 14 個情境家族"),
        ("測試 Test", "150 筆", "15% · 19 個情境家族 · 尚未評估"),
    )
    for column, (title, value, detail) in zip(split_columns, split_cards, strict=True):
        with column:
            st.metric(title, value)
            st.caption(detail)
    st.markdown(
        "切分單位是 `scenario_family_id`，不是逐筆隨機拆分。同一家族及預先標記容易混淆的相關家族會留在同一 split。"
        "每一類都是 140 筆 train、30 筆 validation、30 筆 test。訓練與選模只使用 train／validation；"
        "正式 test 在人工複核及候選核准前保持封存。"
    )

    with st.expander("Pilot 和正式資料有什麼不同？"):
        st.markdown(
            "Pilot 共 50 筆，用於小規模試產與檢查，獨立保存在 `split=pilot`，不併入正式 1,000 筆，"
            "也不參與目前模型訓練或這些比較結果。"
        )


elif selected_section == "architecture":
    st.subheader("現在 Streamlit 分類頁實際使用的路徑")
    st.caption("目前鎖定的開發／展示模型是 E5 + MLP seed 42；分類結果仍需人工確認。")
    active_flow = st.columns(4, gap="medium")
    active_cards = (
        ("文字輸入", "完整通話逐字稿", "保留 R:／L: 對話角色標記。"),
        ("E5 編碼", "384 維向量", "multilingual-e5-small；編碼器凍結。"),
        ("MLP 分類", "384 → 16 → 5", "一層 16 單元 ReLU hidden layer，輸出五類 logits。"),
        ("分類結果", "Softmax 五類分數", "呈現預測與各類分數，交由人工複核。"),
    )
    for column, (title, value, copy) in zip(active_flow, active_cards, strict=True):
        with column:
            st.markdown(f"**{title}**")
            st.markdown(
                f'<div class="guide-code-chip">{html.escape(value)}</div>',
                unsafe_allow_html=True,
            )
            st.caption(copy)
    st.caption("鎖定 MLP 設定：hidden size 16、ReLU、seed 42、80 epochs、learning rate 0.02。")

    st.markdown("#### MLP 的三個層次")
    layer_columns = st.columns(3, gap="medium")
    layers = (
        ("guide-layer-input", "INPUT", "384 維", "E5 對通話文字的向量表示"),
        ("guide-layer-hidden", "HIDDEN", "16 個單元", "全連接線性層 + ReLU"),
        ("guide-layer-output", "OUTPUT", "5 個 logits", "對應五個服務類別，再轉成機率"),
    )
    for column, (css_class, title, value, copy) in zip(layer_columns, layers, strict=True):
        with column:
            st.markdown(
                f'<div class="guide-layer {css_class}"><div class="guide-layer-title">{title}</div>'
                f'<div class="guide-layer-value">{value}</div><div class="guide-layer-copy">{copy}</div></div>',
                unsafe_allow_html=True,
            )

    st.divider()
    st.subheader("研究中的 Connectome 路徑：Fly A → Fly B")
    graph_flow = st.columns(5, gap="small")
    graph_cards = (
        ("E5", "384 維輸入", "文字語意向量"),
        ("Fly A", "MaleCNS 稀疏圖", "500 節點、2,216 條有向邊；兩輪訊息傳遞"),
        ("低維表示", "32 維", "Fly A 的圖核心輸出"),
        ("Fly B", "MaleCNS 稀疏圖", "同一圖拓樸，獨立權重，再做兩輪傳遞"),
        ("輸出", "5 類 logits", "分類服務類別"),
    )
    for column, (title, value, copy) in zip(graph_flow, graph_cards, strict=True):
        with column:
            st.markdown(f"**{title}**")
            st.markdown(
                f'<div class="guide-code-chip">{html.escape(value)}</div>',
                unsafe_allow_html=True,
            )
            st.caption(copy)
    st.markdown(
        '<div class="guide-note">Fly A/B 是研究候選路徑，不是目前 Streamlit 分類頁載入的 checkpoint。'
        '圖的 500 節點工程子集沒有對應到單一解剖腦區；稀疏網路圖是拓樸示意，不是 500 個實際神經元的位置圖。</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<a class="guide-source-link" href="https://male-cns.janelia.org/" target="_blank" rel="noopener noreferrer">'
        '查看 MaleCNS v1.0 資料來源 ↗</a>',
        unsafe_allow_html=True,
    )


elif selected_section == "experiments":
    st.subheader("開發中比較過哪些分類方式？")
    st.markdown(
        "比較從輕量字元特徵開始，之後改用 E5 語意向量，再加入低維投影與 Connectome 圖路徑。"
        "下表只呈現 validation 成績；不同階段的訓練設定不同，請以同一張表內的候選比較，不要跨表直接排名。"
    )

    with st.expander("第一階段｜TF-IDF 字元特徵（單次 smoke test）", expanded=True):
        st.markdown(
            "把逐字稿拆成重疊的字元片段或短字元片語，再交給 Logistic Regression 或 Linear SVM。"
            "特徵器只在 train fit，候選是預先固定的小型比較；這是低資源文字基準。"
        )
        st.markdown(
            _table_markup(
                ("特徵", "分類器", "Validation Accuracy", "Validation Macro-F1"),
                (
                    ("字元 n-gram (2–5)", "Logistic Regression", "0.9400", "0.9389"),
                    ("字元 n-gram (2–5)", "Linear SVM", "0.9800", "0.9797"),
                    ("短字元片語 (2–4)", "Logistic Regression", "0.9400", "0.9389"),
                    ("短字元片語 (2–4)", "Linear SVM", "0.9867", "0.9865"),
                ),
            ),
            unsafe_allow_html=True,
        )
        st.caption("資料：150 筆 validation。這是合成資料上的 smoke test，分數高不代表真實來電表現，也不是目前 UI 使用的分類器。")

    with st.expander("第二階段｜E5 向量上的一般分類器（seed 42）"):
        st.markdown("E5 先把逐字稿編碼成 384 維向量，再比較原始向量分類、MLP 與低維投影。")
        st.markdown(
            _table_markup(
                ("候選流程", "Validation Accuracy", "Validation Macro-F1"),
                (
                    ("E5 → Logistic Regression", "0.8733", "0.8678"),
                    ("E5 → MLP", "0.9200", "0.9181"),
                    ("E5 → PCA(32) → MLP", "0.9067", "0.9055"),
                    ("E5 → LDA(4) → Logistic Regression", "0.9000", "0.8998"),
                ),
            ),
            unsafe_allow_html=True,
        )
        st.caption("每類只有 30 筆 validation；這是單一 seed 的初步比較。LDA 是監督式線性降維，五類最多輸出四維。")

    with st.expander("第三階段｜M3.4 預先登錄的五候選、三個 seed 比較"):
        st.markdown("候選以相同 frozen split 及 seed 42、1337、2026 比較，依三個 seed 的 validation Macro-F1 平均選模。")
        st.markdown(
            _table_markup(
                ("候選", "Macro-F1 平均 ± SD", "Accuracy 平均"),
                (
                    ("Logistic Regression", "0.8678 ± 0.0000", "0.8733"),
                    ("MLP", "0.9022 ± 0.0274", "0.9067"),
                    ("PCA → MLP", "0.8965 ± 0.0154", "0.8978"),
                    ("LDA → Logistic Regression", "0.8998 ± 0.0000", "0.9000"),
                    ("Fly A → Fly B", "0.6601 ± 0.0765", "0.7089"),
                ),
            ),
            unsafe_allow_html=True,
        )
        st.markdown(
            '<div class="guide-callout">這份預先登錄比較暫定選出 MLP。正式資料仍待人工複核，test 保持 not_run。</div>',
            unsafe_allow_html=True,
        )

    with st.expander("第四階段｜相同訓練預算的三候選診斷"):
        st.markdown("後續以三個 seed 對照 MLP、純 Fly A/B 與 gated E5 residual。Residual 保留原始 E5 語意訊號的 gated 路徑，沒有取代已鎖定的 MLP。")
        st.markdown(
            _table_markup(
                ("候選", "Macro-F1 平均 ± SD", "Accuracy 平均 ± SD"),
                (
                    ("MLP", "0.9104 ± 0.0302", "0.9133 ± 0.0267"),
                    ("純 Fly A → Fly B", "0.8040 ± 0.0218", "0.8244 ± 0.0077"),
                    ("Gated E5 residual", "0.9048 ± 0.0084", "0.9089 ± 0.0077"),
                ),
            ),
            unsafe_allow_html=True,
        )
        st.caption("這是 validation-only 診斷；Residual 比較過多個設定，使用同一 validation 選設定可能使分數偏樂觀。")

    with st.expander("Accuracy、Macro-F1 和 SD 怎麼看？"):
        st.markdown(
            "- **Accuracy**：所有 validation 案例中，預測正確的比例。\n"
            "- **Macro-F1**：先分別計算五類的 F1，再對五類等權平均；可看出模型是否只顧到較容易的類別。\n"
            "- **SD**：三個 seed 結果的樣本標準差；數值越大，表示不同初始化下波動越大。\n\n"
            "所有表格都是待人工複核合成資料的 validation 結果。最終 test 尚未執行，因此目前沒有正式泛化效能結論。"
        )


elif selected_section == "examples":
    st.subheader("五類通話情境示例")
    st.markdown(
        "以下為正式合成資料集 v1.0.0 中的五筆原始多輪通話，全部取自 train split。"
        "資料仍待人工複核；這些逐字稿不是模型預測結果，也不代表真實市民通話。"
    )
    try:
        example_records = _load_formal_examples(
            str(FORMAL_DATASET_PATH),
            tuple(record_id for record_id, _, _ in FORMAL_EXAMPLE_SPECS),
        )
    except (OSError, ValueError) as error:
        st.error(f"無法載入正式資料集範例：{error}")
        st.stop()

    example_cards: list[tuple[str, str, str, str]] = []
    for index, ((record_id, expected_label, accent), record) in enumerate(
        zip(FORMAL_EXAMPLE_SPECS, example_records, strict=True),
        start=1,
    ):
        if (
            record.get("label_id") != expected_label
            or record.get("split") != "train"
            or record.get("is_synthetic") is not True
            or record.get("review_status") != "pending_manual_review"
        ):
            st.error(f"範例資料 {record_id} 的標籤或資料狀態與預期不符。")
            st.stop()
        turns: list[str] = []
        for transcript_line in record["transcript"].splitlines():
            if not transcript_line.strip():
                continue
            speaker, separator, utterance = transcript_line.partition(":")
            if not separator or speaker not in {"R", "L"}:
                st.error(f"範例資料 {record_id} 有無法辨識的發言行。")
                st.stop()
            speaker_name = "客服" if speaker == "R" else "來電者"
            turns.append(
                f'<div class="guide-transcript-turn guide-turn-{speaker.lower()}">'
                f'<span class="guide-transcript-speaker">{speaker}｜{speaker_name}</span>'
                f'<span class="guide-transcript-utterance">{html.escape(utterance.strip())}</span>'
                "</div>"
            )
        example_cards.append((record_id, record["label_name"], accent, "".join(turns)))

    example_columns = st.columns(2, gap="medium")
    for index, (record_id, label_name, accent, transcript_markup) in enumerate(example_cards, start=1):
        with example_columns[(index - 1) % 2]:
            with st.container(key=f"guide_example_card_{index}", border=True):
                st.markdown(
                    f'<div class="guide-example-card" style="--example-accent:{accent}">'
                    f'<h3 class="guide-example-card-title">{index:02d} · '
                    f'{html.escape(label_name)}</h3>'
                    "</div>",
                    unsafe_allow_html=True,
                )
                st.markdown(
                    '<div class="guide-example-meta">'
                    '<span class="guide-example-chip">正式資料 v1.0.0</span>'
                    '<span class="guide-example-chip">Train split</span>'
                    '<span class="guide-example-chip">合成・待人工複核</span>'
                    "</div>",
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f'<div class="guide-example-record-id">{html.escape(record_id)}</div>',
                    unsafe_allow_html=True,
                )
                with st.expander("展開一問一答逐字稿（R 客服／L 來電者）", expanded=False):
                    st.markdown(
                        '<div class="guide-transcript-turns">'
                        + transcript_markup
                        + "</div>",
                        unsafe_allow_html=True,
                    )
    st.caption("逐字稿直接載入正式資料集；R 代表客服，L 代表來電民眾。")

st.divider()
st.caption(
    "本頁依據：1999-connectome-demo-spec-v0.2.md、formal_generation_plan_v1.3.md、"
    "M2.2b Windows gate report、M3.4 validation comparison report、M4 matched-budget report。"
)

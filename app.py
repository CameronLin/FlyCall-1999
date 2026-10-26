"""Local Streamlit research demo for the locked FlyCall predictor."""

from __future__ import annotations

import csv
import hashlib
import html
import io
import json
import os
import sys
from time import perf_counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from flycall_data.predictor import FlyCallPredictor, PredictorError  # noqa: E402


LABEL_ZH = {
    "sidewalk_maintenance": "人行道維護",
    "road_surface_defect": "道路凹陷與路面不平",
    "park_general_maintenance": "公園綠地與設施維護",
    "waste_truck_service": "垃圾車清運服務",
    "street_cleaning": "路面清潔",
}

DEFAULT_TRANSCRIPT = """R:您好，這裡是1999，您慢慢說明，我會先把狀況聽清楚。
L:我想反映一下，位置大概在士林區公車候車區外側的人行面附近。靠近行人通道交接處有幾片導盲磚翹起來，邊緣已經鬆開。
R:碰到這個狀況時，你會需要怎麼調整自己的動作？
L:趕著通過的人容易踩到高起的邊，我自己也差點絆到。
R:好，還有一個地方想確認。大概靠近行走面的哪一側，方便用相對位置說明嗎？
L:是靠公共空間入口一側，附近同一段都看得到。
R:我了解。旁邊其他地方有沒有同樣變化，還是集中在這個位置？
L:這次比前一次明顯一些，但仍集中在同一帶。
R:好，謝謝你把現場的情況說明清楚。"""
DEFAULT_TRANSCRIPT_RECORD_ID = "TPE1999-FORMAL-SW-0031"
DEMO_SAMPLE_SPECS = (
    ("TPE1999-FORMAL-SW-0031", "sidewalk_maintenance"),
    ("TPE1999-FORMAL-RD-0076", "road_surface_defect"),
    ("TPE1999-FORMAL-PK-0008", "park_general_maintenance"),
    ("TPE1999-FORMAL-WT-0001", "waste_truck_service"),
    ("TPE1999-FORMAL-SC-0105", "street_cleaning"),
)

MALE_CNS_OVERVIEW_IMAGE = (
    "https://storage.googleapis.com/gweb-research2023-media/images/"
    "Male-Fruit-Fly-Brain-Map-2.width-1250.jpg"
)
MALE_CNS_SOURCE_URL = (
    "https://research.google/blog/a-connectomics-milestone-"
    "mapping-the-complete-male-fruit-fly-brain/"
)


APP_CSS = """
<style>
  :root {
    --fc-ink: #183247;
    --fc-muted: #617587;
    --fc-teal: #167c80;
    --fc-teal-light: #e8f4f2;
    --fc-line: #dce6eb;
    --fc-paper: #f4f7f9;
  }
  [data-testid="stAppViewContainer"] {
    background: radial-gradient(ellipse at 8% 0%, #e6f2f2 0, transparent 34%), var(--fc-paper);
  }
  [data-testid="stHeader"] { background: transparent; }
  [data-testid="stSidebar"],
  [data-testid="stExpandSidebarButton"],
  [data-testid="stSidebarCollapseButton"] { display: none !important; }
  .fc-page-switcher-label {
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
  .st-key-project-guide-cta [data-testid="stPageLink"] a {
    display: flex; justify-content: flex-start; width: 100%;
    color: #183247 !important; background: #e8f4f2 !important;
    border: 1px solid #b8d6d2 !important; border-radius: 12px !important;
    padding: .65rem .8rem !important; text-decoration: none !important; font-weight: 750 !important;
  }
  .st-key-project-guide-cta [data-testid="stPageLink"] a * { color: #183247 !important; }
  .st-key-project-guide-cta [data-testid="stPageLink"] a:hover { background: #dcefeb !important; }
  .st-key-download_result_json button,
  .st-key-download_result_csv button {
    color: #183247 !important; background: #e8f4f2 !important;
    border: 1px solid #b8d6d2 !important; border-radius: 11px !important; font-weight: 750 !important;
  }
  .st-key-download_result_json button:hover,
  .st-key-download_result_csv button:hover { background: #dcefeb !important; }
  .st-key-transcript_sample_picker label,
  .st-key-transcript_sample_picker [data-testid="stSelectbox"] * { color: #183247 !important; }
  .st-key-transcript_sample_picker [data-baseweb="select"] > div,
  div[data-testid="stSelectbox"] [data-baseweb="select"] > div {
    color: #183247 !important; background: #ffffff !important;
    border-color: #b8cbd2 !important; box-shadow: none !important;
  }
  .st-key-transcript_sample_picker [data-baseweb="select"] [role="combobox"],
  .st-key-transcript_sample_picker [data-baseweb="select"] [data-testid="stMarkdownContainer"],
  .st-key-transcript_sample_picker [data-baseweb="select"] svg { color: #183247 !important; fill: #526977 !important; }
  .st-key-transcript_sample_picker [data-baseweb="select"]:focus-within > div {
    border-color: #167c80 !important; box-shadow: 0 0 0 2px #167c8020 !important;
  }
  [data-baseweb="popover"] [data-baseweb="menu"] { color: #183247 !important; background: #ffffff !important; }
  [data-baseweb="menu"] [role="option"] { color: #183247 !important; background: #ffffff !important; }
  [data-baseweb="menu"] [role="option"] * { color: #183247 !important; background: transparent !important; }
  [data-baseweb="menu"] [role="option"]:hover,
  [data-baseweb="menu"] [role="option"][aria-selected="true"] { color: #183247 !important; background: #e8f4f2 !important; }
  .st-key-transcript_sample_picker [data-testid="stSelectbox"] [data-baseweb="select"],
  .st-key-transcript_sample_picker [data-testid="stSelectbox"] [data-baseweb="select"] *,
  div[data-testid="stSelectbox"] [data-baseweb="select"],
  div[data-testid="stSelectbox"] [data-baseweb="select"] * {
    color: #183247 !important; background-color: #ffffff !important;
  }
  .st-key-transcript_sample_picker [data-testid="stSelectbox"] [data-baseweb="select"] svg,
  div[data-testid="stSelectbox"] [data-baseweb="select"] svg { color: #526977 !important; fill: #526977 !important; }
  .st-key-transcript_sample_picker [data-testid="stSelectbox"] [data-baseweb="select"]:focus-within > div,
  div[data-testid="stSelectbox"] [data-baseweb="select"]:focus-within > div {
    border-color: #167c80 !important; box-shadow: 0 0 0 2px #167c8020 !important;
  }
  .st-key-restore_default_transcript [data-testid="stButton"] > button,
  div[data-testid="stButton"] > button[kind="secondary"] {
    color: #183247 !important; background: #e8f4f2 !important;
    border: 1px solid #b8d6d2 !important; border-radius: 11px !important;
    box-shadow: none !important; font-weight: 750 !important;
  }
  .st-key-restore_default_transcript [data-testid="stButton"] > button:hover,
  div[data-testid="stButton"] > button[kind="secondary"]:hover {
    color: #183247 !important; background: #dcefeb !important; border-color: #91c3bb !important;
  }
  .block-container { max-width: 1180px; padding-top: 2.2rem; padding-bottom: 4rem; }
  .fc-hero {
    position: relative; overflow: hidden; padding: 2rem 2.2rem 1.8rem;
    border-radius: 22px; color: white;
    background: linear-gradient(120deg, #17364e 0%, #205769 62%, #167c80 100%);
    box-shadow: 0 16px 38px #17364e20; margin-bottom: 1.15rem;
  }
  .fc-hero:after {
    content: ""; position: absolute; width: 230px; height: 230px; right: -48px; top: -94px;
    border: 1px solid #ffffff28; border-radius: 50%;
    box-shadow: 0 0 0 28px #ffffff0d, 0 0 0 58px #ffffff08;
  }
  .fc-kicker { color: #b8e4de; font-size: .76rem; font-weight: 800; letter-spacing: .15em; text-transform: uppercase; }
  .fc-hero h1 { color: white; margin: .45rem 0 .45rem; font-size: clamp(1.8rem, 3vw, 2.5rem); line-height: 1.2; }
  .fc-hero p { color: #e0edf1; margin: 0; font-size: 1rem; }
  .fc-badges { display: flex; flex-wrap: wrap; gap: .5rem; margin-top: 1.2rem; }
  .fc-badge { border: 1px solid #ffffff38; border-radius: 999px; padding: .3rem .7rem; background: #ffffff12; color: white; font-size: .78rem; font-weight: 700; }
  .fc-status {
    min-height: 94px; padding: .9rem 1rem; border: 1px solid var(--fc-line); border-radius: 15px;
    background: #ffffffdc; box-shadow: 0 4px 15px #193b5208;
  }
  .fc-status-label { color: var(--fc-muted); font-size: .75rem; font-weight: 700; letter-spacing: .03em; }
  .fc-status-value { color: var(--fc-ink); font-size: 1.03rem; font-weight: 800; margin-top: .25rem; }
  .fc-status-sub { color: var(--fc-muted); font-size: .75rem; margin-top: .15rem; }
  .fc-section-kicker { color: var(--fc-teal); font-size: .73rem; font-weight: 850; letter-spacing: .12em; margin: .2rem 0 .35rem; }
  .st-key-transcript-title h3 { color: #000000 !important; }
  .st-key-classification-result-title h3 { color: #000000 !important; }
  .st-key-predicted-class-code [data-testid="stMetricLabel"],
  .st-key-predicted-class-code [data-testid="stMetricValue"],
  .st-key-predicted-class-code [data-testid="stMetricLabel"] *,
  .st-key-predicted-class-code [data-testid="stMetricValue"] * { color: #000000 !important; }
  .st-key-model-ready-message [data-testid="stAlert"] p { color: #14532d !important; }
  .fc-side-card {
    padding: 1.1rem 1.15rem; border: 1px solid var(--fc-line); border-radius: 16px;
    background: white; margin-bottom: .8rem;
  }
  .fc-side-card h3 { color: var(--fc-ink); margin: 0 0 .7rem; font-size: 1rem; }
  .fc-side-card p { color: var(--fc-muted); margin: .35rem 0; font-size: .88rem; line-height: 1.5; }
  .fc-category { padding: .43rem .05rem; border-bottom: 1px solid #edf1f4; color: var(--fc-ink); font-size: .85rem; }
  .fc-category:last-child { border-bottom: 0; }
  [data-testid="stTextArea"] textarea {
    border: 1px solid #cbd9e0; border-radius: 13px; background: white;
    color: var(--fc-ink); line-height: 1.55; padding: .85rem 1rem;
  }
  [data-testid="stTextArea"] textarea:focus { border-color: var(--fc-teal); box-shadow: 0 0 0 2px #167c8020; }
  div[data-testid="stButton"] > button[kind="primary"] {
    min-height: 3.05rem; border: 0; border-radius: 12px; color: white;
    background: linear-gradient(100deg, #176d79, #178a83); font-weight: 800;
    box-shadow: 0 7px 16px #167c8028; transition: transform .15s ease, box-shadow .15s ease;
  }
  div[data-testid="stButton"] > button[kind="primary"]:hover {
    transform: translateY(-1px); box-shadow: 0 10px 20px #167c8038;
  }
  .fc-result {
    padding: 1.2rem 1.35rem; border-radius: 17px; border: 1px solid #b8ddd7;
    background: linear-gradient(120deg, #f0faf7, #ffffff); margin: .3rem 0 .9rem;
  }
  .fc-result-label { color: #000000; font-size: .8rem; font-weight: 750; }
  .fc-result-name { color: #000000; font-size: 1.5rem; line-height: 1.3; font-weight: 850; margin: .25rem 0 .2rem; }
  .fc-result-code { color: #000000; font: .78rem ui-monospace, Consolas, monospace; }
  .fc-score-section-title { color: #000000 !important; font-size: 1.1rem; font-weight: 750; margin: 1.2rem 0 .5rem; }
  .fc-network-panel { padding: clamp(.9rem, 2vw, 1.25rem); border: 1px solid #dce6eb; border-radius: 18px; background: #ffffff; margin: 1rem 0 1.2rem; box-shadow: 0 8px 24px #193b5208; }
  .fc-network-header { display: flex; justify-content: space-between; align-items: flex-start; gap: 1rem; margin-bottom: .9rem; }
  .fc-network-header > div:first-child { min-width: 0; }
  .fc-network-title { color: #183247; font-size: 1.12rem; font-weight: 850; }
  .fc-network-caption { color: #617587; font-size: .82rem; line-height: 1.5; margin-top: .2rem; }
  .fc-model-role-strip { display: grid; grid-template-columns: minmax(0, 1fr); gap: .55rem; margin: .8rem 0 1rem; }
  .fc-model-role-card { display: grid; grid-template-columns: minmax(220px, .7fr) minmax(0, 1.3fr); align-items: center; column-gap: 1rem; row-gap: .15rem; min-width: 0; padding: .8rem 1rem; border: 1px solid #dce6eb; border-radius: 12px; background: #f8fafb; }
  .fc-model-role-card.fc-role-current { border-left: 4px solid #23805f; background: #f0f8f3; }
  .fc-model-role-card.fc-role-research { border-left: 4px solid #7655a6; background: #f7f4fb; }
  .fc-model-role-label { grid-column: 1; grid-row: 1; color: #526977; font-size: .7rem; font-weight: 850; letter-spacing: .04em; }
  .fc-model-role-name { grid-column: 1; grid-row: 2; color: #183247; font-size: .94rem; line-height: 1.35; font-weight: 850; margin: 0; overflow-wrap: anywhere; }
  .fc-model-role-copy { grid-column: 2; grid-row: 1 / span 2; min-width: 0; color: #526977; font-size: .8rem; line-height: 1.55; overflow-wrap: anywhere; }
  .fc-live-badge { flex: 0 0 auto; padding: .3rem .65rem; border-radius: 999px; background: #eef2f4; color: #526977; font-size: .72rem; font-weight: 800; }
  .fc-live-badge.fc-running { background: #dff3ef; color: #0e696e; }
  .fc-live-badge.fc-complete { background: #e7f5ec; color: #287247; }
  .fc-live-badge.fc-error { background: #fff1f1; color: #a23b3b; }
  .fc-live-lane { display: flex; align-items: stretch; gap: .55rem; }
  .fc-live-lane-fly-ab { display: grid; grid-template-columns: minmax(0, 1fr) 28px minmax(0, 1fr) 28px minmax(0, 1fr) 28px minmax(0, 1fr); align-items: stretch; gap: .45rem; }
  .fc-live-lane-mlp { display: grid; grid-template-columns: minmax(145px, .85fr) 26px minmax(300px, 2fr) 26px minmax(145px, .85fr); align-items: stretch; gap: .45rem; }
  .fc-live-stage { flex: 1 1 0; min-width: 0; padding: .9rem; border: 1px solid #dce6eb; border-radius: 13px; background: #f8fafb; text-align: center; }
  .fc-live-lane-mlp > .fc-live-stage { display: flex; flex-direction: column; justify-content: center; min-height: 190px; }
  .fc-live-stage.fc-stage-e5 { --fc-stage-color: #426fb3; border-top: 3px solid #426fb3; background: #f3f7fd; }
  .fc-live-stage.fc-stage-mlp { --fc-stage-color: #167c80; border-top: 3px solid #167c80; background: #f0f8f7; }
  .fc-live-stage.fc-stage-fly-a { --fc-stage-color: #7655a6; border-top: 3px solid #7655a6; background: #f6f2fb; }
  .fc-live-stage.fc-stage-fly-b { --fc-stage-color: #bd7029; border-top: 3px solid #bd7029; background: #fff7ef; }
  .fc-live-stage.fc-stage-output { --fc-stage-color: #36805b; border-top: 3px solid #36805b; background: #f1f8f3; }
  .fc-live-stage.fc-running { border-color: var(--fc-stage-color, #167c80); background: color-mix(in srgb, var(--fc-stage-color, #167c80) 9%, white); box-shadow: 0 0 0 3px color-mix(in srgb, var(--fc-stage-color, #167c80) 13%, transparent); }
  .fc-live-stage.fc-complete { border-color: #9bcfc0; background: #f0faf6; }
  .fc-live-stage.fc-inactive { background: #f4f6f7; border-style: dashed; }
  .fc-live-stage.fc-error { border-color: #dc7777; background: #fff1f1; }
  .fc-stage-title { color: var(--fc-stage-color, #183247); font-size: .94rem; line-height: 1.35; font-weight: 850; overflow-wrap: anywhere; }
  .fc-stage-detail { color: #526977; font-size: .78rem; line-height: 1.45; margin: .3rem 0 .45rem; min-height: 2.2em; display: flex; align-items: center; justify-content: center; overflow-wrap: anywhere; }
  .fc-stage-state { color: #617587; font-size: .73rem; line-height: 1.35; font-weight: 750; margin-top: .4rem; overflow-wrap: anywhere; }
  .fc-live-arrow { align-self: center; color: #6d8792; font-size: 1.35rem; font-weight: 800; }
  .fc-mlp-diagram { display: block; width: 100%; height: auto; max-height: 165px; margin: .25rem auto; }
  .fc-mlp-diagram text { fill: #526977; font-size: 10px; font-family: sans-serif; }
  .fc-mlp-diagram text.fc-mlp-label-input { fill: #3f76a8; font-weight: 800; }
  .fc-mlp-diagram text.fc-mlp-label-hidden { fill: #7655a6; font-weight: 800; }
  .fc-mlp-diagram text.fc-mlp-label-output { fill: #3b805c; font-weight: 800; }
  .fc-diagram-note { color: #718590; font-size: .64rem; margin-top: -.1rem; }
  .fc-mlp-edge { stroke: #b9c9d0; stroke-width: 1.1; }
  .fc-mlp-node { stroke-width: 1.5; }
  .fc-mlp-input { fill: #b7daf5; stroke: #3f76a8; }
  .fc-mlp-hidden { fill: #d7c7f0; stroke: #7655a6; }
  .fc-mlp-output { fill: #bee5ce; stroke: #3b805c; }
  .fc-mlp-diagram.fc-running .fc-mlp-edge,
  .fc-mlp-diagram.fc-complete .fc-mlp-edge { stroke: #258a87; stroke-width: 1.5; }
  .fc-mlp-diagram.fc-running .fc-mlp-input { fill: #8bc3ea; }
  .fc-mlp-diagram.fc-running .fc-mlp-hidden { fill: #b69add; }
  .fc-mlp-diagram.fc-running .fc-mlp-output { fill: #8bcea4; }
  .fc-signal-particle { fill: #f28c28; stroke: #ffffff; stroke-width: 2; filter: drop-shadow(0 1px 3px #17364e66); }
  .fc-architecture-title { color: #183247; font-size: .92rem; font-weight: 850; margin: 1.35rem 0 .45rem; padding-top: .85rem; border-top: 1px solid #e1e9ed; }
  .fc-architecture-note { color: #617587; font-size: .75rem; margin-bottom: .65rem; }
  .fc-graph-module { padding: .85rem; border: 1px solid #dce6eb; border-radius: 14px; background: #fbfcfd; margin-top: .6rem; }
  .fc-graph-module.fc-running { border-color: #167c80; background: #f0faf8; box-shadow: 0 0 0 3px #167c8014; }
  .fc-graph-module.fc-complete { border-color: #9bcfc0; background: #f5fbf7; }
  .fc-graph-module.fc-inactive { opacity: .82; }
  .fc-graph-module.fc-error { border-color: #dc7777; background: #fff7f7; }
  .fc-module-heading { display: flex; justify-content: space-between; align-items: baseline; gap: .8rem; margin-bottom: .65rem; }
  .fc-module-name { color: #183247; font-size: .88rem; font-weight: 850; }
  .fc-module-fly-a .fc-module-name { color: #65458f; }
  .fc-module-fly-b .fc-module-name { color: #a95c1e; }
  .fc-graph-module.fc-module-fly-a.fc-running { border-color: #7655a6; background: #f6f2fb; box-shadow: 0 0 0 3px #7655a61a; }
  .fc-graph-module.fc-module-fly-b.fc-running { border-color: #bd7029; background: #fff7ef; box-shadow: 0 0 0 3px #bd70291a; }
  .fc-module-status { color: #617587; font-size: .7rem; font-weight: 750; }
  .fc-module-flow { display: grid; grid-template-columns: minmax(92px, .8fr) 20px minmax(106px, .95fr) 20px minmax(220px, 1.6fr) 20px minmax(96px, .85fr); align-items: center; gap: .45rem; }
  .fc-module-step { padding: .6rem .5rem; border: 1px solid #dce6eb; border-radius: 11px; background: white; text-align: center; }
  .fc-module-step strong { display: block; color: #183247; font-size: .78rem; }
  .fc-module-step span { display: block; color: #617587; font-size: .7rem; margin-top: .15rem; overflow-wrap: anywhere; }
  .fc-graph-core-wrap { min-width: 0; padding: .5rem .6rem .35rem; border: 1px solid #e1e9ed; border-radius: 12px; background: white; }
  .fc-core-title { color: #183247; text-align: center; font-size: .78rem; font-weight: 800; }
  .fc-core-meta { display: flex; justify-content: center; flex-wrap: wrap; gap: .35rem .7rem; color: #526977; font-size: .67rem; }
  .fc-graph-svg { display: block; width: 100%; max-height: 145px; margin: .05rem auto; }
  .fc-graph-edge { stroke: #9eb3bc; stroke-width: 1.25; fill: none; opacity: .8; }
  .fc-graph-node { fill: #d4e7e7; stroke: #428789; stroke-width: 1.6; }
  .fc-graph-core.fc-running .fc-graph-edge { stroke: #238784; stroke-width: 1.8; }
  .fc-graph-core.fc-running .fc-graph-node { fill: #70c2b0; }
  .fc-graph-core.fc-complete .fc-graph-node { fill: #73b79c; }
  .fc-module-fly-a.fc-running .fc-graph-core .fc-graph-edge { stroke: #7655a6; }
  .fc-module-fly-a.fc-running .fc-graph-core .fc-graph-node { fill: #a990cf; }
  .fc-module-fly-b.fc-running .fc-graph-core .fc-graph-edge { stroke: #bd7029; }
  .fc-module-fly-b.fc-running .fc-graph-core .fc-graph-node { fill: #e4ad75; }
  .fc-module-fly-a.fc-complete .fc-graph-core .fc-graph-edge { stroke: #7655a6; }
  .fc-module-fly-a.fc-complete .fc-graph-core .fc-graph-node { fill: #a990cf; }
  .fc-module-fly-b.fc-complete .fc-graph-core .fc-graph-edge { stroke: #bd7029; }
  .fc-module-fly-b.fc-complete .fc-graph-core .fc-graph-node { fill: #e4ad75; }
  .fc-graph-core.fc-inactive { opacity: .72; }
  .fc-connectome-footnote { color: #718590; font-size: .67rem; margin: .45rem .1rem 0; }
  .fc-inference-guide { display: block; margin: 1.2rem 0 1rem; padding: 0; overflow: hidden; border: 1px solid #dce6eb; border-radius: 16px; background: #fff; box-shadow: 0 6px 20px #193b5208; }
  .fc-inference-guide > summary { display: flex; align-items: center; justify-content: space-between; gap: 1rem; padding: .85rem 1.05rem; color: #183247 !important; background: #f2f6f7 !important; cursor: pointer; list-style: none; font-size: 1rem; font-weight: 850; }
  .fc-inference-guide > summary::-webkit-details-marker { display: none; }
  .fc-inference-guide > summary::after { flex: 0 0 auto; color: #176d79; font-size: .76rem; font-weight: 800; content: "收合解說　−"; }
  .fc-inference-guide:not([open]) > summary::after { content: "深入解說　＋"; }
  .fc-inference-guide-content { padding: 0 1.05rem 1.05rem; }
  .fc-inference-guide-intro { color: #617587; font-size: .76rem; margin: .65rem 0 .8rem; }
  .fc-inference-flow-visual { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: .55rem; margin: .75rem 0 .9rem; }
  .fc-flow-visual-card { position: relative; min-width: 0; padding: .65rem .45rem .55rem; border: 1px solid #dce6eb; border-radius: 12px; background: #fbfcfd; text-align: center; }
  .fc-flow-visual-card:not(:last-child)::after { content: "→"; position: absolute; z-index: 1; top: 38%; right: -.57rem; color: #54808a; background: #fff; font-size: 1rem; font-weight: 850; }
  .fc-flow-visual-card svg { display: block; width: 100%; max-width: 145px; height: 84px; margin: 0 auto .25rem; }
  .fc-flow-visual-title { color: #183247; font-size: .77rem; font-weight: 850; }
  .fc-flow-visual-shape { color: #176d79; font-size: .66rem; font-weight: 750; margin-top: .12rem; }
  .fc-inference-flow-caption { color: #718590; font-size: .65rem; text-align: right; margin: -.55rem .1rem .75rem; }
  .fc-inference-step-visual { margin: .55rem 0 .75rem; }
  .fc-inference-svg-scroll { max-width: 100%; overflow-x: auto; padding: .45rem; border: 1px solid #dce6eb; border-radius: 11px; background: #fbfcfd !important; }
  .fc-inference-svg-scroll svg {
    display: block; width: min(100%, 980px); height: auto; margin: 0 auto;
    flex: 0 0 auto;
  }
  .fc-inference-visual-note { color: #718590; font-size: .66rem; text-align: center; margin-top: .3rem; }
  .fc-inference-step { margin: .5rem 0; border: 1px solid #dce6eb; border-radius: 11px; background: #fbfcfd !important; overflow: hidden; }
  .fc-inference-step summary { display: flex; align-items: center; gap: .65rem; padding: .7rem .8rem; color: #183247 !important; background: #f2f6f7 !important; cursor: pointer; list-style: none; font-weight: 800; }
  .fc-inference-step summary::-webkit-details-marker { display: none; }
  .fc-inference-step summary::after { content: "＋"; color: #176d79 !important; margin-left: auto; font-size: 1rem; }
  .fc-inference-step[open] summary::after { content: "−"; }
  .fc-inference-step summary * { color: #183247 !important; }
  .fc-inference-step summary .fc-inference-step-index { color: #ffffff !important; }
  .fc-inference-step-index { display: inline-grid; place-items: center; flex: 0 0 1.7rem; height: 1.7rem; border-radius: 50%; color: #fff !important; background: #176d79; font-size: .72rem; }
  .fc-inference-step-name { color: #183247 !important; font-size: .84rem; }
  .fc-inference-step-hint { color: #617587 !important; font-size: .7rem; font-weight: 600; }
  .fc-inference-step-body { padding: .8rem .9rem .9rem; color: #183247 !important; background: #fff !important; }
  .fc-inference-step-body p { color: #526977 !important; font-size: .77rem; line-height: 1.55; margin: .25rem 0 .55rem; }
  .fc-inference-meta { display: flex; flex-wrap: wrap; gap: .4rem; margin: .4rem 0 .55rem; }
  .fc-inference-meta span { padding: .28rem .5rem; border: 1px solid #dce6eb; border-radius: 7px; color: #183247 !important; background: #f4f7f8 !important; font-size: .68rem; }
  .fc-inference-source { color: #176d79 !important; font: .69rem ui-monospace, Consolas, monospace; }
  .fc-inference-code {
    display: block; margin: .4rem 0 0; padding: .75rem .85rem; overflow-x: auto;
    white-space: pre-wrap; overflow-wrap: anywhere; border: 1px solid #dce6eb; border-radius: 9px;
    color: #183247 !important; background-color: #f1f6f7 !important;
    box-shadow: none !important; text-shadow: none !important;
    font: .71rem/1.55 ui-monospace, Consolas, monospace;
  }
  .fc-inference-code code {
    padding: 0 !important; border: 0 !important; color: #183247 !important;
    background: transparent !important; box-shadow: none !important; text-shadow: none !important;
    font: inherit; white-space: inherit;
  }
  .fc-logit-table-wrap { width: 100%; overflow-x: auto; border: 1px solid #dce6eb; border-radius: 10px; background: #fff !important; }
  .fc-logit-table { width: 100%; border-collapse: collapse; color: #183247 !important; background: #fff !important; font-size: .79rem; }
  .fc-logit-table th { padding: .65rem .7rem; border-bottom: 1px solid #cbd9e0; color: #183247 !important; background: #eaf2f3 !important; text-align: left; white-space: nowrap; }
  .fc-logit-table td { padding: .58rem .7rem; border-bottom: 1px solid #e8eef0; color: #183247 !important; background: #fff !important; }
  .fc-logit-table tr:nth-child(even) td { background: #f7fafb !important; }
  .fc-logit-table tr:last-child td { border-bottom: 0; }
  .fc-logit-table .fc-logit-code { font-family: ui-monospace, Consolas, monospace; }
  .fc-logit-table .fc-logit-number { text-align: right; font-variant-numeric: tabular-nums; }
  .fc-connectome-context {
    display: grid; grid-template-columns: minmax(0, 1fr) minmax(280px, 1.1fr);
    align-items: center; gap: 1.1rem; margin-top: .8rem; padding: 1rem;
    border: 1px solid #dce6eb; border-radius: 14px; background: #f8fafb;
  }
  .fc-connectome-context-kicker { color: #167c80; font-size: .68rem; font-weight: 850; letter-spacing: .08em; }
  .fc-connectome-context-title { color: #183247; font-size: .9rem; font-weight: 850; margin: .2rem 0 .45rem; }
  .fc-connectome-context-copy p { color: #526977; font-size: .76rem; line-height: 1.55; margin: .35rem 0; }
  .fc-connectome-context-link { color: #176d79; font-size: .73rem; font-weight: 750; text-decoration: none; }
  .fc-connectome-context-link + .fc-connectome-context-link { margin-left: .75rem; }
  .fc-connectome-context-link:hover { text-decoration: underline; }
  .fc-connectome-figure { min-width: 0; margin: 0; padding: .55rem; border: 1px solid #e1e9ed; border-radius: 11px; background: #fff; }
  .fc-connectome-figure img { display: block; width: 100%; max-height: 250px; object-fit: contain; border-radius: 7px; }
  .fc-connectome-figure figcaption { color: #718590; font-size: .65rem; line-height: 1.45; margin-top: .4rem; }
  .fc-class-chips { display: flex; flex-wrap: wrap; justify-content: center; gap: .4rem; margin-top: .7rem; }
  .fc-class-chip { padding: .3rem .6rem; border: 1px solid #dce6eb; border-radius: 999px; color: #183247; background: #f7fafb; font-size: .69rem; }
  .fc-score-head { display: flex; align-items: baseline; justify-content: space-between; gap: 1rem; margin: .65rem 0 .15rem; }
  .fc-score-name { color: #000000; font-size: .9rem; font-weight: 750; }
  .fc-score-value { color: #000000; font-variant-numeric: tabular-nums; font-size: .86rem; font-weight: 850; }
  [data-testid="stProgress"] > div > div { background: linear-gradient(90deg, #278b89, #63b6a9); border-radius: 999px; }
  [data-testid="stProgress"] { margin: 0 0 .45rem; }
  [data-testid="stDataFrame"] { border: 1px solid var(--fc-line); border-radius: 12px; overflow: hidden; }
  [data-testid="stExpander"] {
    border: 1px solid #b9cbd2 !important; border-radius: 13px !important;
    background: #f0f5f6 !important; overflow: hidden;
  }
  [data-testid="stExpander"] summary {
    color: #183247 !important; background: #e8f0f2 !important; font-weight: 750 !important;
  }
  [data-testid="stExpander"] summary * { color: #183247 !important; }
  [data-testid="stExpander"] summary:hover { background: #dce9ec !important; }
  [data-testid="stExpander"] [data-testid="stExpanderDetails"] {
    color: #183247 !important; background: #f8fafb !important;
    border-top: 1px solid #dce6eb;
  }
  [data-testid="stExpander"] [data-testid="stExpanderDetails"] p { color: #183247 !important; }
  [data-testid="stAlert"] { border-radius: 12px; }
  .fc-footer { color: var(--fc-muted); font-size: .76rem; text-align: center; margin-top: 2rem; }
  @media (min-width: 761px) and (max-width: 960px) {
    .fc-model-role-strip { grid-template-columns: 1fr; }
    .fc-live-lane-fly-ab { grid-template-columns: minmax(0, 1fr) 28px minmax(0, 1fr); grid-template-rows: auto 24px auto; }
    .fc-live-lane-fly-ab > :nth-child(1) { grid-column: 1; grid-row: 1; }
    .fc-live-lane-fly-ab > :nth-child(2) { grid-column: 2; grid-row: 1; }
    .fc-live-lane-fly-ab > :nth-child(3) { grid-column: 3; grid-row: 1; }
    .fc-live-lane-fly-ab > :nth-child(4) { grid-column: 3; grid-row: 2; transform: rotate(90deg); }
    .fc-live-lane-fly-ab > :nth-child(5) { grid-column: 3; grid-row: 3; }
    .fc-live-lane-fly-ab > :nth-child(6) { grid-column: 2; grid-row: 3; transform: rotate(180deg); }
    .fc-live-lane-fly-ab > :nth-child(7) { grid-column: 1; grid-row: 3; }
    .fc-live-lane-mlp { grid-template-columns: minmax(145px, .85fr) 24px minmax(280px, 1.8fr) 24px minmax(145px, .85fr); }
    .fc-connectome-context { grid-template-columns: 1fr; }
  }
  @media (max-width: 760px) {
    .block-container { padding: 1rem .8rem 3rem; }
    .fc-hero { padding: 1.4rem 1.2rem; border-radius: 17px; }
    .fc-status { min-height: auto; }
    .fc-network-header { flex-direction: column; }
    .fc-model-role-strip { grid-template-columns: 1fr; }
    .fc-model-role-card { grid-template-columns: minmax(0, 1fr); row-gap: .2rem; }
    .fc-model-role-label, .fc-model-role-name, .fc-model-role-copy { grid-column: 1; grid-row: auto; }
    .fc-inference-step summary { flex-wrap: wrap; }
    .fc-inference-step-hint { flex: 1 0 calc(100% - 2.4rem); margin: -.35rem 0 0 2.35rem; }
    .fc-inference-svg-scroll svg { width: 980px; max-width: none; margin: 0; }
    .fc-inference-flow-visual { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .fc-flow-visual-card:not(:last-child)::after { display: none; }
    .fc-live-lane { flex-wrap: wrap; }
    .fc-live-lane-fly-ab { display: flex; flex-direction: column; gap: .35rem; }
    .fc-live-lane-fly-ab > .fc-live-arrow { align-self: center; transform: rotate(90deg); }
    .fc-live-stage { min-width: 120px; }
    .fc-live-lane-mlp { grid-template-columns: 1fr; }
    .fc-live-lane-mlp > .fc-live-arrow { transform: rotate(90deg); justify-self: center; }
    .fc-live-lane-mlp > .fc-live-stage { min-height: auto; }
    .fc-module-flow { grid-template-columns: 1fr; }
    .fc-module-flow > .fc-live-arrow { transform: rotate(90deg); justify-self: center; }
    .fc-connectome-context { grid-template-columns: 1fr; }
  }
</style>
"""


def _label_name(label: str) -> str:
    return LABEL_ZH.get(label, label)


def _status_label(state: str) -> str:
    return {
        "pending": "等待分類",
        "running": "正在運算",
        "complete": "已完成",
        "inactive": "本次未執行",
        "error": "發生錯誤",
    }.get(state, "等待分類")


def _elapsed_label(elapsed_ms: float | None) -> str:
    if elapsed_ms is None:
        return ""
    if elapsed_ms < 1000:
        return f"{elapsed_ms:.1f} 毫秒"
    return f"{elapsed_ms / 1000:.2f} 秒"


def _live_stage_card(
    title: str,
    detail: str,
    state: str,
    visual: str = "",
    *,
    kind: str = "default",
    elapsed_ms: float | None = None,
) -> str:
    if state not in {"pending", "running", "complete", "inactive", "error"}:
        state = "pending"
    if kind not in {"e5", "mlp", "fly-a", "fly-b", "output"}:
        kind = "default"
    state_text = _status_label(state)
    if state in {"complete", "error"} and elapsed_ms is not None:
        state_text += f" · {_elapsed_label(elapsed_ms)}"
    return (
        f'<div class="fc-live-stage fc-{state} fc-stage-{kind}">'
        f'<div class="fc-stage-title">{html.escape(title)}</div>'
        f'<div class="fc-stage-detail">{html.escape(detail)}</div>'
        f'{visual}<div class="fc-stage-state">{html.escape(state_text)}</div></div>'
    )


def _mlp_svg(state: str) -> str:
    inputs = [(28, y) for y in (35, 55, 75, 95)]
    hidden = [(120, y) for y in (27, 45, 63, 81, 99)]
    outputs = [(212, y) for y in (27, 45, 63, 81, 99)]
    lines = []
    for source in inputs:
        for target in hidden:
            lines.append(
                f'<line class="fc-mlp-edge" x1="{source[0]}" y1="{source[1]}" '
                f'x2="{target[0]}" y2="{target[1]}" />'
            )
    for source in hidden:
        for target in outputs:
            lines.append(
                f'<line class="fc-mlp-edge" x1="{source[0]}" y1="{source[1]}" '
                f'x2="{target[0]}" y2="{target[1]}" />'
            )
    circles = "".join(
        f'<circle class="fc-mlp-node fc-mlp-input" cx="{x}" cy="{y}" r="5.5" />'
        for x, y in inputs
    )
    circles += "".join(
        f'<circle class="fc-mlp-node fc-mlp-hidden" cx="{x}" cy="{y}" r="5.5" />'
        for x, y in hidden
    )
    circles += "".join(
        f'<circle class="fc-mlp-node fc-mlp-output" cx="{x}" cy="{y}" r="5.5" />'
        for x, y in outputs
    )
    particle = ""
    if state in {"running", "complete"}:
        repeat_count = "indefinite" if state == "running" else "1"
        particle = (
            '<circle class="fc-signal-particle" r="4.5">'
            f'<animateMotion dur="2.6s" repeatCount="{repeat_count}" fill="freeze" '
            'path="M 28 55 L 120 63 L 212 63" />'
            '</circle>'
        )
    return (
        f'<svg class="fc-mlp-diagram fc-{state}" viewBox="0 0 240 138" role="img" '
        'aria-label="代表性的全連接神經網路，384 維輸入、16 個隱藏單元、5 個輸出">'
        f'{"".join(lines)}{circles}{particle}'
        '<text class="fc-mlp-label-input" x="28" y="13" text-anchor="middle">Input</text>'
        '<text class="fc-mlp-label-hidden" x="120" y="13" text-anchor="middle">Hidden</text>'
        '<text class="fc-mlp-label-output" x="212" y="13" text-anchor="middle">Output</text>'
        '<text x="28" y="134" text-anchor="middle">384</text>'
        '<text x="120" y="134" text-anchor="middle">16</text>'
        '<text x="212" y="134" text-anchor="middle">5</text>'
        '</svg>'
    )


def _graph_core_svg(state: str, marker_id: str) -> str:
    positions = (
        (18, 73), (48, 34), (49, 111), (86, 19), (91, 64), (94, 126),
        (137, 37), (144, 91), (187, 15), (193, 63), (196, 117), (239, 34),
        (246, 92), (285, 60), (319, 26), (321, 111),
    )
    edges = (
        (0, 3), (0, 4), (1, 4), (1, 6), (2, 5), (2, 7), (3, 6), (4, 6),
        (4, 7), (5, 7), (6, 8), (6, 9), (7, 9), (7, 10), (8, 11), (9, 11),
        (9, 12), (10, 12), (11, 13), (12, 13), (13, 14), (13, 15), (14, 9), (15, 10),
    )
    edge_svg = "".join(
        f'<line class="fc-graph-edge" x1="{positions[source][0]}" y1="{positions[source][1]}" '
        f'x2="{positions[target][0]}" y2="{positions[target][1]}" '
        f'marker-end="url(#{marker_id})" />'
        for source, target in edges
    )
    nodes_svg = "".join(
        f'<circle class="fc-graph-node" cx="{x}" cy="{y}" r="7" />'
        for x, y in positions
    )
    particle = ""
    if state in {"running", "complete"}:
        repeat_count = "indefinite" if state == "running" else "1"
        particle = (
            '<circle class="fc-signal-particle" r="4.5">'
            f'<animateMotion dur="2.6s" repeatCount="{repeat_count}" fill="freeze" '
            'path="M 18 73 L 91 64 L 144 91 L 196 117 L 246 92 L 285 60" />'
            '</circle>'
        )
    return (
        f'<svg class="fc-graph-svg fc-graph-core fc-{state}" viewBox="0 0 340 145" role="img" '
        'aria-label="稀疏有向神經網路的拓樸示意圖">'
        '<defs>'
        f'<marker id="{marker_id}" markerWidth="6" markerHeight="6" refX="5" refY="3" '
        'orient="auto" markerUnits="strokeWidth"><path d="M0,0 L6,3 L0,6 z" fill="#8da5af" /></marker>'
        '</defs>'
        f'{edge_svg}{nodes_svg}{particle}</svg>'
    )


def _graph_module(
    name: str,
    input_title: str,
    input_detail: str,
    transform_title: str,
    transform_detail: str,
    output_title: str,
    output_detail: str,
    state: str,
    marker_id: str,
    module_kind: str,
) -> str:
    if state not in {"pending", "running", "complete", "inactive", "error"}:
        state = "pending"
    return (
        f'<section class="fc-graph-module fc-{state} fc-module-{module_kind}">'
        f'<div class="fc-module-heading"><div class="fc-module-name">{html.escape(name)}</div>'
        f'<div class="fc-module-status">{_status_label(state)}</div></div>'
        '<div class="fc-module-flow">'
        f'<div class="fc-module-step"><strong>{html.escape(input_title)}</strong>'
        f'<span>{html.escape(input_detail)}</span></div>'
        '<div class="fc-live-arrow" aria-hidden="true">→</div>'
        f'<div class="fc-module-step"><strong>{html.escape(transform_title)}</strong>'
        f'<span>{html.escape(transform_detail)}</span></div>'
        '<div class="fc-live-arrow" aria-hidden="true">→</div>'
        '<div class="fc-graph-core-wrap"><div class="fc-core-title">稀疏圖核心 · 兩輪訊息傳遞</div>'
        f'{_graph_core_svg(state, marker_id)}'
        '<div class="fc-core-meta"><span>500 個圖節點</span><span>2,216 條有向連結</span><span>重複更新 ×2</span></div>'
        '</div>'
        '<div class="fc-live-arrow" aria-hidden="true">→</div>'
        f'<div class="fc-module-step"><strong>{html.escape(output_title)}</strong>'
        f'<span>{html.escape(output_detail)}</span></div>'
        '</div></section>'
    )


def _inference_visuals(predictor: FlyCallPredictor) -> tuple[tuple[str, str, str, str], ...]:
    candidate = getattr(predictor, "candidate_name", "mlp")
    is_fly_ab = predictor.backend == "fly_a_to_fly_b"
    input_svg = (
        '<svg viewBox="0 0 140 84" role="img" aria-label="客服與來電者的逐字稿對話">'
        '<rect x="7" y="8" width="96" height="27" rx="9" fill="#eaf2fb" stroke="#7ea1c8"/>'
        '<path d="M20 35 L15 42 L32 35" fill="#eaf2fb" stroke="#7ea1c8"/>'
        '<text x="16" y="25" fill="#294f76" font-size="10" font-weight="700">R：客服提問</text>'
        '<rect x="37" y="46" width="96" height="27" rx="9" fill="#f5effa" stroke="#a18bc0"/>'
        '<path d="M118 73 L126 79 L126 72" fill="#f5effa" stroke="#a18bc0"/>'
        '<text x="46" y="63" fill="#65458f" font-size="10" font-weight="700">L：來電者描述</text>'
        '</svg>'
    )
    embedding_svg = (
        '<svg viewBox="0 0 140 84" role="img" aria-label="文字轉為384維E5向量">'
        '<rect x="4" y="28" width="42" height="25" rx="7" fill="#f3f7fd" stroke="#7d9ec7"/>'
        '<text x="25" y="44" text-anchor="middle" fill="#345f8c" font-size="9" font-weight="700">文字</text>'
        '<path d="M48 40 H62 M57 35 L62 40 L57 45" fill="none" stroke="#68899b" stroke-width="2"/>'
        '<text x="99" y="17" text-anchor="middle" fill="#345f8c" font-size="10" font-weight="700">384 維向量</text>'
        '<rect x="66" y="28" width="12" height="25" rx="3" fill="#b9d5f0" stroke="#6f94bc"/>'
        '<rect x="80" y="28" width="12" height="25" rx="3" fill="#d3e2f2" stroke="#6f94bc"/>'
        '<rect x="94" y="28" width="12" height="25" rx="3" fill="#aacbe9" stroke="#6f94bc"/>'
        '<text x="112" y="45" fill="#345f8c" font-size="14" font-weight="700">···</text>'
        '<text x="97" y="68" text-anchor="middle" fill="#617587" font-size="8">一段文字 → 一列數值</text>'
        '</svg>'
    )

    if is_fly_ab:
        classifier_title = "Fly A → Fly B"
        classifier_shape = "384 → 32 → 5"
        classifier_svg = (
            '<svg viewBox="0 0 140 84" role="img" aria-label="Fly A 將384維映射至32維，再由Fly B輸出5類">'
            '<rect x="5" y="22" width="55" height="40" rx="8" fill="#f4effa" stroke="#967cb7"/>'
            '<text x="32" y="39" text-anchor="middle" fill="#65458f" font-size="10" font-weight="700">Fly A</text>'
            '<text x="32" y="52" text-anchor="middle" fill="#65458f" font-size="8">384 → 32</text>'
            '<path d="M63 42 H76 M72 37 L77 42 L72 47" fill="none" stroke="#68899b" stroke-width="2"/>'
            '<rect x="81" y="22" width="55" height="40" rx="8" fill="#fff4e8" stroke="#c6905d"/>'
            '<text x="108" y="39" text-anchor="middle" fill="#9c5b23" font-size="10" font-weight="700">Fly B</text>'
            '<text x="108" y="52" text-anchor="middle" fill="#9c5b23" font-size="8">32 → 5</text>'
            '</svg>'
        )
    elif candidate == "mlp":
        classifier_title = "MLP 分類器"
        classifier_shape = "384 → 16 → 5"
        input_nodes = [(24, y) for y in (18, 32, 46, 60)]
        hidden_nodes = [(70, y) for y in (18, 32, 46, 60)]
        output_nodes = [(116, y) for y in (25, 39, 53)]
        edges = []
        for source_x, source_y in input_nodes:
            for target_x, target_y in hidden_nodes:
                edges.append(
                    f'<line x1="{source_x + 4}" y1="{source_y}" x2="{target_x - 4}" y2="{target_y}" stroke="#c7d4dd" stroke-width=".8"/>'
                )
        for source_x, source_y in hidden_nodes:
            for target_x, target_y in output_nodes:
                edges.append(
                    f'<line x1="{source_x + 4}" y1="{source_y}" x2="{target_x - 4}" y2="{target_y}" stroke="#c7d4dd" stroke-width=".8"/>'
                )
        nodes = ''.join(
            f'<circle cx="{x}" cy="{y}" r="4" fill="#b9d9f2" stroke="#3f76a8" stroke-width="1.2"/>'
            for x, y in input_nodes
        ) + ''.join(
            f'<circle cx="{x}" cy="{y}" r="4" fill="#d7c7f0" stroke="#7655a6" stroke-width="1.2"/>'
            for x, y in hidden_nodes
        ) + ''.join(
            f'<circle cx="{x}" cy="{y}" r="4" fill="#bee5ce" stroke="#3b805c" stroke-width="1.2"/>'
            for x, y in output_nodes
        )
        classifier_svg = (
            '<svg viewBox="0 0 140 84" role="img" aria-label="MLP 的 Input、Hidden、Output 三層示意圖">'
            + ''.join(edges) + nodes
            + '<text x="24" y="78" text-anchor="middle" fill="#3f76a8" font-size="7" font-weight="700">Input</text>'
            + '<text x="70" y="78" text-anchor="middle" fill="#7655a6" font-size="7" font-weight="700">Hidden</text>'
            + '<text x="116" y="78" text-anchor="middle" fill="#3b805c" font-size="7" font-weight="700">Output</text>'
            + '</svg>'
        )
    else:
        candidate_labels = {
            "pca_mlp": "PCA + MLP",
            "logistic_regression": "Logistic Regression",
            "lda_logistic_regression": "LDA + Logistic Regression",
        }
        classifier_title = candidate_labels.get(candidate, str(candidate))
        classifier_shape = "384 → 分類器 → 5"
        classifier_svg = (
            '<svg viewBox="0 0 140 84" role="img" aria-label="E5向量輸入鎖定分類器並輸出五類">'
            '<rect x="5" y="27" width="34" height="28" rx="7" fill="#eaf2fb" stroke="#7ea1c8"/>'
            '<text x="22" y="44" text-anchor="middle" fill="#294f76" font-size="8" font-weight="700">384</text>'
            '<path d="M42 41 H54 M50 37 L55 41 L50 45" fill="none" stroke="#68899b" stroke-width="2"/>'
            '<rect x="59" y="22" width="48" height="38" rx="8" fill="#f1f6f7" stroke="#79a7a2"/>'
            f'<text x="83" y="44" text-anchor="middle" fill="#176d79" font-size="8" font-weight="700">{html.escape(classifier_title)}</text>'
            '<path d="M109 41 H120 M116 37 L121 41 L116 45" fill="none" stroke="#68899b" stroke-width="2"/>'
            '<circle cx="128" cy="31" r="3" fill="#78b98f"/><circle cx="128" cy="41" r="3" fill="#78b98f"/><circle cx="128" cy="51" r="3" fill="#78b98f"/>'
            '</svg>'
        )

    softmax_svg = (
        '<svg viewBox="0 0 140 84" role="img" aria-label="五個 logits 經 Softmax 轉成五類相對分數">'
        '<text x="20" y="15" text-anchor="middle" fill="#9c5b23" font-size="8" font-weight="700">logits</text>'
        '<rect x="5" y="24" width="6" height="35" rx="3" fill="#efc18f"/>'
        '<rect x="14" y="33" width="6" height="26" rx="3" fill="#e8b77f"/>'
        '<rect x="23" y="19" width="6" height="40" rx="3" fill="#dda66d"/>'
        '<rect x="32" y="28" width="6" height="31" rx="3" fill="#e8b77f"/>'
        '<rect x="41" y="37" width="6" height="22" rx="3" fill="#efc18f"/>'
        '<text x="55" y="45" text-anchor="middle" fill="#68899b" font-size="18" font-weight="700">→</text>'
        '<text x="98" y="15" text-anchor="middle" fill="#287247" font-size="8" font-weight="700">五類分數</text>'
        '<rect x="65" y="24" width="63" height="6" rx="3" fill="#e7eef0"/><rect x="65" y="24" width="42" height="6" rx="3" fill="#68ad87"/>'
        '<rect x="65" y="34" width="63" height="6" rx="3" fill="#e7eef0"/><rect x="65" y="34" width="30" height="6" rx="3" fill="#82bd9a"/>'
        '<rect x="65" y="44" width="63" height="6" rx="3" fill="#e7eef0"/><rect x="65" y="44" width="21" height="6" rx="3" fill="#9bcaaa"/>'
        '<rect x="65" y="54" width="63" height="6" rx="3" fill="#e7eef0"/><rect x="65" y="54" width="13" height="6" rx="3" fill="#b4d7bd"/>'
        '<rect x="65" y="64" width="63" height="6" rx="3" fill="#e7eef0"/><rect x="65" y="64" width="8" height="6" rx="3" fill="#c8e2ce"/>'
        '<text x="98" y="80" text-anchor="middle" fill="#617587" font-size="8">總和 = 1</text>'
        '</svg>'
    )
    cards = (
        ("01", "逐字稿", "R/L 對話文字", input_svg),
        ("02", "E5 語意編碼", "[1, 384] 向量", embedding_svg),
        ("03", classifier_title, classifier_shape, classifier_svg),
        ("04", "Softmax", "5 logits → 5 分數", softmax_svg),
    )
    return cards


def _inference_flow_visual_html(predictor: FlyCallPredictor) -> str:
    cards = _inference_visuals(predictor)
    return '<div class="fc-inference-flow-visual">' + ''.join(
        '<div class="fc-flow-visual-card">'
        f'{visual}<div class="fc-flow-visual-title">{step_id} · {html.escape(title)}</div>'
        f'<div class="fc-flow-visual-shape">{html.escape(shape)}</div></div>'
        for step_id, title, shape, visual in cards
    ) + '</div><div class="fc-inference-flow-caption">架構節點與分數長度為說明示意；實際維度標註於各步驟中。</div>'


def _inference_step_visual_html(step_id: str, predictor: FlyCallPredictor, prediction=None) -> str:
    if step_id == "01":
        return (
            '<svg viewBox="0 0 700 170" width="700" height="170" role="img" aria-label="R與L對話合併為一段逐字稿後送入E5">'
            '<text x="22" y="19" fill="#526977" font-size="11" font-weight="700">客服與來電者的多輪對話</text>'
            '<rect x="20" y="31" width="190" height="43" rx="10" fill="#eaf2fb" stroke="#7ea1c8" stroke-width="1.5"/>'
            '<text x="34" y="49" fill="#294f76" font-size="12" font-weight="700">R：客服提問／確認</text>'
            '<text x="34" y="65" fill="#526977" font-size="10">一輪通話文字</text>'
            '<rect x="20" y="86" width="190" height="43" rx="10" fill="#f5effa" stroke="#a18bc0" stroke-width="1.5"/>'
            '<text x="34" y="104" fill="#65458f" font-size="12" font-weight="700">L：來電者描述問題</text>'
            '<text x="34" y="120" fill="#526977" font-size="10">另一輪通話文字</text>'
            '<path d="M224 80 H267 M259 73 L267 80 L259 87" fill="none" stroke="#68899b" stroke-width="2.4"/>'
            '<rect x="282" y="37" width="235" height="85" rx="12" fill="#f3f7f8" stroke="#89a8b2" stroke-width="1.5"/>'
            '<text x="399" y="59" text-anchor="middle" fill="#183247" font-size="12" font-weight="700">保留說話者標記的逐字稿</text>'
            '<text x="303" y="82" fill="#345f8c" font-size="11">R: ...</text><text x="303" y="101" fill="#65458f" font-size="11">L: ...</text>'
            '<text x="399" y="142" text-anchor="middle" fill="#617587" font-size="10">目前作為一段完整文字輸入</text>'
            '<path d="M531 80 H573 M565 73 L573 80 L565 87" fill="none" stroke="#68899b" stroke-width="2.4"/>'
            '<rect x="588" y="55" width="95" height="50" rx="10" fill="#e8f4f2" stroke="#72a9a2" stroke-width="1.5"/>'
            '<text x="635" y="77" text-anchor="middle" fill="#176d79" font-size="12" font-weight="700">送入 E5</text>'
            '<text x="635" y="93" text-anchor="middle" fill="#526977" font-size="10">單筆文字</text>'
            '</svg>'
        )
    if step_id == "02":
        vector_cells = ''.join(
            f'<rect x="{x}" y="70" width="22" height="35" rx="4" fill="{color}" stroke="#6f94bc"/>'
            for x, color in zip((478, 504, 530, 556, 582, 608), ("#b9d5f0", "#d3e2f2", "#aacbe9", "#c6dbee", "#a9c9e8", "#d3e2f2"), strict=True)
        )
        return (
            '<svg viewBox="0 0 700 170" width="700" height="170" role="img" aria-label="E5加上任務前綴後編碼成384維正規化向量">'
            '<rect x="18" y="47" width="185" height="74" rx="11" fill="#f3f7fd" stroke="#7d9ec7" stroke-width="1.5"/>'
            '<text x="110" y="70" text-anchor="middle" fill="#294f76" font-size="12" font-weight="700">任務前綴 + 逐字稿</text>'
            '<text x="110" y="91" text-anchor="middle" fill="#526977" font-size="10">passage: ...</text>'
            '<text x="110" y="107" text-anchor="middle" fill="#526977" font-size="10">整段通話文字</text>'
            '<path d="M214 84 H253 M245 77 L253 84 L245 91" fill="none" stroke="#68899b" stroke-width="2.4"/>'
            '<rect x="268" y="35" width="174" height="98" rx="13" fill="#edf3fb" stroke="#7d9ec7" stroke-width="1.5"/>'
            '<path d="M292 61 H418 M292 75 H418 M292 89 H418 M292 103 H418" stroke="#b2c9e0" stroke-width="3" stroke-linecap="round"/>'
            '<text x="355" y="52" text-anchor="middle" fill="#294f76" font-size="12" font-weight="700">E5-small Encoder</text>'
            '<text x="355" y="121" text-anchor="middle" fill="#526977" font-size="10">語意轉換</text>'
            '<path d="M453 84 H466 M459 77 L467 84 L459 91" fill="none" stroke="#68899b" stroke-width="2.4"/>'
            + vector_cells
            + '<text x="544" y="54" text-anchor="middle" fill="#345f8c" font-size="12" font-weight="700">[1, 384]</text>'
            '<text x="630" y="92" fill="#345f8c" font-size="16" font-weight="700">···</text>'
            '<text x="544" y="124" text-anchor="middle" fill="#526977" font-size="10">384 個數值特徵</text>'
            '<rect x="476" y="137" width="143" height="22" rx="11" fill="#eaf5ee" stroke="#9bcaaa"/>'
            '<text x="547" y="152" text-anchor="middle" fill="#287247" font-size="10" font-weight="700">L2 正規化 · ||x||₂ = 1</text>'
            '</svg>'
        )
    if step_id == "03" and predictor.backend == "fly_a_to_fly_b":
        return (
            '<svg viewBox="0 0 760 190" width="760" height="190" role="img" aria-label="Fly A圖網路轉成32維表示，再由Fly B圖網路輸出五類logits">'
            '<rect x="12" y="58" width="93" height="62" rx="10" fill="#eaf2fb" stroke="#7ea1c8" stroke-width="1.5"/>'
            '<text x="58" y="82" text-anchor="middle" fill="#294f76" font-size="12" font-weight="700">E5 向量</text>'
            '<text x="58" y="101" text-anchor="middle" fill="#526977" font-size="10">[1, 384]</text>'
            '<path d="M111 89 H131 M124 83 L132 89 L124 95" fill="none" stroke="#68899b" stroke-width="2.2"/>'
            '<rect x="140" y="25" width="244" height="132" rx="13" fill="#f7f3fb" stroke="#967cb7" stroke-width="1.5"/>'
            '<text x="262" y="47" text-anchor="middle" fill="#65458f" font-size="13" font-weight="700">Fly A</text>'
            '<rect x="155" y="61" width="91" height="58" rx="8" fill="#fff" stroke="#cfc1e0"/>'
            '<text x="200" y="83" text-anchor="middle" fill="#65458f" font-size="10" font-weight="700">線性投影</text><text x="200" y="101" text-anchor="middle" fill="#526977" font-size="9">+ tanh</text>'
            '<path d="M251 90 H267 M261 84 L269 90 L261 96" fill="none" stroke="#967cb7" stroke-width="2"/>'
            '<rect x="274" y="61" width="96" height="58" rx="8" fill="#fff" stroke="#cfc1e0"/>'
            '<text x="322" y="80" text-anchor="middle" fill="#65458f" font-size="9" font-weight="700">稀疏圖核心</text><text x="322" y="97" text-anchor="middle" fill="#526977" font-size="8">500 節點 · 2 輪</text>'
            '<text x="262" y="143" text-anchor="middle" fill="#65458f" font-size="10">輸出：[1, 32] 表示</text>'
            '<path d="M391 89 H410 M403 83 L411 89 L403 95" fill="none" stroke="#68899b" stroke-width="2.2"/>'
            '<rect x="420" y="25" width="244" height="132" rx="13" fill="#fff7ef" stroke="#c6905d" stroke-width="1.5"/>'
            '<text x="542" y="47" text-anchor="middle" fill="#9c5b23" font-size="13" font-weight="700">Fly B</text>'
            '<rect x="435" y="61" width="91" height="58" rx="8" fill="#fff" stroke="#e4c8aa"/>'
            '<text x="480" y="83" text-anchor="middle" fill="#9c5b23" font-size="10" font-weight="700">輸入適配器</text><text x="480" y="101" text-anchor="middle" fill="#526977" font-size="9">32 → 32</text>'
            '<path d="M531 90 H547 M541 84 L549 90 L541 96" fill="none" stroke="#c6905d" stroke-width="2"/>'
            '<rect x="554" y="61" width="96" height="58" rx="8" fill="#fff" stroke="#e4c8aa"/>'
            '<text x="602" y="80" text-anchor="middle" fill="#9c5b23" font-size="9" font-weight="700">圖核心 + 讀出</text><text x="602" y="97" text-anchor="middle" fill="#526977" font-size="8">500 節點 · 2 輪</text>'
            '<text x="542" y="143" text-anchor="middle" fill="#9c5b23" font-size="10">輸出：[1, 5] logits</text>'
            '<path d="M671 89 H691 M684 83 L692 89 L684 95" fill="none" stroke="#68899b" stroke-width="2.2"/>'
            '<rect x="700" y="58" width="50" height="62" rx="9" fill="#eaf5ee" stroke="#9bcaaa" stroke-width="1.5"/>'
            '<text x="725" y="83" text-anchor="middle" fill="#287247" font-size="10" font-weight="700">5 類</text><text x="725" y="102" text-anchor="middle" fill="#526977" font-size="9">logits</text>'
            '</svg>'
        )
    if step_id == "03" and getattr(predictor, "candidate_name", "mlp") == "mlp":
        input_nodes = [(170, y) for y in (58, 83, 108, 133, 158)]
        hidden_nodes = [(425, y) for y in (58, 83, 108, 133, 158)]
        output_nodes = [(690, y) for y in (58, 83, 108, 133, 158)]
        edge_svg = []
        for source_x, source_y in input_nodes:
            for target_x, target_y in hidden_nodes:
                edge_svg.append(
                    f'<line x1="{source_x + 7}" y1="{source_y}" x2="{target_x - 7}" y2="{target_y}" stroke="#b8c9d3" stroke-width="1" opacity=".62"/>'
                )
        for source_x, source_y in hidden_nodes:
            for target_x, target_y in output_nodes:
                edge_svg.append(
                    f'<line x1="{source_x + 7}" y1="{source_y}" x2="{target_x - 7}" y2="{target_y}" stroke="#b8c9d3" stroke-width="1" opacity=".62"/>'
                )
        layer_nodes = ''.join(
            f'<circle cx="{x}" cy="{y}" r="7" fill="#b9d9f2" stroke="#3f76a8" stroke-width="1.5"/>'
            for x, y in input_nodes
        ) + ''.join(
            f'<circle cx="{x}" cy="{y}" r="7" fill="#d7c7f0" stroke="#7655a6" stroke-width="1.5"/>'
            for x, y in hidden_nodes
        ) + ''.join(
            f'<circle cx="{x}" cy="{y}" r="7" fill="#bee5ce" stroke="#3b805c" stroke-width="1.5"/>'
            for x, y in output_nodes
        )
        class_labels = (
            "人行道維護", "道路凹陷與路面不平", "公園綠地與設施維護", "垃圾車清運服務", "路面清潔"
        )
        output_labels = ''.join(
            f'<text x="710" y="{y + 4}" fill="#526977" font-size="10">{html.escape(label)}</text>'
            for y, label in zip((58, 83, 108, 133, 158), class_labels, strict=True)
        )
        return (
            '<svg viewBox="0 0 870 210" width="870" height="210" role="img" aria-label="MLP全連接網路：384維Input、16個ReLU Hidden units、五類Output logits">'
            '<text x="170" y="25" text-anchor="middle" fill="#3f76a8" font-size="13" font-weight="700">INPUT · 384 維</text>'
            '<text x="425" y="25" text-anchor="middle" fill="#7655a6" font-size="13" font-weight="700">HIDDEN · 16 units</text>'
            '<text x="690" y="25" text-anchor="middle" fill="#3b805c" font-size="13" font-weight="700">OUTPUT · 5 logits</text>'
            + ''.join(edge_svg) + layer_nodes + output_labels
            + '<text x="297" y="106" text-anchor="middle" fill="#526977" font-size="10">Linear</text>'
            + '<text x="557" y="106" text-anchor="middle" fill="#526977" font-size="10">Linear</text>'
            + '<rect x="370" y="178" width="110" height="22" rx="11" fill="#f2ecfa" stroke="#c7b6de"/>'
            + '<text x="425" y="193" text-anchor="middle" fill="#65458f" font-size="10" font-weight="700">ReLU activation</text>'
            + '<text x="170" y="188" text-anchor="middle" fill="#526977" font-size="9">節點僅抽樣呈現</text>'
            + '<text x="690" y="188" text-anchor="middle" fill="#526977" font-size="9">依固定類別順序</text>'
            + '</svg>'
        )
    if step_id == "03":
        candidate = getattr(predictor, "candidate_name", "classifier")
        label = html.escape(str(candidate))
        return (
            '<svg viewBox="0 0 700 170" width="700" height="170" role="img" aria-label="E5向量送入鎖定分類器後輸出固定順序的五類logits">'
            '<rect x="25" y="49" width="130" height="68" rx="11" fill="#eaf2fb" stroke="#7ea1c8" stroke-width="1.5"/>'
            '<text x="90" y="77" text-anchor="middle" fill="#294f76" font-size="13" font-weight="700">E5 features</text><text x="90" y="98" text-anchor="middle" fill="#526977" font-size="11">[1, 384]</text>'
            '<path d="M164 83 H214 M206 76 L214 83 L206 90" fill="none" stroke="#68899b" stroke-width="2.4"/>'
            '<rect x="230" y="40" width="220" height="86" rx="12" fill="#f1f6f7" stroke="#79a7a2" stroke-width="1.5"/>'
            f'<text x="340" y="74" text-anchor="middle" fill="#176d79" font-size="13" font-weight="700">{label}</text>'
            '<text x="340" y="99" text-anchor="middle" fill="#526977" font-size="11">鎖定 checkpoint</text>'
            '<path d="M459 83 H509 M501 76 L509 83 L501 90" fill="none" stroke="#68899b" stroke-width="2.4"/>'
            '<rect x="525" y="49" width="150" height="68" rx="11" fill="#eaf5ee" stroke="#9bcaaa" stroke-width="1.5"/>'
            '<text x="600" y="77" text-anchor="middle" fill="#287247" font-size="13" font-weight="700">五類 logits</text><text x="600" y="98" text-anchor="middle" fill="#526977" font-size="11">[1, 5]</text>'
            '<text x="350" y="151" text-anchor="middle" fill="#617587" font-size="10">此模型依目前鎖定的參數執行；logits 尚未轉成 Softmax 分數。</text>'
            '</svg>'
        )
    if step_id == "04":
        rows = []
        if prediction is None:
            labels = ("人行道維護", "道路凹陷與路面不平", "公園綠地與設施維護", "垃圾車清運服務", "路面清潔")
            scores = (0.86, 0.68, 0.52, 0.34, 0.18)
        else:
            labels = tuple(_label_name(label) for label in prediction.label_order)
            scores = tuple(float(score) for score in prediction.probabilities)

        for index, (label, score) in enumerate(zip(labels, scores, strict=True)):
            y = 63 + index * 25
            bar_width = round(max(0.0, min(1.0, score)) * 140)
            is_predicted = prediction is not None and prediction.label_order[index] == prediction.predicted_label
            bar_color = "#23805f" if is_predicted else "#78b98f"
            label_color = "#176d59" if is_predicted else "#526977"
            label_weight = "700" if is_predicted else "400"
            rows.append(
                f'<text x="592" y="{y + 2}" fill="{label_color}" font-size="10" font-weight="{label_weight}">{html.escape(label)}</text>'
                f'<rect x="770" y="{y - 9}" width="140" height="13" rx="6" fill="#e7eef0"/>'
                f'<rect x="770" y="{y - 9}" width="{bar_width}" height="13" rx="6" fill="{bar_color}"/>'
                f'<text x="922" y="{y + 2}" fill="#183247" font-size="10" font-weight="700">{score:.2%}</text>'
            )
        actual_output = prediction is not None
        score_title = "本次五類分數" if actual_output else "五類分數（示意）"
        selection_note = (
            f"本次最高分：{html.escape(_label_name(prediction.predicted_label))}"
            if actual_output
            else "示意比例，尚非本次預測結果"
        )
        return (
            f'<svg viewBox="0 0 980 220" width="980" height="220" role="img" aria-label="{score_title}與最高分類別">'
            '<text x="105" y="31" text-anchor="middle" fill="#9c5b23" font-size="13" font-weight="700">分類器原始分數</text>'
            '<rect x="25" y="49" width="160" height="125" rx="12" fill="#fff7ef" stroke="#c6905d" stroke-width="1.5"/>'
            '<text x="105" y="78" text-anchor="middle" fill="#9c5b23" font-size="11">五類各有一個分數</text>'
            '<text x="105" y="106" text-anchor="middle" fill="#526977" font-size="10">分數大小還不受限於 0～1</text>'
            '<text x="105" y="135" text-anchor="middle" fill="#9c5b23" font-size="12" font-weight="700">[1, 5]</text>'
            '<path d="M194 111 H222 M215 104 L223 111 L215 118" fill="none" stroke="#68899b" stroke-width="2.4"/>'
            '<rect x="238" y="49" width="300" height="125" rx="12" fill="#f1f6f7" stroke="#79a7a2" stroke-width="1.5"/>'
            '<text x="388" y="73" text-anchor="middle" fill="#176d79" font-size="13" font-weight="700">Softmax：把分數轉成比例</text>'
            '<rect x="250" y="87" width="82" height="43" rx="8" fill="#fff7ef" stroke="#d9b187"/>'
            '<text x="291" y="105" text-anchor="middle" fill="#9c5b23" font-size="10" font-weight="700">輸入分數</text>'
            '<text x="291" y="120" text-anchor="middle" fill="#526977" font-size="8">五類原始值</text>'
            '<path d="M334 108 H341 M337 104 L342 108 L337 112" fill="none" stroke="#68899b" stroke-width="1.8"/>'
            '<rect x="344" y="87" width="82" height="43" rx="8" fill="#edf3fb" stroke="#a8bfd9"/>'
            '<text x="385" y="105" text-anchor="middle" fill="#345f8c" font-size="10" font-weight="700">轉成正值</text>'
            '<text x="385" y="120" text-anchor="middle" fill="#526977" font-size="8">指數轉換</text>'
            '<path d="M428 108 H435 M431 104 L436 108 L431 112" fill="none" stroke="#68899b" stroke-width="1.8"/>'
            '<rect x="438" y="87" width="88" height="43" rx="8" fill="#eaf5ee" stroke="#9bcaaa"/>'
            '<text x="482" y="105" text-anchor="middle" fill="#287247" font-size="10" font-weight="700">除以總和</text>'
            '<text x="482" y="120" text-anchor="middle" fill="#526977" font-size="8">五類一起比較</text>'
            '<text x="388" y="154" text-anchor="middle" fill="#526977" font-size="10">得到的五類分數加總為 1</text>'
            '<path d="M547 111 H574 M567 104 L575 111 L567 118" fill="none" stroke="#68899b" stroke-width="2.4"/>'
            f'<text x="777" y="31" text-anchor="middle" fill="#287247" font-size="13" font-weight="700">{score_title}</text>'
            + ''.join(rows)
            + '<rect x="680" y="190" width="280" height="22" rx="11" fill="#eaf5ee" stroke="#9bcaaa"/>'
            + f'<text x="820" y="205" text-anchor="middle" fill="#287247" font-size="10" font-weight="700">{selection_note}</text>'
            + '</svg>'
        )
    return ""


def _inference_explainer_html(predictor: FlyCallPredictor, prediction=None) -> str:
    candidate = getattr(predictor, "candidate_name", "mlp")
    is_fly_ab = predictor.backend == "fly_a_to_fly_b"
    if is_fly_ab:
        classifier_title = "Fly A → Fly B"
        classifier_shape = "Fly A：[1, 384] → [1, 32]；Fly B：[1, 32] → [1, 5] logits"
        classifier_copy = (
            "Fly A 將 E5 向量轉成 32 維表示，Fly B 再讀取這個表示輸出五類 logits。"
        )
        classifier_source = "src/flycall_data/predictor.py · FlyCallPredictor._predict_embedding"
        classifier_code = (
            'fly_a_output = self.model["fly_a"](values)\n'
            'logits = self.model["fly_b"](fly_a_output)[0].tolist()'
        )
    elif candidate == "mlp":
        classifier_title = "MLP"
        classifier_shape = "Input [1, 384] → Hidden [1, 16] → Output [1, 5] logits"
        classifier_copy = (
            "Input 是 E5 的 384 維向量；Hidden layer 有 16 個神經元並使用 ReLU；"
            "Output layer 產生五個 logits。這裡還沒有轉成分數。"
        )
        classifier_source = "src/flycall_data/embedding_pipeline.py · _fit_torch_mlp"
        classifier_code = (
            "model = nn.Sequential(\n"
            "    nn.Linear(x_train.shape[1], hidden_size),\n"
            "    nn.ReLU(),\n"
            "    nn.Linear(hidden_size, len(label_order)),\n"
            ")"
        )
    else:
        candidate_labels = {
            "pca_mlp": "PCA + MLP",
            "logistic_regression": "Logistic Regression",
            "lda_logistic_regression": "LDA + Logistic Regression",
        }
        classifier_title = candidate_labels.get(candidate, str(candidate))
        classifier_shape = "E5 向量 → 目前鎖定的分類器 → 5 類 logits"
        classifier_copy = (
            "分類器依鎖定的 checkpoint 設定，把 E5 向量轉成固定類別順序的五個 logits。"
        )
        classifier_source = "src/flycall_data/predictor.py · FlyCallPredictor._predict_embedding"
        classifier_code = (
            "logits = self._predict_embedding(\n"
            "    embedding, progress_callback=progress_callback\n"
            ")"
        )

    steps = (
        (
            "01",
            "逐字稿輸入",
            "文字字串 · 一筆通話",
            "app.py 將輸入框的整段逐字稿交給 predictor；R:／L: 標記仍是文字的一部分，目前沒有獨立的說話者輸入通道。",
            "app.py · predictor.predict(transcript)",
            "prediction = predictor.predict(\n    transcript, progress_callback=update_network_stage\n)",
        ),
        (
            "02",
            "E5 語意編碼",
            "輸入：[1 筆文字]　輸出：[1, 384] 向量",
            "E5 在逐字稿前加上固定任務前綴，編碼成一個 L2 正規化的 384 維向量。",
            "src/flycall_data/predictor.py · FlyCallPredictor.predict",
            "prefixed = E5_SMALL_CONFIG.prefix + transcript\nvectors = self.encoder.encode([prefixed])",
        ),
        (
            "03",
            f"分類器：{classifier_title}",
            classifier_shape,
            classifier_copy,
            classifier_source,
            classifier_code,
        ),
        (
            "04",
            "Softmax 與類別選擇",
            "5 個 logits → 5 個分數",
            "先把五類原始分數轉成正值，再各自除以五類分數總和，得到加總為 1 的相對分數；最後依固定類別順序選出最高分。這些分數不等於準確率。",
            "src/flycall_data/predictor.py · FlyCallPredictor.predict / _softmax",
            "probabilities = _softmax(logits)\npredicted_index = max(\n    range(len(LABEL_ORDER)), key=probabilities.__getitem__\n)",
        ),
    )
    detail_markup = []
    for index, (step_id, title, shape, copy, source, snippet) in enumerate(steps):
        opened = " open" if (prediction is None and index == 2) or (prediction is not None and step_id == "04") else ""
        visual_note = (
            '<div class="fc-inference-visual-note">這是本次模型輸出的分數；分數代表五類間的相對比例，不是準確率。</div>'
            if step_id == "04" and prediction is not None
            else '<div class="fc-inference-visual-note">圖為原理示意；節點數與分數比例不代表實際維度或預測值，實際資料形狀以標示為準。</div>'
        )
        detail_markup.append(
            f'<details class="fc-inference-step"{opened}>'
            '<summary>'
            f'<span class="fc-inference-step-index">{step_id}</span>'
            f'<span class="fc-inference-step-name">{html.escape(title)}</span>'
            f'<span class="fc-inference-step-hint">{html.escape(shape)}</span>'
            '</summary>'
            '<div class="fc-inference-step-body">'
            f'<p>{html.escape(copy)}</p>'
            '<div class="fc-inference-step-visual">'
            f'<div class="fc-inference-svg-scroll">{_inference_step_visual_html(step_id, predictor, prediction)}</div>'
            + visual_note
            + '</div>'
            f'<div class="fc-inference-meta"><span><strong>資料形狀</strong>　{html.escape(shape)}</span></div>'
            f'<div class="fc-inference-source">{html.escape(source)}</div>'
            f'<div class="fc-inference-code"><code>{html.escape(snippet)}</code></div>'
            '</div></details>'
        )

    return (
        '<details class="fc-inference-guide">'
        '<summary>模型原理解說｜資料如何變成分類結果</summary>'
        '<div class="fc-inference-guide-content">'
        '<div class="fc-inference-guide-intro">展開後可查看流程總覽、各階段圖示、資料形狀與程式位置。</div>'
        + _inference_flow_visual_html(predictor)
        + ''.join(detail_markup)
        + '</div></details>'
    )


def _score_table_html(rows: list[dict[str, str | float]]) -> str:
    table_rows = []
    for row in rows:
        table_rows.append(
            '<tr>'
            f'<td>{html.escape(str(row["服務類別"]))}</td>'
            f'<td class="fc-logit-code">{html.escape(str(row["類別代碼"]))}</td>'
            f'<td class="fc-logit-number">{float(row["分數"]):.4f}</td>'
            f'<td class="fc-logit-number">{float(row["Logit"]):.4f}</td>'
            '</tr>'
        )
    return (
        '<div class="fc-logit-table-wrap"><table class="fc-logit-table">'
        '<thead><tr><th>服務類別</th><th>類別代碼</th><th>分數</th><th>Logit</th></tr></thead>'
        '<tbody>' + ''.join(table_rows) + '</tbody></table></div>'
    )


def _network_status_html(
    predictor: FlyCallPredictor,
    states: dict[str, str],
    durations_ms: dict[str, float] | None = None,
    total_duration_ms: float | None = None,
) -> str:
    durations_ms = durations_ms or {}
    is_fly_ab = predictor.backend == "fly_a_to_fly_b"
    if is_fly_ab:
        lane_class = "fc-live-lane-fly-ab"
        route_nodes = (
            _live_stage_card(
                "E5 語意編碼", "文字 → 384 維向量", states.get("embedding", "pending"),
                kind="e5", elapsed_ms=durations_ms.get("embedding"),
            ),
            _live_stage_card(
                "Fly A", "384 → 32 維表示", states.get("fly_a", "pending"),
                kind="fly-a", elapsed_ms=durations_ms.get("fly_a"),
            ),
            _live_stage_card(
                "Fly B", "32 → 5 類 logits", states.get("fly_b", "pending"),
                kind="fly-b", elapsed_ms=durations_ms.get("fly_b"),
            ),
            _live_stage_card(
                "五類輸出", "Softmax 機率", states.get("output", "pending"),
                kind="output", elapsed_ms=durations_ms.get("output"),
            ),
        )
        model_name = "Fly A + Fly B"
        architecture_state_a = states.get("fly_a", "pending")
        architecture_state_b = states.get("fly_b", "pending")
        architecture_note = "目前 checkpoint 實際執行 Fly A → Fly B；下方節點會隨推論階段亮起。"
        fly_detail_title = "本次模型的 Fly A → Fly B 圖神經網路"
    else:
        candidate = getattr(predictor, "candidate_name", "mlp")
        lane_class = "fc-live-lane-mlp" if candidate == "mlp" else ""
        candidate_labels = {
            "mlp": "MLP",
            "pca_mlp": "PCA + MLP",
            "logistic_regression": "Logistic Regression",
            "lda_logistic_regression": "LDA + Logistic Regression",
        }
        candidate_details = {
            "mlp": "384 → 16 → 5 logits",
            "pca_mlp": "384 維 → PCA → 5 logits",
            "logistic_regression": "384 → 5 logits",
            "lda_logistic_regression": "384 維 → LDA → 5 logits",
        }
        model_name = candidate_labels.get(candidate, str(candidate))
        diagram = (
            _mlp_svg(states.get("classifier", "pending"))
            + '<div class="fc-diagram-note">小球表示訊號流向；節點數量為示意，實際層寬為 384 → 16 → 5。</div>'
            if candidate == "mlp"
            else ""
        )
        route_nodes = (
            _live_stage_card(
                "E5 語意編碼", "文字 → 384 維向量", states.get("embedding", "pending"),
                kind="e5", elapsed_ms=durations_ms.get("embedding"),
            ),
            _live_stage_card(
                model_name,
                candidate_details.get(candidate, "鎖定分類器"),
                states.get("classifier", "pending"),
                visual=diagram,
                kind="mlp" if candidate == "mlp" else "default",
                elapsed_ms=durations_ms.get("classifier"),
            ),
            _live_stage_card(
                "五類輸出", "Softmax 機率", states.get("output", "pending"),
                kind="output", elapsed_ms=durations_ms.get("output"),
            ),
        )
        architecture_state_a = architecture_state_b = "inactive"
        architecture_note = (
            f"目前鎖定模型為 {html.escape(model_name)}；Fly A／Fly B 是另一個研究候選，"
            "本次分類不會呼叫它們。"
        )
        fly_detail_title = "研究候選架構：Fly A → Fly B（本次不執行）"

    if is_fly_ab:
        active_role = (
            '<div class="fc-model-role-card fc-role-current">'
            '<div class="fc-model-role-label">本次實際執行</div>'
            '<div class="fc-model-role-name">Fly A → Fly B</div>'
            '<div class="fc-model-role-copy">目前鎖定的 checkpoint 會依序執行兩個網路。</div></div>'
        )
        research_role = (
            '<div class="fc-model-role-card fc-role-research">'
            '<div class="fc-model-role-label">另一個分類候選 · 本次未呼叫</div>'
            '<div class="fc-model-role-name">E5 + MLP 對照模型</div>'
            '<div class="fc-model-role-copy">Fly A/B 被選為目前模型時，MLP 不會同時參與預測。</div></div>'
        )
    else:
        active_role = (
            '<div class="fc-model-role-card fc-role-current">'
            '<div class="fc-model-role-label">本次實際執行</div>'
            f'<div class="fc-model-role-name">{html.escape(model_name)}</div>'
            '<div class="fc-model-role-copy">本次分類使用鎖定的 E5 分類模型；狀態圖顯示實際執行步驟。</div></div>'
        )
        research_role = (
            '<div class="fc-model-role-card fc-role-research">'
            '<div class="fc-model-role-label">研究候選 · 本次未呼叫</div>'
            '<div class="fc-model-role-name">Fly A → Fly B · MaleCNS 圖</div>'
            f'<div class="fc-model-role-copy">此候選使用 MaleCNS 連結資料建構研究子圖，不影響目前 {html.escape(model_name)} 的輸出。</div></div>'
        )

    if any(state == "error" for state in states.values()):
        live_state = "error"
        live_label = "分類失敗"
    elif any(state == "running" for state in states.values()):
        live_state = "running"
        live_label = "正在分類"
    elif states.get("output") == "complete":
        live_state = "complete"
        live_label = "分類完成"
    else:
        live_state = "pending"
        live_label = "等待輸入逐字稿"

    fly_a = _graph_module(
        "Fly A · 文字表示網路",
        "E5 向量輸入",
        "384 維",
        "線性投影 + tanh",
        "384 → 32 個輸入節點",
        "Fly A 表示",
        "32 維正規化向量",
        architecture_state_a,
        "fly-a-arrow",
        "fly-a",
    )
    fly_b = _graph_module(
        "Fly B · 案件分類網路",
        "Fly A 表示",
        "32 維",
        "輸入適配器",
        "32 → 32 個輸入節點",
        "線性讀出層",
        "32 → 5 類 logits",
        architecture_state_b,
        "fly-b-arrow",
        "fly-b",
    )
    output_chips = "".join(
        f'<span class="fc-class-chip">{html.escape(label)}</span>'
        for label in (
            "人行道維護", "道路凹陷與路面不平", "公園綠地與設施維護", "垃圾車清運服務", "路面清潔"
        )
    )
    return (
        '<div class="fc-network-panel">'
        '<div class="fc-network-header"><div>'
        '<div class="fc-network-title">神經網路架構與分類狀態</div>'
        f'<div class="fc-network-caption">目前模型：{html.escape(model_name)}。狀態會隨實際推論步驟更新。'
        + (
            f' 本次分類流程：{_elapsed_label(total_duration_ms)}（含介面狀態更新）。'
            if total_duration_ms is not None
            else ""
        )
        + '</div>'
        + f'<div class="fc-live-badge fc-{live_state}">{live_label}</div></div></div>'
        '<div class="fc-model-role-strip">' + active_role + research_role + '</div>'
        '<div class="fc-architecture-title">本次分類的實際資料流</div>'
        f'<div class="fc-live-lane {lane_class}">'
        + '<div class="fc-live-arrow" aria-hidden="true">→</div>'.join(route_nodes)
        + '</div>'
        + f'<div class="fc-architecture-title">{fly_detail_title}</div>'
        + f'<div class="fc-architecture-note">{architecture_note}</div>'
        + fly_a
        + '<div class="fc-live-arrow" style="text-align:center" aria-hidden="true">↓</div>'
        + fly_b
        + '<div class="fc-architecture-title">MaleCNS 腦部資料來源</div>'
        + '<section class="fc-connectome-context" aria-label="MaleCNS 資料來源背景示意">'
        + '<div class="fc-connectome-context-copy">'
        + '<div class="fc-connectome-context-kicker">資料來源背景 · MALECNS V1.0</div>'
        + '<div class="fc-connectome-context-title">雄性果蠅中樞神經系統</div>'
        + '<p>右圖是 Google Research 公開的腦部與神經索區域示意，呈現中央腦、視葉及腹神經索；它用來說明連結資料的來源範圍。</p>'
        + '<p>本專案使用的是 500 個節點、2,216 條連結的工程子圖。節點依固定種子與圖遍歷規則選取，沒有對應到單一解剖腦區，因此圖中不圈選位置。</p>'
        + f'<a class="fc-connectome-context-link" href="{MALE_CNS_SOURCE_URL}" target="_blank" rel="noopener noreferrer">查看 Google Research 原始說明 ↗</a>'
        + f'<a class="fc-connectome-context-link" href="{MALE_CNS_OVERVIEW_IMAGE}" target="_blank" rel="noopener noreferrer">直接開啟原圖 ↗</a>'
        + '</div>'
        + '<figure class="fc-connectome-figure">'
        + f'<img src="{MALE_CNS_OVERVIEW_IMAGE}" alt="雄性果蠅中樞神經系統示意，顯示中央腦、視葉與腹神經索；未標示本專案子圖位置。" loading="lazy">'
        + '<figcaption>Google Research 圖示：中央腦（綠）、視葉（紫）與腹神經索（藍）。這是整體資料背景圖，不是 500 節點子圖的定位圖。</figcaption>'
        + '</figure></section>'
        + '<div class="fc-class-chips">'
        + output_chips
        + '</div>'
        + '<div class="fc-connectome-footnote">圖中節點與連線是稀疏拓樸示意；500 個圖節點、2,216 條有向連結與兩輪傳遞來自專案模型設定。</div>'
        + '</div>'
    )


def main() -> None:
    try:
        import streamlit as st
    except ImportError as error:
        raise SystemExit(
            "Install the optional demo dependency in the model environment with "
            "`uv pip install --python <venv-python> -r requirements-demo.txt`."
        ) from error

    st.set_page_config(
        page_title="FlyCall-1999 研究 Demo",
        page_icon="☎️",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    @st.cache_data(show_spinner=False)
    def load_demo_examples(dataset_path: str) -> tuple[dict, ...]:
        wanted = dict(DEMO_SAMPLE_SPECS)
        found: dict[str, dict] = {}
        with Path(dataset_path).open("r", encoding="utf-8") as dataset_file:
            for line in dataset_file:
                record = json.loads(line)
                record_id = record.get("id")
                if record_id in wanted:
                    found[record_id] = record
                    if len(found) == len(wanted):
                        break
        missing = set(wanted).difference(found)
        if missing:
            raise ValueError(f"正式資料集缺少範例：{', '.join(sorted(missing))}")
        for record_id, expected_label in DEMO_SAMPLE_SPECS:
            record = found[record_id]
            if (
                record.get("label_id") != expected_label
                or record.get("split") != "train"
                or record.get("is_synthetic") is not True
                or record.get("review_status") != "pending_manual_review"
            ):
                raise ValueError(f"範例 {record_id} 的分類或資料狀態不符合預期")
        return tuple(found[record_id] for record_id, _ in DEMO_SAMPLE_SPECS)

    st.markdown(APP_CSS, unsafe_allow_html=True)
    with st.container(key="page-switcher"):
        st.markdown('<div class="fc-page-switcher-label">頁面導覽</div>', unsafe_allow_html=True)
        switcher_columns = st.columns([1.3, 1.3, 7.4], gap="small")
        with switcher_columns[0]:
            with st.container(key="page-switcher-current"):
                st.page_link("app.py", label="通話分類", icon=":material/home:", width="stretch")
        with switcher_columns[1]:
            with st.container(key="page-switcher-item"):
                st.page_link(
                    "pages/1_專案說明.py",
                    label="專案說明",
                    icon=":material/menu_book:",
                    width="stretch",
                )
    st.markdown(
        """
        <div class="fc-hero">
          <div class="fc-kicker">FLYCALL-1999 · LOCAL RESEARCH DEMO</div>
          <h1>1999 市政服務案件分類</h1>
          <p>輸入一段通話逐字稿，查看鎖定模型的分類結果與各類分數。</p>
          <div class="fc-badges">
            <span class="fc-badge">合成資料</span>
            <span class="fc-badge">本機推論</span>
            <span class="fc-badge">人工確認必要</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.container(key="project-guide-cta"):
        st.page_link(
            "pages/1_專案說明.py",
            label="查看專案說明｜資料生成、模型架構與分類比較",
            icon=":material/menu_book:",
            width="stretch",
        )

    status_columns = st.columns(3, gap="medium")
    status_cards = (
        ("資料狀態", "合成資料", "尚待逐筆人工複核"),
        ("模型狀態", "鎖定 MLP · seed 42", "本機固定 checkpoint"),
        ("派送狀態", "僅供模擬", "不會建立或送出案件"),
    )
    for column, (label, value, detail) in zip(status_columns, status_cards, strict=True):
        with column:
            st.markdown(
                f'<div class="fc-status"><div class="fc-status-label">{label}</div>'
                f'<div class="fc-status-value">{value}</div>'
                f'<div class="fc-status-sub">{detail}</div></div>',
                unsafe_allow_html=True,
            )

    st.markdown(
        '<div class="fc-section-kicker">MODEL SETUP</div>',
        unsafe_allow_html=True,
    )

    manifest_text = os.environ.get("FLYCALL_MODEL_MANIFEST", "")
    snapshot_text = os.environ.get("E5_SNAPSHOT", "")
    if not manifest_text or not snapshot_text:
        st.error(
            "尚未設定 FLYCALL_MODEL_MANIFEST 與 E5_SNAPSHOT。"
            "請先指定通過 checksum、候選鎖定與設定鎖定的模型 manifest。"
        )
        return
    manifest_path = Path(manifest_text)
    snapshot_path = Path(snapshot_text)

    @st.cache_resource(show_spinner="正在驗證模型檔案並載入本機模型…")
    def load_predictor(manifest_name: str, model_snapshot: str, manifest_sha256: str) -> FlyCallPredictor:
        return FlyCallPredictor.from_locked_manifest(
            Path(manifest_name),
            e5_snapshot=Path(model_snapshot),
        )

    try:
        manifest_sha256 = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
        predictor = load_predictor(str(manifest_path), str(snapshot_path), manifest_sha256)
    except (PredictorError, OSError, RuntimeError, ValueError) as error:
        st.error(f"模型未載入：{error}")
        return

    try:
        demo_examples = load_demo_examples(
            str(PROJECT_ROOT / "data" / "1999_synthetic" / "formal" / "v1.0.0" / "formal_dataset_v1.0.0.jsonl")
        )
        demo_examples_error = False
    except (OSError, ValueError):
        demo_examples = ()
        demo_examples_error = True
    demo_examples_by_id = {record["id"]: record for record in demo_examples}
    default_record = demo_examples_by_id.get(DEFAULT_TRANSCRIPT_RECORD_ID)
    default_transcript = (
        default_record["transcript"] if default_record is not None else DEFAULT_TRANSCRIPT
    )
    custom_sample_option = "__custom__"

    if "transcript_input" not in st.session_state:
        st.session_state["transcript_input"] = st.session_state.pop(
            "transcript-input", default_transcript
        )
    if "transcript_sample_picker" not in st.session_state:
        current_transcript = st.session_state["transcript_input"]
        st.session_state["transcript_sample_picker"] = next(
            (
                record_id
                for record_id, record in demo_examples_by_id.items()
                if record["transcript"] == current_transcript
            ),
            custom_sample_option,
        )
    valid_sample_options = set(demo_examples_by_id) | {custom_sample_option}
    if st.session_state["transcript_sample_picker"] not in valid_sample_options:
        st.session_state["transcript_sample_picker"] = (
            DEFAULT_TRANSCRIPT_RECORD_ID
            if DEFAULT_TRANSCRIPT_RECORD_ID in demo_examples_by_id
            else custom_sample_option
        )

    def apply_selected_demo_example() -> None:
        selected_record = demo_examples_by_id.get(
            st.session_state["transcript_sample_picker"]
        )
        if selected_record is not None:
            st.session_state["transcript_input"] = selected_record["transcript"]

    def mark_transcript_as_custom() -> None:
        selected_record = demo_examples_by_id.get(
            st.session_state["transcript_sample_picker"]
        )
        if (
            selected_record is not None
            and st.session_state["transcript_input"] != selected_record["transcript"]
        ):
            st.session_state["transcript_sample_picker"] = custom_sample_option

    def restore_default_demo_example() -> None:
        st.session_state["transcript_input"] = default_transcript
        st.session_state["transcript_sample_picker"] = (
            DEFAULT_TRANSCRIPT_RECORD_ID
            if DEFAULT_TRANSCRIPT_RECORD_ID in demo_examples_by_id
            else custom_sample_option
        )

    with st.container(key="model-ready-message"):
        st.success("模型與 E5 檔案驗證完成，可在本機進行研究展示。")
    inference_explainer_display = st.empty()
    inference_explainer_display.markdown(
        _inference_explainer_html(predictor),
        unsafe_allow_html=True,
    )
    input_column, guide_column = st.columns([1.55, 0.85], gap="large")
    with input_column:
        st.markdown('<div class="fc-section-kicker">01 · TRANSCRIPT</div>', unsafe_allow_html=True)
        with st.container(key="transcript-title"):
            st.subheader("輸入通話逐字稿")
        sample_columns = st.columns([2.4, 0.9], gap="small")
        with sample_columns[0]:
            st.selectbox(
                "載入資料集範例",
                options=[*demo_examples_by_id, custom_sample_option],
                format_func=lambda option: (
                    "自訂／目前輸入"
                    if option == custom_sample_option
                    else f"{demo_examples_by_id[option]['label_name']} · {option}"
                ),
                key="transcript_sample_picker",
                on_change=apply_selected_demo_example,
                help="範例直接取自正式合成資料集的 train split。",
            )
        with sample_columns[1]:
            st.button(
                "還原預設",
                key="restore_default_transcript",
                on_click=restore_default_demo_example,
                width="stretch",
            )
        selected_sample_id = st.session_state["transcript_sample_picker"]
        selected_sample = demo_examples_by_id.get(selected_sample_id)
        if selected_sample is not None:
            st.caption(
                f"{selected_sample['id']} · Train split · 合成資料、待人工複核。"
                "可直接分類，也可編輯內容；分類器只處理輸入框中的文字。"
            )
        elif demo_examples_error:
            st.caption(
                f"目前是預設合成範例（{DEFAULT_TRANSCRIPT_RECORD_ID}）；"
                "範例清單無法載入，但仍可編輯或手動輸入逐字稿。"
            )
        else:
            st.caption("目前為自訂內容；選擇範例可載入資料集逐字稿。")
        transcript = st.text_area(
            "通話逐字稿",
            height=250,
            placeholder="例如：貼上單筆 1999 通話逐字稿…",
            label_visibility="collapsed",
            key="transcript_input",
            on_change=mark_transcript_as_custom,
        )
        classify_clicked = st.button(
            "分析案件類別",
            type="primary",
            width="stretch",
        )

    with guide_column:
        st.markdown(
            """
            <div class="fc-side-card">
              <h3>使用方式</h3>
              <p><b>1.</b> 貼上單筆通話逐字稿</p>
              <p><b>2.</b> 執行分類並查看分數</p>
              <p><b>3.</b> 由人工判斷案件類別</p>
            </div>
            <div class="fc-side-card">
              <h3>模型可判斷的服務類別</h3>
              <div class="fc-category">人行道維護</div>
              <div class="fc-category">道路凹陷與路面不平</div>
              <div class="fc-category">公園綠地與設施維護</div>
              <div class="fc-category">垃圾車清運服務</div>
              <div class="fc-category">路面清潔</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    stage_states: dict[str, str] = {}
    stage_started: dict[str, float] = {}
    stage_durations_ms: dict[str, float] = {}
    result_display = st.container()
    with st.container():
        network_display = st.empty()
    network_display.markdown(
        _network_status_html(predictor, stage_states, stage_durations_ms),
        unsafe_allow_html=True,
    )

    if classify_clicked:
        if not transcript.strip():
            with result_display:
                st.warning("請先貼上一筆通話逐字稿，再執行分類。")
            return
        inference_started = perf_counter()
        try:
            def update_network_stage(stage: str, state: str) -> None:
                now = perf_counter()
                if state == "running":
                    stage_started[stage] = now
                elif stage in stage_started:
                    stage_durations_ms[stage] = (now - stage_started.pop(stage)) * 1000
                stage_states[stage] = state
                network_display.markdown(
                    _network_status_html(predictor, stage_states, stage_durations_ms),
                    unsafe_allow_html=True,
                )

            prediction = predictor.predict(
                transcript,
                progress_callback=update_network_stage,
            )
            total_duration_ms = (perf_counter() - inference_started) * 1000
            network_display.markdown(
                _network_status_html(
                    predictor,
                    stage_states,
                    stage_durations_ms,
                    total_duration_ms,
                ),
                unsafe_allow_html=True,
            )
            inference_explainer_display.markdown(
                _inference_explainer_html(predictor, prediction),
                unsafe_allow_html=True,
            )
        except (PredictorError, RuntimeError, ValueError) as error:
            now = perf_counter()
            stage_states["error"] = "error"
            for stage, state in tuple(stage_states.items()):
                if state == "running":
                    started_at = stage_started.pop(stage, None)
                    if started_at is not None:
                        stage_durations_ms[stage] = (now - started_at) * 1000
                    stage_states[stage] = "error"
            network_display.markdown(
                _network_status_html(
                    predictor,
                    stage_states,
                    stage_durations_ms,
                    (now - inference_started) * 1000,
                ),
                unsafe_allow_html=True,
            )
            with result_display:
                st.error(f"無法分類：{error}")
            return

        with result_display:
            st.markdown('<div class="fc-section-kicker">02 · RESULT</div>', unsafe_allow_html=True)
            with st.container(key="classification-result-title"):
                st.subheader("分類結果")
            result_column, flow_column = st.columns([1.25, 0.75], gap="large")
            with result_column:
                st.markdown(
                    f'<div class="fc-result"><div class="fc-result-label">模型最高分服務類別</div>'
                    f'<div class="fc-result-name">{html.escape(_label_name(prediction.predicted_label))}</div>'
                    f'<div class="fc-result-code">{html.escape(prediction.predicted_label)}</div></div>',
                    unsafe_allow_html=True,
                )
                # Keep the fixed taxonomy ID visible for reproducibility and existing AppTest checks.
                with st.container(key="predicted-class-code"):
                    st.metric("預測類別代碼", prediction.predicted_label)

            with flow_column:
                stages = " <span style='color:#167c80;font-weight:800'>→</span> ".join(
                    html.escape(stage) for stage in prediction.stages
                )
                st.markdown(
                    f'<div class="fc-side-card"><h3>推論流程</h3><p>{stages}</p>'
                    f'<p>模型候選：{html.escape(getattr(prediction, "candidate_name", "locked-model"))}</p></div>',
                    unsafe_allow_html=True,
                )

            st.markdown('<h4 class="fc-score-section-title">五類分數</h4>', unsafe_allow_html=True)
            probability_rows = list(
                zip(prediction.label_order, prediction.probabilities, strict=True)
            )
            ranked_probability_rows = sorted(
                probability_rows,
                key=lambda item: item[1],
                reverse=True,
            )
            top_two_gap = (
                float(ranked_probability_rows[0][1] - ranked_probability_rows[1][1])
                if len(ranked_probability_rows) > 1
                else 0.0
            )
            st.caption(
                f"最高分與次高分差距：{top_two_gap:.1%}。"
                "Softmax 分數是五類間的相對輸出，不代表準確率或經校準的可信度；結果仍需人工複核。"
            )
            for rank, (label, probability) in enumerate(ranked_probability_rows, start=1):
                value = min(max(float(probability), 0.0), 1.0)
                st.markdown(
                    f'<div class="fc-score-head"><span class="fc-score-name">{rank:02d}　'
                    f'{html.escape(_label_name(label))}</span><span class="fc-score-value">{value:.1%}</span></div>',
                    unsafe_allow_html=True,
                )
                st.progress(value)

            score_table = [
                {
                    "服務類別": _label_name(label),
                    "類別代碼": label,
                    "分數": probability,
                    "Logit": logit,
                }
                for label, probability, logit in zip(
                    prediction.label_order,
                    prediction.probabilities,
                    prediction.logits,
                    strict=True,
                )
            ]
            with st.expander("查看固定類別順序的精確分數與 logits"):
                st.markdown(_score_table_html(score_table), unsafe_allow_html=True)

            st.info(
                f"模擬派送類別：{_label_name(prediction.predicted_label)}。"
                "請由人工確認後再決定後續處理；未執行真實派工。"
            )

            selected_sample_id = st.session_state.get("transcript_sample_picker")
            source_record = demo_examples_by_id.get(selected_sample_id)
            candidate_name = getattr(prediction, "candidate_name", "locked-model")
            export_scores = [
                {
                    "label_id": label,
                    "label_name": _label_name(label),
                    "softmax_score": float(probability),
                    "logit": float(logit),
                }
                for label, probability, logit in zip(
                    prediction.label_order,
                    prediction.probabilities,
                    prediction.logits,
                    strict=True,
                )
            ]
            export_payload = {
                "predicted_label_id": prediction.predicted_label,
                "predicted_label_name": _label_name(prediction.predicted_label),
                "candidate_name": candidate_name,
                "source_record": (
                    {
                        "id": source_record["id"],
                        "split": source_record["split"],
                        "is_synthetic": source_record["is_synthetic"],
                        "review_status": source_record["review_status"],
                    }
                    if source_record is not None
                    else None
                ),
                "transcript": transcript,
                "scores": export_scores,
            }
            score_csv = io.StringIO(newline="")
            csv_fields = (
                "predicted_label_id",
                "candidate_name",
                "source_record_id",
                "label_id",
                "label_name",
                "softmax_score",
                "logit",
            )
            csv_writer = csv.DictWriter(score_csv, fieldnames=csv_fields)
            csv_writer.writeheader()
            for score in export_scores:
                csv_writer.writerow(
                    {
                        "predicted_label_id": prediction.predicted_label,
                        "candidate_name": candidate_name,
                        "source_record_id": source_record["id"] if source_record else "",
                        **score,
                    }
                )

            st.markdown('<div class="fc-section-kicker">SAVE RESULT</div>', unsafe_allow_html=True)
            download_columns = st.columns([1, 1, 4], gap="small")
            with download_columns[0]:
                st.download_button(
                    "下載 JSON（含逐字稿）",
                    data=json.dumps(export_payload, ensure_ascii=False, indent=2).encode("utf-8"),
                    file_name="flycall_prediction.json",
                    mime="application/json",
                    key="download_result_json",
                    on_click="ignore",
                    width="stretch",
                )
            with download_columns[1]:
                st.download_button(
                    "下載分數 CSV",
                    data=score_csv.getvalue().encode("utf-8-sig"),
                    file_name="flycall_prediction_scores.csv",
                    mime="text/csv",
                    key="download_result_csv",
                    on_click="ignore",
                    width="stretch",
                )

    st.markdown(
        '<div class="fc-footer">FlyCall-1999 · 本機研究展示 · 所有分類結果均需人工確認</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()

# FlyCall-1999 專案

本專案整理臺灣 1999 客服與民眾的合成通話資料，用於市政服務案件分類研究。正式資料使用 `R=客服`、`L=來電民眾`；Pilot 僅供試產與複核，與正式資料分開。

專案也包含 MaleCNS v1.0 connectome 的來源稽核、匯入、子圖可行性檢查，以及 Fly A/B 圖分類模型核心與訓練流程。各階段範圍與限制記錄在 `1999-connectome-demo-spec-v0.2.md` 及 `.scratch/1999-connectome-demo/issues/`。

## 目前正式資料

- 正式資料 v1.0.0：1,000 筆、五類各 200 筆。主要檔案為 [JSONL](data/1999_synthetic/formal/v1.0.0/formal_dataset_v1.0.0.jsonl) 與 [CSV](data/1999_synthetic/formal/v1.0.0/formal_dataset_v1.0.0.csv)。Pilot 50 筆不計入此資料集。
- 正式分類設定：[taxonomy v1.3](data/1999_synthetic/taxonomy/current/taxonomy_v1.3.yaml)、[family merge map v1.0](data/1999_synthetic/taxonomy/current/family_merge_map_v1.0.yaml)、[frozen split manifest v1.0](data/1999_synthetic/taxonomy/current/formal_split_manifest_frozen_v1.0.yaml)。
- 自動驗證結果：[正式資料驗證報告](data/1999_synthetic/formal/v1.0.0/validation_report_v1.0.md)為 PASS；正式逐字稿仍待人工複核，程式檢查不代表人工簽核。
- Pilot 最新檔：[pilot v1.2.3](data/1999_synthetic/pilot/v1.2.3/pilot_v1.2.3.jsonl)，50 筆，保持 `pending_manual_review`，不屬於正式資料。

## 文字嵌入目標設定

專案已在 2026-10-26 於 Windows x64 CPU 通過 M2.2b E5 資源閘門，完成固定 revision 模型驗證、850 筆 train/validation embeddings 與 provisional baselines；M2.3 LDA baseline 也已完成。M2.4 的 durable one-use test gate 回歸測試已通過，但正式 test 評估仍須等待人工複核與候選設定核准。詳見 [M2.2b Windows 執行報告](.scratch/1999-connectome-demo/research/m2-2b-e5-windows-gate-and-provisional-run-20261026.md) 與 [M2 工作票](.scratch/1999-connectome-demo/issues/)。

## Connectome 訓練進度

M3.0 契約、M3.1 圖核心 fixture、M3.2 Fly A 訓練及 M3.3 凍結 Fly A 後訓練 Fly B 的 train/validation-only 流程均已完成。M1.2/M1.3 的固定 pin 與 Git LF 內容相符；Windows checkout 的 CRLF 轉換曾造成工作目錄位元組雜湊不符，現在只對文字 manifest 做 CRLF→LF 正規化後比對原 pin，Parquet 仍按原始位元組 checksum 驗證。M3.2/M3.3 在目前隔離環境已完成 seed 42、1337、2026 三筆 provisional run：每筆 500 nodes／2,216 edges、700 train／150 validation，checkpoint reload 通過，test 為 `not_run` 且 0 model inputs。先前 PyArrow Application Control denial 未在這三次 run 重現；未採用 policy workaround。結果仍為合成資料、待人工複核。詳見 [M3.2／M3.3 工作票](.scratch/1999-connectome-demo/issues/12-m3-2-fly-ab-provisional-training.md) 和 [Windows Parquet runtime gate 歷史與後續報告](.scratch/1999-connectome-demo/research/m3-2-pyarrow-application-control-block-20261026.md)。

## M3.4 驗證集比較

M3.4 已使用 M2.2b 與 M3.2／M3.3 的 seed 42、1337、2026 run 完成五個候選的 validation-only 比較；比較器核對來源／輸出雜湊、資料切分、標籤順序與 test `not_run`，並報告各 seed 分數、Macro-F1 與 accuracy 平均及樣本標準差。暫定 validation 候選為 MLP（平均 Macro-F1 0.9022，樣本標準差 0.0274；accuracy 0.9067，樣本標準差 0.0231），仍待人工審查，不是正式選模或效能結論。比較輸出在 [M3.4 三 seed 報告](.scratch/1999-connectome-demo/runs/m3-4-validation-comparison-seeds-42-1337-2026-20261026/report.md)；test 保持 `not_run`，`formal_test_eligible=false`。

開發／展示用 MLP seed-42 模型已依照使用者指定鎖定；正式人工審查與核准尚未完成，test gate 仍關閉。詳見 [M3.4 工作票](.scratch/1999-connectome-demo/issues/13-m3-4-validation-comparison.md) 與 [M3.2 工作票](.scratch/1999-connectome-demo/issues/12-m3-2-fly-ab-provisional-training.md)。

依 Spec v0.2 §7.3，正式報告需每類至少人工複核 20 筆並涵蓋 train／validation／test，另須處理所有「需人工特別確認」與 AI `revise` 記錄；AI 建議不能代替人工決定。候選、checkpoint seed 與設定已鎖定；接下來須先完成 [正式資料複核活頁簿](outputs/flycall-1999-formal-review-pack-v1.0/FlyCall_1999_正式資料人工複核資料包_v1.0.xlsx) 中的人工複核並記錄決定，再執行一次性 test 評估。人工決定另行記錄，不修改資料列的 `review_status`。

## M3.5 Fly A/B representation diagnosis

A frozen three-seed probe measured raw E5 MLP validation Macro-F1 at 0.9022 versus 0.7758 for Fly A 32-D output. The best of four separately trained gated E5 residual settings reached 0.9048 Macro-F1 and 0.9089 accuracy across three seeds. This candidate was selected on the same validation set, remains exploratory, does not replace the M3.4 provisional MLP winner, and did not use test data. See the [diagnosis report](.scratch/1999-connectome-demo/runs/fly-ab-diagnosis-20261026/report.md).

## M4 本機推論與展示

M2.2b runner 現在會保存並驗證四個 E5 baseline checkpoints，prediction CSV 含固定類別順序 logits；M3.2 成功 run 會保存 graph definition。共同推論 API 與 CLI 會核對模型 lock、run manifest、candidate registration 和 checkpoint hashes，僅接受 manifest 鎖定設定的本機模型。Streamlit UI 共用同一 API，顯示五類分數及「待人工確認／模擬派送」，不連接真實派工。

M4 技術開發已完成：依照使用者指定，保留 M3.4 預註冊 MLP 為開發／展示模型，鎖定 seed 42（hidden size 16、80 epochs、learning rate 0.02）；gated E5 residual 留作研究候選。相同訓練預算的 validation-only 比較中，MLP 平均 Macro-F1 為 0.9104（SD 0.0302）、accuracy 0.9133；residual 為 0.9048（SD 0.0084）、0.9089。已建立 [開發用鎖定 manifest](.scratch/1999-connectome-demo/runs/m2-2b-e5-seed-42-current-runner-20261026/locked_model_manifest.json)，並使用實際 checkpoint 與固定 E5 snapshot 驗證 CLI、API 和 Streamlit AppTest：預測標籤、五類 logits 與分數完全一致，最大差異 0.0。資料仍是合成資料，人工複核與正式核准待完成；test split 未讀取，正式一次性評估保持 `not_run`。完整比較和驗收數據見 [M4 驗收紀錄](.scratch/1999-connectome-demo/runs/m4-matched-budget-validation-20261026/m4_live_acceptance_report.md)。其他虛擬環境可執行以下安裝命令，再設定實際檔案路徑：

```powershell
$env:FLYCALL_PYTHON = 'path\to\model-venv\Scripts\python.exe'
uv pip install --python $env:FLYCALL_PYTHON -r requirements-demo.txt
$env:FLYCALL_SCRIPTS = (Split-Path $env:FLYCALL_PYTHON)
$env:FLYCALL_MODEL_MANIFEST = (Resolve-Path 'path\to\locked_model_manifest.json').Path
$env:E5_SNAPSHOT = (Resolve-Path 'path\to\pinned-e5-snapshot').Path
& "$env:FLYCALL_SCRIPTS\streamlit.exe" run app.py
```

CLI 可使用相同兩個檔案路徑：

```powershell
python scripts\predict_flycall.py --model-manifest $env:FLYCALL_MODEL_MANIFEST --e5-snapshot $env:E5_SNAPSHOT --text '在此放入一筆逐字稿'
```

詳見 [M4.1 工作票](.scratch/1999-connectome-demo/issues/14-m4-1-locked-predictor.md) 與 [M4.2 工作票](.scratch/1999-connectome-demo/issues/15-m4-2-streamlit-research-demo.md)。

## 執行完整測試

完整 `unittest` 套件也會載入 M1.1 匯入器與 M1.2 子圖工具，需在同一 Python 環境安裝 `requirements-connectome.txt` 中的 DuckDB 1.5.6 與 PyArrow 26.0.0。Windows PowerShell 範例：

```powershell
$env:FLYCALL_PYTHON = 'path\to\model-venv\Scripts\python.exe'
$connectomeCache = Join-Path $env:TEMP 'flycall-connectome-uv-cache'
uv pip install --cache-dir $connectomeCache --python $env:FLYCALL_PYTHON -r requirements-connectome.txt
$env:PYTHONPATH = "$PWD\src;$PWD\tests;$PWD\scripts"
& $env:FLYCALL_PYTHON -m unittest discover -s tests
```

在 E5 隔離環境安裝 DuckDB 1.5.6 與 Streamlit 1.66.0 後，完整測試套件 141 項全數通過，包含 Streamlit 的錯誤與合成 fixture 成功畫面測試。M1.3/M1.2 的 peak-RSS 工具使用 Windows 可用的 process memory API；M1.2 也會先拒絕不允許的輸出路徑，再檢查來源檔案是否存在。

## 檔案索引

資料版本、草案、封存檔、正式生成歷程、複核包、逐檔用途、搬移路徑與 SHA-256，請見[合成資料詳細索引](data/1999_synthetic/README.md)。舊路徑相容連結供歷史文件解析；新文件請使用索引中的新路徑。

## Connectome 開發資料

Git repository 保留來源 manifest、匯入程式、測試用小型子圖與驗證記錄；MaleCNS 原始 Feather（約 1.05 GB）及完整匯入 Parquet（約 654 MB）不納入 Git，避免超過 GitHub 的單檔大小限制。另一台電腦 clone 後，可依以下步驟取得固定版本並重建匯入資料：

```sh
mkdir -p data/connectome/malecns_v1.0
curl --fail --location --show-error \
  'https://storage.googleapis.com/flyem-male-cns/v1.0/connectome-data/flat-connectome/connectome-weights-male-cns-v1.0-minconf-0.5.feather?generation=1780494887545976' \
  --output data/connectome/malecns_v1.0/connectome-weights-male-cns-v1.0-minconf-0.5.feather
shasum -a 256 data/connectome/malecns_v1.0/connectome-weights-male-cns-v1.0-minconf-0.5.feather
python3 -m pip install -r requirements-connectome.txt
python3 scripts/import_malecns_v1.py
python3 scripts/verify_malecns_import.py
```

下載檔的預期 SHA-256 為 `e35da783d1c686b2b58b3b87cd6a403ae43bfcfba8bff28e08ef752c1a56afc1`。完整來源、授權 attribution、版本 generation 與匯入契約見 [`source_manifest.yaml`](data/connectome/malecns_v1.0/source_manifest.yaml)；匯入輸出的兩個大型 Parquet 也由 `.gitignore` 排除，可在各電腦本機重建。

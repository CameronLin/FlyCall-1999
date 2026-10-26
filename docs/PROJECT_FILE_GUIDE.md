# FlyCall-1999 專案資料夾與檔案導覽

盤點日期：2026-10-26。這份文件說明專案目前的資料夾用途、重要檔案，以及哪些檔案是正式來源、歷史紀錄或可再生產物。它是導覽，不會取代 `README.md`、v0.2 規格或 `data/1999_synthetic/README.md` 中的詳細資料版本清單。

## 盤點範圍

- Git 索引中原有 499 個檔案；這次移除兩份活頁簿檢視工具輸出，新增本導覽文件。請用 `git status --short` 查看尚未提交的整理變更。
- `.git/` 是 Git 版本歷史，不逐一列出內部物件。
- 本機 `.scratch/1999-connectome-demo/caches/` 有 850 個 E5 embedding 快取檔，約 6.55 MiB；這些 hash 檔可由程式重建，但保留可避免重算。它們已由 `.gitignore` 排除。
- 各處 `__pycache__/` 共 51 個 Python `.pyc` 檔，約 1 MiB；是執行 Python 自動產生的快取，不是原始碼，刪除後會再生。
- `.scratch` 中的 checkpoints、圖表資料、run report 和 manifest 是實驗追蹤／重現材料；它們不是暫存快取，不能只因為在 `.scratch` 就一併刪除。

## 專案根目錄：未放在子資料夾的檔案

根目錄的散置檔案共 8 個；`requirements-connectome.txt`、兩份 spec 等也都在這份清單內：

| 檔案 | 用途 |
|---|---|
| `README.md` | 專案摘要、目前資料與模型狀態、執行方式、Connectome 來源及完整測試方式。快速了解現況先看這份。 |
| `1999-connectome-demo-spec-v0.2.md` | 目前規格：問題定義、資料契約、防止 test 洩漏、模型流程、驗收與工作項目。 |
| `1999-connectome-demo-spec-v0.1.md` | 舊版規格，保留設計演進紀錄；目前以 v0.2 為準。 |
| `AGENTS.md` | 專案工作規則入口，指向 `.scratch` issue tracker 與 domain 文件。 |
| `app.py` | Streamlit 本機研究展示的應用程式入口。 |
| `requirements-demo.txt` | 本機模型推論／demo 的 Python 套件需求。 |
| `requirements-connectome.txt` | Connectome 匯入與圖資料處理所需套件。 |
| `.gitignore` | 排除 Python bytecode、E5 cache、檢視工具輸出等非來源產物。 |

## `docs/`

- `docs/agents/domain.md`：修改領域程式前如何讀取 context 與 ADR 的規則。目前根目錄沒有 `CONTEXT.md` 或 `docs/adr/`。
- `docs/agents/issue-tracker.md`：`.scratch/<feature>/issues/` 的 issue 命名、狀態與留言規則。
- `docs/research/1999-case-classification-proposal-revised.md`：以 Connectome 限制探索低維表示來分類 1999 案件的研究提案。
- `docs/research/m0-1-malecns-v1.0-source-research.md`：MaleCNS v1.0 來源、授權及下載／來源選擇研究。
- `docs/research/m3-0-connectome-classifier-contract.md`：Fly A/Fly B 資料界線、訓練與驗證合約及目前狀態。
- `docs/research/m3-1-small-fixture-model-core-report.md`：M3.1 小型 fixture 模型核心的實作驗收紀錄。
- `docs/PROJECT_FILE_GUIDE.md`：本專案資料夾與檔案導覽。

## `data/`

### `data/1999_synthetic/`

此處保存合成通話資料、分類 taxonomy、切分設定、生成紀錄與歷史版本。**逐檔資料清單、舊路徑 symlink 對照及版本歷史見 [`data/1999_synthetic/README.md`](../data/1999_synthetic/README.md)。**該索引比重複抄列 184 個資料檔更適合作為資料版本清單。

| 資料夾／檔案 | 內容與使用方式 |
|---|---|
| `README.md` | 合成資料版本、正式資料入口、歷史路徑相容 symlink、各複核工作簿用途及 SHA／搬移記錄的詳細索引。 |
| `formal/v1.0.0/` | 正式資料 v1.0.0。`formal_dataset_v1.0.0.jsonl` 與 `.csv` 是正式資料入口；README 記錄為 1,000 筆、五類各 200 筆。這些資料仍需人工複核。 |
| `formal/v1.0.0/filtered_batches/` | 20 個 `batch_001.jsonl` 至 `batch_020.jsonl`，按批保存通過篩選的生成資料。 |
| `formal/v1.0.0/filtered/` | 合併後的 filtered JSONL。 |
| `formal/v1.0.0/raw_generated/` | 20 批生成過程的原始嘗試，以及 `formal_raw_all_attempts_v1.0.0.jsonl` 完整合併記錄；供生成來源追溯，不作為正式模型輸入。 |
| `formal/v1.0.0/superseded/` | 被後續版本取代的生成批次；`first_generator_pass/` 保存早期全套產物，`SUPERSEDED.md` 說明其狀態。屬歷史來源，不能誤認為目前正式資料。 |
| `formal/v1.0.0/scripts/` | `generate_formal_dataset.py` 生成資料、`validate_formal_dataset.py` 驗證資料、`finalize_assets.rb` 整理最終資產。 |
| `formal/v1.0.0/batch_log.jsonl`、`batch_manifest.csv`、`generation_manifest.csv`、`checkpoint.json` | 生成批次、產物對照、進度與中斷續跑狀態。 |
| `formal/v1.0.0/preflight_and_freeze_record_v1.0.md`、`validation_report_v1.0.md` | 凍結前檢查記錄與自動驗證結果；自動 PASS 不代表逐筆人工核准。 |
| `pilot/` 與根目錄 `pilot_v1.2.x.jsonl` | v1.2.1、v1.2.2、v1.2.3 的試行資料及各版本人工複核／驗證文件。Pilot 與正式資料分開；目前 pilot v1.2.3 不是正式模型資料集。根目錄舊檔名為相容 symlink。 |
| `archive/` | pre-v1.2 與 v1.2 歷史試行資料、taxonomy、人工複核與驗證紀錄；保留資料生成沿革。 |
| `planning/` | formal generation plan/todo 各版本、taxonomy 擴充草案、split manifest 草案及部分舊路徑 symlink。草案不應覆蓋 `taxonomy/current/` 的凍結設定。 |
| `taxonomy/current/` | 正式使用的 `taxonomy_v1.3.yaml`、`family_merge_map_v1.0.yaml`、`formal_split_manifest_frozen_v1.0.yaml`。分類定義與凍結資料切分以此處為準。 |
| `taxonomy/drafts/` | taxonomy、family merge map 與 split manifest 的草案版本。 |
| `review/family_review_decisions_v1.0.md`、`family_review_decisions_v1.0.md` | 情境家族合併／複核決策的工作記錄；其中助理建議不能當成使用者已完成的人工核准。根目錄另有相容路徑。 |
| `formal_generation_plan_v1.3.md`、`formal_generation_todo_v1.2.md`、`manual_review_v1.2.x.md`、`taxonomy_expansion_draft_v1.2.x.md`、`validation_report_v1.2.3.md` | 舊版規劃、複核及驗證文件；詳細對應版本和 symlink 請查資料 README。 |

舊的根目錄路徑、`planning/` 內部分路徑以及 `data/outputs` 是相容 symlink，不是重複資料副本。舊文件與程式仍可能引用它們，**不要直接刪除或改成普通副本**。`data/outputs` 指向專案根目錄的 `outputs/`。

### `data/connectome/`

| 路徑 | 用途 |
|---|---|
| `malecns_v1.0/source_manifest.yaml` | MaleCNS v1.0 的來源、版本與匯入契約。 |
| `malecns_v1.0/probe_bulk_range.py`、`probe_result_v1.0.json` | 來源資料可讀性／範圍探測程式及結果。 |
| `derived/malecns_v1.0/import_manifest.json` | 匯入產物與來源的 manifest。 |
| `derived/malecns_v1.0/subgraphs/engineering-demo-v1.0/manifest.json` | 工程 demo 子圖的來源與選取資訊。 |
| 同目錄的 `nodes.parquet`、`edges.parquet` | 小型工程 fixture 的節點與邊表。不是完整 MaleCNS 原始資料。 |

大型 MaleCNS 原始 Feather 與完整匯入 Parquet 不納入 Git；如何取得及重建見根目錄 `README.md` 與 source manifest。

## `outputs/`：人工複核與分析交付物

這裡是資料複核工作簿及其摘要，並非程式原始碼。歷史工作簿保留各輪複核差異；AI／助理建議不代表人工通過。

| 路徑／檔案 | 用途 |
|---|---|
| `flycall-1999-formal-review-pack-v1.0/FlyCall_1999_正式資料人工複核資料包_v1.0.xlsx` | 目前正式資料人工複核工作簿，包含 399 筆複核樣本及人工判定欄位。 |
| 同目錄 `review_summary_v1.0.md` | 複核抽樣、風險與自動檢查摘要。 |
| `flycall-1999-review-pack-v1/FlyCall_1999_人工複核資料包_v1.0.xlsx` | 早期 pilot／家族複核工作簿。 |
| `flycall-1999-review-pack-ai-v1/FlyCall_1999_人工複核資料包_AI初審_v1.0.xlsx` | AI 初審建議工作簿，不是人工核准。 |
| `flycall-1999-review-pack-assistant-review-v1/FlyCall_1999_獨立複核建議資料包_v1.0.xlsx` | 助理獨立複核建議工作簿。 |
| 同目錄 `validation_report_independent_review_v1.0.md` | 上述建議工作簿的版本、欄位及 ID 核對紀錄。 |
| `flycall-1999-review-pack-second-review-v1/FlyCall_1999_情境家族第二次複核建議_v1.0.xlsx` | 情境家族第二輪建議工作簿。 |
| 同目錄 `FlyCall_1999_第二次複核資料包_v1.1.xlsx` | 第二輪複核資料工作簿。 |
| `flycall-1999-review-decisions-v1/FlyCall_1999_助理獨立複核決定_v1.0.xlsx` | 助理對 pilot 與家族資料的複核決定工作簿。 |
| 同目錄 `independent_review_decisions_v1.0.md` | 上述決定的摘要、修訂界線及合併規則。 |
| `FlyCall-1999_Project_Briefing_zh-TW.html` | 本機可離線播放的專案簡報；支援鍵盤切頁、講者備註及瀏覽器列印。 |
| `FlyCall-1999_Project_Briefing_Speaker_Notes_zh-TW.md` | 簡報逐頁講稿與簡報依據，方便另外閱讀或列印。 |

原先兩份 `*.xlsx.inspect.ndjson` 是從活頁簿衍生的檢視工具輸出，不是人工複核的來源。2026-10-26 已刪除這兩份副本；來源 `.xlsx` 保留，`.gitignore` 會忽略日後同類輸出。

## `scripts/`：可直接執行的工作流程

| 檔案 | 用途 |
|---|---|
| `import_malecns_v1.py`、`verify_malecns_import.py` | 匯入與核對 MaleCNS 資料。 |
| `run_m2_2a_smoke_test.py` | 執行輕量文字 baseline smoke test。 |
| `run_m2_2b_e5_provisional.py` | 建立 E5 embedding 並執行暫定分類候選。 |
| `run_m3_2_fly_ab_provisional.py` | 執行 Fly A/B 的 train/validation 訓練流程。 |
| `diagnose_fly_a_b.py`、`tune_fly_b_e5_residual.py` | 診斷 Fly A/B 表徵及訓練 E5 residual 研究候選。 |
| `compare_m3_4_validation.py` | 比較多 seed validation 候選。 |
| `compare_m4_matched_budget.py` | 以相同訓練預算比較 M4 候選。 |
| `predict_flycall.py` | 載入鎖定 manifest 執行 CLI 預測。 |

## `src/flycall_data/`：程式庫模組

| 檔案 | 職責 |
|---|---|
| `__init__.py` | Python package 初始化。 |
| `loader.py` | 資料讀取、欄位與 split 載入。 |
| `model_config.py` | 模型候選及訓練設定。 |
| `text_baseline.py` | 輕量文字 baseline。 |
| `e5_runtime.py`、`embedding_pipeline.py` | E5 runtime、文字嵌入與快取流程。 |
| `lda_baseline.py` | LDA baseline。 |
| `evaluation.py`、`comparison.py` | 分類指標、候選比較與 validation 報告。 |
| `fly_ab_training.py`、`fly_ab_diagnostics.py` | Fly A/B 訓練和表示診斷。 |
| `m32_inputs.py` | M3.2 訓練輸入與 split 契約。 |
| `predictor.py` | 鎖定模型載入與共用推論介面。 |
| `runtime_resources.py` | 執行期資源／記憶體監測。 |
| `connectome_importer.py` | MaleCNS 圖資料匯入。 |
| `graph_core.py` | 有向圖核心操作。 |
| `streaming_bfs.py`、`subgraph_probe.py` | 串流 BFS、子圖抽樣與探測。 |
| `io_reachability.py` | 圖資料 I/O 可達性檢查。 |

## `tests/`：測試模組

以下檔案測試對應的資料或程式模組；它們不含正式模型輸出：

| 測試檔 | 測試範圍 |
|---|---|
| `test_connectome_importer.py` | Connectome 匯入。 |
| `test_dataset_loader.py` | 資料與 split 載入。 |
| `test_e5_runtime.py` | E5 執行環境。 |
| `test_embedding_logistic.py`、`test_embedding_pipeline.py`、`test_embedding_torch.py` | 嵌入後的分類器、產生流程與 PyTorch 模型。 |
| `test_evaluation.py`、`test_m34_comparison.py` | 指標和 M3.4 候選比較。 |
| `test_fly_ab_diagnostics.py`、`test_fly_ab_training.py` | Fly A/B 診斷與訓練。 |
| `test_graph_core.py`、`test_streaming_bfs.py`、`test_subgraph_probe.py` | 圖核心、BFS 與子圖探測。 |
| `test_io_reachability.py` | 圖資料 I/O 可達性。 |
| `test_lda_baseline.py`、`test_text_baseline.py` | LDA 與文字 baseline。 |
| `test_m2_checkpoint.py`、`test_m2_seed_preregistration.py` | checkpoint 與 seed 預先登記。 |
| `test_m32_inputs.py`、`test_m32_runner.py` | M3.2 輸入契約與 runner。 |
| `test_m4_prediction.py`、`test_streamlit_app.py` | M4 推論與 Streamlit UI。 |
| `test_runtime_resources.py` | 執行資源監測。 |

## `.scratch/1999-connectome-demo/`：工程工作記錄

此目錄依 `docs/agents/issue-tracker.md` 保存 issue、研究報告、探測和每次實驗的產物。可重建的快取另在 `caches/`，被 `.gitignore` 排除。

### `issues/`：16 個工作項目

| 檔案 | 主題 |
|---|---|
| `01-m2-1-data-contract-readonly-loader.md` | 資料契約與唯讀 loader。 |
| `02-m0-1-malecns-source-manifest.md` | MaleCNS 來源 manifest。 |
| `03-m1-1-directed-graph-importer.md` | 有向圖匯入器。 |
| `04-m1-2-subgraph-selection-feasibility.md` | 子圖選取可行性。 |
| `05-m1-3-io-reachability.md` | I/O 可達性。 |
| `06-m2-2a-lightweight-text-baseline.md` | 輕量文字 baseline。 |
| `07-m3-0-connectome-classifier-contract.md` | Connectome 分類器契約。 |
| `08-m3-1-small-fixture-model-core.md` | 小型 fixture 模型核心。 |
| `09-m2-2b-e5-embeddings-and-classifiers.md` | E5 embeddings 與分類器。 |
| `10-m2-4-evaluator-test-gate.md` | evaluator 與一次性 test gate。 |
| `11-m2-3-lda-classification-baseline.md` | LDA baseline。 |
| `12-m3-2-fly-ab-provisional-training.md` | Fly A/B 暫定訓練。 |
| `13-m3-4-validation-comparison.md` | 多 seed validation 比較與人工審查門檻。 |
| `14-m4-1-locked-predictor.md` | 鎖定模型 predictor。 |
| `15-m4-2-streamlit-research-demo.md` | Streamlit 研究 demo。 |
| `16-fly-ab-representation-diagnosis.md` | Fly A/B 表示診斷。 |

### `research/`：設計、預檢與研究報告

`fly-a-b-diagnostic-preregistration-20261026.md` 記錄診斷預註冊；`m1-1-import-report.md`、`m1-2-feasibility-probe.md`、`m1-3-io-reachability-report.md`、`m1-3-preflight.md` 分別記錄匯入、子圖與 I/O 階段；`m2-2a-smoke-test-report.md`、`m2-2b-e5-resource-preflight-20261016.md`、`m2-2b-e5-windows-gate-and-provisional-run-20261026.md` 記錄 baseline／E5 資源閘門；`m2-3-lda-fixture-report.md`、`m2-4-evaluator-fixture-report.md` 記錄 LDA 與 evaluator fixture；`m3-2-pyarrow-application-control-block-20261026.md` 記錄 Windows PyArrow 閘門歷程；`m4-matched-budget-comparison-plan-20261026.md` 記錄 M4 比較計畫。

### `benchmarks/`、`probes/`、匯入檢查資料夾

- `benchmarks/m1-2-rowgroup-index-bfs-seed-20261015/artifacts/` 的 `sample_edges.parquet`、`sample_nodes.parquet`、`sample_induced_directed_edges.parquet`、`weak_adjacency_sorted.parquet` 是子圖／BFS row-group benchmark 的資料產物。
- `probes/m1-2/` 下 `highest_weak_degree_in_bounded_prefix/`、`median_weak_degree_in_bounded_prefix/`、`prefix-50000-seed-10001/`、`repeat-high-degree-10003/`、`uniform_seeded_from_observed_nodes/` 保存 probe 結果。`streaming-bfs-*` 資料夾額外保存 seed、run summary、probe 結果及 candidate Parquet；第二次 run 有 replay/archive 驗證程式。
- `m1-1-resource-audit-unapproved-threads-4/malecns_v1.0/import_manifest.json` 是資源審查期間的匯入 manifest；`m1-3/engineering-demo-io-v1.0-20261016/` 保存 I/O manifest 與報告。

### `runs/`：每次執行的輸出

| 子資料夾 | 內容 |
|---|---|
| `fly-ab-diagnosis-20261026/` | Fly A/B 表示診斷、E5 residual 多設定結果與 checkpoint。 |
| `m2-2a-smoke-20261015T170818Z/` | M2.2a 初次 smoke 執行結果。 |
| `m2-2a-smoke-final-20261015T170949Z/` | M2.2a 最終 smoke 執行結果。 |
| `m2-2a-smoke-final-loader-audit-20261015T171135Z/` | 加上 loader audit 的 smoke 結果。 |
| `m2-2b-e5-provisional-20261025T184727Z/`、`m2-2b-e5-provisional-20261025T184820Z/`、`m2-2b-e5-provisional-20261025T185218Z/`、`m2-2b-e5-provisional-20261026T015843Z/` | 不同階段的 E5 暫定候選執行；保留失敗、改進與報告歷程。 |
| `m2-2b-e5-seed-42-current-runner-20261026/`、`m2-2b-e5-seed-1337-current-runner-20261026/`、`m2-2b-e5-seed-2026-current-runner-20261026/` | 三個 seed 的 E5 候選結果；seed 42 另含開發用 `locked_model_manifest.json`。 |
| `m3-2-crlf-normalization-gate-20261026/` | M3.2 manifest 換行正規化閘門檢查及 checkpoint。 |
| `m3-2-fly-ab-provisional-20261026T-gate-check/` | M3.2 訓練前 gate 記錄。 |
| `m3-2-fly-ab-seed-42-crlf-fix-20261026/`、`m3-2-fly-ab-seed-1337-20261026/`、`m3-2-fly-ab-seed-2026-20261026/` | Fly A/B 三個 seed 的暫定訓練及 validation 結果。 |
| `m3-4-validation-comparison-seeds-42-1337-2026-20261026/` | M3.4 多候選、多 seed validation-only 比較報告。 |
| `m4-matched-budget-validation-20261026/` | M4 同訓練預算比較、checkpoint 與 `m4_live_acceptance_report.md` 驗收結果。 |

各 run 內檔案依名稱判讀：`report.md` 是人讀摘要；`metrics.json` 是指標；`predictions.csv` 是該次 run 的預測輸出；`run_manifest.json`、`embedding_manifest.json`、`pre_registered_candidates.json` 記錄輸入、模型／嵌入與候選登記；`training_history.json`、`graph_definition.json`、`diagnosis.json`、`probe_results.json`、`tuning_results.json` 等保存對應流程設定或細項；`.pt`／`.joblib` 是 checkpoint；`candidate_reports/` 是各候選的子報告。相同檔名代表不同 run 的獨立輸出，不是可互換副本。

### `.scratch` 的依賴鎖檔

`requirements-m2-2a-smoke.txt` 是 smoke 階段需求；`requirements-m2-2b-e5-windows.in`／`.lock` 是 E5 Windows 需求來源與鎖定版本；`requirements-m3-2-fly-ab-windows.in`／`.lock` 是 Fly A/B Windows 需求來源與鎖定版本。

## 哪些可清、哪些要留

| 類別 | 建議 |
|---|---|
| `*.inspect.ndjson` | 已清理目前兩份活頁簿檢視輸出，並加上忽略規則；如需檢視可從原始 `.xlsx` 重建。這只移除工作目錄副本，不改寫 Git 歷史。 |
| `__pycache__/*.pyc` | 可在需要釋出空間時刪除；程式會重新產生。 |
| `.scratch/1999-connectome-demo/caches/` | 可重建但建議先保留，避免重算 embeddings。 |
| `data/1999_synthetic/archive/`、`superseded/`、舊 pilot／taxonomy／manifest | 保留版本歷史與生成來源，不因「較舊」就刪除。 |
| `.scratch/` 的 run reports、checkpoints、Parquet、manifest | 保留可追溯性與目前 M4 驗收依據；清理前需先定義封存／重建政策，並查明是否被 README、issue、manifest 或程式引用。 |
| `data/1999_synthetic` 舊路徑及 `data/outputs` symlink | 保留相容性；移除可能使舊文件或程式路徑失效。 |
| `outputs/` 人工複核工作簿 | 保留原始版本及歷史建議。當前正式複核請用 `flycall-1999-formal-review-pack-v1.0/`，不要把 AI／助理建議表當成已核准結果。 |

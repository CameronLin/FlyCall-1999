# FlyCall-1999 專案資料夾與檔案導覽

盤點日期：2026-11-16（首版 2026-10-26）。這份文件說明各資料夾的用途、重要檔案，以及哪些是正式來源、歷史紀錄或可重新產生的檔案。它只是導覽：專案說明看根目錄 `README.md`，名詞看 `CONTEXT.md`，資料版本細節看 `data/1999_synthetic/README.md`。

## 盤點範圍

- Git 追蹤 937 個檔案。用 `git status --short` 查看尚未提交的變更。
- `.git/` 是 Git 版本歷史，不逐一列出。
- 下列本機資料由 `.gitignore` 排除，不在 Git 裡：
  - `.scratch/1999-connectome-demo/caches/`：E5 embedding 快取，可由程式重建，保留可避免重算。
  - `.scratch/1999-connectome-demo/test-ledger/`：一次性 test 的使用紀錄（`PersistentTestRunLedger`）。**不要刪除**，它是「test 已評估過、不得重開」的依據。
  - MaleCNS 原始 Feather 與完整匯入 Parquet：重建方式見 `README.md`。
  - 各處 `__pycache__/`：Python 自動產生的快取，刪除後會再生。
- `.scratch` 裡的 checkpoint、run report 和 manifest 是實驗追蹤與重現材料，不是暫存檔，不能因為放在 `.scratch` 就刪除。

## 專案根目錄

| 檔案 | 用途 |
|---|---|
| `README.md` | 專案一句話說明、主要結論、從哪裡開始看、資料版本、進度與執行方式。第一次看專案先讀這份。 |
| `CONTEXT.md` | 名詞表：Fly A／B、G0–G2-glu+、T、SupCon、一次性 test 等用語在本專案的意思。 |
| `1999-connectome-demo-spec.md` | 原始規格正本：問題定義、資料契約、防止 test 洩漏、模型流程與驗收。檔名的「demo」是歷史沿用。 |
| `AGENTS.md` | 給 AI 助理的工作規則入口，指向 `docs/agents/`。 |
| `requirements-connectome.txt` | 連接圖匯入與測試所需套件（DuckDB、PyArrow）。 |
| `.gitignore` | 排除快取、大型原始資料、test ledger 等。 |

## `docs/`

| 路徑 | 用途 |
|---|---|
| `agents/domain.md` | 修改程式前如何讀取 `CONTEXT.md` 與 ADR 的規則（目前沒有 `docs/adr/`）。 |
| `agents/issue-tracker.md` | `.scratch/<feature>/issues/` 工作票的命名、狀態與留言規則。 |
| `intro/` | 專案介紹頁 `outputs/FlyCall-1999_專案介紹.html` 的原始檔（分頁、樣式、程式、由腳本產生的區塊）。修改方式見 `intro/README.md`。 |
| `briefing/deck.html` | 專案簡報的原始檔（投影片、講稿、動畫）；由 `scripts/build_briefing_html.py` 組裝成 `outputs/FlyCall-1999_專案簡報.html` 與講稿 `.md`。 |
| `PROJECT_FILE_GUIDE.md` | 本導覽。 |

原本的 `docs/research/` 已於 2026-11-16 併入 `.scratch/1999-connectome-demo/research/`。

## `data/`

### `data/1999_synthetic/`

合成通話資料、類別定義、切分設定、生成紀錄與歷史版本。**逐檔清單、舊路徑 symlink 對照及版本歷史見 [`data/1999_synthetic/README.md`](../data/1999_synthetic/README.md)。**

| 資料夾／檔案 | 內容與使用方式 |
|---|---|
| `README.md` | 資料版本、正式資料入口、相容 symlink、各複核工作簿用途及 SHA／搬移記錄的詳細索引。 |
| `formal/v2.0.0/`（目前主要使用） | 資料 v2：`formal_dataset_v2.0.0.jsonl`／`.csv` 是入口；`validation_report_v2.0.0.md` 是自動品質檢查；`KNOWN_ISSUES.md` 記錄 77 筆開場接不上、326 筆補字問答位置不自然及其驗證；`SHA256SUMS` 為檔案雜湊。未經人工複核；test 已評估一次，不得重開。 |
| `formal/v1.0.0/` | 資料 v1：`formal_dataset_v1.0.0.jsonl`／`.csv` 是入口。第一代實驗與目前鎖定的推論模型使用此版。 |
| `formal/v1.0.0/filtered_batches/`、`filtered/` | 按批及合併後通過篩選的生成資料。 |
| `formal/v1.0.0/raw_generated/` | 生成過程的原始嘗試，供來源追溯，不作為模型輸入。 |
| `formal/v1.0.0/superseded/` | 被取代的早期生成批次，`SUPERSEDED.md` 說明狀態。不能誤認為目前資料。 |
| `formal/v1.0.0/scripts/` | v1 的生成、驗證與資產整理程式。 |
| `formal/v1.0.0/batch_log.jsonl`、`batch_manifest.csv`、`generation_manifest.csv`、`checkpoint.json` | v1 生成批次、產物對照、進度與續跑狀態。 |
| `formal/v1.0.0/preflight_and_freeze_record_v1.0.md`、`validation_report_v1.0.md` | v1 凍結前檢查與自動驗證；自動 PASS 不代表人工核准。 |
| `pilot/` 與根目錄 `pilot_v1.2.x.jsonl` | 50 筆試產資料及複核文件，與正式資料分開。根目錄舊檔名為相容 symlink。 |
| `archive/` | pre-v1.2 與 v1.2 的歷史試行資料、taxonomy、複核與驗證紀錄。 |
| `planning/` | 生成計畫、taxonomy 擴充與 split manifest 草案。草案不應覆蓋 `taxonomy/current/`。 |
| `taxonomy/current/` | 正式使用的 `taxonomy_v1.3.yaml`、`family_merge_map_v1.0.yaml`、`formal_split_manifest_frozen_v1.0.yaml`，以此處為準。 |
| `taxonomy/drafts/` | 上述設定的草案版本。 |
| `review/` 與根目錄複核文件 | 情境家族合併／複核決策的工作紀錄；助理建議不等於人工核准。 |

舊的根目錄路徑、`planning/` 內部分路徑以及 `data/outputs` 是相容 symlink，不是重複副本。舊文件與程式仍可能引用它們，**不要刪除或改成普通副本**。

### `data/connectome/`

| 路徑 | 用途 |
|---|---|
| `malecns_v1.0/source_manifest.yaml` | MaleCNS v1.0 連接圖的來源、版本、授權與匯入契約。 |
| `malecns_v1.0/neurotransmitter_source_manifest.yaml` | 神經傳導物質（正負號）來源的版本與雜湊（工作票 18）。 |
| `malecns_v1.0/probe_bulk_range.py`、`probe_result_v1.0.json` | 來源資料可讀性探測程式及結果。 |
| `derived/malecns_v1.0/import_manifest.json` | 匯入產物與來源的 manifest。 |
| `derived/malecns_v1.0/neuron_signs_v1.0_summary.json` | 每個神經元正負號表的統計摘要。 |
| `derived/malecns_v1.0/subgraphs/engineering-demo-v1.0/` | G0：起點 274013289、500 點／2,216 邊的 `nodes.parquet`、`edges.parquet` 與 `manifest.json`。 |
| `derived/malecns_v1.0/subgraphs/signed-quota-v1.0/` | 有正負號子圖（起點 810979，300 興奮／200 抑制）：`manifest.json` 加上三種圖定義 `graph_definition_G1_all_positive.json`（G1）、`graph_definition_G2_glu_inhibitory.json`（G2）、`graph_definition_G2_glu_excitatory.json`（G2-glu+）。 |

子圖檔案都在 Git 裡，只跑模型不需要重建完整連接圖。

## `outputs/`：給人看的成果

| 路徑／檔案 | 用途 |
|---|---|
| `FlyCall-1999_專案介紹.html` | 完整圖文介紹（約 2.6 MB，由 `docs/intro/` 組裝，不要直接改）。 |
| `FlyCall-1999_專案簡報.html`、`FlyCall-1999_專案簡報_講稿.md` | 34 頁專案簡報（瀏覽器開啟；← → 換頁、N 講稿、F 全螢幕）與逐頁講稿，由 `docs/briefing/` 組裝，不要直接改。 |
| `FlyCall-1999_FlyA_FlyB_分析報告.html` | Fly A 與 Fly B 兩個「腦」的差異分析（資料 v2）。 |
| `FlyCall-1999_FlyA_FlyB_分析報告_資料v1.html` | 同一份分析的資料 v1 版本。 |
| `FlyCall-1999_連接圖訊號傳遞.html` | 子圖上訊號傳遞的互動示意；專案介紹頁也以內嵌方式顯示。 |
| `archive/` | 已過時、僅供回顧的成果：`FlyCall-1999_Project_Briefing_zh-TW.html` 與 `..._Speaker_Notes_zh-TW.md` 是 2026-10-27 第一代階段的專案簡報與講稿（沒有資料 v2、有正負號子圖與 test 結果；目前內容請看專案介紹頁）。 |
| `flycall-1999-formal-review-pack-v1.0/` | 資料 v1 的正式人工複核工作簿（399 筆樣本）與 `review_summary_v1.0.md`。 |
| `flycall-1999-review-pack-v1/` | 早期 pilot／情境家族複核工作簿。 |
| `flycall-1999-review-pack-ai-v1/` | AI 初審建議工作簿，不是人工核准。 |
| `flycall-1999-review-pack-assistant-review-v1/` | 助理獨立複核建議工作簿與核對紀錄。 |
| `flycall-1999-review-pack-second-review-v1/` | 情境家族第二輪複核工作簿。 |
| `flycall-1999-review-decisions-v1/` | 助理對 pilot 與家族資料的複核決定及摘要。 |

## `scripts/`：可直接執行的流程

| 檔案 | 用途 |
|---|---|
| **連接圖與子圖** | |
| `import_malecns_v1.py`、`verify_malecns_import.py` | 匯入與核對 MaleCNS 資料。 |
| `build_neurotransmitter_signs.py` | 由神經傳導物質檔產生每個神經元的正負號表（工作票 18）。 |
| `select_signed_subgraph.py` | 挑選有正負號的 300＋200 子圖並檢查輸入到輸出的可達性（工作票 21）。 |
| **資料 v2** | |
| `v2_dataset_tools.py` | 批次規劃、批次解析與自動品質檢查（工作票 25）。 |
| `v2_vary_stock_lines.py` | 改寫重複的固定句與模板用語。 |
| `v2_apply_inserts.py` | 在指定紀錄結尾前補一段問答。 |
| `v2_freeze_dataset.py` | 把批次凍結成 v2.0.0 的 JSONL＋CSV。 |
| **基準模型與第一代果蠅** | |
| `run_m2_2a_smoke_test.py` | 輕量文字 baseline smoke test。 |
| `run_m2_2b_e5_provisional.py` | 產生 E5 embedding 並訓練 LR／MLP／LDA 等基準。 |
| `run_m3_2_fly_ab_provisional.py` | 第一代 Fly A／B 的 train／validation 訓練。 |
| `compare_m3_4_validation.py`、`compare_m4_matched_budget.py` | 多 seed validation 比較；同訓練預算比較 M4 候選。 |
| `diagnose_fly_a_b.py`、`tune_fly_b_e5_residual.py` | Fly A／B 表示診斷；E5 residual 研究候選。 |
| **第二代實驗** | |
| `run_reducer_classifier_factorial.py` | 交叉實驗 {E5, LDA, Fly A} × {SVM, Fly B}（工作票 17）。 |
| `run_independent_tuning.py` | Fly A／Fly B 獨立調參與四張圖比較（工作票 20、22）。 |
| `compare_fly_a_fly_b_brains.py` | 訓練後比較 Fly A 與 Fly B 的連線與神經元活動。 |
| `run_v2_test_evaluation.py` | 資料 v2 的一次性 test 評估（已執行，不得重跑）。 |
| **報告與專案介紹頁** | |
| `build_brain_report_html.py`、`brain_report_template.html`、`make_tuning_aux.py` | 產生 Fly A／Fly B 分析報告 HTML 及其輔助檔。 |
| `build_intro_html.py` | 組裝專案介紹頁（`--check` 只檢查是否最新）。 |
| `build_intro_training_time.py`、`build_intro_brain_section.py`、`build_intro_result_charts.py`、`build_intro_bfs_data.py` | 由 run 結果產生介紹頁的訓練時間、腦部比較、結果圖表與 BFS 動畫資料。 |
| `build_briefing_html.py` | 組裝專案簡報與講稿（`--check` 只檢查是否最新）。 |
| **推論** | |
| `predict_flycall.py` | 載入鎖定 manifest，對一筆逐字稿做 CLI 預測。 |

## `src/flycall_data/`：程式庫模組

| 檔案 | 職責 |
|---|---|
| `__init__.py`、`loader.py`、`dataset_versions.py` | 唯讀載入凍結資料、欄位與 split 契約；可選的資料版本（v1／v2）。 |
| `model_config.py` | 模型候選與訓練設定。 |
| `text_baseline.py` | TF-IDF 輕量文字 baseline。 |
| `e5_runtime.py`、`embedding_pipeline.py` | 固定版本 E5 的執行環境、文字嵌入與快取。 |
| `lda_baseline.py` | LDA baseline。 |
| `evaluation.py`、`comparison.py` | 分類指標、一次性 test 機制、多 seed 比較報告。 |
| `connectome_importer.py` | MaleCNS 匯入。 |
| `streaming_bfs.py`、`subgraph_probe.py` | G0 的 hash 優先值起點選擇與串流 BFS；子圖可行性探測。 |
| `io_reachability.py` | 32 個輸入點／32 個輸出點的選擇與可達性檢查。 |
| `neurotransmitter_signs.py` | 神經傳導物質對應到正負號（工作票 18）。 |
| `signed_subgraph.py` | 有正負號子圖的配額 BFS（工作票 21）。 |
| `graph_core.py` | 圖核心（訊號沿邊傳遞 T 步、可訓練的正值邊強度、固定正負號）與 Fly A、Fly B 模型。 |
| `m32_inputs.py`、`fly_ab_training.py`、`fly_ab_diagnostics.py` | 第一代 Fly A／B 的輸入檢查、訓練與診斷。 |
| `reducer_classifier_factorial.py` | 交叉實驗的元件（工作票 17）。 |
| `independent_tuning.py` | 分組 5-fold CV、SupCon、學習率與 epoch 選擇（工作票 20）。 |
| `brain_comparison.py` | Fly A／Fly B 訓練後的腦部比較。 |
| `predictor.py` | 鎖定模型的載入與共用推論介面。 |
| `runtime_resources.py` | 執行期記憶體等資源量測。 |

## `tests/`：測試

每個測試檔對應上面同名的模組或流程，例如 `test_graph_core.py` 測 `graph_core.py`。比較不容易從檔名看出的有：

| 測試檔 | 測試範圍 |
|---|---|
| `test_graph_core_hops.py` | T 步等於 T 跳的修正（工作票 23）。 |
| `test_signed_graph_core.py` | 有正負號圖核心與 Dale 原則。 |
| `test_embedding_logistic.py`、`test_embedding_torch.py` | 嵌入後的 LR 與 PyTorch 分類器。 |
| `test_m2_checkpoint.py`、`test_m2_seed_preregistration.py` | 基準模型 checkpoint 與 seed 預先登記。 |
| `test_m32_inputs.py`、`test_m32_runner.py`、`test_m34_comparison.py` | 第一代 Fly 輸入、runner 與多 seed 比較。 |
| `test_m4_prediction.py` | 鎖定模型推論 API 與 CLI。 |

執行方式見 `README.md`。

## `.scratch/1999-connectome-demo/`：工作紀錄

依 `docs/agents/issue-tracker.md` 保存工作票、研究筆記、探測與每次實驗的結果。

### `issues/`：25 張工作票

| 檔案 | 主題 |
|---|---|
| `01-m2-1-data-contract-readonly-loader.md` | 資料契約與唯讀 loader。 |
| `02-m0-1-malecns-source-manifest.md` | MaleCNS 來源。 |
| `03-m1-1-directed-graph-importer.md` | 有向圖匯入。 |
| `04-m1-2-subgraph-selection-feasibility.md` | 子圖挑選（G0 起點與 BFS）。 |
| `05-m1-3-io-reachability.md` | 輸入／輸出點與可達性。 |
| `06-m2-2a-lightweight-text-baseline.md` | 輕量文字 baseline。 |
| `07-m3-0-connectome-classifier-contract.md` | Fly A／B 設計契約。 |
| `08-m3-1-small-fixture-model-core.md` | 小型模型核心。 |
| `09-m2-2b-e5-embeddings-and-classifiers.md` | E5 嵌入與基準分類器。 |
| `10-m2-4-evaluator-test-gate.md` | 評估器與一次性 test 機制。 |
| `11-m2-3-lda-classification-baseline.md` | LDA baseline。 |
| `12-m3-2-fly-ab-provisional-training.md` | 第一代 Fly A／B 訓練。 |
| `13-m3-4-validation-comparison.md` | 多 seed validation 比較。 |
| `14-m4-1-locked-predictor.md` | 鎖定模型與 CLI。 |
| `15-m4-2-streamlit-research-demo.md` | Streamlit 展示（已於 2026-11-14 移除）。 |
| `16-fly-ab-representation-diagnosis.md` | Fly A／B 表示診斷。 |
| `17-reducer-classifier-factorial.md` | 降維器 × 分類器交叉實驗。 |
| `18-m0-2-neurotransmitter-sign-source.md` | 神經傳導物質與正負號來源。 |
| `19-m3-6-signed-graph-core.md` | 有正負號的圖核心。 |
| `20-m3-7-independent-fly-a-fly-b-tuning.md` | Fly A／Fly B 獨立調參。 |
| `21-m1-4-signed-subgraph-selection.md` | 有正負號子圖挑選（起點 810979）。 |
| `22-signed-graph-comparison.md` | 四張圖比較。 |
| `23-graph-core-effective-hops.md` | 有效跳數修正。 |
| `24-t2-vs-t4-comparison.md` | T=2 vs T=4。 |
| `25-dataset-v2-rewrite.md` | 資料 v2 改寫、重新訓練與一次性 test。 |

### `research/`：設計、預註冊與研究報告

| 檔案 | 內容 |
|---|---|
| `1999-case-classification-proposal-revised.md` | 研究提案。 |
| `m0-1-malecns-v1.0-source-research.md` | MaleCNS 來源、授權與下載研究。 |
| `m1-1-import-report.md`、`m1-2-feasibility-probe.md`、`m1-3-preflight.md`、`m1-3-io-reachability-report.md` | 匯入、子圖挑選與輸入／輸出點階段的報告。 |
| `m2-2a-smoke-test-report.md`、`m2-2b-e5-resource-preflight-20261016.md`、`m2-2b-e5-windows-gate-and-provisional-run-20261026.md` | 文字 baseline 與 E5 的報告。 |
| `m2-3-lda-fixture-report.md`、`m2-4-evaluator-fixture-report.md` | LDA 與評估器的驗收報告。 |
| `m3-0-connectome-classifier-contract.md` | Fly A／B 資料界線、訓練與驗證契約。 |
| `m3-1-small-fixture-model-core-report.md` | 小型模型核心驗收紀錄。 |
| `m3-2-pyarrow-application-control-block-20261026.md` | Windows PyArrow 封鎖問題的處理經過。 |
| `fly-a-b-diagnostic-preregistration-20261026.md` | Fly A／B 診斷的預註冊。 |
| `m4-matched-budget-comparison-plan-20261026.md` | M4 同預算比較計畫。 |
| `reducer-classifier-factorial-preregistration-20261113.md` | 交叉實驗的預註冊。 |
| `independent-fly-a-fly-b-tuning-preregistration-20261113.md` | 獨立調參的預註冊。 |

### `runs/`：每次實驗的結果

| 子資料夾 | 內容 |
|---|---|
| **基準模型（M2）** | |
| `m2-2a-smoke-final-loader-audit-20261015T171135Z/` | 文字 baseline smoke 結果。 |
| `m2-2b-e5-provisional-20261025T185218Z/`、`m2-2b-e5-provisional-20261026T015843Z/` | E5 暫定執行；後者是第一代流程釘選的版本。 |
| `m2-2b-e5-seed-{42,1337,2026}-current-runner-20261026/` | 資料 v1 的三個 seed E5 基準；seed 42 含鎖定推論模型 `locked_model_manifest.json`。 |
| `m2-2b-e5-dataset-v2-seed-42-20261114/` | 資料 v2 的 E5 基準。 |
| **第一代果蠅（M3）** | |
| `m3-2-fly-ab-provisional-20261026T-gate-check/` | 訓練前檢查紀錄。 |
| `m3-2-fly-ab-seed-42-crlf-fix-20261026/`、`m3-2-fly-ab-seed-{1337,2026}-20261026/` | 第一代 Fly A／B 三個 seed 的訓練結果。 |
| `m3-4-validation-comparison-seeds-42-1337-2026-20261026/` | 多候選、多 seed 的 validation 比較。 |
| `fly-ab-diagnosis-20261026/` | Fly A／B 表示診斷與 E5 residual。 |
| `m4-matched-budget-validation-20261026/` | M4 同預算比較與驗收報告。 |
| **第二代實驗** | |
| `reducer-classifier-factorial-20261113/` | 交叉實驗（工作票 17）。 |
| `independent-tuning-t-hops-20261113/`、`independent-tuning-t4-20261113/` | 資料 v1 的獨立調參，T=2 與 T=4（含四張圖、三個 seed 的 checkpoint）。 |
| `independent-tuning-v2-t2-20261114/`、`independent-tuning-v2-t4-20261114/` | 資料 v2 的獨立調參，T=2 與 T=4。 |
| `fly-ab-brain-comparison-t-hops-20261113/`、`-t4-20261113/`、`-v2-t2-20261114/`、`-v2-t4-20261114/` | 四個版本的 Fly A／Fly B 腦部比較（數據與圖）。 |
| `test-evaluation-dataset-v2-20261114/` | 資料 v2 的一次性 test 結果（`test_results.json`、`report.md`）。 |
| `v2-known-issues-ablation-20261114/` | 驗證資料 v2 已知問題不影響分類的消融實驗。 |

各 run 內檔案依名稱判讀：`report.md` 是給人讀的摘要；`results.json`／`metrics.json` 是指標；`predictions.csv` 是預測輸出；`*_manifest.json` 記錄輸入、模型與候選登記；`timings.json` 是訓練時間；`.pt`／`.joblib` 是 checkpoint。不同 run 的同名檔案是各自獨立的輸出，不能互換。

### 其他資料夾

| 路徑 | 內容 |
|---|---|
| `data-v2/` | 資料 v2 生成過程的批次規劃、原始與整理後批次、品質稽核與類別一致性檢查。 |
| `benchmarks/m1-2-rowgroup-index-bfs-seed-20261015/` | 子圖／BFS 的效能測試資料。 |
| `probes/m1-2/` | 各種起點挑法的探測結果；`streaming-bfs-hash-priority-seed-274013289-*` 是 G0 起點的兩次執行與驗證。 |
| `m1-1-resource-audit-unapproved-threads-4/`、`m1-3/` | 匯入資源審查與輸入／輸出點 manifest。 |
| `requirements-*.txt`／`.in`／`.lock` | 各階段的套件需求與鎖定版本（smoke、E5 Windows、Fly A／B Windows）。 |
| `caches/`、`test-ledger/` | 不在 Git，見「盤點範圍」。 |

## 哪些可清、哪些要留

| 類別 | 建議 |
|---|---|
| `__pycache__/` | 需要空間時可刪，程式會重新產生。 |
| `.scratch/1999-connectome-demo/caches/` | 可重建，但建議保留，避免重算 embeddings。 |
| `.scratch/1999-connectome-demo/test-ledger/` | **必須保留**，一次性 test 的紀錄。 |
| `.scratch/` 的 run reports、checkpoints、manifest | 保留。鎖定推論模型、專案介紹頁與分析報告都從這裡讀資料；清理前要先確認沒有被 README、工作票、manifest 或程式引用。 |
| `data/1999_synthetic/archive/`、`superseded/`、舊 pilot／taxonomy | 保留版本歷史，不因「較舊」就刪除。 |
| `data/1999_synthetic` 舊路徑及 `data/outputs` symlink | 保留相容性。 |
| `outputs/` 複核工作簿 | 保留原始版本與歷史建議；AI／助理建議不等於人工核准。 |

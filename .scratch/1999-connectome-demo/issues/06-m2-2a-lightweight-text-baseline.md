# 06: M2.2a 輕量文字分類基線 smoke test

**What to build:** 在既有正式合成資料上建立可重現、低資源的文字分類基線 smoke test，作為 spec v0.2 預訓練 embedding 流程之外的補充對照。此 ticket 不取代 spec 的 M2.2 Encoder／embedding cache 或 M2.3 baseline。

**Blocked by:** 01 M2.1 資料契約與唯讀 loader (completed)

**Status:** completed (smoke_test／provisional; not a formal evaluation)

## 範圍

- 唯讀使用 `data/1999_synthetic/formal/v1.0.0/formal_dataset_v1.0.0.jsonl`，並透過 M2.1 loader 與 `data/1999_synthetic/taxonomy/current/formal_split_manifest_frozen_v1.0.yaml` 核對資料契約；Pilot 不納入。
- 依 frozen manifest 使用既有 train／validation／test split。`scenario_family_id` 只作為隔離稽核欄位，不作為特徵；不得重切資料或讓同一家族跨 split。
- 文字輸入僅使用 `transcript`，保留 `R:`／`L:` 聲道標記。不得把 ID、label 名稱、scenario、family、split、generator、prompt、review 狀態或其他管理欄位送入模型。
- 建立字元 n-gram 與輕量詞組／token n-gram TF-IDF 表示，搭配 Logistic Regression 與 Linear SVM 的小型固定候選組；中文分詞若需套件，僅使用已安裝的本機套件。向量器只在 train fit；候選與有限設定須事先記錄，以 validation 作比較，不做大規模搜尋。
- 以 8 GiB RAM 筆電、CPU 為基準；不下載或載入大型模型。必要套件先核對專案環境並以最小依賴處理。
- 本 ticket 的運行結果只可標示為 `smoke_test`／`provisional`。正式資料目前仍為 `review_status=pending_manual_review`；在人工複核品質閘門通過前，不得發布正式評估或分類效能結論。
- M2.1 loader 可讀取完整凍結資料（包含 test 列），但僅用於資料契約稽核。模型流程只接收 train／validation；test 列不得進入向量器 fit／transform、模型 fit／predict、候選調整、指標或預測輸出。正式 test 評估留待模型清單、設定、選模規則鎖定且資料人工複核閘門通過後，由共用 evaluator 一次性執行；不得用 test 調參或回頭選模。

## 評估與重現產物

- 回報 train／validation 的 macro-F1、固定 taxonomy 順序的各類 precision／recall／F1、support、confusion matrix；另列 accuracy、資料筆數及 split。對未評估的 test 明確標示 `not_run`。
- 記錄 vectorizer 與模型完整設定、程式版本／工作樹識別、Python 與依賴版本、訓練 seed、固定標籤順序、M2.1 audit 結果，以及正式 JSONL、CSV、taxonomy、frozen manifest 的來源路徑與 SHA-256。
- 結果及預測檔標記合成資料、待人工複核、smoke test；不得更改原資料或其中的 `review_status`。

## 驗收條件

- [x] 載入器成功核對 1,000 筆正式資料、五類各 200 筆、train／validation／test 的 700／150／150 配額、逐類 140／30／30 配額，以及 66 個 scenario-family split 隔離；本 ticket 不重切資料。
- [x] Train-only fit 有 fixture 測試與執行紀錄；validation 僅用於預先列出的候選比較；test 只由 M2.1 loader 讀取作全資料契約稽核，未進入模型／特徵流程、調參、指標或預測輸出。
- [x] 四個固定 TF-IDF 線性候選均在 CPU／8 GiB 環境完成 smoke run，程式、依賴、資料及輸出 checksum／設定可追溯。
- [x] Train／validation 指標包含 macro-F1、五類各自 precision／recall／F1、support、confusion matrix；test 為 `not_run`。
- [x] manifest、報告與每列預測均標為 `smoke_test`／`provisional`，並標示合成資料及 `review_status=pending_manual_review`；沒有把 AI／自動檢查當成人工複核。
- [x] 正式 JSONL、CSV、taxonomy、frozen manifest 的 SHA-256 前後不變；Pilot 未使用，沒有生成或修改案件資料。

## 依賴與後續關係

- M2.1 已完成，提供唯一正式資料載入與稽核入口。
- 本 ticket 是額外的純文字基線，可與 spec M2.2 平行；不改動 M2.2→M2.3→M2.4 原依賴，也不替代固定 multilingual-e5-small embedding 基線。
- 正式 test 評估依 spec M2.4 的一次性閘門及資料人工複核要求辦理。

## Comments

- 2026-10-16：新增規劃 ticket。僅建立範圍與驗收條件；未實作、訓練、讀取 test split 或下載模型。
- 2026-10-16：開始執行後完成資源與依賴預檢，尚未載入正式資料。實測 RAM 為 8,589,934,592 bytes；目前 Python 3.14.8 找不到 scikit-learn、NumPy、SciPy 或 PyArrow，uv cache 也沒有 scikit-learn／SciPy／joblib／threadpoolctl。另確認 M2.1 `load_frozen_dataset` 會對完整 JSONL／CSV 呼叫 `read_bytes()` 並解析全部紀錄，沒有 train/validation-only 入口，故無法同時遵守「使用此 loader」與字面上的「不讀 test」。沒有安裝依賴、呼叫 loader、讀取正式資料、訓練或產生指標。詳見 `../research/m2-2a-smoke-test-report.md`；待使用者確認資料讀取界線及提供／核准可用的分類依賴後再續行。
- 2026-10-16：使用者明確確認 M2.1 loader 可完整讀取資料（包含 test）作契約稽核，模型流程只接收 train／validation；據此更新本 ticket 的 test 邊界。另在專案隔離 CPython 3.13 環境安裝 CPU-only scikit-learn 1.9.1 及必要相依，實際下載約 32.6 MiB（低於 500 MiB），保持超過 4 GiB 磁碟餘裕。
- 2026-10-16：以 TDD 增加 5 個 M2.2a fixture tests；與 M2.1 loader 測試共 14 項通過。完成正式資料 train／validation smoke test；資料 1,000 筆仍全為 `pending_manual_review`。loader 稽核核對全體配額與 family isolation；模型只使用 train 700／validation 150，test input／prediction 均為 0、test metrics `not_run`。來源四檔 SHA-256 由 loader 契約稽核在執行前後核對一致；8 GiB RAM 下峰值 RSS 251,641,856 bytes，執行期間保留超過 4 GiB 磁碟。
- 最終產物：`../research/m2-2a-smoke-test-report.md`；完整結果、各類 precision／recall／F1、confusion matrices：`../runs/m2-2a-smoke-final-loader-audit-20261015T171135Z/report.md`；manifest、metrics、標示狀態的 train／validation-only predictions 位於同一 run 目錄。未讀取 Pilot、未改正式資料、未開始 M3.0 或 connectome 分類器。

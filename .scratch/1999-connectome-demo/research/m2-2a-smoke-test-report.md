# M2.2a 輕量文字分類基線 smoke test

日期：2026-10-16（臺北時間）  
Ticket：`06 M2.2a`，`completed`（僅 smoke test；結果為 `smoke_test`／`provisional`）  
正式資料：1,000 筆全為 `review_status=pending_manual_review`；本次沒有納入 Pilot。

## 執行界線與資料核對

透過 M2.1 `load_frozen_dataset()` 完整載入正式 JSONL／CSV、taxonomy 與 frozen manifest，包含 test 列；此完整讀取只用於核對凍結契約與來源完整性。模型函式只接收 train 和 validation；沒有把 test 傳給向量器、分類器、候選比較、指標或預測輸出。Test 模型輸入與預測列均為 0，test 指標為 `not_run`。未以 test 調參或選模。

稽核確認 1,000 筆、五類各 200 筆、全體 train／validation／test 為 700／150／150、逐類為 140／30／30；scenario-family 共 66 個，train／validation／test 分別為 33／14／19 家族，切分無家族交集。模型只收到 train 700 筆／33 家族和 validation 150 筆／14 家族；兩者家族交集為 0。

正式資料與基準檔的 SHA-256 由 M2.1 loader 在契約稽核讀取時取得，執行前後完全一致；本次沒有在 loader 外直接重讀正式資料來計算雜湊：

| 檔案 | SHA-256 |
|---|---|
| `formal_dataset_v1.0.0.jsonl` | `1dd58478b66afd901d61f50f0ae41e7341e88b7935ced845b82a7316642a367a` |
| `formal_dataset_v1.0.0.csv` | `5efe5ada8c304be7122c746eb6770e34e053d5d433f725f8761ede0cc99be3aa` |
| `taxonomy_v1.3.yaml` | `4e6050adf90e198d453b822a9ac01ffcf0e553eefde25c6b0f8d2dcdd0bcdcf8` |
| `formal_split_manifest_frozen_v1.0.yaml` | `9c6f8e4584185091149722b6c6ef33e5b8332567f8bd238a6adb4aefe2ec01dc` |

## 環境與資源

- 使用專案隔離環境 `.scratch/1999-connectome-demo/env/m2-2a-smoke`，CPython 3.13.0、arm64。
- scikit-learn 1.9.1、NumPy 2.5.4、SciPy 1.18.1、joblib 1.6.0、threadpoolctl 3.7.0、narwhals 2.27.1、cloudpickle 3.1.2；套件 pin 見 [requirements](../requirements-m2-2a-smoke.txt)。僅安裝 CPU wheel，沒有 GPU 套件或模型。
- 安裝前核對 wheel 與 Python 3.13 相容性。下載量約 32.6 MiB（上限 500 MiB 內）；隔離環境約 147 MiB。scikit-learn 安裝方式遵循[官方安裝文件](https://scikit-learn.org/stable/install)的隔離環境建議。
- 實測實體 RAM：8,589,934,592 bytes（8 GiB）。程序峰值 RSS：265,682,944 bytes。
- 可用磁碟：執行前 23,655,501,824 bytes；輸出完成後 23,654,637,568 bytes；整段執行均高於 4 GiB 保留線。
- M2.1 loader 契約稽核約 0.320 秒；固定候選的向量化、訓練、train／validation 評估約 2.187 秒。
- 最終執行峰值 RSS：251,641,856 bytes。

## 固定候選與結果摘要

TF-IDF 使用逐字稿（保留 `R:`／`L:`）的字符 n-gram `(2, 5)` 及短字符片語 n-gram `(2, 4)`，`min_df=2`、`max_features=50000`、`sublinear_tf=true`、不轉小寫。詞彙表與 IDF 僅以 train fit；validation 僅 transform。Logistic Regression 和 Linear SVM 都使用預先固定參數，seed 42，未做大規模搜尋。

| 特徵 | 分類器 | Train accuracy | Train macro-F1 | Validation accuracy | Validation macro-F1 |
|---|---|---:|---:|---:|---:|
| char `(2,5)` | Logistic Regression | 1.0000 | 1.0000 | 0.9400 | 0.9389 |
| char `(2,5)` | Linear SVM | 1.0000 | 1.0000 | 0.9800 | 0.9797 |
| phrase-char `(2,4)` | Logistic Regression | 1.0000 | 1.0000 | 0.9400 | 0.9389 |
| phrase-char `(2,4)` | Linear SVM | 1.0000 | 1.0000 | 0.9867 | 0.9865 |

四組設定各自的五類 precision／recall／F1、support、完整 confusion matrix 與逐筆 train／validation 預測，見[完整執行報告](../runs/m2-2a-smoke-final-loader-audit-20261015T171135Z/report.md)。預測 CSV 有 3,400 列（四組候選 × train 700 + validation 150），每列均標記 `synthetic`、`pending_manual_review`、`smoke_test/provisional`；split 只包含 train／validation。

## 測試、重現與限制

- M2.2a fixture 測試：5 項通過，涵蓋 test 列排除、train-only vectorizer fit、固定候選輸出、標籤及 family split 驗證、預測檔標籤。
- M2.1 loader 測試：9 項通過，涵蓋有效資料、缺欄／重複 ID、標籤與配額、JSONL／CSV 不一致、family 跨 split 及來源唯讀檢查。
- 執行版本及資料來源 SHA-256 記於 [run manifest](../runs/m2-2a-smoke-final-loader-audit-20261015T171135Z/run_manifest.json)；完整 train／validation metrics 在同一目錄的 `metrics.json`。曾嘗試 repository-wide unittest discovery，但專用環境未安裝無關的 PyArrow connectome 測試依賴，且第一次探索命令未設定 `PYTHONPATH=src`，因此該次全域探索未通過；之後使用正確 import path 執行 M2.2a 與 M2.1 相關測試，共 14 項全部通過。
- 高 train 分數及 validation 分數只說明這批待人工複核合成資料上的 smoke pipeline 可執行。它們不是正式模型效能、真實案件表現或部署能力；需完成資料人工複核及後續評估關卡後才能做正式結論。
- 沒有修改正式資料、split、taxonomy、manifest、Pilot 或 connectome 產物；沒有開始 M3.0 或 connectome 分類器。

# M2.2a 輕量文字分類基線 smoke test

狀態：`smoke_test`／`provisional`  
日期：2026-10-15T17:11:41+00:00  
資料：正式合成資料 v1.0.0；全部 `review_status=pending_manual_review`。本報告不是正式效能結論。

## 使用界線

M2.1 `load_frozen_dataset()` 為契約稽核完整讀取 JSONL／CSV、taxonomy 與 frozen manifest，包含 test 列；本次再次載入僅用於前後契約／checksum 核對。模型流程只接收 train 與 validation 列。Test 列沒有進入 TF-IDF fit／transform、分類器 fit／predict、特徵比較、調參、指標或預測輸出；test 指標為 `not_run`。

模型輸入只有 `transcript`，保留逐字稿中的 `R:`／`L:` 標記。ID、label 名稱、scenario、scenario_family_id、split、review_status 及其他 metadata 不作為特徵。`scenario_family_id` 只用來稽核既有切分隔離。

## 資料契約與 split 核對

- M2.1 loader audit：1000 筆、5 類、66 個 scenario families；taxonomy `1.3`、manifest `frozen-1.0`。
- 全體 split 配額（loader 契約稽核）：`{"test": 150, "train": 700, "validation": 150}`。這是資料契約計數，不是 test 分類指標。
- 各 split 家族數（契約稽核）：`{"test": 19, "train": 33, "validation": 14}`。
- 模型輸入：train 700 筆／33 家族；validation 150 筆／14 家族。
- Train／validation 家族交集：0；`scenario_family_id` 不跨 split。
- Test 模型輸入列、預測列、指標計算：均為 0／`not_run`。

## 固定實驗設定

- Label 順序與名稱：`{"park_general_maintenance": "一般公園綠地管理及設施維護（含車輛違規進入）", "road_surface_defect": "道路凹陷、不平、有高低差", "sidewalk_maintenance": "人行道維護", "street_cleaning": "路面清潔（含行人果皮箱、菸蒂、狗便）", "waste_truck_service": "垃圾車清運及服務事項"}`。
- TF-IDF：字符 n-gram `(2, 5)` 與短字符片語 n-gram `(2, 4)`；`min_df=2`、`max_features=50000`、`sublinear_tf=true`、不轉小寫。片語候選以連續字符片段實作，未引入分詞套件。
- Classifiers：Logistic Regression (`C=1`, `lbfgs`, `max_iter=1000`) 與 Linear SVM (`C=1`, `dual=auto`, `max_iter=5000`)；固定 seed 42。候選組預先固定，無超參數搜尋。
- 向量器 vocabulary／IDF 只以 train fit；validation 僅 transform 與比較。
- 隔離環境：`.scratch/1999-connectome-demo/env/m2-2a-smoke`；安裝方式 `uv pip install --python <isolated-venv-python> --only-binary=:all: -r requirements-m2-2a-smoke.txt`；僅 CPU wheel，沒有 GPU 套件或模型。
- 依賴版本：Python 3.13.0；scikit-learn 1.9.1；NumPy 2.5.4；SciPy 1.18.1；joblib 1.6.0；threadpoolctl 3.7.0；narwhals 2.27.1；cloudpickle 3.1.2。
- 下載量上限 500 MiB；實際安裝時約下載 32.6 MiB；環境目錄大小 147 MiB。安裝前的 wheel 相容性檢查與套件版本詳列於鎖定檔及 ticket。
- CPU；實測實體 RAM 8589934592 bytes。

## Train／validation 摘要

| 特徵 | 分類器 | split | 筆數 | Accuracy | Macro-F1 |
|---|---|---|---:|---:|---:|
| char | logistic_regression | train | 700 | 1.0000 | 1.0000 |
| char | logistic_regression | validation | 150 | 0.9400 | 0.9389 |
| char | linear_svm | train | 700 | 1.0000 | 1.0000 |
| char | linear_svm | validation | 150 | 0.9800 | 0.9797 |
| phrase_char | logistic_regression | train | 700 | 1.0000 | 1.0000 |
| phrase_char | logistic_regression | validation | 150 | 0.9400 | 0.9389 |
| phrase_char | linear_svm | train | 700 | 1.0000 | 1.0000 |
| phrase_char | linear_svm | validation | 150 | 0.9867 | 0.9865 |

## 分類指標與混淆矩陣

### char + logistic_regression

固定設定：`{"classifier": {"C": 1.0, "max_iter": 1000, "random_state": 42, "solver": "lbfgs"}, "features": {"analyzer": "char", "dtype": "scikit-learn default (float64)", "lowercase": false, "max_features": 50000, "min_df": 2, "ngram_range": [2, 5], "sublinear_tf": true}}`  
特徵數：42248。

#### Train

| label_id | label_name | Precision | Recall | F1 | Support |
|---|---|---:|---:|---:|---:|
| `sidewalk_maintenance` | 人行道維護 | 1.0000 | 1.0000 | 1.0000 | 140 |
| `road_surface_defect` | 道路凹陷、不平、有高低差 | 1.0000 | 1.0000 | 1.0000 | 140 |
| `park_general_maintenance` | 一般公園綠地管理及設施維護（含車輛違規進入） | 1.0000 | 1.0000 | 1.0000 | 140 |
| `waste_truck_service` | 垃圾車清運及服務事項 | 1.0000 | 1.0000 | 1.0000 | 140 |
| `street_cleaning` | 路面清潔（含行人果皮箱、菸蒂、狗便） | 1.0000 | 1.0000 | 1.0000 | 140 |

Confusion matrix（rows=actual, columns=predicted; label order follows the frozen taxonomy）:


Labels: `sidewalk_maintenance=人行道維護`, `road_surface_defect=道路凹陷、不平、有高低差`, `park_general_maintenance=一般公園綠地管理及設施維護（含車輛違規進入）`, `waste_truck_service=垃圾車清運及服務事項`, `street_cleaning=路面清潔（含行人果皮箱、菸蒂、狗便）`


```text

140 0 0 0 0

0 140 0 0 0

0 0 140 0 0

0 0 0 140 0

0 0 0 0 140

```

#### Validation

| label_id | label_name | Precision | Recall | F1 | Support |
|---|---|---:|---:|---:|---:|
| `sidewalk_maintenance` | 人行道維護 | 0.8889 | 0.8000 | 0.8421 | 30 |
| `road_surface_defect` | 道路凹陷、不平、有高低差 | 0.9062 | 0.9667 | 0.9355 | 30 |
| `park_general_maintenance` | 一般公園綠地管理及設施維護（含車輛違規進入） | 0.9677 | 1.0000 | 0.9836 | 30 |
| `waste_truck_service` | 垃圾車清運及服務事項 | 1.0000 | 1.0000 | 1.0000 | 30 |
| `street_cleaning` | 路面清潔（含行人果皮箱、菸蒂、狗便） | 0.9333 | 0.9333 | 0.9333 | 30 |

Confusion matrix（rows=actual, columns=predicted; label order follows the frozen taxonomy）:


Labels: `sidewalk_maintenance=人行道維護`, `road_surface_defect=道路凹陷、不平、有高低差`, `park_general_maintenance=一般公園綠地管理及設施維護（含車輛違規進入）`, `waste_truck_service=垃圾車清運及服務事項`, `street_cleaning=路面清潔（含行人果皮箱、菸蒂、狗便）`


```text

24 3 1 0 2

1 29 0 0 0

0 0 30 0 0

0 0 0 30 0

2 0 0 0 28

```

### char + linear_svm

固定設定：`{"classifier": {"C": 1.0, "dual": "auto", "max_iter": 5000, "random_state": 42}, "features": {"analyzer": "char", "dtype": "scikit-learn default (float64)", "lowercase": false, "max_features": 50000, "min_df": 2, "ngram_range": [2, 5], "sublinear_tf": true}}`  
特徵數：42248。

#### Train

| label_id | label_name | Precision | Recall | F1 | Support |
|---|---|---:|---:|---:|---:|
| `sidewalk_maintenance` | 人行道維護 | 1.0000 | 1.0000 | 1.0000 | 140 |
| `road_surface_defect` | 道路凹陷、不平、有高低差 | 1.0000 | 1.0000 | 1.0000 | 140 |
| `park_general_maintenance` | 一般公園綠地管理及設施維護（含車輛違規進入） | 1.0000 | 1.0000 | 1.0000 | 140 |
| `waste_truck_service` | 垃圾車清運及服務事項 | 1.0000 | 1.0000 | 1.0000 | 140 |
| `street_cleaning` | 路面清潔（含行人果皮箱、菸蒂、狗便） | 1.0000 | 1.0000 | 1.0000 | 140 |

Confusion matrix（rows=actual, columns=predicted; label order follows the frozen taxonomy）:


Labels: `sidewalk_maintenance=人行道維護`, `road_surface_defect=道路凹陷、不平、有高低差`, `park_general_maintenance=一般公園綠地管理及設施維護（含車輛違規進入）`, `waste_truck_service=垃圾車清運及服務事項`, `street_cleaning=路面清潔（含行人果皮箱、菸蒂、狗便）`


```text

140 0 0 0 0

0 140 0 0 0

0 0 140 0 0

0 0 0 140 0

0 0 0 0 140

```

#### Validation

| label_id | label_name | Precision | Recall | F1 | Support |
|---|---|---:|---:|---:|---:|
| `sidewalk_maintenance` | 人行道維護 | 1.0000 | 0.9000 | 0.9474 | 30 |
| `road_surface_defect` | 道路凹陷、不平、有高低差 | 0.9375 | 1.0000 | 0.9677 | 30 |
| `park_general_maintenance` | 一般公園綠地管理及設施維護（含車輛違規進入） | 1.0000 | 1.0000 | 1.0000 | 30 |
| `waste_truck_service` | 垃圾車清運及服務事項 | 1.0000 | 1.0000 | 1.0000 | 30 |
| `street_cleaning` | 路面清潔（含行人果皮箱、菸蒂、狗便） | 0.9677 | 1.0000 | 0.9836 | 30 |

Confusion matrix（rows=actual, columns=predicted; label order follows the frozen taxonomy）:


Labels: `sidewalk_maintenance=人行道維護`, `road_surface_defect=道路凹陷、不平、有高低差`, `park_general_maintenance=一般公園綠地管理及設施維護（含車輛違規進入）`, `waste_truck_service=垃圾車清運及服務事項`, `street_cleaning=路面清潔（含行人果皮箱、菸蒂、狗便）`


```text

27 2 0 0 1

0 30 0 0 0

0 0 30 0 0

0 0 0 30 0

0 0 0 0 30

```

### phrase_char + logistic_regression

固定設定：`{"classifier": {"C": 1.0, "max_iter": 1000, "random_state": 42, "solver": "lbfgs"}, "features": {"analyzer": "char", "dtype": "scikit-learn default (float64)", "lowercase": false, "max_features": 50000, "min_df": 2, "ngram_range": [2, 4], "sublinear_tf": true}}`  
特徵數：27556。

#### Train

| label_id | label_name | Precision | Recall | F1 | Support |
|---|---|---:|---:|---:|---:|
| `sidewalk_maintenance` | 人行道維護 | 1.0000 | 1.0000 | 1.0000 | 140 |
| `road_surface_defect` | 道路凹陷、不平、有高低差 | 1.0000 | 1.0000 | 1.0000 | 140 |
| `park_general_maintenance` | 一般公園綠地管理及設施維護（含車輛違規進入） | 1.0000 | 1.0000 | 1.0000 | 140 |
| `waste_truck_service` | 垃圾車清運及服務事項 | 1.0000 | 1.0000 | 1.0000 | 140 |
| `street_cleaning` | 路面清潔（含行人果皮箱、菸蒂、狗便） | 1.0000 | 1.0000 | 1.0000 | 140 |

Confusion matrix（rows=actual, columns=predicted; label order follows the frozen taxonomy）:


Labels: `sidewalk_maintenance=人行道維護`, `road_surface_defect=道路凹陷、不平、有高低差`, `park_general_maintenance=一般公園綠地管理及設施維護（含車輛違規進入）`, `waste_truck_service=垃圾車清運及服務事項`, `street_cleaning=路面清潔（含行人果皮箱、菸蒂、狗便）`


```text

140 0 0 0 0

0 140 0 0 0

0 0 140 0 0

0 0 0 140 0

0 0 0 0 140

```

#### Validation

| label_id | label_name | Precision | Recall | F1 | Support |
|---|---|---:|---:|---:|---:|
| `sidewalk_maintenance` | 人行道維護 | 0.8889 | 0.8000 | 0.8421 | 30 |
| `road_surface_defect` | 道路凹陷、不平、有高低差 | 0.9062 | 0.9667 | 0.9355 | 30 |
| `park_general_maintenance` | 一般公園綠地管理及設施維護（含車輛違規進入） | 0.9677 | 1.0000 | 0.9836 | 30 |
| `waste_truck_service` | 垃圾車清運及服務事項 | 1.0000 | 1.0000 | 1.0000 | 30 |
| `street_cleaning` | 路面清潔（含行人果皮箱、菸蒂、狗便） | 0.9333 | 0.9333 | 0.9333 | 30 |

Confusion matrix（rows=actual, columns=predicted; label order follows the frozen taxonomy）:


Labels: `sidewalk_maintenance=人行道維護`, `road_surface_defect=道路凹陷、不平、有高低差`, `park_general_maintenance=一般公園綠地管理及設施維護（含車輛違規進入）`, `waste_truck_service=垃圾車清運及服務事項`, `street_cleaning=路面清潔（含行人果皮箱、菸蒂、狗便）`


```text

24 3 1 0 2

1 29 0 0 0

0 0 30 0 0

0 0 0 30 0

2 0 0 0 28

```

### phrase_char + linear_svm

固定設定：`{"classifier": {"C": 1.0, "dual": "auto", "max_iter": 5000, "random_state": 42}, "features": {"analyzer": "char", "dtype": "scikit-learn default (float64)", "lowercase": false, "max_features": 50000, "min_df": 2, "ngram_range": [2, 4], "sublinear_tf": true}}`  
特徵數：27556。

#### Train

| label_id | label_name | Precision | Recall | F1 | Support |
|---|---|---:|---:|---:|---:|
| `sidewalk_maintenance` | 人行道維護 | 1.0000 | 1.0000 | 1.0000 | 140 |
| `road_surface_defect` | 道路凹陷、不平、有高低差 | 1.0000 | 1.0000 | 1.0000 | 140 |
| `park_general_maintenance` | 一般公園綠地管理及設施維護（含車輛違規進入） | 1.0000 | 1.0000 | 1.0000 | 140 |
| `waste_truck_service` | 垃圾車清運及服務事項 | 1.0000 | 1.0000 | 1.0000 | 140 |
| `street_cleaning` | 路面清潔（含行人果皮箱、菸蒂、狗便） | 1.0000 | 1.0000 | 1.0000 | 140 |

Confusion matrix（rows=actual, columns=predicted; label order follows the frozen taxonomy）:


Labels: `sidewalk_maintenance=人行道維護`, `road_surface_defect=道路凹陷、不平、有高低差`, `park_general_maintenance=一般公園綠地管理及設施維護（含車輛違規進入）`, `waste_truck_service=垃圾車清運及服務事項`, `street_cleaning=路面清潔（含行人果皮箱、菸蒂、狗便）`


```text

140 0 0 0 0

0 140 0 0 0

0 0 140 0 0

0 0 0 140 0

0 0 0 0 140

```

#### Validation

| label_id | label_name | Precision | Recall | F1 | Support |
|---|---|---:|---:|---:|---:|
| `sidewalk_maintenance` | 人行道維護 | 1.0000 | 0.9333 | 0.9655 | 30 |
| `road_surface_defect` | 道路凹陷、不平、有高低差 | 1.0000 | 1.0000 | 1.0000 | 30 |
| `park_general_maintenance` | 一般公園綠地管理及設施維護（含車輛違規進入） | 0.9677 | 1.0000 | 0.9836 | 30 |
| `waste_truck_service` | 垃圾車清運及服務事項 | 1.0000 | 1.0000 | 1.0000 | 30 |
| `street_cleaning` | 路面清潔（含行人果皮箱、菸蒂、狗便） | 0.9677 | 1.0000 | 0.9836 | 30 |

Confusion matrix（rows=actual, columns=predicted; label order follows the frozen taxonomy）:


Labels: `sidewalk_maintenance=人行道維護`, `road_surface_defect=道路凹陷、不平、有高低差`, `park_general_maintenance=一般公園綠地管理及設施維護（含車輛違規進入）`, `waste_truck_service=垃圾車清運及服務事項`, `street_cleaning=路面清潔（含行人果皮箱、菸蒂、狗便）`


```text

28 0 1 0 1

0 30 0 0 0

0 0 30 0 0

0 0 0 30 0

0 0 0 0 30

```


## 執行資源與資料完整性

- M2.1 loader 稽核時間：0.320 秒（含全資料契約檢查）。
- TF-IDF／模型 fit 與 train／validation 評估時間：2.187 秒。
- 程序峰值 RSS：251641856 bytes。
- 可用磁碟：執行前 23655501824 bytes；輸出後 23654637568 bytes；4 GiB 保留線通過：True。
- 正式 JSONL／CSV／taxonomy／frozen manifest 的 M2.1 audit SHA-256 前後一致：True。
- 完整設定及 source SHA-256 見 `run_manifest.json`；只含 train／validation 的預測見 `predictions.csv`。
- 依賴鎖定檔：`requirements-m2-2a-smoke.txt`；實際環境套件版本記錄於 manifest。

## 限制

資料仍未完成逐筆人工複核；分數只能用來確認低資源 pipeline 可運作與輸出形狀。不得解讀為正式模型效能、真實案件表現或可部署分類能力。Test split 僅被 M2.1 loader 用於 frozen data contract 稽核，沒有被模型流程讀取或評估。

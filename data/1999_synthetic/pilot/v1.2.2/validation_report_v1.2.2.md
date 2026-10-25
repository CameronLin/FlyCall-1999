# Pilot v1.2.2 驗證報告

日期：2026-10-11（Asia/Taipei）  
狀態：草案；50 筆均待人工複核，沒有人工通過紀錄。  
資料：`pilot_v1.2.2.jsonl`；對照基準：`pilot_v1.2.1.jsonl`。  
Taxonomy 基準：`taxonomy_v1.2.1.yaml`；家族規劃來源：`taxonomy_expansion_draft_v1.2.md`。

## 修訂範圍

指定 15 筆（V12-013, V12-014, V12-015, V12-016, V12-020, V12-028, V12-029, V12-030, V12-037, V12-038, V12-041, V12-042, V12-044, V12-046, V12-048）更新逐字稿；其餘 35 筆逐字稿與 v1.2.1 完全相同。V12-015／016 的 `scenario_family_id` 依 merge map 改為 `FAM-ROAD-INTERSECTION-DENT`，標籤、ID 與 scenario_id 保留。V12-020 描述單一長條縱向高低轉換，沒有改為大範圍波狀起伏家族。新版 `prompt_version` 為 `taipei1999-synth-pilot-v1.2.2`。

## Pilot 驗證結果

| 檢查 | 結果 |
|---|---|
| JSONL／必要欄位 | 50 行均可解析；12 個必要欄位齊全；ID 及 scenario_id 唯一 |
| 類別配額 | 五類各 10 筆，共 50 筆 |
| metadata 保留 | ID、label、scenario_id、split、synthetic、speaker_map、generator_model、review_status 與 v1.2.1 相同；015／016 的 family ID 依 merge map 更新 |
| split／複核狀態 | 全數 `split="pilot"`、`review_status="pending_manual_review"`、`is_synthetic=true` |
| family ID | 全數屬於 65 個暫列獨立家族；015／016 使用有效合併目標 |
| 聲道／行數 | R=客服、L=來電民眾；每筆 R 開場、R 結尾、逐行交替；11–13 行 |
| 中文字數 | 302–398 字，平均 333.5 字（按 CJK 統一漢字計數） |
| 完全重複 | 0 對 |
| 近似重複初篩 | 同類字元三連詞 Jaccard 最高 0.125（V12-015／V12-016）；屬字串初篩，仍需人工判斷語意及話術相似度 |
| 個資格式初篩 | 電子郵件、手機、身分證、門牌號碼樣式 0 命中；此檢查不能辨識所有可識別資訊 |
| 首句／末句差異 | 49 種不同首句、50 種不同末句 |

自動檢查不能判斷主訴是否單一、分類和家族邊界、臺灣口語自然度、位置是否足夠清楚、客服是否在來電者說明前透露主題或作實質回答；以上仍待人工複核。

## 正式 split manifest 核對

正式資料目標為另外新增 1,000 筆，不包含 Pilot。v1.2.1 與 v1.2.2 是同一組 50 筆 Pilot 的基準／修訂草案版本，不重複計數。切分草案以 65 個暫列家族作分組，狀態未凍結。

| 類別 | 家族數 train／validation／test | 筆數 train／validation／test | 每家族預計筆數 train／validation／test |
|---|---:|---:|---:|
| 人行道維護 | 8／3／3 | 140／30／30 | 17–18／10／10 |
| 道路凹陷、不平、有高低差 | 8／3／3 | 140／30／30 | 17–18／10／10 |
| 一般公園綠地管理及設施維護 | 9／3／3 | 140／30／30 | 15–16／10／10 |
| 垃圾車清運及服務事項 | 5／3／3 | 140／30／30 | 28／10／10 |
| 路面清潔 | 5／3／3 | 140／30／30 | 28／10／10 |
| **合計** | **35／15／15** | **700／150／150** | — |

逐家族核算精確：每類 200 筆，全體 1,000 筆；65 個 family ID 各只屬一個 split，沒有家族跨組。11 家族類別 train 每家族需 28 筆，validation/test 每家族 10 筆，訓練家族資料量差異較大。5/3/3 讓每類 holdout 各含 3 個家族，但其代表性及測試穩定性仍有限。家族核准或合併異動後必須重新計算。

## 未解決／阻塞項目

- Pilot 50 筆仍待人工複核，沒有人工通過紀錄；正式生成維持阻塞。
- taxonomy 的 15 個 revise 家族及 10 個合併規則尚未人工核准。
- `formal_split_manifest_draft_v1.1.yaml` 仍為 `draft_unfrozen`；家族清單定案後須重新核對並由人工凍結。
- 語意分類、客服行為、位置描述、口語自然度及近似內容仍須人工判斷。
- 本次未開始正式 1,000 筆生成。

逐筆清單見 [`manual_review_v1.2.2.md`](manual_review_v1.2.2.md)，阻塞事項見 [`formal_generation_todo_v1.2.md`](formal_generation_todo_v1.2.md)。

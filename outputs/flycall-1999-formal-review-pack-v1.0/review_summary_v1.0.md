# 正式資料 v1.0.0 人工複核摘要

建立時間：2026-10-12T07:36:18.006Z

## 範圍與抽樣

- 來源：formal_dataset_v1.0.0.jsonl、formal_dataset_v1.0.0.csv，均唯讀。
- validation 150 筆、test 150 筆全數納入；train 有 33 個家族，每個 scenario_family_id 抽 3 筆，共 99 筆。
- 總複核樣本 399 筆。固定 seed 20261012。先依 family ID 排序，再於家族內按 record ID 排序，使用 Python 3.14.8 random.Random(20261012).sample(..., 3)。
- 逐家族抽樣 record ID 列於活頁簿「抽樣清單」工作表。

| 類別 | train 抽樣 | validation | test | 合計 | manifest 家族 train/validation/test |
|---|---:|---:|---:|---:|---:|
| 人行道維護 | 21 | 30 | 30 | 81 | 7/3/4 |
| 道路凹陷、不平、有高低差 | 21 | 30 | 30 | 81 | 7/3/4 |
| 一般公園綠地管理及設施維護（含車輛違規進入） | 24 | 30 | 30 | 84 | 8/3/4 |
| 垃圾車清運及服務事項 | 21 | 30 | 30 | 81 | 7/2/3 |
| 路面清潔（含行人果皮箱、菸蒂、狗便） | 12 | 30 | 30 | 72 | 4/3/4 |
| **全體** | **99** | **150** | **150** | **399** | **33/14/19** |

## 複核欄位

- 399 列的人工決定均為 pending，人工意見均留白；來源 JSONL 的 review_status 未修改。
- AI 建議：pass 375、revise 24、reject 0；需人工特別確認 103 筆。這些是 AI 初審，不是人工核准。
- JSONL 與 CSV 各 1,000 筆且逐列對照通過；欄位、唯一 ID、family/split、R/L、8–14 回合、200 字最低長度、規則型個資／分類名稱／客服承諾掃描均通過。

## 風險項目

- 最短逐字稿：TPE1999-FORMAL-SW-0188，205 個中文字，train／FAM-SW-PEDESTRIAN-DECK；未落入固定 train 抽樣。
- 樣本中 19 筆低於 230 字但均達 200 字最低規格：TPE1999-FORMAL-SW-0060（228 字，train）、TPE1999-FORMAL-SW-0191（228 字，train）、TPE1999-FORMAL-PK-0155（226 字，train）、TPE1999-FORMAL-PK-0083（223 字，train）、TPE1999-FORMAL-PK-0047（228 字，train）、TPE1999-FORMAL-SW-0081（226 字，validation）、TPE1999-FORMAL-SW-0071（217 字，validation）、TPE1999-FORMAL-RD-0144（228 字，validation）、TPE1999-FORMAL-PK-0139（221 字，validation）、TPE1999-FORMAL-PK-0118（215 字，validation）、TPE1999-FORMAL-SC-0198（220 字，validation）、TPE1999-FORMAL-SC-0168（222 字，validation）、TPE1999-FORMAL-SW-0048（228 字，test）、TPE1999-FORMAL-RD-0196（220 字，test）、TPE1999-FORMAL-PK-0166（223 字，test）、TPE1999-FORMAL-WT-0176（229 字，test）、TPE1999-FORMAL-WT-0179（226 字，test）、TPE1999-FORMAL-SC-0160（223 字，test）、TPE1999-FORMAL-SC-0158（226 字，test）。
- 全體 499,500 對字元 3-gram Jaccard 掃描，門檻 0.72 命中 0 對；最高 0.4756，TPE1999-FORMAL-WT-0101／TPE1999-FORMAL-WT-0104。WT-0104 在樣本，WT-0101 未抽中。
- 垃圾車 validation 僅 2 個家族、test 僅 3 個家族；兩 split 各 30 筆皆已納入，但家族覆蓋範圍較窄。
- 道路縱向轉換、隆起與波狀起伏都在 test；國定假日與一般週末收運家族也同在 test。家族沒有跨 split，仍須人工確認邊界。
- 最常見開場原句重複 141 次，最常見收尾原句重複 60 次。複核時看追問順序、口語節奏及收尾是否呼應民眾補充。
- 規則掃描不能判定單一主訴、family 語意吻合、口語自然度或客服是否變相作實質案件答覆，這些仍待人工逐筆判斷。

## 來源保護

- 專案目錄不是 Git repository，無 git status 可用。
- 工作前／後 JSONL SHA-256：1dd58478b66afd901d61f50f0ae41e7341e88b7935ced845b82a7316642a367a
- 工作前／後 CSV SHA-256：5efe5ada8c304be7122c746eb6770e34e053d5d433f725f8761ede0cc99be3aa
- 雜湊一致；未修改正式 JSONL／CSV、taxonomy、frozen manifest、生成紀錄或既有驗證報告。

## 人工複核建議

- 優先查看活頁簿「風險提示」中的最短逐字稿、短篇幅樣本、最高相似對、垃圾車 family 數及相近道路／假日家族邊界。
- 在「複核資料」篩選「需人工特別確認=是」，並依實際判讀填寫人工決定與人工意見。
- AI 建議只供參考；不要將 AI pass 當成通過簽核。

## 活頁簿工作表

- 複核資料、複核摘要、抽樣清單、風險提示、家族界線、複核說明。

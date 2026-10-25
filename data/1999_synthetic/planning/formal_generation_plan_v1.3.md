# 正式 1,000 筆資料生成計畫 v1.3

狀態：已依使用者指示採納助理獨立複核決定；taxonomy 與 split manifest 已另存正式版並凍結。正式資料生成及自動驗證已於 2026-10-12 完成，Pilot 保持獨立。

## 範圍與版本

- 本次新增正式通話 **1,000 筆**，五類各 200 筆；Pilot v1.2.3 的 50 筆不計入，也不合併。
- Pilot 來源：`pilot_v1.2.3.jsonl`。四筆逐字稿依採納決定修訂；Pilot 的 `review_status` 仍為 `pending_manual_review`。
- 正式分類來源：`taxonomy_v1.3.yaml`；合併規則：`family_merge_map_v1.0.yaml`；已凍結切分：`formal_split_manifest_frozen_v1.0.yaml`。
- 新版僅新增檔案；既有草案、Pilot、複核活頁簿與決定文件不覆寫。

## 固定資料規格

- 固定角色 `R=客服`、`L=來電民眾`；客服先以中性問候開場，不在民眾說明前透露案件內容。
- 每通使用 9、11 或 13 行多輪對話（符合 8–14 行範圍），至少 200 個中文字；包含民眾描述、客服追問、民眾補充與客服自然收尾。
- 每筆只表達一個主要問題。客服只釐清與記錄，不替案件作實質回覆、不承諾處理或時程。
- 使用自然臺灣繁體中文；輪替追問順序、對話長短、補充方式、自我修正和收尾。
- 位置只保留行政區與公共空間類型；不放姓名、電話、門牌、精確地址、具名路口或可識別個資。
- 每筆 `is_synthetic=true`、`review_status=pending_manual_review`，包含必要欄位：`id`、`transcript`、`label_id`、`label_name`、`scenario_id`、`scenario_family_id`、`split`、`speaker_map`、`generator_model`、`prompt_version`。

## 唯一 ID 與切分

- ID 規則：`TPE1999-FORMAL-<CAT>-<SEQ4>`；情境 ID：`SCENARIO-FORMAL-<CAT>-<SEQ4>`。類別代碼 SW、RD、PK、WT、SC；各類序號 0001–0200。
- 70/15/15 依類別配額為 train/validation/test 各 140/30/30，全體 700/150/150。每個家族完整放在單一 split；家族內逐家族整數配額已寫在凍結 manifest，皆大於 0。
- 五類有效家族為 14／14／15／12／11，共 66。家族數分配為人行道 7/3/4、道路 7/3/4、公園 8/3/4、垃圾車 7/2/3、路面清潔 4/3/4。垃圾車調整是為讓「漏停／整段未服務／部分收運／停留過短」同在 train；validation 為 2 個家族，test 為 3 個家族。
- 道路縱向轉換、局部隆起與廣域波狀起伏全部在 test；垃圾車國定假日與一般週末家族全部在 test。條件式 merge targets 依 manifest 所列群組固定同 split。

## 批次與續跑

- 20 批、每批 50 筆。每筆在 `generation_manifest.csv` 預排 ID、label、family、split、批次與家族序號。
- 每批原始嘗試寫入 `formal_v1.0.0/raw_generated/batch_NNN_attempt_MMM.jsonl`。只有整批逐欄與對話檢查通過才寫入 `filtered_batches/batch_NNN.jsonl`；批次摘要、SHA-256、拒絕與重跑資訊記錄在 append-only `batch_log.jsonl`。彙整原始候選為 `raw_generated/formal_raw_all_attempts_v1.0.0.jsonl`。
- `checkpoint.json` 每完成一批更新一次。失敗重跑沿用原 ID、scenario ID、label、family、split，增加 attempt 記錄；不覆寫先前失敗原始輸出。
- 生成與驗證工具位於 `scripts/`。生成器使用固定種子及正式 taxonomy/manifest 作唯一來源。
- 最終原始、篩選及交付檔案分別為 `raw_generated/formal_raw_all_attempts_v1.0.0.jsonl`、`filtered/formal_filtered_v1.0.0.jsonl`、`formal_dataset_v1.0.0.jsonl` 與 `.csv`；另有 `batch_manifest.csv`、`generation_manifest.csv`、`checkpoint.json`、`batch_log.jsonl`。

## 最終驗收

- 最終 JSONL 和 CSV 各恰 1,000 列；五類各 200，逐類 split 140/30/30，全體 split 700/150/150。
- 驗證欄位、label-family 對照、ID 唯一、家族隔離、非零且精確配額、speaker map、9/11/13 行、中文字數、個資模式、類別名稱洩漏、完全重複與近似重複。
- 不合格記錄留在原始批次，重生相同預排 ID，通過後才加入 filtered/final。人工逐筆複核仍需後續完成；AI/程式檢查不等同人工簽核。

## 版本差異與限制

- v1.2 manifest 的公園 `label_name` 少了官方名稱中的「含車輛違規進入」；正式版改用 taxonomy 與 Pilot 一致的完整名稱。
- v1.2 把四個收運事件標為同一 related group，卻分散在 train/validation；正式版讓四者同在 train，配額精確後垃圾車 split 家族數改為 7/2/3。validation/test 的家族樣本數有限，人工評估時需按家族檢視。
- 本次沒有把 Pilot 改為人工通過，也沒有將生成資料的 `review_status` 設成通過。

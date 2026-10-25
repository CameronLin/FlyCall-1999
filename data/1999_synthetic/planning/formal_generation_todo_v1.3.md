# 正式 1,000 筆生成待辦 v1.3

狀態：生成完成，正式 manifest 已凍結，資料通過自動驗證。正式資料為另外新增的 1,000 筆；Pilot 50 筆維持獨立。

## 已完成

- [x] 核對採納的決定文件、來源 Pilot、taxonomy 草案、merge map 草案與 manifest 草案；來源雜湊與凍結前紀錄相符。
- [x] 建立正式 `taxonomy_v1.3.yaml`、`family_merge_map_v1.0.yaml` 與 `formal_split_manifest_frozen_v1.0.yaml`；有效家族 66 個，9 個合併目標有效，未解條件路由為 0。
- [x] 每個家族取得唯一 split 與正整數配額；每類 140/30/30、全體 700/150/150。
- [x] 完成 20 批、每批 50 筆，生成正式 JSONL/CSV、原始候選、篩選資料、批次清單、checkpoint 及 log。
- [x] 驗證欄位、ID、label/family/split、角色、中文字數、發言行數、個資格式、類別名稱洩漏、客服承諾及完全／近似重複；結果見 [`formal_v1.0.0/validation_report_v1.0.md`](formal_v1.0.0/validation_report_v1.0.md)。
- [x] Pilot v1.2.3 保持 50 筆、`split=pilot`、`pending_manual_review`；正式資料不包含 Pilot。

## 尚待人工處理

- [ ] 逐筆複核 Pilot 50 筆，人工決定欄完成前仍維持 pending。
- [ ] 逐筆複核正式 1,000 筆的自然度、單一主要問題、位置描述、情境合理性及家族界線；不得將程式驗證或 AI 意見視作人工通過。
- [ ] 若需要改稿，建立新版本並保留本版與批次原始紀錄；不可覆寫 frozen manifest 或既有來源。

## 切分註記

- 垃圾車家族 split 採 7/2/3（train/validation/test），而非草案目標 5/3/4。`waste_stop_presence` 及條件式合併的相關家族閉包共有 7 個，依家族隔離要求必須同放一個 split；其餘兩個 split 容量不足以容納，故安排 train。資料筆數仍精確為 140/30/30，且同一／易混淆家族未跨 split。
- 道路縱向轉換、局部隆起及廣域波狀起伏皆在 test；國定假日及一般週末家族皆在 test。

## 主要輸出

- 正式資料：[`formal_v1.0.0/formal_dataset_v1.0.0.jsonl`](formal_v1.0.0/formal_dataset_v1.0.0.jsonl)、[`formal_v1.0.0/formal_dataset_v1.0.0.csv`](formal_v1.0.0/formal_dataset_v1.0.0.csv)
- 凍結 manifest：[`formal_split_manifest_frozen_v1.0.yaml`](formal_split_manifest_frozen_v1.0.yaml)
- 驗證程式：[`formal_v1.0.0/scripts/validate_formal_dataset.py`](formal_v1.0.0/scripts/validate_formal_dataset.py)

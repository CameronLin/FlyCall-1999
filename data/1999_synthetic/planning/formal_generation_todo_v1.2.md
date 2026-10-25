# 正式 1,000 筆生成待辦 v1.2

狀態：未開始生成、manifest 未凍結。正式目標為另外新增 1,000 筆，五類各 200 筆；Pilot 不計入。

## 必要阻塞項目

- [ ] 完成 [`manual_review_v1.2.2.md`](manual_review_v1.2.2.md) 的 50 筆逐筆複核，明確記錄人工決定；pending 不視為 pass。
- [ ] 依人工意見修正 Pilot 草案並保存新版本；未核准前維持 pending 狀態。
- [ ] 人工核准 taxonomy 的 15 個待修訂家族界線及 10 個合併規則，確認類別權責與納入／排除規則。
- [ ] 按最終家族清單重算 split manifest；每類 140/30/30、全體 700/150/150，family 不跨 split。
- [ ] 審閱 11 家族類別的訓練量（每家族 28 筆）及每類 validation/test 各只有 3 個家族的限制。
- [ ] 人工審閱並凍結正式 manifest；現行 [`formal_split_manifest_draft_v1.1.yaml`](formal_split_manifest_draft_v1.1.yaml) 為 `draft_unfrozen`。
- [ ] 定案 prompt、模型、正式 ID／scenario_id、批次大小、PII 規則及驗證門檻。

## 可先準備、不會啟動生成

- [ ] 更新核對正式類別來源資料，確認標籤、權責及納入／排除規則。
- [ ] 準備輸出目錄、批次記錄格式及驗證腳本。
- [ ] 以空資料預演 quota／family isolation 檢查，不產生逐字稿。

## 已完成的草案檢查

- [x] 建立 v1.2.2 Pilot 草案：15 筆修訂、35 筆逐字稿保留，所有記錄維持 pending。
- [x] 建立 65 個暫列家族的 70/15/15 manifest 草案；配額與家族隔離機械核對通過。
- [x] 更新驗證報告、逐筆複核清單與檔案索引。
- [x] 未修改 v1.2.1、基準 taxonomy 或原始複核活頁簿；未開始正式生成。

任一必要阻塞項目未完成前，不得開始正式資料生成。

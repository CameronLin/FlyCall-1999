# M2.4 evaluator fixture-only 實作報告

日期：2026-10-19  
狀態：fixture-only slice complete；M2.4 ticket 仍為 `in-progress`

## 範圍與變更

- 新增 `src/flycall_data/evaluation.py`：共用純 Python precision、recall、F1、support、Macro-F1、accuracy 與固定方向 confusion matrix（列為 actual、欄為 predicted）。固定 label order 重用既有五類 taxonomy ID 順序。
- 新增 `PredictionBatch` 和 `evaluate_predictions(...)`；只接收預測、label、record ID 與 scenario-family provenance，不讀資料檔、不接收 transcript，也不載入模型。train／validation 的 record IDs 與 scenario-family 必須互斥。
- 加入 test gate：預設拒絕 test；須有鎖定候選清單、鎖定設定 fingerprint、人工複核 gate 通過及 approval reference。fixture gate 每個預先聲明 candidate 在目前 process 只可消耗一次。此記憶體內狀態不是跨程序持久化 ledger，不能單獨用於正式 test 評估。
- 加入固定順序的 Markdown renderer／writer；預設報告標示 `smoke_test/provisional`、`synthetic_fixture`、`pending_manual_review`，未解鎖 test 為 `not_run`，列出逐類指標、混淆矩陣及錯誤 record IDs。
- `embedding_pipeline.py` 與 `text_baseline.py` 改用共用 metrics helper；沒有更改既有 run/report/model artifacts。
- 新增本機 ticket：`issues/10-m2-4-evaluator-test-gate.md`。

## TDD 與驗證

先執行新測試，當時因 `flycall_data.evaluation` 不存在而失敗；實作後再執行。已知 synthetic prediction oracle 驗證 confusion matrix、逐類 precision／recall／F1、support、accuracy 與 Macro-F1；另覆蓋空預測類別、未知 label、長度錯誤、family/record 跨 split、預設 test lock、無效 unlock、有效 fixture unlock 一次性與 Markdown 輸出。

相關測試共 **24 項通過**：

| 測試範圍 | 結果 |
|---|---:|
| `test_evaluation.py` | 11 passed |
| `test_embedding_pipeline.py` | 5 passed |
| `test_text_baseline.py` | 5 passed |
| `test_embedding_logistic.py` | 3 passed |

已知 oracle 的 synthetic fixture 值包含 accuracy `0.7`、Macro-F1 `0.693333...`；它們只作單元測試預期值，**不是模型結果或正式分類成績**。test gate 測試用的是人工建立的合成 fixture，不是正式 test rows。

## 未完成／阻塞

- M2.2b E5 環境資源 gate 仍為 `blocked`；沒有下載／安裝／載入 E5、PyTorch 或其他預訓練模型。
- M2.2／M2.3 的完整候選流程尚未與共用 evaluator 整合；本次沒有正式 train／validation 評估。
- M2.4 成本欄位未量測，因為本次只評估合成 prediction fixture，沒有模型執行或訓練。
- test authorization 消耗目前是 process-local；正式的一次性 test 流程還需跨程序持久化 ledger、來源與設定核對，並等待人工複核品質 gate、模型清單及設定鎖定。
- 整體 M2.4 ticket 因正式依賴與上述 gate 未完成，保持 `in-progress`。沒有讀取正式 JSONL／CSV、Pilot、connectome 產物或正式 test rows；沒有修改資料、taxonomy、manifest 或既有結果。

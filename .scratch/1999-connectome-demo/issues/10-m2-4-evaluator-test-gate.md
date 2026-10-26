# 10: M2.4 共用評估器與 test 一次性 gate

**What to build:** 依 Demo Spec v0.2 建立跨分類候選共用的分類指標、錯誤清單、成本摘要與 provisional 報告介面，並提供明確條件及一次性消耗的 test 評估 gate。

**Blocked by:** None for provisional train/validation reporting. Durable test unlock and test evaluation remain blocked by the manual-review gate and candidate/config approval.

**Status:** in-progress (provisional reporting and durable one-use ledger are implemented and regression-tested; formal test evaluation remains gated by manual review and explicit candidate/config approval)

## 範圍

- 共用五類固定 taxonomy 順序的 precision、recall、F1、support、Macro-F1、accuracy 及 confusion matrix；矩陣列為 actual、欄為 predicted。
- 接收已產生的預測與 record/family provenance，不負責載入資料、tokenize、嵌入、訓練、選模或讀取 test rows。
- train／validation 報告標記 `synthetic_fixture` 或 `synthetic`、`pending_manual_review` 及 `smoke_test/provisional`，列出 split 筆數與錯誤 record IDs；未執行的 test 標記 `not_run`。
- 提供 Markdown 報告輸出；報告格式固定順序、可由 fixture 重現。
- test 評估須有明確 unlock：預先聲明候選清單、設定 fingerprint、人工複核品質 gate 通過及 approval reference。每個候選只可消耗一次 unlock；缺任一條件或重複執行即拒絕。fixture-only 介面不得讀正式資料。
- 後續正式使用需將 unlock/消耗狀態持久化，並在輸入邊界核對模型、設定、人工複核摘要及資料來源；本次 fixture slice 不代表正式 test 已解鎖。

## 依賴與邊界

- M2.1 loader 已完成；M2.4 不呼叫 loader，以避免在 fixture 驗證時觸及任何正式資料或 test rows。
- M2.2a train／validation smoke 與 M2.2b embedding pipeline 可提供候選預測；M2.4 只評分其輸出，不改模型或資料。
- 不修改正式 JSONL／CSV、Pilot、taxonomy、split manifest、M1.1／M1.2／M1.3 產物或既有模型結果。
- 人工複核品質 gate 未通過前不得產生正式成績或正式 test 報告；test rows、test predictions 與 test metrics 保持未讀取／`not_run`。
- 僅使用小型合成 fixture。不得下載／安裝／載入任何模型或依賴。

## TDD 測試 seam

- `PredictionBatch`: split、record IDs、scenario-family IDs、expected labels 與 predictions。
- `evaluate_predictions(train, validation, ...)`: train／validation 評估；可選 test fixture 僅在提供完整有效的 `TestEvaluationUnlock` 時通過。
- `render_markdown_report(...)`／`write_markdown_report(...)`: 固定順序的報告產生。

## 驗收條件

- [x] 已知 prediction fixture 精確驗證逐類 precision／recall／F1／support、Macro-F1、accuracy 與 confusion matrix。
- [x] 固定 taxonomy 順序即使有類別無 prediction 也保留零值欄／列，拒絕未知標籤、空輸入或長度不一致。
- [x] train／validation record ID 與 scenario-family 不重疊；split 名稱或 provenance 不符時拒絕。
- [x] 不帶 unlock 的 test fixture 在計算指標前被拒絕；條件不完整的 unlock 被拒絕；有效 unlock 對每個預先聲明候選僅可消耗一次。
- [x] Markdown fixture 報告含 provisional／synthetic／pending 標記、逐類指標、矩陣及 test `not_run`；輸出寫在測試 temporary directory。
- [x] 執行測試不載入正式資料、Pilot、connectome、test rows 或預訓練模型；無下載／安裝。
- [x] M2.2b/M2.3 provisional train/validation predictions 已透過共用 evaluator 產生固定順序 metrics、錯誤清單與 Markdown；run 記錄 embedding/model 耗時、peak working set 及磁碟變化。Test 維持 `not_run`。
- [x] Implemented a cross-process, fail-closed one-use reservation ledger with candidate/configuration fingerprints, manual-review summary, approval reference, and source SHA-256. Fixture regression coverage is complete.
- [x] 以 fixture regression coverage 驗證 ledger 的條件拒絕、跨程序重複保留、record tampering、完成／失敗記錄與重複 finalization；未驗證前不得作為正式 test 執行依據。
- [ ] 只有人工複核 gate 實際通過、候選與設定鎖定並經明確核准後，才可使用 reservation 在任何 test input 存取前消耗一次性名額並執行一次 test 評估；目前不得讀取 test transcript。

## Comments

- 2026-10-26: After the Windows runtime-resource portability fix and installation of the declared DuckDB 1.5.6 test dependency into the isolated E5 environment, complete `unittest` discovery passed 131/131 tests. This verifies the durable test-gate regression suite only; no real test rows were read and the formal one-time test reservation remains unused.
- 2026-10-26: After adding optional Streamlit `AppTest` coverage for missing-model and synthetic prediction UI states, full `unittest` discovery passed 133/133 tests. The one-time test reservation remains unused; no test rows or transcript content were read.

- 2026-10-19：依 Demo Spec v0.2 與本機 ticket 慣例建立。盤點確認之前沒有 M2.4 獨立 ticket；M2.2b 明確把共用 evaluator 與 test gate 留在本票範圍之外。尚未讀取正式資料、test rows 或模型產物。
- 2026-10-19：完成 fixture-only TDD 切片。先新增 `tests/test_evaluation.py` 並執行，因 `flycall_data.evaluation` 尚不存在而紅；新增 evaluator 後測試轉綠。共用固定 taxonomy label order 與純 Python metrics，M2.2a／M2.2b metrics 改接同一 helper。test 需要明確候選清單、設定 fingerprint、人工複核 gate 與 approval reference；fixture unlock 每候選每 process 僅能消耗一次。完整測試結果與限制見 `../research/m2-4-evaluator-fixture-report.md`。
- 本次相關測試共 24 項通過：evaluator 11、embedding pipeline 5、M2.2a text baseline 5、M2.2b Logistic fixture integration 3。只使用合成 fixtures；沒有呼叫 M2.1 loader、讀正式 JSONL／CSV／Pilot／test rows 或 connectome，沒有載入 PyTorch／E5／預訓練模型，沒有下載／安裝依賴或產生正式指標。
- （截至 2026-10-19 的歷史狀態）尚未完成 M2.4 與 M2.2／M2.3 正式候選預測整合、成本量測、持久化 test-run ledger 與人工複核 gate 後的報告；當時 M2.2b E5 gate 仍 blocked。後續狀態見以下 2026-10-26 comments。
- 2026-10-26：共用 `evaluate_predictions` 新增明確的 `data_status="synthetic"` 表示，保留 fixture 預設值。M2.2b runner 對 4 個預先登錄候選呼叫 evaluator，寫出每個候選的 train/validation Markdown、metrics、錯誤 record IDs、predictions CSV、時間及資源摘要；test input/predictions/metrics 均為 0／`not_run`。成本與 provisional integration 完成；沒有建立或消耗 durable test unlock，人工複核 gate 仍未通過，因此 ticket 維持 in-progress。
- 2026-10-26：新增跨程序 reservation ledger API 與候選清單 fingerprint 驗證；slot 以候選名稱為一次性 identity，預先原子建立記錄，失敗後仍保持消耗，支援明確記錄 completed／failed-after-reservation。沒有建立任何 ledger record，也沒有讀取 test rows。依工作環境限制，這次未新增或執行測試；ledger 回歸驗證仍是開放驗收項目，不能用來授權正式 test。


- 2026-10-26 regression closeout: the selected M2 suite passed 58/58 tests. Evaluator/ledger tests covered failed gate conditions, cross-process duplicate reservation, record checksum tampering, consuming a slot before metrics, successful/failed finalization, and preventing reuse. Test ledgers were created only in temporary directories; no formal reservation or test rows were used. The formal one-time test evaluation remains unrun until manual review passes and candidate/configuration approval is recorded.

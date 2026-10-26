# 11: M2.3 E5→LDA→Logistic Regression baseline

**What to build:** 依 spec v0.2 與使用者確認的方法契約，建立 multilingual-e5-small 384 維 embedding 上的 LDA 監督式降維及 Logistic Regression 分類流程。

**Blocked by:** None for the provisional train/validation scope; the manual-review gate still blocks formal claims and all test use.

**Status:** completed (fixed-seed E5 train/validation smoke run; synthetic data remains pending manual review; test not run)

## 依賴與邊界

- M2.1 loader 已完成；正式流程日後沿用其稽核，不另行切分資料。此 fixture-only 階段不呼叫 loader、不讀取正式資料、Pilot、connectome 產物或 test rows。
- M2.2b 提供固定 `intfloat/multilingual-e5-small` revision `614241f622f53c4eeff9890bdc4f31cfecc418b3` 的 384 維 embeddings。Windows E5 resource gate 已於 2026-10-26 通過；fixture 開發不得繞過或替代該依賴。
- M2.2a TF-IDF 不作為 M2.3 輸入。
- M2.4 evaluator 已提供固定 taxonomy 順序與 train/validation 指標；test 維持 `not_run`。
- 正式資料仍為 `pending_manual_review`。任何未通過人工複核閘門的正式 train/validation 執行只能標示 `smoke_test`／`provisional`；不得產生正式效能主張。
- 不修改正式資料、labels、split、taxonomy、Pilot、connectome 產物或既有 run。

## 方法契約

1. 輸入是 train 與 validation 的 multilingual-e5-small 384 維 embeddings，沿用既有固定五類 label 順序及 scenario-family split。
2. LDA 是監督式降維器，不是本 ticket 的分類器。以 train embeddings 與 train labels fit；輸出維度固定為 `min(4, class_count - 1)`，五類時為 4。
3. LDA 僅以已 fit 的狀態 transform train 與 validation 特徵。Validation 不得參與 LDA、分類器或其他轉換的 fit。
4. 將 LDA 轉換後的 train 特徵交給 Logistic Regression fit。Validation 只作 transform、predict 及 provisional 評估。
5. 不使用 test split；公共模型入口不得接收 test batch。Test 預測與指標保持 `not_run`。
6. 直接 LDA classifier 是不同實驗，不在本 ticket 範圍。
7. Fixture 只使用小型合成 384 維向量及合成 label／split/family metadata；不呼叫 E5 encoder 或資料 loader。

## 產物

- LDA→Logistic Regression train/validation-only 模組。
- TDD fixture tests，驗證維度、固定類別順序、可重現性、train-only fit、validation transform、family 隔離及 test 邊界。
- 本機 Markdown 實作報告，區分 fixture-only 完成項目與 E5／正式資料阻塞項目。

## 驗收條件

### Fixture-only（可執行）

- [x] 先新增 fixture 測試並確認其因功能缺少而失敗，再實作。
- [x] 384 維合成 train/validation 輸入產生 `min(4, C−1)` 維 LDA 表示；五類時為 4 維。
- [x] LDA 與 Logistic Regression 僅以 train rows/labels fit；validation 只 transform/predict。相同 train、改變 validation 特徵或 labels 不得改變 fitted train artifacts。
- [x] 固定 label 順序的分類分數、predictions 與 train/validation 指標正確；scenario_family 不跨 train/validation。
- [x] 無 test 參數或 test 資料入口；fixture test 指標狀態明確為 `not_run`。
- [x] 同一 fixture/config/seed 可重現；無效維度、缺少 train 類別、record ID 或 family overlap 明確失敗。
- [x] 使用已存在的隔離 scikit-learn/NumPy 環境；不安裝套件、不載入模型。

### E5／正式資料（provisional train/validation scope）

- [x] M2.2b 資源閘門通過後，確認 embeddings 的 model revision、384 維及來源 manifest。
- [x] 只使用既有 train/validation；以預先登錄的 seed 42 執行 provisional smoke run，輸出設定、checkpoint、指標與重現資訊。
- [x] 保存 LDA→Logistic Regression checkpoint 與設定；重載後 validation predictions 及固定順序 scores 完全一致。
- [x] 模型流程只接收 train／validation rows；test 下游 transcript、embedding、prediction 與 metrics 均為 0／`not_run`。
- [x] 資料仍待人工複核，結果標為 `smoke_test`／`provisional`；未產生正式評估結論。

## Comments

- 2026-10-21：依使用者確認建立方法契約。M2.2b E5 閘門仍 blocked；先做不接觸正式資料或模型的合成 fixture 部分。沒有以 TF-IDF 取代 E5。
- 2026-10-21：依 TDD 先加入 `tests/test_lda_baseline.py`，確認缺少 `flycall_data.lda_baseline` 時測試失敗，再實作 E5-384→LDA(4D)→Logistic Regression train/validation-only seam。六個 M2.3 fixture tests 及 M2.4 evaluator、embedding pipeline、既有 embedding Logistic Regression 相關測試共 27 項通過。沒有讀取正式資料、Pilot、connectome 產物或資料集 test rows；沒有載入模型或安裝依賴。fixture-only 已完成；E5 embeddings、正式 train/validation smoke run 與 checkpoint 驗證仍受 M2.2b 閘門阻塞。詳見 `../research/m2-3-lda-fixture-report.md`。
- 2026-10-26：M2.2b Windows resource gate 通過後，使用 384 維 E5 cache、frozen train/validation split 及 seed 42 完成 provisional LDA(4)→Logistic Regression run。checkpoint 已保存並 reload；validation predictions 與固定 label order scores 完全相同。共用 evaluator 產生 train/validation 指標與 Markdown。run manifest、source/checkpoint hashes 與資源數據見 [Windows E5 report](../research/m2-2b-e5-windows-gate-and-provisional-run-20261026.md) 及 run `m2-2b-e5-provisional-20261025T185218Z`。Test downstream input/prediction/metrics 為 0／`not_run`；資料仍 pending manual review，故本 ticket 只完成 provisional scope。

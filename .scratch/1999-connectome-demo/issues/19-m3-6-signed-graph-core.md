# 19: M3.6 固定符號、可訓練大小的圖核心

**Blocked by:** None（用 fixture 開發；接上真實符號要等工作票 18、21）

**Status:** completed (2026-11-13; fixture-tested; real signs await tickets 18 and 21)

## 背景

目前 `SparseGraphCore` 的邊權重是 `softplus(raw) + ε`（`src/flycall_data/graph_core.py`），永遠是正數，等於整張圖都是增強，沒有抑制。使用者要求：在維持架構的前提下，Fly A／Fly B 只訓練連線大小，正負號固定不變。

## 要做的事

- `SparseGraphCore` 新增可選參數 `node_signs`：每個節點一個 +1 或 −1，依 Dale's principle 由來源神經元決定該點所有出邊的符號。
- 符號存成 buffer，不是 `nn.Parameter`，不接受梯度。訊息改為 `sign[source] × (softplus(raw) + ε) × hidden[source]`；其餘運算維持不變（入度正規化、tanh、T 步、I/O 順序）。
- 沒有提供 `node_signs` 時行為與現在完全相同：現有 checkpoint、M3.2 重跑、M4 鎖定模型的輸出都要逐位元一致。
- checkpoint metadata 記錄符號向量的 SHA-256 與 ±1 數量；topology hash 要把符號納入，避免同一張圖不同符號的 checkpoint 被混用。
- 初始化：大小沿用現有 log1p 先驗；記錄抑制邊在初始化時的總量，避免 tanh 一開始就飽和或整體被壓成零。

## 驗收條件

- 測試：
  - 預設（無符號）時 logits 與修改前逐位元相同
  - 訓練後每條邊的符號與初始完全相同，大小仍嚴格非零
  - 符號 buffer 沒有梯度
  - 抑制邊確實會降低目標點的活化值（小型 fixture）
  - checkpoint 重載一致；用錯符號向量重載要明確失敗
- 不建立 dense N×N 可訓練矩陣；不新增或刪除邊。

## Comments

- 2026-11-13：完成。
  - **實作：** `SparseGraphCore(node_signs=...)` 依來源點決定邊的符號，存成 non-persistent buffer `edge_signs`（不在 `state_dict`，checkpoint 無法覆寫）。有效權重 `signed_edge_weights` = 符號 × `softplus(raw) + ε`；`edge_gains` 仍是嚴格為正的大小。`GraphDefinition` 新增可選的 `node_signs`，所以既有的訓練和載入函式不用修改就能使用。
  - **checkpoint 防呆：** 有符號時，checkpoint metadata 會記錄 `node_signs_sha256`、±1 點數與邊數，`topology_sha256` 也納入符號，因此用錯符號或用無符號圖重載都會失敗。`sign_summary()` 回報各符號的邊數與大小總和，初始化時的數值也會保存。
  - **相容性：** 沒有符號時走原本路徑，`state_dict`、metadata、topology hash 都不變。M3.2 三個 seed 的真實 Fly A／Fly B checkpoint 用新程式載入後，validation 預測都是 150/150 與存檔一致。
  - **測試：** 新增 `tests/test_signed_graph_core.py` 8 項，全部通過，涵蓋：
    - 無符號時與舊公式逐位元相同
    - 符號 buffer 不可訓練
    - 抑制輸入會降低目標點活化
    - 訓練後符號不變、大小仍為正
    - 重載一致，錯誤符號重載失敗
    - 無效符號表會被拒絕
  - **完整套件：** 157 項中 155 項通過；另 2 項是先前就有的 Streamlit fixture 問題，依使用者指示暫時跳過。

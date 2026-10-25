# 08: M3.1 小型 fixture 模型核心

**What to build:** 依已確認的 M3.0 工程契約，使用手工建立的小型有向圖與合成數值輸入，實作並驗證 Fly A／Fly B sparse recurrent graph core 與最小 forward/backward/checkpoint 路徑。此 ticket 不包含正式資料讀取、embedding 模型、正式訓練或效能評估。

**Blocked by:** 05 M1.3 I/O 可達性與 graph manifest (completed); 07 M3.0 Connectome 分類資料流與訓練契約決策 (completed)

**Status:** completed

## 範圍

- 依 `docs/research/m3-0-connectome-classifier-contract.md` v1.1 實作小型 fixture-only 模型核心；模組遵守現有 `src/flycall_data/` 慣例，測試遵守 `unittest` 慣例。
- 先寫並執行有意義的 fixture 測試，再實作。可唯讀讀取 M1.3 `io_manifest.json` 的 32 個 ordered input/output IDs；edge rows 必須是手工建立的小型 synthetic fixture，不讀取 500-node edge table。以這些 IDs 建立小型 toy graph，測試真實 manifest 座標順序但不使用正式 connectome 邊。
- 覆蓋 Fly A 的 frozen-input adapter／圖核心／ordered output、Fly A output normalization、Fly B trainable 32→32 adapter／獨立圖核心／32→5 readout。Encoder 可由測試直接注入數值向量；不載入 E5。
- 使用固定稀疏 edge list；每條存在 edge 各一個 trainable raw parameter，非邊沒有參數，自連線保留。每個 Fly 的 gains 獨立；同一 Fly 的 edge gains 在 T 個時間步共享。
- 主要 fixture 設定使用 scalar state、每步 input injection、`T=2`、`source_id→target_id` 有向傳遞與固定入度 normalization；可用相同 fixture 驗證 T=4 的 shape／運算，但不得讀取正式資料或以 test split 選擇 T。
- 不新增正式公開 API、CLI、資料 loader、embedding cache 或正式 run artifact；feasibility seam 依現有 package 慣例決定並在報告記錄。

## 明確不在範圍內

- 不讀取／載入正式 JSONL、CSV、taxonomy 或 frozen split manifest；不以 train、validation、test 資料訓練或計算指標。
- 除唯讀讀取 M1.3 I/O manifest 的有序 IDs 外，不讀取 M1.1／M1.2／M1.3 edge/node 資料；不修改其任何產物，不建立 connectome index 或子圖。
- 不下載／載入 E5、其他模型、GPU wheel；不安裝系統套件、不訓練正式模型、不產生正式 checkpoint。
- 不修改 spec v0.2、正式資料、Pilot、split、taxonomy、來源或 graph manifest。

## 核心公式與不變條件

對 fixture 的每條既有 edge `e=(u,v)`：

```text
r_e = log1p(source_weight_e)
prior_e = r_e / mean({r_j : j targets to v})
raw_e_init = inverse_softplus(prior_e - 1e-6)
gain_e = 1e-6 + softplus(raw_e)
```

`prior_e` 對每個 target 的 incoming mean 為 1；`gain_e` 初始對應該 prior。若 source weight 無效、incoming prior mean 為 0、或 `prior_e <= 1e-6` 而無法得到有限 `raw_e_init`，須明確失敗，不得改公式、加 clipping、刪 edge 或靜默替換初始化。`epsilon=1e-6`。每步以固定入度 `deg_in(v)` 聚合：`m_v=(Σ_(u→v) gain_uv*h_u)/deg_in(v)`，自連線納入 incoming edge 數；入度為 0 時聚合為 0。更新為 `tanh(m_v + x_v)`，input drive 每步加在 ordered input nodes。

契約不包含額外 per-node trainable bias。所有既有 edge gains 必須有限且嚴格為正；拓樸支援集在 optimizer update 前後完全相同。

## 預期產物

- 小型 graph core／Fly A／Fly B 模組，建議 `src/flycall_data/graph_core.py`；若實際 package 邊界需要不同位置，在 ticket comment 記錄理由。
- `tests/test_graph_core.py` fixture 測試，依 TDD 先紅後綠。
- checkpoint／reload 的最小 fixture 支援與一份 M3.1 驗證報告，記錄命令、依賴版本、fixture checksum／設定、參數量及限制。

## 驗收條件

- [x] **有向訊息傳遞：** fixture 證明訊號沿 `source_id→target_id` 傳送；反向沒有邊時不會反向傳遞；self-loop 納入 prior 與固定入度。
- [x] **T 與共享參數：** 每 node scalar state、初始狀態為 0、每一步注入 input drive、同一 edge gain 向量跨時間步共享；T=2／T=4 fixture 傳播行為通過。
- [x] **固定拓樸：** 只為 fixture edge list 中的 edge 建 parameter；非邊沒有 parameter；optimizer 更新前後 edge support 相同；既有 edge gain 有限且 `>0`。
- [x] **weight prior 與 normalization：** per-target `log1p(weight)` prior 平均為 1、epsilon／inverse-softplus 初始化符合契約、固定入度含 self-loop；無效／負／非有限 weight、零 prior mean 或 prior 不可參數化時明確失敗。
- [x] **梯度與實際更新：** Fly A、Fly B fixture loss backward 後各有有限非零 edge gradient，optimizer step 後 edge raw parameter 有實際變化。
- [x] **圖核心確實影響輸出且無捷徑：** fixture 改變必要可達 edge gain 會改變 logits；forward 實作只由 graph core output 接 readout，沒有 input-to-readout shortcut。
- [x] **Fly A/B 尺寸與 node order：** d→32、ordered 32 維輸出／輸入、32→32 adapter、32→5 logits 與固定類別順序均通過；fixture 從指定 M1.3 manifest 只讀取 `io_selection.input_node_ids`／`output_node_ids`，確認各 32 個、各自唯一、互斥，並驗證 `graph_core` 原樣保留順序。fixture edges 為合成資料。
- [x] **訓練界線：** Fly A distance-preserving loss 與 Fly B cross-entropy fixture 通過；Fly A 凍結；流程僅使用合成記憶體張量，未呼叫正式 loader 或讀取任何 split rows／指標。
- [x] **checkpoint 一致：** CPU/eval fixture 載入前後 logits 在容差內一致；metadata 記錄 node／edge 順序、topology checksum、T、weight init／aggregation、A/B 參數量與 label order；不相容設定拒絕載入。
- [x] **資源閘門：** 實測 RAM `8,589,934,592` bytes；隔離環境使用 PyTorch CPU wheel，resolver 下載 `131.29 MiB`；最終 fixture 測試峰值 RSS `290,045,952` bytes；最新可用磁碟 `23,275,204 KiB`，高於 4 GiB 保留線；未載入模型。
- [x] **報告：** `docs/research/m3-1-small-fixture-model-core-report.md` 列出命令、fixture、參數量、依賴、RSS／磁碟、TDD 與限制；無正式資料訓練、test 指標或生物學代表性主張。

## Comments

- 2026-10-16：依使用者已確認的 M3.0 v1.1 工程契約建立 ticket。Ticket 只定義小型 fixture 核心與驗收條件；本次沒有開始實作、寫測試、安裝套件、下載／載入模型或訓練。
- 2026-10-16：依使用者指示先寫 fixture 測試，紅燈確認缺少 `flycall_data.graph_core` 後新增核心；專用測試 12/12 通過。資源、套件與 fixture 細節見 `docs/research/m3-1-small-fixture-model-core-report.md`。因本次明確限制不得讀 M1.3 manifest，保留實際 32+32 manifest ID 對照項目未勾選，ticket 維持 `in-progress`；未讀正式資料／connectome 產物，未做正式訓練。
- 2026-10-16：依後續授權只讀指定 `io_manifest.json` 的 ordered I/O ID 欄位，確認 input/output 各 32 個、唯一、互斥；以實際 ID 與合成 edges 驗證 graph core、Fly A／Fly B 的節點順序和端到端 fixture logits。M3.1 專用測試 13/13 通過，所有驗收條件完成，ticket 標記 `completed`。未讀 Parquet、完整子圖或正式資料，未訓練或開始 M3.2。

# Fly A／Fly B 各自調參與四張圖比較：預註冊

日期：2026-11-13｜狀態：預註冊（執行前寫定）｜工作票：20（M3.7）、22｜範圍：train／validation only，test `not_run`

## 目的

在架構不變的前提下，讓 Fly A（降維）與 Fly B（分類）各自調到目前能做到的最好，並分開評分；再比較四張圖：

| 圖 | 內容 |
|---|---|
| G0 | 原 M1.2／M1.3 圖：500 點、2,216 邊，全部 +1 |
| G1 | 工作票 21 子圖：500 點、6,691 邊，全部 +1 |
| G2 | 同 G1 的點與邊；依傳導物質 ±1（Glu = −1） |
| G2-glu+ | 同 G2，但 Glu = +1 |

## 固定不變的部分

- 資料：M2.2b E5 快取，700 train／150 validation；用 `diagnose_fly_a_b.load_train_validation_inputs` 的 checksum 流程載入。test 不讀取。
- 架構：
  - Fly A：`FlyA`，384→32 轉接層＋圖核心（T=2），輸出 L2-normalize。
  - Fly B：`FlyB`，轉接層（輸入寬度→32）＋圖核心＋32→5 readout。
  - 帶符號的圖只訓練連線大小，符號固定（工作票 19）。
- 優化器：Adam，batch 32，gradient clip 1.0，torch threads 1。
- Fly A 先訓練、凍結，再訓練 Fly B；不聯合微調。
- 圖檔驗證：
  - G0：既有 pin（500／2,216／T=2）。
  - G1／G2／G2-glu+：比對 `signed-quota-v1.0/manifest.json` 的檔案 SHA-256、點數、邊數、32+32 I/O、T=2。

## Fly A 訓練目標（決策 D4：兩種都跑）

- `distance`：原本的距離保留損失 `distance_preserving_loss(x, z)`，不看類別。
- `distance_supcon`：距離保留損失 ＋ λ × 監督式對比損失（SupCon，Khosla et al. 2020），作用在 L2-normalize 後的 32 維輸出上。
  - λ = 1.0、溫度 τ = 0.1，固定，不調。
  - 同一 batch 內沒有同類樣本的錨點不計入；整個 batch 都沒有同類配對時，SupCon 項記為 0。

## 交叉驗證（調參不碰 validation）

- **分組 5-fold：** 依 `scenario_family_id` 分組，並依類別分層。
  - 每一類的家族先用 BLAKE2b-128（key `FlyCallM37-CV-v1`）排序。
  - 再以全域遞增計數輪流分配到 5 個 fold。
  - 同一家族只會出現在一個 fold。
- **評分方式：** 各 fold 的 held-out 預測合併成 700 筆 out-of-fold 預測，計算一個 Macro-F1。這樣某個 fold 缺少某類時也能正確計算。
- **Seeds：** 交叉驗證與最終訓練都用 42、1337、2026。交叉驗證分數取三個 seed 的平均。
- **候選學習率：** {0.001, 0.003, 0.01}。最多 200 epoch，patience 25。

### 第一階段：Fly A

- 對每張圖、每個目標、每個學習率、每個 seed、每個 fold：在 fold-train 上訓練，用 held-out fold 上的該目標損失做 early stopping。
  - `distance` 用距離損失。
  - `distance_supcon` 用合併損失；held-out 標籤來自 train split。
- 評分：凍結的 Fly A 輸出接固定 SVM（`StandardScaler` ＋ `SVC(rbf, C=1, gamma="scale")`），SVM 只在 fold-train 上 fit，預測 held-out。
- 選學習率：三個 seed 平均 OOF Macro-F1 最高者；同分取較小的學習率。

### 第二階段：Fly B

- Fly B 的三種輸入，都在各 fold 內重新產生，避免洩漏：
  - `lda`：在 fold-train 上 fit LDA(4)，再做 z-score。
  - `fly_a_distance`、`fly_a_distance_supcon`：第一階段選定學習率的同 fold、同 seed Fly A 的輸出。
- 對每個輸入、學習率、seed、fold：在 fold-train 上訓練，用 held-out 的 Macro-F1（同分取較低 loss）做 early stopping，與 M3.3 規則相同。
- 量尺：同一份 fold 輸入接 SVM 的 OOF Macro-F1。
- 選學習率：同第一階段。

### 第三階段：最終訓練與 validation（每個設定只讀一次 validation）

- 用全部 700 筆 train，以選定學習率訓練**固定 epoch 數**：交叉驗證中選定設定各 fold、各 seed 選出 epoch 的中位數（四捨五入，至少 1）。最終訓練不做 early stopping，也不看 validation。
- 最終模型在 validation 上報告：
  - Fly A→SVM（兩種目標）
  - Fly A 的 validation 距離 stress
  - LDA→SVM
  - LDA→Fly B
  - Fly A→Fly B（兩種目標）
- 報告三個 seed 的平均與樣本標準差。

## 判讀規則

- 沿用工作票 17：三個 seed 的 Δ 同號，且 |平均 Δ| ≥ 0.02，才稱為「一致」。
- 主要比較：
  - G2 − G1：加入抑制的效果
  - G2 − G2-glu+：麩胺酸符號的效果
  - `distance_supcon` − `distance`：Fly A 訓練目標的效果
  - G1 − G0：換圖的整體效果；起點、組成與邊數都不同，不歸因於單一因素
- Fly B「練到位」的標準：LDA→Fly B 與 LDA→SVM 的差距，以及 Fly A→Fly B 與 Fly A→SVM 的差距，都要報告。

## 限制

- 最終結果是 validation 數字，但設定只用 train 交叉驗證選出，validation 只讀一次，因此比工作票 17 的 s2 更接近無偏估計。不過四張圖、兩種目標仍在同一個 validation 上比較。
- 不取代 M3.4 暫定 winner 或 M4 鎖定模型。資料是合成資料，待人工複核。

## 輸出

`.scratch/1999-connectome-demo/runs/independent-tuning-20261113/`：`results.json`、`report.md`、`cv_results.json`、最終 checkpoints。

## 增補（2026-11-13，重跑前寫定）：T 步＝T 跳（工作票 23，決策 D6a）

第一次執行後發現，舊圖核心的狀態從 0 開始，T=2 實際只傳 1 跳：G0 只有 16 條邊收到梯度，32 個輸出點中有 23 個永遠為 0。使用者選擇 D6(a)：

- 新增 `input_at_step_zero=True`：狀態從 tanh(外部輸入) 開始，T=2 即傳 2 跳。舊行為保留為預設，M3.2／M4 可完全重現（已驗證 150/150）。
- 在新語意 T=2 下，四張圖的 32 個輸出點都收得到訊號（G0：1 跳 9 個、2 跳 23 個；G1／G2／G2-glu+：1 跳 20 個、2 跳 12 個）。
- **其他所有設定與上文完全相同**：資料、fold、seeds、學習率候選、epoch 上限、patience、SupCon λ／τ、選擇規則、判讀規則。
- 輸出到新資料夾 `.scratch/1999-connectome-demo/runs/independent-tuning-t-hops-20261113/`；第一次執行（舊語意）的結果保留作為對照，不刪除。
- 腦部比較分析（`scripts/compare_fly_a_fly_b_brains.py`）在新模型上重跑。

## 增補二（2026-11-13，執行前寫定）：T=4 對照（工作票 24）

- 與「增補」相同的流程與所有設定，唯一改變是圖核心步數 `steps=4`，並維持 `input_at_step_zero=True`。
- 依結構計算，T=4 時會影響輸出的連線比例：G0 76%、G1／G2／G2-glu+ 84%（T=2 時分別為 12%、8%）。
- 輸出到 `.scratch/1999-connectome-demo/runs/independent-tuning-t4-20261113/`。T=2 基準為 `runs/independent-tuning-t-hops-20261113/`。
- 比較 T4 − T2，三個 seed 配對，判讀規則同上。不在看過 T=4 結果後調整任何設定。

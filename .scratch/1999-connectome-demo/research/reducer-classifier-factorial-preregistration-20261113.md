# 降維器 × 分類器 交叉實驗預註冊

日期：2026-11-13｜狀態：預註冊（執行前寫定）｜範圍：train／validation only，test `not_run`

## 研究問題

M3.4 的 Fly A→Fly B 驗證 Macro-F1 平均 0.6601，比一般 baseline（約 0.87–0.90）低很多，但目前無法判斷差距來自 **Fly A 降維**還是 **Fly B 分類**：

- M3.5 diagnosis 用 LR／MLP probe 檢查過 Fly A 32-D 輸出（0.7958／0.7758），沒有用 SVM。
- 從來沒有把一個已知好的降維結果（LDA）交給 Fly B 分類。

本實驗把兩段拆開，交叉組合：

| 降維器 ＼ 分類器 | SVM | Fly B |
|---|---|---|
| 無（E5 384-D，參考） | E5→SVM | E5→Fly B（繞過 Fly A） |
| LDA 4-D | LDA→SVM | **LDA→Fly B**（使用者指定） |
| Fly A 32-D | **Fly A→SVM**（使用者指定） | Fly A→Fly B（重跑 M3.2 Fly B） |

## 固定設定

- 資料：既有 M2.2b E5 快取（700 train／150 validation），由 `scripts/diagnose_fly_a_b.py` 的 checksum 載入流程讀取；test 不讀取。
- Seeds：42、1337、2026。Fly A 使用各 seed 的 M3.2 checkpoint（凍結）。
- LDA：`sklearn` `LinearDiscriminantAnalysis(solver="svd", n_components=4)`，只在 train fit。之後以 train-only 平均與標準差做 z-score（SVM 與 Fly B 共用同一份 LDA 特徵）。LDA 不含隨機性，三個 seed 結果相同。
- Fly A 特徵：M3.2 Fly A 的 L2-normalized 32-D 輸出，與 M3.3 Fly B 的輸入相同，不另做縮放。
- E5 特徵：原始 L2-normalized 384-D。
- SVM：`StandardScaler`（train-only）＋ `SVC(kernel="rbf", C=1.0, gamma="scale", decision_function_shape="ovr")`，不調參。SVC 不含隨機性；Fly A→SVM 的 seed 差異只來自 Fly A checkpoint。
- Fly B：同一個 500 nodes／2,216 edges／32+32 I/O／T=2 圖；`input_adapter` 改為 `Linear(輸入寬度→32)`（Fly A 32、LDA 4、E5 384），graph core 與 `readout(32→5)` 不變。以 validation Macro-F1（同分取較低 validation loss）選 checkpoint，與 M3.3 相同。
- Fly B 訓練排程兩組，全部組合都跑：
  - `s1_m3_2_default`：Adam LR 0.001、batch 32、最多 100 epochs、patience 10、clip 1.0（等同 M3.2）。**主要結果**。
  - `s2_long`：Adam LR 0.003、batch 32、最多 200 epochs、patience 25、clip 1.0（等同 M3.5 最佳 residual 的訓練預算）。用來檢查 Fly B 是否只是訓練不足。
- 不做其他調參；不新增候選。

## 健全性檢查

- Fly A→Fly B `s1` 走原本的 `train_fly_b` 路徑，亂數順序與 M3.2 相同，預期各 seed validation Macro-F1 與 M3.2 存檔一致。若不一致，如實報告差異，不刪除結果。
- 每個 Fly B checkpoint 重載後，validation logits 最大差異必須 ≤ 1e-6。

## 判讀規則（執行前寫定）

- **降維器效果**（分類器固定）：Δ = F1(LDA→X) − F1(Fly A→X)，X ∈ {SVM, Fly B}。
- **分類器效果**（降維器固定）：Δ = F1(R→SVM) − F1(R→Fly B)，R ∈ {E5, LDA, Fly A}。
- 三個 seed 的 Δ 同號，且 |平均 Δ| ≥ 0.02，才稱為「一致的差異」；否則寫「差異不明確」。
- 以 `s1` 為主判讀；`s2` 只用來回答「Fly B 是否訓練不足」。
- 這些都是 validation 結果：設定在同一 validation set 上比較，不是無偏的最終估計，也不取代 M3.4 暫定 winner 或 M4 鎖定模型。資料仍為合成資料、待人工複核。

## 輸出

`.scratch/1999-connectome-demo/runs/reducer-classifier-factorial-20261113/`：`results.json`、`report.md`、`validation_predictions.csv`、Fly B checkpoints。

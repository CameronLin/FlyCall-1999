# 17: 降維器 × 分類器 交叉實驗（Fly A→SVM、LDA→Fly B）

**Blocked by:** None for this validation-only experiment. Formal selection and any test use remain gated by manual review and candidate/configuration approval.

**Status:** completed (validation only; three seeds; test `not_run`, 0 model inputs). Synthetic data pending manual review.

## 問題

M3.4 的 Fly A→Fly B 只有 0.6601 Macro-F1，但先前沒有把降維和分類分開測，無法判斷分數低是 Fly A 降維造成的、Fly B 分類造成的，還是兩者都有。使用者要求：

- Fly A 降維 → SVM 分類
- LDA 降維 → Fly B 分類

另外補上 E5（不降維）兩格作為參考，構成 {E5, LDA, Fly A} × {SVM, Fly B} 的完整交叉表。

## 結果（validation Macro-F1，三 seed 平均 ± 樣本 SD）

| 降維器 | SVM | Fly B s1（M3.2 預算） | Fly B s2（LR 0.003／200 ep） |
|---|---:|---:|---:|
| E5 384-D（無降維） | 0.9248 ± 0.0000 | 0.8107 ± 0.1376 | 0.9198 ± 0.0076 |
| LDA 4-D | 0.8998 ± 0.0000 | **0.8468 ± 0.0203** | 0.8646 ± 0.0273 |
| Fly A 32-D | **0.7921 ± 0.0086** | 0.6601 ± 0.0765 | 0.8040 ± 0.0218 |

粗體是使用者指定的兩格。健全性檢查：Fly A→Fly B s1 重跑後，三個 seed 都和 M3.2 存檔完全相同（差異 0）；所有 Fly B checkpoint 重載後 logits 差異 0。

## 判讀

1. **Fly A 降維是主要瓶頸。** 分類器固定為 SVM（不含隨機性，最乾淨的量尺）時，LDA − Fly A = +0.108，E5 − Fly A = +0.133，三個 seed 一致。Fly A 的 32-D 輸出約損失 0.11–0.13 的 Macro-F1。
2. **Fly B 在 M3.2 預算下訓練不足，但本身不是差的分類器。** 給 Fly B 較長的訓練（s2）後，Fly A 輸入提升 +0.144（三 seed 一致），E5 輸入提升 +0.109。在 s2 下，Fly B 和 SVM 在 Fly A 輸入上沒有明確差距（SVM − Fly B = −0.012，不明確）；在 E5 輸入上也很接近（0.920 vs 0.925）。
3. **原本 0.66 大致拆成兩段等量損失：** E5→SVM 0.925 → Fly A→SVM 0.792（Fly A 降維約 −0.13）→ Fly A→Fly B s1 0.660（Fly B 訓練不足約 −0.13）。
4. **例外：LDA→Fly B 一直低於 LDA→SVM。** s1 −0.053、s2 −0.035，三個 seed 都一致。4 維輸入經 4→32 adapter 進入圖時，Fly B 的表現不如 SVM。LDA 已把類別資訊壓到 4 維，SVM 能直接使用；Fly B 還要經過稀疏圖傳遞。

## 限制

- 全部是 validation 結果。s2 預算來自 M3.5 在同一 validation set 上的探索，因此 s2 的數字偏樂觀，不是無偏估計。
- LDA 與 SVM 不含隨機性；它們的 SD 為 0，不代表沒有不確定性。
- 不取代 M3.4 暫定 winner（MLP）或 M4 開發／展示鎖定模型。資料是合成資料，待人工複核。

## 實作

- `FlyB` 新增 `input_width`（預設 32，舊 checkpoint metadata 不變），讓 LDA 4-D 或 E5 384-D 可以接到同一個 graph core 與 readout。
- `train_fly_b` 的訓練迴圈抽成共用的 `_fit_fly_b_on_representations`；原本 Fly A 路徑的亂數順序不變（重跑結果與 M3.2 完全相同）。新增 `train_fly_b_on_features`，接受不必 L2-normalize 的降維特徵；仍然拒絕 test split。
- 新增 `src/flycall_data/reducer_classifier_factorial.py`：train-only LDA(4)＋z-score、StandardScaler＋RBF SVC、預註冊的判讀規則。
- 新增 `scripts/run_reducer_classifier_factorial.py`，沿用 `diagnose_fly_a_b.load_train_validation_inputs` 的 checksum 載入流程。
- Checkpoint 寫入加入 PermissionError 短暫重試：OneDrive 同步會鎖住剛寫好的檔案（WinError 5）。

## 產物

- 預註冊：[reducer-classifier-factorial-preregistration-20261113.md](../research/reducer-classifier-factorial-preregistration-20261113.md)
- 報告：[report.md](../runs/reducer-classifier-factorial-20261113/report.md)；`results.json`（含各類別指標、checkpoint 雜湊、source 雜湊）；`validation_predictions.csv`（4,050 列）

## 驗證

```powershell
$env:PYTHONPATH = "$PWD\src;$PWD\tests;$PWD\scripts"
& $env:FLYCALL_PYTHON -m unittest discover -s tests
& $env:FLYCALL_PYTHON scripts\run_reducer_classifier_factorial.py
```

- 新增 9 項測試（`tests/test_reducer_classifier_factorial.py`）通過；完整套件 149 項中 147 項通過。
- 另外 2 項失敗在 HEAD 上本來就存在，與這次修改無關：`test_streamlit_app` 與 `test_m4_prediction` 的 fixture predictor 沒有 `backend` 屬性，而 `app.py` 的推論解說區塊會讀取它。依使用者指示，Streamlit 部分暫時跳過。
- 整組實驗（18 次 Fly B 訓練＋9 次 SVM）在 Windows CPU 上耗時 67 秒。

## Comments

- 2026-11-13：後續工作已拆成工作票 18–22：傳導物質符號來源、固定符號圖核心、Fly A／Fly B 各自調參、300 增強＋200 抑制子圖、三張圖比較。

# Fly A／Fly B 各自調參與四張圖比較（validation）

- 預註冊：`.scratch/1999-connectome-demo/research/independent-fly-a-fly-b-tuning-preregistration-20261113.md`
- 資料：`synthetic`；複核：`pending_manual_review`；test：`not_run`（0 model inputs）
- 設定只用 train 分組 5-fold 交叉驗證選出；最終模型以固定 epoch 訓練，validation 每個模型只讀一次。
- Seeds：42, 1337, 2026；數值為 validation Macro-F1 平均 ± 樣本標準差

## Validation Macro-F1

| 組合 | G0 | G1 | G2 | G2_glu_plus |
|---|---:|---:|---:|---:|
| Fly A（distance）→ SVM | 0.8654 ± 0.0231 | 0.8549 ± 0.0295 | 0.8786 ± 0.0044 | 0.8654 ± 0.0172 |
| Fly A（distance+SupCon）→ SVM | 0.8787 ± 0.0277 | 0.9043 ± 0.0245 | 0.9028 ± 0.0395 | 0.8886 ± 0.0381 |
| LDA → SVM（參考） | 0.8998 ± 0.0000 | 0.8998 ± 0.0000 | 0.8998 ± 0.0000 | 0.8998 ± 0.0000 |
| LDA → Fly B | 0.8603 ± 0.0334 | 0.9037 ± 0.0098 | 0.8977 ± 0.0108 | 0.8980 ± 0.0035 |
| Fly A（distance）→ Fly B | 0.8569 ± 0.0161 | 0.8728 ± 0.0114 | 0.8680 ± 0.0199 | 0.8525 ± 0.0350 |
| Fly A（distance+SupCon）→ Fly B | 0.8897 ± 0.0260 | 0.9177 ± 0.0140 | 0.8770 ± 0.0217 | 0.8863 ± 0.0301 |

## 差異（三個 seed 同號且 |平均 Δ| ≥ 0.02 才算一致）

| 比較 | 組合 | 平均 Δ | 各 seed | 判讀 |
|---|---|---:|---|---|
| 加入抑制（G2 − G1） | Fly A（distance）→ SVM | +0.0237 | +0.0084, +0.0040, +0.0587 | 一致 |
| 加入抑制（G2 − G1） | Fly A（distance+SupCon）→ SVM | -0.0014 | -0.0124, +0.0225, -0.0144 | 不明確 |
| 加入抑制（G2 − G1） | LDA → Fly B | -0.0060 | -0.0063, +0.0141, -0.0257 | 不明確 |
| 加入抑制（G2 − G1） | Fly A（distance）→ Fly B | -0.0048 | +0.0138, -0.0202, -0.0078 | 不明確 |
| 加入抑制（G2 − G1） | Fly A（distance+SupCon）→ Fly B | -0.0407 | -0.0406, -0.0324, -0.0491 | 一致 |
| 麩胺酸符號（G2 − G2-glu+） | Fly A（distance）→ SVM | +0.0132 | +0.0269, +0.0127, +0.0000 | 不明確 |
| 麩胺酸符號（G2 − G2-glu+） | Fly A（distance+SupCon）→ SVM | +0.0143 | -0.0064, +0.0323, +0.0169 | 不明確 |
| 麩胺酸符號（G2 − G2-glu+） | LDA → Fly B | -0.0003 | +0.0000, +0.0074, -0.0082 | 不明確 |
| 麩胺酸符號（G2 − G2-glu+） | Fly A（distance）→ Fly B | +0.0155 | +0.0447, +0.0402, -0.0383 | 不明確 |
| 麩胺酸符號（G2 − G2-glu+） | Fly A（distance+SupCon）→ Fly B | -0.0092 | -0.0214, -0.0071, +0.0007 | 不明確 |
| 換圖整體（G1 − G0） | Fly A（distance）→ SVM | -0.0105 | +0.0220, -0.0114, -0.0422 | 不明確 |
| 換圖整體（G1 − G0） | Fly A（distance+SupCon）→ SVM | +0.0256 | +0.0527, +0.0585, -0.0344 | 不明確 |
| 換圖整體（G1 − G0） | LDA → Fly B | +0.0434 | +0.0851, +0.0130, +0.0321 | 一致 |
| 換圖整體（G1 − G0） | Fly A（distance）→ Fly B | +0.0159 | +0.0360, +0.0245, -0.0128 | 不明確 |
| 換圖整體（G1 − G0） | Fly A（distance+SupCon）→ Fly B | +0.0281 | +0.0182, +0.0662, -0.0002 | 不明確 |
| Fly A 目標（SupCon − distance），G0 | → SVM | +0.0133 | +0.0231, -0.0299, +0.0466 | 不明確 |
| Fly A 目標（SupCon − distance），G0 | → Fly B | +0.0328 | +0.0669, +0.0025, +0.0290 | 一致 |
| Fly A 目標（SupCon − distance），G1 | → SVM | +0.0494 | +0.0539, +0.0400, +0.0543 | 一致 |
| Fly A 目標（SupCon − distance），G1 | → Fly B | +0.0450 | +0.0492, +0.0442, +0.0416 | 一致 |
| Fly A 目標（SupCon − distance），G2 | → SVM | +0.0242 | +0.0331, +0.0584, -0.0188 | 不明確 |
| Fly A 目標（SupCon − distance），G2 | → Fly B | +0.0090 | -0.0052, +0.0320, +0.0003 | 不明確 |
| Fly A 目標（SupCon − distance），G2_glu_plus | → SVM | +0.0232 | +0.0665, +0.0388, -0.0357 | 不明確 |
| Fly A 目標（SupCon − distance），G2_glu_plus | → Fly B | +0.0338 | +0.0608, +0.0792, -0.0387 | 不明確 |

## 交叉驗證選出的設定

| 圖 | 項目 | 學習率 | 最終 epoch |
|---|---|---:|---:|
| G0 | Fly A distance | 0.003 | 85 |
| G0 | Fly A distance_supcon | 0.001 | 33 |
| G0 | Fly B on lda | 0.001 | 38 |
| G0 | Fly B on fly_a_distance | 0.01 | 32 |
| G0 | Fly B on fly_a_distance_supcon | 0.003 | 199 |
| G1 | Fly A distance | 0.001 | 67 |
| G1 | Fly A distance_supcon | 0.003 | 14 |
| G1 | Fly B on lda | 0.003 | 8 |
| G1 | Fly B on fly_a_distance | 0.01 | 32 |
| G1 | Fly B on fly_a_distance_supcon | 0.003 | 200 |
| G2 | Fly A distance | 0.003 | 48 |
| G2 | Fly A distance_supcon | 0.001 | 37 |
| G2 | Fly B on lda | 0.001 | 28 |
| G2 | Fly B on fly_a_distance | 0.01 | 32 |
| G2 | Fly B on fly_a_distance_supcon | 0.001 | 200 |
| G2_glu_plus | Fly A distance | 0.003 | 59 |
| G2_glu_plus | Fly A distance_supcon | 0.001 | 34 |
| G2_glu_plus | Fly B on lda | 0.003 | 10 |
| G2_glu_plus | Fly B on fly_a_distance | 0.01 | 29 |
| G2_glu_plus | Fly B on fly_a_distance_supcon | 0.01 | 200 |

## Fly A validation 距離 stress（越低越能保留距離）

| 圖 | distance | distance+SupCon |
|---|---:|---:|
| G0 | 0.0042 | 0.1616 |
| G1 | 0.0022 | 0.1814 |
| G2 | 0.0025 | 0.1636 |
| G2_glu_plus | 0.0023 | 0.1624 |

## 限制

- G1 − G0 混合起點、點組成（G0 多為無符號片段）與邊數（6,691 vs 2,216）差異，不歸因於單一因素。
- 四張圖、兩種目標在同一個 validation 上比較；資料為合成資料、待人工複核。不取代 M3.4／M4 結果。

完整交叉驗證分數、各類別指標、checkpoint 雜湊見 `results.json`。

## 每張圖的訓練時間（由 progress.log 時間戳記計算）

| 圖 | Fly A 交叉驗證 | Fly B 交叉驗證 | 最終訓練 | 合計 |
|---|---:|---:|---:|---:|
| G0 | 4 分 47 秒 | 6 分 40 秒 | 0 分 46 秒 | 12 分 13 秒 |
| G1 | 6 分 58 秒 | 13 分 21 秒 | 1 分 16 秒 | 21 分 35 秒 |
| G2 | 7 分 32 秒 | 14 分 40 秒 | 1 分 10 秒 | 23 分 23 秒 |
| G2_glu_plus | 7 分 30 秒 | 13 分 26 秒 | 1 分 12 秒 | 22 分 8 秒 |

整次執行合計 79 分 21 秒（Windows CPU，單執行緒；圖核心語意：T 步 = T 跳）。

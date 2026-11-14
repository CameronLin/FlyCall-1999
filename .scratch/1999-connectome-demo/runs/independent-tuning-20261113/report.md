# Fly A／Fly B 各自調參與四張圖比較（validation）

- 預註冊：`.scratch/1999-connectome-demo/research/independent-fly-a-fly-b-tuning-preregistration-20261113.md`
- 資料：`synthetic`；複核：`pending_manual_review`；test：`not_run`（0 model inputs）
- 設定只用 train 分組 5-fold 交叉驗證選出；最終模型以固定 epoch 訓練，validation 每個模型只讀一次。
- Seeds：42, 1337, 2026；數值為 validation Macro-F1 平均 ± 樣本標準差

## Validation Macro-F1

| 組合 | G0 | G1 | G2 | G2_glu_plus |
|---|---:|---:|---:|---:|
| Fly A（distance）→ SVM | 0.7641 ± 0.0114 | 0.8657 ± 0.0218 | 0.8876 ± 0.0275 | 0.8704 ± 0.0111 |
| Fly A（distance+SupCon）→ SVM | 0.8807 ± 0.0151 | 0.9023 ± 0.0508 | 0.9185 ± 0.0159 | 0.9097 ± 0.0357 |
| LDA → SVM（參考） | 0.8998 ± 0.0000 | 0.8998 ± 0.0000 | 0.8998 ± 0.0000 | 0.8998 ± 0.0000 |
| LDA → Fly B | 0.8576 ± 0.0321 | 0.9001 ± 0.0062 | 0.8959 ± 0.0138 | 0.9072 ± 0.0001 |
| Fly A（distance）→ Fly B | 0.7962 ± 0.0556 | 0.8588 ± 0.0373 | 0.8891 ± 0.0135 | 0.8844 ± 0.0066 |
| Fly A（distance+SupCon）→ Fly B | 0.8604 ± 0.0395 | 0.9044 ± 0.0316 | 0.9023 ± 0.0322 | 0.9220 ± 0.0033 |

## 差異（三個 seed 同號且 |平均 Δ| ≥ 0.02 才算一致）

| 比較 | 組合 | 平均 Δ | 各 seed | 判讀 |
|---|---|---:|---|---|
| 加入抑制（G2 − G1） | Fly A（distance）→ SVM | +0.0219 | +0.0269, +0.0320, +0.0069 | 一致 |
| 加入抑制（G2 − G1） | Fly A（distance+SupCon）→ SVM | +0.0162 | +0.0326, -0.0340, +0.0499 | 不明確 |
| 加入抑制（G2 − G1） | LDA → Fly B | -0.0042 | +0.0061, +0.0073, -0.0259 | 不明確 |
| 加入抑制（G2 − G1） | Fly A（distance）→ Fly B | +0.0304 | +0.0806, +0.0277, -0.0173 | 不明確 |
| 加入抑制（G2 − G1） | Fly A（distance+SupCon）→ Fly B | -0.0021 | +0.0336, -0.0269, -0.0131 | 不明確 |
| 麩胺酸符號（G2 − G2-glu+） | Fly A（distance）→ SVM | +0.0172 | +0.0391, +0.0067, +0.0057 | 不明確 |
| 麩胺酸符號（G2 − G2-glu+） | Fly A（distance+SupCon）→ SVM | +0.0088 | +0.0060, -0.0131, +0.0334 | 不明確 |
| 麩胺酸符號（G2 − G2-glu+） | LDA → Fly B | -0.0113 | -0.0070, +0.0000, -0.0269 | 不明確 |
| 麩胺酸符號（G2 − G2-glu+） | Fly A（distance）→ Fly B | +0.0048 | +0.0101, +0.0073, -0.0031 | 不明確 |
| 麩胺酸符號（G2 − G2-glu+） | Fly A（distance+SupCon）→ Fly B | -0.0197 | +0.0076, -0.0128, -0.0539 | 不明確 |
| 換圖整體（G1 − G0） | Fly A（distance）→ SVM | +0.1016 | +0.1271, +0.0741, +0.1036 | 一致 |
| 換圖整體（G1 − G0） | Fly A（distance+SupCon）→ SVM | +0.0216 | +0.0338, +0.0761, -0.0449 | 不明確 |
| 換圖整體（G1 − G0） | LDA → Fly B | +0.0425 | +0.0000, +0.0664, +0.0610 | 不明確 |
| 換圖整體（G1 − G0） | Fly A（distance）→ Fly B | +0.0626 | +0.0678, +0.0094, +0.1105 | 一致 |
| 換圖整體（G1 − G0） | Fly A（distance+SupCon）→ Fly B | +0.0440 | +0.0724, +0.0812, -0.0214 | 不明確 |
| Fly A 目標（SupCon − distance），G0 | → SVM | +0.1166 | +0.1038, +0.1019, +0.1440 | 一致 |
| Fly A 目標（SupCon − distance），G0 | → Fly B | +0.0642 | +0.0716, +0.0007, +0.1202 | 一致 |
| Fly A 目標（SupCon − distance），G1 | → SVM | +0.0366 | +0.0105, +0.1039, -0.0044 | 不明確 |
| Fly A 目標（SupCon − distance），G1 | → Fly B | +0.0456 | +0.0762, +0.0724, -0.0117 | 不明確 |
| Fly A 目標（SupCon − distance），G2 | → SVM | +0.0309 | +0.0162, +0.0379, +0.0386 | 一致 |
| Fly A 目標（SupCon − distance），G2 | → Fly B | +0.0131 | +0.0291, +0.0179, -0.0076 | 不明確 |
| Fly A 目標（SupCon − distance），G2_glu_plus | → SVM | +0.0393 | +0.0494, +0.0577, +0.0109 | 一致 |
| Fly A 目標（SupCon − distance），G2_glu_plus | → Fly B | +0.0376 | +0.0317, +0.0380, +0.0432 | 一致 |

## 交叉驗證選出的設定

| 圖 | 項目 | 學習率 | 最終 epoch |
|---|---|---:|---:|
| G0 | Fly A distance | 0.01 | 25 |
| G0 | Fly A distance_supcon | 0.001 | 52 |
| G0 | Fly B on lda | 0.003 | 22 |
| G0 | Fly B on fly_a_distance | 0.01 | 27 |
| G0 | Fly B on fly_a_distance_supcon | 0.01 | 83 |
| G1 | Fly A distance | 0.003 | 25 |
| G1 | Fly A distance_supcon | 0.003 | 23 |
| G1 | Fly B on lda | 0.001 | 58 |
| G1 | Fly B on fly_a_distance | 0.01 | 36 |
| G1 | Fly B on fly_a_distance_supcon | 0.01 | 198 |
| G2 | Fly A distance | 0.01 | 36 |
| G2 | Fly A distance_supcon | 0.001 | 44 |
| G2 | Fly B on lda | 0.01 | 5 |
| G2 | Fly B on fly_a_distance | 0.01 | 50 |
| G2 | Fly B on fly_a_distance_supcon | 0.01 | 200 |
| G2_glu_plus | Fly A distance | 0.003 | 42 |
| G2_glu_plus | Fly A distance_supcon | 0.003 | 14 |
| G2_glu_plus | Fly B on lda | 0.003 | 12 |
| G2_glu_plus | Fly B on fly_a_distance | 0.01 | 43 |
| G2_glu_plus | Fly B on fly_a_distance_supcon | 0.01 | 200 |

## Fly A validation 距離 stress（越低越能保留距離）

| 圖 | distance | distance+SupCon |
|---|---:|---:|
| G0 | 0.0074 | 0.1642 |
| G1 | 0.0031 | 0.1420 |
| G2 | 0.0031 | 0.1500 |
| G2_glu_plus | 0.0030 | 0.1535 |

## 限制

- G1 − G0 混合起點、點組成（G0 多為無符號片段）與邊數（6,691 vs 2,216）差異，不歸因於單一因素。
- 四張圖、兩種目標在同一個 validation 上比較；資料為合成資料、待人工複核。不取代 M3.4／M4 結果。

完整交叉驗證分數、各類別指標、checkpoint 雜湊見 `results.json`。

## 每張圖的訓練時間（由 progress.log 時間戳記計算）

| 圖 | Fly A 交叉驗證 | Fly B 交叉驗證 | 最終訓練 | 合計 |
|---|---:|---:|---:|---:|
| G0 | 4 分 19 秒 | 7 分 16 秒 | 0 分 25 秒 | 12 分 1 秒 |
| G1 | 5 分 47 秒 | 11 分 51 秒 | 0 分 58 秒 | 18 分 37 秒 |
| G2 | 5 分 25 秒 | 12 分 9 秒 | 0 分 58 秒 | 18 分 33 秒 |
| G2_glu_plus | 5 分 5 秒 | 12 分 59 秒 | 0 分 56 秒 | 19 分 0 秒 |

整次執行合計 68 分 13 秒（Windows CPU，單執行緒）。Fly A 交叉驗證 90 次訓練、Fly B 交叉驗證 135 次、最終訓練 15 次（每張圖）。

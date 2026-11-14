# Fly A／Fly B 各自調參與四張圖比較（validation）

- 預註冊：`.scratch/1999-connectome-demo/research/independent-fly-a-fly-b-tuning-preregistration-20261113.md`
- 資料：`synthetic`；複核：`pending_manual_review`；test：`not_run`（0 model inputs）
- 設定只用 train 分組 5-fold 交叉驗證選出；最終模型以固定 epoch 訓練，validation 每個模型只讀一次。
- Seeds：42, 1337, 2026；數值為 validation Macro-F1 平均 ± 樣本標準差

## Validation Macro-F1

| 組合 | G0 | G1 | G2 | G2_glu_plus |
|---|---:|---:|---:|---:|
| Fly A（distance）→ SVM | 0.8332 ± 0.0217 | 0.8850 ± 0.0300 | 0.8667 ± 0.0178 | 0.8704 ± 0.0139 |
| Fly A（distance+SupCon）→ SVM | 0.8927 ± 0.0210 | 0.9025 ± 0.0360 | 0.8892 ± 0.0381 | 0.9263 ± 0.0018 |
| LDA → SVM（參考） | 0.8998 ± 0.0000 | 0.8998 ± 0.0000 | 0.8998 ± 0.0000 | 0.8998 ± 0.0000 |
| LDA → Fly B | 0.8353 ± 0.0341 | 0.9025 ± 0.0108 | 0.9070 ± 0.0232 | 0.9024 ± 0.0080 |
| Fly A（distance）→ Fly B | 0.7974 ± 0.0320 | 0.8694 ± 0.0198 | 0.8528 ± 0.0262 | 0.8564 ± 0.0326 |
| Fly A（distance+SupCon）→ Fly B | 0.8386 ± 0.0765 | 0.8652 ± 0.0084 | 0.8988 ± 0.0134 | 0.9280 ± 0.0174 |

## 差異（三個 seed 同號且 |平均 Δ| ≥ 0.02 才算一致）

| 比較 | 組合 | 平均 Δ | 各 seed | 判讀 |
|---|---|---:|---|---|
| 加入抑制（G2 − G1） | Fly A（distance）→ SVM | -0.0183 | -0.0308, -0.0351, +0.0108 | 不明確 |
| 加入抑制（G2 − G1） | Fly A（distance+SupCon）→ SVM | -0.0133 | -0.0111, -0.0128, -0.0162 | 不明確 |
| 加入抑制（G2 − G1） | LDA → Fly B | +0.0044 | -0.0202, +0.0409, -0.0074 | 不明確 |
| 加入抑制（G2 − G1） | Fly A（distance）→ Fly B | -0.0166 | -0.0382, -0.0216, +0.0100 | 不明確 |
| 加入抑制（G2 − G1） | Fly A（distance+SupCon）→ Fly B | +0.0336 | +0.0310, +0.0439, +0.0258 | 一致 |
| 麩胺酸符號（G2 − G2-glu+） | Fly A（distance）→ SVM | -0.0037 | -0.0143, +0.0198, -0.0166 | 不明確 |
| 麩胺酸符號（G2 − G2-glu+） | Fly A（distance+SupCon）→ SVM | -0.0371 | -0.0260, -0.0072, -0.0781 | 一致 |
| 麩胺酸符號（G2 − G2-glu+） | LDA → Fly B | +0.0046 | -0.0136, +0.0273, +0.0000 | 不明確 |
| 麩胺酸符號（G2 − G2-glu+） | Fly A（distance）→ Fly B | -0.0036 | -0.0158, +0.0337, -0.0287 | 不明確 |
| 麩胺酸符號（G2 − G2-glu+） | Fly A（distance+SupCon）→ Fly B | -0.0292 | -0.0200, -0.0044, -0.0633 | 一致 |
| 換圖整體（G1 − G0） | Fly A（distance）→ SVM | +0.0518 | +0.0353, +0.0695, +0.0506 | 一致 |
| 換圖整體（G1 − G0） | Fly A（distance+SupCon）→ SVM | +0.0097 | +0.0044, +0.0652, -0.0404 | 不明確 |
| 換圖整體（G1 − G0） | LDA → Fly B | +0.0672 | +0.0991, +0.0181, +0.0845 | 一致 |
| 換圖整體（G1 − G0） | Fly A（distance）→ Fly B | +0.0720 | +0.0295, +0.1243, +0.0622 | 一致 |
| 換圖整體（G1 − G0） | Fly A（distance+SupCon）→ Fly B | +0.0266 | -0.0306, +0.1090, +0.0013 | 不明確 |
| Fly A 目標（SupCon − distance），G0 | → SVM | +0.0595 | +0.0631, +0.0202, +0.0952 | 一致 |
| Fly A 目標（SupCon − distance），G0 | → Fly B | +0.0412 | +0.0734, -0.0129, +0.0631 | 不明確 |
| Fly A 目標（SupCon − distance），G1 | → SVM | +0.0175 | +0.0322, +0.0160, +0.0042 | 不明確 |
| Fly A 目標（SupCon − distance），G1 | → Fly B | -0.0042 | +0.0133, -0.0282, +0.0023 | 不明確 |
| Fly A 目標（SupCon − distance），G2 | → SVM | +0.0225 | +0.0519, +0.0383, -0.0228 | 不明確 |
| Fly A 目標（SupCon − distance），G2 | → Fly B | +0.0460 | +0.0825, +0.0374, +0.0181 | 一致 |
| Fly A 目標（SupCon − distance），G2_glu_plus | → SVM | +0.0559 | +0.0635, +0.0654, +0.0386 | 一致 |
| Fly A 目標（SupCon − distance），G2_glu_plus | → Fly B | +0.0716 | +0.0867, +0.0755, +0.0526 | 一致 |

## 交叉驗證選出的設定

| 圖 | 項目 | 學習率 | 最終 epoch |
|---|---|---:|---:|
| G0 | Fly A distance | 0.001 | 62 |
| G0 | Fly A distance_supcon | 0.003 | 46 |
| G0 | Fly B on lda | 0.003 | 20 |
| G0 | Fly B on fly_a_distance | 0.01 | 53 |
| G0 | Fly B on fly_a_distance_supcon | 0.003 | 59 |
| G1 | Fly A distance | 0.003 | 85 |
| G1 | Fly A distance_supcon | 0.003 | 21 |
| G1 | Fly B on lda | 0.01 | 5 |
| G1 | Fly B on fly_a_distance | 0.01 | 26 |
| G1 | Fly B on fly_a_distance_supcon | 0.01 | 199 |
| G2 | Fly A distance | 0.001 | 70 |
| G2 | Fly A distance_supcon | 0.001 | 33 |
| G2 | Fly B on lda | 0.003 | 16 |
| G2 | Fly B on fly_a_distance | 0.01 | 30 |
| G2 | Fly B on fly_a_distance_supcon | 0.01 | 118 |
| G2_glu_plus | Fly A distance | 0.003 | 46 |
| G2_glu_plus | Fly A distance_supcon | 0.01 | 9 |
| G2_glu_plus | Fly B on lda | 0.003 | 14 |
| G2_glu_plus | Fly B on fly_a_distance | 0.01 | 19 |
| G2_glu_plus | Fly B on fly_a_distance_supcon | 0.01 | 114 |

## Fly A validation 距離 stress（越低越能保留距離）

| 圖 | distance | distance+SupCon |
|---|---:|---:|
| G0 | 0.0051 | 0.1618 |
| G1 | 0.0023 | 0.1619 |
| G2 | 0.0025 | 0.1855 |
| G2_glu_plus | 0.0021 | 0.1608 |

## 限制

- G1 − G0 混合起點、點組成（G0 多為無符號片段）與邊數（6,691 vs 2,216）差異，不歸因於單一因素。
- 四張圖、兩種目標在同一個 validation 上比較；資料為合成資料、待人工複核。不取代 M3.4／M4 結果。

完整交叉驗證分數、各類別指標、checkpoint 雜湊見 `results.json`。

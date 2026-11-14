# Fly A／Fly B 各自調參與四張圖比較（validation）

- 預註冊：`.scratch/1999-connectome-demo/research/independent-fly-a-fly-b-tuning-preregistration-20261113.md`
- 資料：`synthetic` v2.0.0；複核：`automated_qa_passed_no_manual_review`；test：`not_run`（0 model inputs）
- 設定只用 train 分組 5-fold 交叉驗證選出；最終模型以固定 epoch 訓練，validation 每個模型只讀一次。
- Seeds：42, 1337, 2026；數值為 validation Macro-F1 平均 ± 樣本標準差

## Validation Macro-F1

| 組合 | G0 | G1 | G2 | G2_glu_plus |
|---|---:|---:|---:|---:|
| Fly A（distance）→ SVM | 0.8269 ± 0.0412 | 0.8958 ± 0.0367 | 0.9042 ± 0.0105 | 0.8777 ± 0.0177 |
| Fly A（distance+SupCon）→ SVM | 0.9086 ± 0.0205 | 0.9142 ± 0.0109 | 0.9048 ± 0.0115 | 0.9312 ± 0.0105 |
| LDA → SVM（參考） | 0.9132 ± 0.0000 | 0.9132 ± 0.0000 | 0.9132 ± 0.0000 | 0.9132 ± 0.0000 |
| LDA → Fly B | 0.7362 ± 0.0679 | 0.8233 ± 0.0176 | 0.8860 ± 0.0186 | 0.9002 ± 0.0197 |
| Fly A（distance）→ Fly B | 0.8306 ± 0.0165 | 0.8827 ± 0.0308 | 0.8985 ± 0.0428 | 0.8667 ± 0.0326 |
| Fly A（distance+SupCon）→ Fly B | 0.8649 ± 0.0495 | 0.8827 ± 0.0674 | 0.8954 ± 0.0187 | 0.9020 ± 0.0268 |

## 差異（三個 seed 同號且 |平均 Δ| ≥ 0.02 才算一致）

| 比較 | 組合 | 平均 Δ | 各 seed | 判讀 |
|---|---|---:|---|---|
| 加入抑制（G2 − G1） | Fly A（distance）→ SVM | +0.0085 | +0.0585, -0.0135, -0.0196 | 不明確 |
| 加入抑制（G2 − G1） | Fly A（distance+SupCon）→ SVM | -0.0095 | -0.0124, -0.0164, +0.0005 | 不明確 |
| 加入抑制（G2 − G1） | LDA → Fly B | +0.0627 | +0.0392, +0.0970, +0.0518 | 一致 |
| 加入抑制（G2 − G1） | Fly A（distance）→ Fly B | +0.0158 | +0.0989, -0.0411, -0.0104 | 不明確 |
| 加入抑制（G2 − G1） | Fly A（distance+SupCon）→ Fly B | +0.0127 | -0.0271, -0.0021, +0.0675 | 不明確 |
| 麩胺酸符號（G2 − G2-glu+） | Fly A（distance）→ SVM | +0.0266 | +0.0334, -0.0012, +0.0475 | 不明確 |
| 麩胺酸符號（G2 − G2-glu+） | Fly A（distance+SupCon）→ SVM | -0.0264 | -0.0054, -0.0415, -0.0322 | 一致 |
| 麩胺酸符號（G2 − G2-glu+） | LDA → Fly B | -0.0142 | -0.0377, +0.0062, -0.0111 | 不明確 |
| 麩胺酸符號（G2 − G2-glu+） | Fly A（distance）→ Fly B | +0.0318 | +0.0761, -0.0325, +0.0519 | 不明確 |
| 麩胺酸符號（G2 − G2-glu+） | Fly A（distance+SupCon）→ Fly B | -0.0066 | -0.0068, +0.0345, -0.0474 | 不明確 |
| 換圖整體（G1 − G0） | Fly A（distance）→ SVM | +0.0689 | +0.0168, +0.1250, +0.0648 | 一致 |
| 換圖整體（G1 − G0） | Fly A（distance+SupCon）→ SVM | +0.0057 | +0.0418, -0.0126, -0.0122 | 不明確 |
| 換圖整體（G1 − G0） | LDA → Fly B | +0.0871 | +0.0442, +0.0634, +0.1537 | 一致 |
| 換圖整體（G1 − G0） | Fly A（distance）→ Fly B | +0.0521 | +0.0088, +0.0942, +0.0534 | 一致 |
| 換圖整體（G1 − G0） | Fly A（distance+SupCon）→ Fly B | +0.0177 | +0.0666, +0.0936, -0.1071 | 不明確 |
| Fly A 目標（SupCon − distance），G0 | → SVM | +0.0817 | +0.0467, +0.1399, +0.0583 | 一致 |
| Fly A 目標（SupCon − distance），G0 | → Fly B | +0.0343 | +0.0281, +0.0027, +0.0722 | 一致 |
| Fly A 目標（SupCon − distance），G1 | → SVM | +0.0184 | +0.0718, +0.0022, -0.0186 | 不明確 |
| Fly A 目標（SupCon − distance），G1 | → Fly B | -0.0001 | +0.0859, +0.0021, -0.0883 | 不明確 |
| Fly A 目標（SupCon − distance），G2 | → SVM | +0.0005 | +0.0009, -0.0007, +0.0015 | 不明確 |
| Fly A 目標（SupCon − distance），G2 | → Fly B | -0.0031 | -0.0401, +0.0411, -0.0104 | 不明確 |
| Fly A 目標（SupCon − distance），G2_glu_plus | → SVM | +0.0535 | +0.0397, +0.0395, +0.0812 | 一致 |
| Fly A 目標（SupCon − distance），G2_glu_plus | → Fly B | +0.0353 | +0.0428, -0.0259, +0.0889 | 不明確 |

## 交叉驗證選出的設定

| 圖 | 項目 | 學習率 | 最終 epoch |
|---|---|---:|---:|
| G0 | Fly A distance | 0.01 | 26 |
| G0 | Fly A distance_supcon | 0.003 | 26 |
| G0 | Fly B on lda | 0.001 | 51 |
| G0 | Fly B on fly_a_distance | 0.01 | 22 |
| G0 | Fly B on fly_a_distance_supcon | 0.003 | 31 |
| G1 | Fly A distance | 0.001 | 74 |
| G1 | Fly A distance_supcon | 0.01 | 8 |
| G1 | Fly B on lda | 0.01 | 6 |
| G1 | Fly B on fly_a_distance | 0.01 | 26 |
| G1 | Fly B on fly_a_distance_supcon | 0.01 | 10 |
| G2 | Fly A distance | 0.003 | 56 |
| G2 | Fly A distance_supcon | 0.003 | 15 |
| G2 | Fly B on lda | 0.01 | 6 |
| G2 | Fly B on fly_a_distance | 0.01 | 20 |
| G2 | Fly B on fly_a_distance_supcon | 0.003 | 21 |
| G2_glu_plus | Fly A distance | 0.001 | 82 |
| G2_glu_plus | Fly A distance_supcon | 0.003 | 7 |
| G2_glu_plus | Fly B on lda | 0.01 | 14 |
| G2_glu_plus | Fly B on fly_a_distance | 0.01 | 23 |
| G2_glu_plus | Fly B on fly_a_distance_supcon | 0.003 | 27 |

## Fly A validation 距離 stress（越低越能保留距離）

| 圖 | distance | distance+SupCon |
|---|---:|---:|
| G0 | 0.0167 | 0.1355 |
| G1 | 0.0035 | 0.1177 |
| G2 | 0.0038 | 0.1068 |
| G2_glu_plus | 0.0036 | 0.1234 |

## 限制

- G1 − G0 混合起點、點組成（G0 多為無符號片段）與邊數（6,691 vs 2,216）差異，不歸因於單一因素。
- 四張圖、兩種目標在同一個 validation 上比較；資料為合成資料、待人工複核。不取代 M3.4／M4 結果。

完整交叉驗證分數、各類別指標、checkpoint 雜湊見 `results.json`。

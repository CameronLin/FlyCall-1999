# Fly A／Fly B 各自調參與四張圖比較（validation）

- 預註冊：`.scratch/1999-connectome-demo/research/independent-fly-a-fly-b-tuning-preregistration-20261113.md`
- 資料：`synthetic` v2.0.0；複核：`automated_qa_passed_no_manual_review`；test：`not_run`（0 model inputs）
- 設定只用 train 分組 5-fold 交叉驗證選出；最終模型以固定 epoch 訓練，validation 每個模型只讀一次。
- Seeds：42, 1337, 2026；數值為 validation Macro-F1 平均 ± 樣本標準差

## Validation Macro-F1

| 組合 | G0 | G1 | G2 | G2_glu_plus |
|---|---:|---:|---:|---:|
| Fly A（distance）→ SVM | 0.8639 ± 0.0487 | 0.8952 ± 0.0145 | 0.9223 ± 0.0136 | 0.9132 ± 0.0136 |
| Fly A（distance+SupCon）→ SVM | 0.9261 ± 0.0057 | 0.9381 ± 0.0162 | 0.9357 ± 0.0094 | 0.9273 ± 0.0175 |
| LDA → SVM（參考） | 0.9132 ± 0.0000 | 0.9132 ± 0.0000 | 0.9132 ± 0.0000 | 0.9132 ± 0.0000 |
| LDA → Fly B | 0.8143 ± 0.0085 | 0.8793 ± 0.0178 | 0.8756 ± 0.0282 | 0.8876 ± 0.0164 |
| Fly A（distance）→ Fly B | 0.8569 ± 0.0385 | 0.8855 ± 0.0254 | 0.9006 ± 0.0195 | 0.8897 ± 0.0320 |
| Fly A（distance+SupCon）→ Fly B | 0.8789 ± 0.0646 | 0.9141 ± 0.0295 | 0.9187 ± 0.0196 | 0.8757 ± 0.0147 |

## 差異（三個 seed 同號且 |平均 Δ| ≥ 0.02 才算一致）

| 比較 | 組合 | 平均 Δ | 各 seed | 判讀 |
|---|---|---:|---|---|
| 加入抑制（G2 − G1） | Fly A（distance）→ SVM | +0.0271 | +0.0265, +0.0070, +0.0478 | 一致 |
| 加入抑制（G2 − G1） | Fly A（distance+SupCon）→ SVM | -0.0024 | -0.0067, -0.0256, +0.0252 | 不明確 |
| 加入抑制（G2 − G1） | LDA → Fly B | -0.0037 | -0.0492, +0.0332, +0.0048 | 不明確 |
| 加入抑制（G2 − G1） | Fly A（distance）→ Fly B | +0.0152 | +0.0268, -0.0052, +0.0239 | 不明確 |
| 加入抑制（G2 − G1） | Fly A（distance+SupCon）→ Fly B | +0.0046 | +0.0077, -0.0446, +0.0508 | 不明確 |
| 麩胺酸符號（G2 − G2-glu+） | Fly A（distance）→ SVM | +0.0091 | +0.0205, -0.0200, +0.0267 | 不明確 |
| 麩胺酸符號（G2 − G2-glu+） | Fly A（distance+SupCon）→ SVM | +0.0084 | -0.0067, -0.0067, +0.0387 | 不明確 |
| 麩胺酸符號（G2 − G2-glu+） | LDA → Fly B | -0.0120 | -0.0320, -0.0000, -0.0041 | 不明確 |
| 麩胺酸符號（G2 − G2-glu+） | Fly A（distance）→ Fly B | +0.0109 | +0.0487, -0.0258, +0.0099 | 不明確 |
| 麩胺酸符號（G2 − G2-glu+） | Fly A（distance+SupCon）→ Fly B | +0.0430 | +0.0350, +0.0424, +0.0516 | 一致 |
| 換圖整體（G1 − G0） | Fly A（distance）→ SVM | +0.0313 | +0.0908, -0.0131, +0.0164 | 不明確 |
| 換圖整體（G1 − G0） | Fly A（distance+SupCon）→ SVM | +0.0120 | +0.0133, +0.0331, -0.0104 | 不明確 |
| 換圖整體（G1 − G0） | LDA → Fly B | +0.0651 | +0.0779, +0.0566, +0.0608 | 一致 |
| 換圖整體（G1 − G0） | Fly A（distance）→ Fly B | +0.0286 | +0.0768, +0.0450, -0.0360 | 不明確 |
| 換圖整體（G1 − G0） | Fly A（distance+SupCon）→ Fly B | +0.0352 | -0.0147, +0.1425, -0.0222 | 不明確 |
| Fly A 目標（SupCon − distance），G0 | → SVM | +0.0622 | +0.1110, +0.0068, +0.0688 | 一致 |
| Fly A 目標（SupCon − distance），G0 | → Fly B | +0.0220 | +0.1040, -0.0566, +0.0187 | 不明確 |
| Fly A 目標（SupCon − distance），G1 | → SVM | +0.0429 | +0.0336, +0.0530, +0.0420 | 一致 |
| Fly A 目標（SupCon − distance），G1 | → Fly B | +0.0286 | +0.0124, +0.0409, +0.0325 | 一致 |
| Fly A 目標（SupCon − distance），G2 | → SVM | +0.0134 | +0.0004, +0.0205, +0.0194 | 不明確 |
| Fly A 目標（SupCon − distance），G2 | → Fly B | +0.0180 | -0.0067, +0.0014, +0.0594 | 不明確 |
| Fly A 目標（SupCon − distance），G2_glu_plus | → SVM | +0.0141 | +0.0276, +0.0072, +0.0075 | 不明確 |
| Fly A 目標（SupCon − distance），G2_glu_plus | → Fly B | -0.0140 | +0.0071, -0.0668, +0.0177 | 不明確 |

## 交叉驗證選出的設定

| 圖 | 項目 | 學習率 | 最終 epoch |
|---|---|---:|---:|
| G0 | Fly A distance | 0.003 | 60 |
| G0 | Fly A distance_supcon | 0.003 | 15 |
| G0 | Fly B on lda | 0.01 | 11 |
| G0 | Fly B on fly_a_distance | 0.01 | 30 |
| G0 | Fly B on fly_a_distance_supcon | 0.003 | 52 |
| G1 | Fly A distance | 0.001 | 84 |
| G1 | Fly A distance_supcon | 0.003 | 8 |
| G1 | Fly B on lda | 0.01 | 6 |
| G1 | Fly B on fly_a_distance | 0.01 | 21 |
| G1 | Fly B on fly_a_distance_supcon | 0.003 | 31 |
| G2 | Fly A distance | 0.01 | 58 |
| G2 | Fly A distance_supcon | 0.01 | 7 |
| G2 | Fly B on lda | 0.01 | 7 |
| G2 | Fly B on fly_a_distance | 0.01 | 23 |
| G2 | Fly B on fly_a_distance_supcon | 0.003 | 31 |
| G2_glu_plus | Fly A distance | 0.003 | 81 |
| G2_glu_plus | Fly A distance_supcon | 0.003 | 8 |
| G2_glu_plus | Fly B on lda | 0.001 | 38 |
| G2_glu_plus | Fly B on fly_a_distance | 0.01 | 20 |
| G2_glu_plus | Fly B on fly_a_distance_supcon | 0.001 | 81 |

## Fly A validation 距離 stress（越低越能保留距離）

| 圖 | distance | distance+SupCon |
|---|---:|---:|
| G0 | 0.0073 | 0.1179 |
| G1 | 0.0036 | 0.1022 |
| G2 | 0.0056 | 0.1181 |
| G2_glu_plus | 0.0038 | 0.1050 |

## 限制

- G1 − G0 混合起點、點組成（G0 多為無符號片段）與邊數（6,691 vs 2,216）差異，不歸因於單一因素。
- 四張圖、兩種目標在同一個 validation 上比較；資料為合成資料、待人工複核。不取代 M3.4／M4 結果。

完整交叉驗證分數、各類別指標、checkpoint 雜湊見 `results.json`。

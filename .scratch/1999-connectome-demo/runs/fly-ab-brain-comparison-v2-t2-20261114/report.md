# Fly A／Fly B 腦部差異分析（事後分析）

- 資料：最終 checkpoints（`.scratch/1999-connectome-demo/runs/independent-tuning-v2-t2-20261114/checkpoints`）；圖核心語意：`input_at_step_zero (T hops)`。活化與 η² 用 700 筆 train；損傷影響用 150 筆 validation。
- 這是事後分析，不做任何模型選擇；test 未讀取。資料為合成資料、待人工複核。
- 每個比較都附「同一隻換 seed」的基準：Fly A vs Fly B 要明顯低於基準，才代表任務造成的差異。

## 相似度：Fly A vs Fly B（同 seed）／Fly A 換 seed／Fly B 換 seed

| 指標 | G0 distance | G0 distance_supcon | G1 distance | G1 distance_supcon | G2 distance | G2 distance_supcon | G2_glu_plus distance | G2_glu_plus distance_supcon |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 邊的改變量 Spearman ρ | -0.08／0.70／0.73 | -0.11／0.25／0.83 | 0.02／0.63／0.55 | 0.28／0.11／0.60 | 0.05／0.29／0.62 | 0.15／0.16／0.47 | 0.02／0.50／0.50 | 0.18／0.03／0.45 |
| 加強最多的前 10% 邊重疊（Jaccard） | 0.30／0.77／0.76 | 0.31／0.55／0.79 | 0.51／0.83／0.80 | 0.66／0.63／0.84 | 0.64／0.75／0.85 | 0.67／0.70／0.81 | 0.62／0.82／0.80 | 0.65／0.65／0.79 |
| 類別選擇性 η² Spearman ρ | -0.19／0.26／-0.33 | -0.22／0.17／-0.06 | 0.14／0.36／0.58 | 0.29／0.73／0.42 | 0.23／0.44／0.43 | 0.24／0.32／0.41 | 0.40／0.45／0.45 | 0.35／0.43／0.30 |
| 平均活化強度 Spearman ρ | 0.35／0.53／0.86 | 0.72／0.75／0.92 | 0.78／0.81／0.95 | 0.88／0.90／0.96 | 0.82／0.86／0.97 | 0.83／0.82／0.96 | 0.77／0.81／0.94 | 0.85／0.84／0.95 |
| 損傷影響 Spearman ρ | 0.11／0.07／0.16 | 0.11／0.30／-0.04 | 0.05／0.23／-0.13 | 0.05／0.12／0.16 | 0.14／0.16／-0.08 | 0.07／0.06／-0.05 | -0.14／0.07／0.00 | -0.17／0.11／-0.12 |
| 最重要 20 個神經元重疊（Jaccard） | 0.30／0.39／0.36 | 0.22／0.28／0.30 | 0.19／0.24／0.12 | 0.17／0.23／0.29 | 0.24／0.29／0.25 | 0.17／0.12／0.13 | 0.27／0.29／0.28 | 0.11／0.22／0.08 |

## 兩個腦各自的特徵（三 seed 平均；Fly A／Fly B）

| 指標 | G0 distance | G0 distance_supcon | G1 distance | G1 distance_supcon | G2 distance | G2 distance_supcon | G2_glu_plus distance | G2_glu_plus distance_supcon |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 邊改變量的分散程度（SD） | 0.049／0.314 | 0.026／0.265 | 0.034／0.281 | 0.011／0.191 | 0.063／0.278 | 0.029／0.193 | 0.057／0.284 | 0.015／0.196 |
| 增強邊平均改變量 | 0.001／0.095 | -0.002／0.087 | 0.002／0.055 | 0.001／0.039 | 0.005／0.039 | 0.001／0.021 | 0.004／0.030 | 0.001／0.025 |
| 神經元 η² 中位數 | 0.318／0.699 | 0.914／0.972 | 0.200／0.784 | 0.875／0.962 | 0.297／0.727 | 0.882／0.956 | 0.176／0.778 | 0.851／0.952 |
| η² > 0.5 的神經元數 | 69.333／464.000 | 476.667／498.000 | 52.333／435.000 | 433.000／436.000 | 73.333／433.000 | 433.000／436.000 | 20.333／435.000 | 424.333／436.000 |
| 幾乎不活動（平均 \|活化\| < 0.01）的神經元數 | 406.000／2.000 | 440.667／2.000 | 401.667／88.000 | 403.000／73.667 | 279.000／112.667 | 290.333／99.000 | 370.000／117.333 | 401.333／88.000 |
| 關掉後掉 ≥ 0.02 的神經元數 | 10.667／8.333 | 3.000／2.000 | 6.667／4.333 | 3.667／3.667 | 11.667／2.667 | 1.000／4.000 | 11.667／4.333 | 2.667／2.667 |
| 平均損傷影響：輸入點 | 0.009／0.009 | 0.004／0.001 | 0.002／0.002 | 0.003／0.001 | 0.010／0.001 | 0.003／0.002 | 0.011／0.001 | 0.001／-0.001 |
| 平均損傷影響：內部點 | 0.000／0.001 | 0.000／0.000 | -0.000／0.000 | 0.000／-0.000 | 0.000／0.000 | 0.000／0.000 | 0.000／-0.000 | 0.000／0.000 |
| 平均損傷影響：輸出點 | 0.001／0.000 | 0.002／-0.000 | -0.002／0.002 | 0.001／0.002 | 0.004／-0.000 | 0.002／0.003 | 0.006／-0.001 | 0.000／-0.001 |

## 拿掉全部抑制邊後掉的 Macro-F1（Fly A→SVM／Fly A→Fly B）

| 圖 | Fly A | Fly B |
|---|---:|---:|
| G2 distance | +0.123 | +0.071 |
| G2 distance_supcon | +0.031 | +0.021 |
| G2_glu_plus distance | +0.144 | +0.068 |
| G2_glu_plus distance_supcon | +0.000 | -0.007 |

## 圖

- `G0_distance_hist_edge_change.png`
- `G0_distance_scatter_edge_a_vs_b.png`
- `G0_distance_hist_class_selectivity.png`
- `G0_distance_scatter_lesion.png`
- `G0_distance_supcon_hist_edge_change.png`
- `G0_distance_supcon_scatter_edge_a_vs_b.png`
- `G0_distance_supcon_hist_class_selectivity.png`
- `G0_distance_supcon_scatter_lesion.png`
- `G2_distance_hist_edge_change.png`
- `G2_distance_scatter_edge_a_vs_b.png`
- `G2_distance_hist_class_selectivity.png`
- `G2_distance_scatter_lesion.png`
- `G2_distance_supcon_hist_edge_change.png`
- `G2_distance_supcon_scatter_edge_a_vs_b.png`
- `G2_distance_supcon_hist_class_selectivity.png`
- `G2_distance_supcon_scatter_lesion.png`
- `summary_similarity_vs_seed_baseline.png`

## 限制

- 損傷影響在 150 筆 validation 上量測，1 筆約等於 0.007 的 accuracy，小的差異可能只是雜訊。
- Fly A 和 Fly B 的輸入不同（E5 vs Fly A 輸出），轉接層也不同；差異不全來自圖上的連線。
- Fly A 的損傷以重新 fit 的 SVM 評估；Fly B 的損傷直接用它自己的輸出層。

分析耗時 883 秒。完整數值見 `results.json`。

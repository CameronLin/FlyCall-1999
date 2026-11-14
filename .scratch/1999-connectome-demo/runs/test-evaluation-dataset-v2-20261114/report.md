# Dataset v2.0.0 一次性 test 評估（D-V2-5）

自動品質檢查通過，未經人工複核。設定在讀取 test 前以 validation 鎖定（`lock.json`），每個候選只評估一次。

- 選定的 Fly 模型（validation 規則）：`T2/G2/fly_a_distance_supcon_to_fly_b` → test Macro-F1 0.8870 ± 0.0184

| 候選 | validation Macro-F1 | test Macro-F1 (mean ± sd) | test accuracy |
|---|---:|---:|---:|
| T2/G0/lda_to_svm | 0.9132 | 0.8994 ± 0.0000 | 0.9067 |
| T2/G0/fly_a_distance_to_svm | 0.8639 | 0.7579 ± 0.0240 | 0.7822 |
| T2/G0/fly_a_distance_supcon_to_svm | 0.9261 | 0.8972 ± 0.0115 | 0.9044 |
| T2/G0/lda_to_fly_b | 0.8143 | 0.8421 ± 0.0316 | 0.8511 |
| T2/G0/fly_a_distance_to_fly_b | 0.8569 | 0.7323 ± 0.0113 | 0.7667 |
| T2/G0/fly_a_distance_supcon_to_fly_b | 0.8789 | 0.8161 ± 0.0117 | 0.8378 |
| T2/G1/lda_to_svm | 0.9132 | 0.8994 ± 0.0000 | 0.9067 |
| T2/G1/fly_a_distance_to_svm | 0.8952 | 0.8005 ± 0.0287 | 0.8244 |
| T2/G1/fly_a_distance_supcon_to_svm | 0.9381 | 0.9137 ± 0.0327 | 0.9200 |
| T2/G1/lda_to_fly_b | 0.8793 | 0.8754 ± 0.0283 | 0.8844 |
| T2/G1/fly_a_distance_to_fly_b | 0.8855 | 0.8143 ± 0.0300 | 0.8333 |
| T2/G1/fly_a_distance_supcon_to_fly_b | 0.9141 | 0.8686 ± 0.0329 | 0.8844 |
| T2/G2/lda_to_svm | 0.9132 | 0.8994 ± 0.0000 | 0.9067 |
| T2/G2/fly_a_distance_to_svm | 0.9223 | 0.7684 ± 0.0232 | 0.7978 |
| T2/G2/fly_a_distance_supcon_to_svm | 0.9357 | 0.9223 ± 0.0144 | 0.9267 |
| T2/G2/lda_to_fly_b | 0.8756 | 0.8572 ± 0.0049 | 0.8667 |
| T2/G2/fly_a_distance_to_fly_b | 0.9006 | 0.8212 ± 0.0115 | 0.8289 |
| T2/G2/fly_a_distance_supcon_to_fly_b | 0.9187 | 0.8870 ± 0.0184 | 0.8978 |
| T2/G2_glu_plus/lda_to_svm | 0.9132 | 0.8994 ± 0.0000 | 0.9067 |
| T2/G2_glu_plus/fly_a_distance_to_svm | 0.9132 | 0.7961 ± 0.0137 | 0.8200 |
| T2/G2_glu_plus/fly_a_distance_supcon_to_svm | 0.9273 | 0.9317 ± 0.0236 | 0.9356 |
| T2/G2_glu_plus/lda_to_fly_b | 0.8876 | 0.8789 ± 0.0230 | 0.8867 |
| T2/G2_glu_plus/fly_a_distance_to_fly_b | 0.8897 | 0.8034 ± 0.0272 | 0.8244 |
| T2/G2_glu_plus/fly_a_distance_supcon_to_fly_b | 0.8757 | 0.8939 ± 0.0134 | 0.9044 |
| T4/G0/lda_to_svm | 0.9132 | 0.8994 ± 0.0000 | 0.9067 |
| T4/G0/fly_a_distance_to_svm | 0.8269 | 0.7355 ± 0.0643 | 0.7711 |
| T4/G0/fly_a_distance_supcon_to_svm | 0.9086 | 0.8505 ± 0.0534 | 0.8644 |
| T4/G0/lda_to_fly_b | 0.7362 | 0.7776 ± 0.0529 | 0.7889 |
| T4/G0/fly_a_distance_to_fly_b | 0.8306 | 0.7463 ± 0.0527 | 0.7778 |
| T4/G0/fly_a_distance_supcon_to_fly_b | 0.8649 | 0.7514 ± 0.0157 | 0.7733 |
| T4/G1/lda_to_svm | 0.9132 | 0.8994 ± 0.0000 | 0.9067 |
| T4/G1/fly_a_distance_to_svm | 0.8958 | 0.7783 ± 0.0347 | 0.8133 |
| T4/G1/fly_a_distance_supcon_to_svm | 0.9142 | 0.9010 ± 0.0250 | 0.9089 |
| T4/G1/lda_to_fly_b | 0.8233 | 0.8523 ± 0.0128 | 0.8622 |
| T4/G1/fly_a_distance_to_fly_b | 0.8827 | 0.7945 ± 0.0254 | 0.8222 |
| T4/G1/fly_a_distance_supcon_to_fly_b | 0.8827 | 0.8677 ± 0.0124 | 0.8778 |
| T4/G2/lda_to_svm | 0.9132 | 0.8994 ± 0.0000 | 0.9067 |
| T4/G2/fly_a_distance_to_svm | 0.9042 | 0.7991 ± 0.0202 | 0.8222 |
| T4/G2/fly_a_distance_supcon_to_svm | 0.9048 | 0.8961 ± 0.0106 | 0.9044 |
| T4/G2/lda_to_fly_b | 0.8860 | 0.8873 ± 0.0212 | 0.8956 |
| T4/G2/fly_a_distance_to_fly_b | 0.8985 | 0.8025 ± 0.0551 | 0.8289 |
| T4/G2/fly_a_distance_supcon_to_fly_b | 0.8954 | 0.9079 ± 0.0176 | 0.9156 |
| T4/G2_glu_plus/lda_to_svm | 0.9132 | 0.8994 ± 0.0000 | 0.9067 |
| T4/G2_glu_plus/fly_a_distance_to_svm | 0.8777 | 0.7853 ± 0.0458 | 0.8156 |
| T4/G2_glu_plus/fly_a_distance_supcon_to_svm | 0.9312 | 0.9495 ± 0.0040 | 0.9511 |
| T4/G2_glu_plus/lda_to_fly_b | 0.9002 | 0.8797 ± 0.0126 | 0.8889 |
| T4/G2_glu_plus/fly_a_distance_to_fly_b | 0.8667 | 0.7862 ± 0.0779 | 0.8044 |
| T4/G2_glu_plus/fly_a_distance_supcon_to_fly_b | 0.9020 | 0.9043 ± 0.0340 | 0.9111 |
| e5_logistic_regression |  | 0.7908 ± 0.0000 | 0.8267 |
| e5_mlp |  | 0.8446 ± 0.0000 | 0.8600 |
| e5_lda_logistic |  | 0.8908 ± 0.0000 | 0.9000 |

# M1.3 I/O 可達性檢查

狀態：`passed`

輸入只讀自封存的 MaleCNS v1.0 `engineering-demo-v1.0` 子圖。
I/O IDs 是合成工程端點，不代表神經元身分或生物學功能。

- Input nodes：32
- Output nodes：32
- T：4
- 方向：`source_id -> target_id`
- Weight 語意：Published segment-to-segment connection weight; source documentation describes it as the number of connections/postsynaptic densities, not calibrated synaptic efficacy. M1.1 retains int64 and globally sums duplicate directed pairs.；本檢查不把 weight 當作路徑成本。
- 有向邊列數：2216
- 可達 outputs：32/32
- 不可達 output IDs：[]
- Selection salt：`FlyCallM13-IO-v1`
- Unreachable policy：不重選、不增加 T，明確停止並記錄結果。

## Output 最短有向 hop

| Output node ID | Shortest hops from any input |
|---:|---:|
| 12440 | 1 |
| 18564 | 1 |
| 19123 | 2 |
| 21806 | 1 |
| 23044 | 1 |
| 23353 | 2 |
| 28537 | 1 |
| 33704 | 2 |
| 41989 | 2 |
| 72432 | 1 |
| 89422 | 1 |
| 97249 | 2 |
| 101099 | 1 |
| 198311948 | 2 |
| 388055699 | 2 |
| 397832802 | 2 |
| 410400468 | 2 |
| 492128127 | 2 |
| 523478128 | 2 |
| 563624867 | 2 |
| 567186674 | 2 |
| 615553874 | 2 |
| 674221890 | 1 |
| 727874291 | 2 |
| 732156618 | 2 |
| 756414572 | 2 |
| 782476408 | 2 |
| 813624297 | 2 |
| 815889974 | 2 |
| 922096505 | 2 |
| 931114962 | 2 |
| 1026342716 | 2 |

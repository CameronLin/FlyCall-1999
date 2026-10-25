# 05: M1.3 I/O 可達性與 graph manifest

**What to build:** 在已驗證的 M1.2 engineering-demo 子圖上，選擇互不重疊的 input/output node IDs，檢查每個 output 是否能沿有向邊在指定步數內由至少一個 input 到達，並產生可重現的 I/O graph manifest。

**Blocked by:** 04 M1.2 確定性子圖選取與可行性驗證 (completed)

**Status:** completed (2026-10-16)

## Scope

- 唯讀使用 `data/connectome/derived/malecns_v1.0/subgraphs/engineering-demo-v1.0/` 中的 `nodes.parquet`、`edges.parquet` 與 `manifest.json`。開始時核對 schema 與 SHA-256；不得改寫 M1.2、M1.1 或 MaleCNS 原始檔。
- 將 M1.1 node ID 視為 endpoint IDs；不得推論神經元身分、腦區、感覺／運動功能或生物學角色。I/O 是此 engineering demo 的計算端點選擇。
- 以可重現、明確記錄的規則選擇 input 與 output 節點。Spec v0.2 的初始配置為各 32 個、`T=4`；這是可調整的工程起始值，不是已驗證的生物學設定。input/output 集合須互斥且所有 ID 都存在於子圖。
- 可達性依 `source_id -> target_id` 方向計算；每個 output 必須能在 1 至 `T` 條有向邊內，從至少一個 input 到達。不得將無向 BFS 的弱連通當成有向可達性。
- 若任一 output 不可達，須按預先寫明且可重現的調整／重選規則再試，或停止並明確報告失敗；不得靜默更換節點或增加 `T`。
- 輸出 I/O 選擇規則、seed/salt（若適用）、input/output IDs、`T`、方向、連通／可達摘要、來源與輸出 checksum，以及所有調整紀錄。
- 不開始 M1.3 以後的模型、訓練、分類器或正式實驗；不修改 1999 案件資料。

## Dependencies

- M1.2 完成，並提供已驗證的 500-node engineering-demo graph 與 provenance manifest。
- M0.1、M1.1 的官方來源與有向 edge 契約沿用既有紀錄；本 ticket 不重做來源查核或匯入。

## Planned artifacts

- 有向 T-step 可達性 helper 及小型 Parquet fixture tests。
- `io_manifest.json` 與簡短結果報告，記錄輸入 graph checksum、I/O node IDs、選擇規則、`T`、方向、逐 output 可達結果及輸出 checksum。
- 若依規則重選或調整 `T`，記錄初始結果、調整理由與最終設定；不可刪除失敗紀錄。

## Acceptance conditions

- [x] Loader 僅讀取 M1.2 engineering-demo 子圖，驗證 nodes/edges schema、manifest 對應關係及來源 checksum；M1.2 archive checksums 前後相同。M1.1 原始檔前後 checksum：**不適用**；本任務未讀取 M1.1，來源完整性依 M1.2 manifest provenance 核對。不得描述成已重新驗證 M1.1 原始檔。
- [x] Input/output node selection deterministic and reproducible; selection rule and salt are recorded, sets are disjoint, and every ID exists in `nodes.parquet`.
- [x] Fixture tests verify directed edge orientation, reachability at and beyond the `T` boundary, multiple inputs, disjoint-set enforcement, missing IDs, and an unreachable output.
- [x] For the accepted configuration (32 input IDs, 32 output IDs, `T=4`), every output is reachable from at least one input within `T` directed steps; no adjustment was required.
- [x] Manifest records I/O IDs, `T`, source-to-target direction, selection rule, per-output reachability summary, graph/source/output checksums, and adjustment policy.
- [x] No model, training, classifier, dense adjacency matrix, or case-data changes are introduced; endpoint IDs are not described as biologically typed nodes.

## Comments

- 2026-10-15: Created after M1.2 reproducibility verification and engineering-demo archive. This ticket defines I/O reachability only; it does not implement it.
- 2026-10-15: M1.3 preflight completed read-only. The ticket defines the behavior and acceptance cases, but does not define a public test seam for deterministic I/O selection and directed T-step reachability. The repository TDD skill requires the seam to be confirmed before tests are written. Proposed seams are `select_io_nodes(node_ids, input_count=32, output_count=32, salt=...)` and `check_io_reachability(edges, input_ids, output_ids, max_steps=4)`; no tests or implementation have been added pending confirmation. See `../research/m1-3-preflight.md`.
- 2026-10-16: User confirmed the two test seams. Implemented deterministic BLAKE2b-128 hash-priority I/O selection and directed multi-source T-step BFS. All 11 focused fixtures pass; the archived 500-node graph produced 32/32 reachable outputs at T=4. See `../research/m1-3-io-reachability-report.md` and `.scratch/1999-connectome-demo/m1-3/engineering-demo-io-v1.0-20261016/`.
- 2026-10-16: At the end of the implementation pass, status remained `in-progress` because the original acceptance text requested a fresh M1.1 checksum. The user then clarified that M1.1 is out of scope and directed that this check be marked not applicable, with provenance checked against M1.2 records instead.
- 2026-10-16: Compared the M1.3 manifest's M1.1 source/edges/nodes provenance hashes with the M1.2 archived manifest and M1.2 research record; values match. Recomputed only the three archived M1.2 artifact checksums and confirmed they match the M1.3 before/after values. M1.1 was not read or rehashed. All revised acceptance conditions pass; status set to `completed`.

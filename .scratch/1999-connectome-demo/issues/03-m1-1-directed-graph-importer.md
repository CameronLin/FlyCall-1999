# 03: M1.1 有向圖匯入器

**What to build:** 將 M0.1 選定的 MaleCNS v1.0 connectivity Feather 唯讀匯入獨立的標準 edge/node Parquet 表，供後續 M1.2 使用。不得下載其他來源、加入未選定資料表、開始子圖選取、模型／分類器或正式實驗。

**Blocked by:** None

**Status:** completed (2026-10-13)

## Confirmed contract (2026-10-13)

- M0.1 已完成；來源固定為 `data/connectome/malecns_v1.0/connectome-weights-male-cns-v1.0-minconf-0.5.feather`，generation `1780494887545976`、size `1,051,241,946` bytes、SHA-256 `e35da783d1c686b2b58b3b87cd6a403ae43bfcfba8bff28e08ef752c1a56afc1`。
- Feather 原檔唯讀，不覆寫、不搬移、不複製整份來源檔。衍生資料只寫入 `data/connectome/derived/malecns_v1.0/`。
- `body_pre -> source_id`、`body_post -> target_id`、`weight -> weight`；三欄均為 int64。`nodes.parquet` 以 `node_id:int64` 儲存 source／target endpoints 的去重集合。使用「node」一詞，不宣稱 endpoint IDs 全是神經元，也不衍生來源未提供的 region／cell_type。
- `import_manifest.json` 記錄來源檔名、generation、來源 SHA-256、來源列數、輸出 edge/node 數、PyArrow 版本、輸出校驗值與匯入規則。
- 全資料集重複 `(source_id,target_id)` 的 weight 加總，即使重複項跨 record batches；保留自連線，不追加篩選。
- 公開 seam：`iter_normalized_edges(path, batch_rows)` 逐批映射來源欄位並保留輸入列；跨批重複 pair 聚合由 `write_standard_tables(source_path, output_dir, batch_rows)` 負責。
- `minconf-0.5` 精確 upstream predicate 仍未知；不推論、不追加第二層篩選。

## Scope

- 以 PyArrow IPC Feather reader 逐批驗證 schema、空值及正整數 weight，並無損映射 int64 endpoint IDs。
- 用 DuckDB 有界記憶體與磁碟 spill 全域彙整跨批重複 pairs；記錄版本、memory limit、批次設定、估計與實際暫存磁碟需求。
- 在寫衍生檔前檢查可用磁碟與保守空間估算；空間不足時不建立半成品。以 staging directory 寫檔，成功後再原子發布；失敗時清除本次 staging。
- 全量完成後檢查來源列數、聚合 edge/node 數、總 weight、輸出 schema、manifest 和來源檔執行前後 size/SHA-256。

## Planned artifacts

- 唯讀匯入模組，提供上述兩個函式及可讀的明確錯誤。
- `data/connectome/derived/malecns_v1.0/edges.parquet`、`nodes.parquet`、`import_manifest.json`。
- 小型 Arrow/Feather fixture 測試：欄位方向映射、跨 batch 重複加總、自連線保留、nodes 去重、空值／錯誤 schema 明確失敗、輸出 schema。
- 最小依賴檔，列實際安裝及通過測試的 PyArrow 與用於外部聚合的 DuckDB 版本。
- 可重跑的全量匯入與驗證紀錄，包含命令、資源估算／實際暫存量、輸出筆數與 hash、來源前後 hash。

## Acceptance conditions

- [x] Feather 原檔未改動／移動；執行前後 size、generation、SHA-256 符合以上固定值。
- [x] 公開介面符合 `iter_normalized_edges(path, batch_rows)` 和 `write_standard_tables(source_path, output_dir, batch_rows)`；前者保留來源列，後者負責全域聚合。
- [x] 151,856,684 rows 逐批處理，不整批載入 RAM；磁碟中介方法、磁碟預檢與資源需求有文件記錄。
- [x] `edges.parquet` schema 恰為 `source_id:int64,target_id:int64,weight:int64`；`nodes.parquet` schema 恰為 `node_id:int64` 且 IDs 唯一、等於所有 endpoints 的集合。
- [x] 跨任意 record batch 邊界的重複 pairs 正確加總，自連線保留；空值、錯誤欄位／型別、非正 weight 明確失敗，不靜默修補。
- [x] 小型 fixture 測試涵蓋指定契約；來源 hash 不變測試通過。
- [x] 全量 edge/node 數、聚合 weight、輸出 manifest／schema／checksum 驗證通過；沒有額外信心篩選或 1999 資料變更。
- [x] 所有驗收條件通過後標記 `completed`。

## Discovery evidence (2026-10-13)

- 使用 Arrow IPC file reader 逐 record batch 掃描；共 2,318 batches、151,856,684 rows。欄位為 `body_pre:int64`、`body_post:int64`、`weight:int64`；全欄空值數為 0；weight min/max 為 1/2,591；非正 weight rows 為 0；自連線為 123 rows。此前未計算全檔重複 pair 數；本次匯入須完整計算並聚合。
- 官方下載頁說明資料為 segment-to-segment connectivity；neuPrint query 文件區分 upstream/downstream。映射方向採已確認的 `body_pre -> source_id`、`body_post -> target_id`。端點語意仍以 node 表達。
- M0.1 的 exact `minconf-0.5` upstream predicate 仍未知；本匯入不得推論或追加篩選。

## Comments

- 2026-10-13：使用者確認輸出 schema、路徑、方向映射、自連線與全域重複加總規則、公開 seam、原始檔唯讀、依賴、測試及全量驗證要求。M1.1 可依此實作；不開始 M1.2。
- 2026-10-13：SQLite fixture 與初次全量嘗試發現逐列 upsert 吞吐不足；未發布任何輸出，已清除 staging。實作改採固定 2 GiB memory limit 的 DuckDB 外部 group-by，並在 fixture 通過後重跑全量。DuckDB 1.5.6 是專為受控磁碟 spill 聚合新增的直接依賴。
- 2026-10-13：資源複核實測實體 RAM 8,589,934,592 bytes；`sysctl` 需以 elevated read-only command 執行。4-thread 全量結果在複核開始前已完成，已按原雜湊保留在 `.scratch/1999-connectome-demo/m1-1-resource-audit-unapproved-threads-4/`，未刪除。改為 2 GiB／2 threads 後重跑，完整 Parquet 串流驗證及 15 項單元測試通過。詳細結果見 `.scratch/1999-connectome-demo/research/m1-1-import-report.md`。

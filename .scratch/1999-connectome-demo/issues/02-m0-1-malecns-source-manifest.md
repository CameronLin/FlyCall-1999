# 02: M0.1 MaleCNS 資料來源 manifest

**What to build:** 研究者能依可追溯、可重跑的來源紀錄取得並理解 MaleCNS v1.0 所需的連線資料；來源檔、欄位語意或使用條件未確認時，真實 connectome 流程會明確停止。

**Blocked by:** None

**Status:** completed

- [x] 比較官方提供的 API 與 bulk connectivity 資料取得方式，選定本專案使用的一種可重現路徑，並保留官方來源與 release 資訊。
- [x] 建立機器可讀來源 manifest，記錄官方 URL、版本、取得日期、授權與完整 attribution、存取步驟、使用的檔案或 API、資料檔 SHA-256，以及 neuron／connection 欄位定義。
- [x] 明確記錄 source → target 方向、connection weight 的欄位與語意、信心欄位及最低信心篩選；若不適用篩選，記錄原因，不推定欄位含義。
- [x] 提供小量 API probe 或資料下載步驟，使另一位執行者可依 manifest 重跑並核對結果與 checksum。
- [x] 只取得建立連線圖所需資料，不下載不需要的影像資料。
- [x] 來源存取與 CC BY 4.0 授權已由官方來源確認；未以隨機圖或其他來源替代 MaleCNS v1.0。

## Comments

- 2026-10-13: 選定 MaleCNS 官方 public GCS bulk Feather `connectome-weights-male-cns-v1.0-minconf-0.5.feather`，供未來全圖用途。記錄位置：`data/connectome/malecns_v1.0/source_manifest.yaml`；官方來源分析：`docs/research/m0-1-malecns-v1.0-source-research.md`。
- 已完成 pinned-generation HEAD 與首尾各 65,536 bytes 的 range probe，檢查 Feather magic 並從實際首段 metadata 讀得 `body_pre`, `body_post`, `weight`（均 int64；metadata row count 151,856,684）。range SHA-256 與 GCS MD5/CRC32C 見 `data/connectome/malecns_v1.0/probe_result_v1.0.json`。重跑命令與驗證邏輯見 `data/connectome/malecns_v1.0/probe_bulk_range.py`。
- 目前未下載完整 1,051,241,946-byte 物件，因此完整物件 SHA-256 仍為待辦；manifest 不以 ETag、MD5、CRC32C 或 range hash 冒充完整 SHA-256。此項完成前 ticket 保持 in-progress。
- `minconf-0.5` 是所選官方 artifact 的發布篩選；官方下載頁未公開其精確 upstream comparator。記錄為未確認，不另加推測性篩選。M1 前需解碼小批資料確認實際 edge row 與 weight 解讀。
- 未下載影像、未做 M1 圖匯入或子圖實作，未讀寫案件資料。
- Follow-up 2026-10-13（以下更新 supersedes 前述「完整物件未下載」的當時狀態）：已使用 query `generation=1780494887545976` 及 `x-goog-if-generation-match: 1780494887545976` 下載官方完整物件。HTTP 回應 generation 為 `1780494887545976`、Content-Length 為 `1051241946`；本機 `stat` 同樣為 `1051241946` bytes。完整檔 SHA-256：`e35da783d1c686b2b58b3b87cd6a403ae43bfcfba8bff28e08ef752c1a56afc1`。完整命令、檔案位置及日期記錄於 `data/connectome/malecns_v1.0/source_manifest.yaml` 和 `docs/research/m0-1-malecns-v1.0-source-research.md`。
- 下載後僅計算完整檔案 SHA-256 與大小，未解析或轉換 edge 列；`minconf-0.5` 精確 predicate 仍依官方資訊記為未確認，不套用第二層篩選。M0.1 驗收條件均已完成；edge 列語意驗證留給 M1.1。

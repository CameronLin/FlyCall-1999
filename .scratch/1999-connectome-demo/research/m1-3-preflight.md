# M1.3 唯讀預檢

日期：2026-10-15
狀態：等待測試 seam 確認；未開始實作

## 已讀文件與範圍

依序檢查專案 `AGENTS.md`、M1.3 ticket、`1999-connectome-demo-spec-v0.2.md`，並參照本機 issue tracker/domain 慣例。M1.3 使用唯讀輸入：

`data/connectome/derived/malecns_v1.0/subgraphs/engineering-demo-v1.0/`

Ticket 定義 32 個 input、32 個 output、`T=4` 的初始工程配置；I/O IDs 必須互斥並存在於 nodes，且每個 output 須沿 `source_id -> target_id` 有向邊在 1 至 T 步內從至少一個 input 到達。不可達時須依預先記錄的確定規則調整，或明確停止。不可改 M1.1/M1.2 輸入，不可開始訓練或分類器。

## 資源與輸入完整性

- 實體 RAM：8,589,934,592 bytes（8 GiB），以 `sysconf(SC_PHYS_PAGES) * sysconf(SC_PAGE_SIZE)` 實測。
- 專案與 demo 所在磁碟可用空間：19,414,962,176 bytes（`df -k` 回報 18,959,924 個 1,024-byte blocks）。
- 相關程序：以唯讀 `ps -axo pid,etime,command` 檢查；除檢查命令本身外，沒有 M1.3/connectome 工作程序。
- 封存 demo 目錄大小：116 KiB。
- 輸入 SHA-256：
  - `manifest.json`: `5300c6cefdc6b84a854545e64f4131baa3fc42f0bde97a83f68fcc1c3769cf40`
  - `nodes.parquet`: `a8ad1e6a42c0a386d4bdef517ac628c29a5b7b8f023c51b43cce8e0354087428`
  - `edges.parquet`: `afa69be2078eaf136d00511539145dc82ea54af5aa2f52ffdcb87501488e2175`
- 三個檔案雜湊與 `manifest.json` 記錄一致。沒有讀取、寫入或重跑 M1.2；沒有碰 M1.1 Parquet、1999 資料、taxonomy 或 split manifest。

## 停止原因與待確認 seam

Ticket 和 spec 已定義 I/O 的語意與驗收行為，但沒有指定可測試的程式介面。依本專案採用的 TDD skill，寫測試前必須先向使用者確認測試 seam。因此尚未建立測試或實作。

提議的最小公開 seams：

1. `select_io_nodes(node_ids, input_count=32, output_count=32, salt=...)`：使用固定 hash-priority，回傳互斥且可重現的 input/output ID 集合。
2. `check_io_reachability(edges, input_ids, output_ids, max_steps=4)`：沿有向 source-to-target edge 回傳逐 output 最短距離及不可達清單。

Parquet schema/checksum 驗證、manifest 產生和檔案 I/O 可由 ticket 範圍內 runner 處理。使用者確認 seam 後再依 TDD 先建立 fixture 測試。這些介面目前只是提案，尚未核准或實作。

## 本次結果

- ticket 狀態維持 `ready-for-agent`。
- 程式、測試與 demo 輸入均未更動。
- 資源預檢通過；但尚未執行任何 I/O 選擇、可達性計算或輸出產生。

## 後續更新

2026-10-16 使用者確認上述兩個測試 seam。M1.3 已依 TDD 實作並完成 fixture 測試與 500-node demo I/O 檢查；結果和 ticket 剩餘驗收項目見 [M1.3 I/O 可達性報告](m1-3-io-reachability-report.md)。

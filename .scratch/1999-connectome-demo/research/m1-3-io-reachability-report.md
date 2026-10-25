# M1.3 I/O 可達性與 graph manifest

日期：2026-10-16  
Ticket 狀態：`completed`

## 範圍

只讀取封存的 `data/connectome/derived/malecns_v1.0/subgraphs/engineering-demo-v1.0/`。新增確定性 I/O 選擇與有向可達性 helper，並在 `.scratch/1999-connectome-demo/m1-3/` 寫出檢查 manifest 和結果報告。未讀取完整 connectome、未建立索引、未跑 M1.2、未載入模型，也未修改 M1.1、M1.2、案件資料、taxonomy 或 split manifest。

Input/output 是供工程 demo 使用的合成 I/O 節點，不代表神經元身分、腦區或生物學功能。

## 實作

- `src/flycall_data/io_reachability.py`
  - `select_io_nodes(...)` 使用 keyed BLAKE2b-128 hash-priority 選取。固定 salt 為 `FlyCallM13-IO-v1`；input/output 使用不同 role domain，ID 以 signed int64 little-endian 編碼；digest 升冪排序，碰撞時以 node ID 升冪 tie-break。輸入節點列順序不影響結果，輸出 ID 以升冪 canonicalize。
  - 生產 runner 僅接受封存的 `engineering-demo-v1.0` 路徑，檢查 nodes/edges schema、列數、manifest 對應、SHA-256、空值、重複 node ID 與 edge endpoints。輸出目錄限於 `.scratch/1999-connectome-demo/m1-3/`，且不覆寫既有目錄。
  - `check_io_reachability(...)` 從所有 input 同時做 `source_id -> target_id` BFS，回傳每個 output 最短 hop；最多探索到 T。不可達 output 回傳 JSON null 並列入清單。weight 不作路徑成本。
  - 遇到不可達 output 時不自動換節點、不增加 T；將失敗狀態寫入 scratch manifest 並停止。
- `tests/test_io_reachability.py`
  - 11 個 fixture 覆蓋可重現與互斥、列順序獨立、有向方向、忽略 weight 成本、多來源最短路徑、T 邊界、不可達 null、input/output 重疊、非 demo ID、未知 edge endpoint、重複／不足節點等情況。

## TDD 與測試

先新增 fixture 測試，首次執行因 `flycall_data.io_reachability` 尚不存在而按預期失敗（red）。實作後執行：

```sh
PYTHONPATH=src uv run --offline --python 3.12 --with pyarrow==26.0.0 -- python -m unittest discover -s tests -p 'test_io_reachability.py' -v
```

結果：**11 tests passed**。環境為 Python 3.12.14、PyArrow 26.0.0；使用本機 cache 的 offline 執行，未下載套件。

## 封存子圖檢查結果

M1.2 manifest、Parquet schema 與實際內容一致：`nodes.parquet` 是 500 列 `node_id:int64`；`edges.parquet` 是 2,216 列 `source_id:int64,target_id:int64,weight:int64`。沒有空值或重複 node ID；所有 edge endpoints 均存在於 nodes。I/O 選擇和 BFS 僅載入這 500 個 nodes 與 2,216 條 edge。

| 項目 | 結果 |
|---|---:|
| Input nodes | 32 |
| Output nodes | 32 |
| Sets disjoint | 是 |
| 方向 | `source_id -> target_id` |
| T | 4 |
| Output 可達 | 32/32 |
| 不可達 output | 0 |
| 最短 hop 分布 | 1 hop：9；2 hops：23 |
| 自動重選／調整 | 無 |

Weight 保持來源定義：published segment-to-segment connection weight，來源文件說明為 connections／postsynaptic densities 數量；本次只用 edge 拓樸計算路徑，不用 weight 作為成本，也不將其描述為校準的突觸效能。

## 資源與 checksum

- 實測實體 RAM：8,589,934,592 bytes（8 GiB）。
- 執行前可用磁碟：23,113,964 KiB；最後快照：23,103,980 KiB。期間全磁碟可用量減少 9,984 KiB；M1.3 輸出目錄為 12 KiB。`df` 是系統層級數值，未將其餘差額歸因於 M1.3。
- M1.3 function 執行時間：0.383612 秒；peak RSS：62,226,432 bytes。沒有 dense adjacency、DuckDB、全圖讀取或模型。
- 封存輸入 checksum（執行前後相同）：
  - `manifest.json`: `5300c6cefdc6b84a854545e64f4131baa3fc42f0bde97a83f68fcc1c3769cf40`
  - `nodes.parquet`: `a8ad1e6a42c0a386d4bdef517ac628c29a5b7b8f023c51b43cce8e0354087428`
  - `edges.parquet`: `afa69be2078eaf136d00511539145dc82ea54af5aa2f52ffdcb87501488e2175`
- M1.3 輸出：
  - `.scratch/1999-connectome-demo/m1-3/engineering-demo-io-v1.0-20261016/io_manifest.json` SHA-256：`48148a1d64cc5402b17db99dff61ad42a3c29bef8d422ebfa6a25e375e07f585`
  - `.scratch/1999-connectome-demo/m1-3/engineering-demo-io-v1.0-20261016/io_report.md` SHA-256：`441eebe8df03a359d2269203dc0dbbc4d242e4349c4ff6bbbc14ee4161138922`

Manifest 同時記錄 32 個 input/output IDs、hash 規則與 salt、逐 output hop、weight 語意、來源前後 checksums、輸出報告 checksum，以及明確的不可達停止政策。

## 驗收與未完成事項

Selection、fixture、I/O 可達性、manifest 及禁止事項均通過。依使用者指示，ticket 的 M1.1 原始檔前後 checksum 驗收改為：**不適用；本任務未讀取 M1.1，來源完整性依 M1.2 manifest provenance 核對**。M1.3 I/O manifest 中記錄的 M1.1 source、edges、nodes checksum，與 M1.2 封存 manifest 及 M1.2 研究紀錄一致。這是 provenance 對照，不是重新驗證 M1.1 原始檔。

M1.3 封存輸入 `manifest.json`、`nodes.parquet`、`edges.parquet` 的 SHA-256 前後一致，且與 M1.2 manifest 相符。修訂後所有 ticket 驗收條件均符合，狀態更新為 `completed`。此結果僅說明目前 engineering-demo 子圖在固定 hash-priority 合成 I/O 設定下通過 T=4 有向可達性檢查，不作為生物學代表性或功能主張。

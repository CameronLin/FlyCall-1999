# M3.1 小型 fixture 模型核心實作報告

日期：2026-10-16  
狀態：`completed`；M3.1 fixture 驗收全部通過。  
依據：M3.1 ticket `08-m3-1-small-fixture-model-core.md`、M3.0 契約 v1.1。

## 範圍

新增 sparse recurrent graph core、Fly A／Fly B fixture 模型、distance-preserving loss 與 checkpoint fixture helpers。所有 edge、node ID、embedding、label 都由測試在記憶體內合成。測試沒有呼叫正式資料 loader，也未讀取正式 JSONL／CSV、test rows、M1.1／M1.2／M1.3 產物或 E5；沒有正式訓練、模型下載或正式 checkpoint。

依本次授權，只讀取指定 `io_manifest.json` 內的 `io_selection.input_node_ids` 與 `io_selection.output_node_ids` 清單；未讀取 manifest 的其他欄位、nodes／edges Parquet、完整子圖或其他 M1.1／M1.2／M1.3 產物。以這兩份實際清單建立合成 edge fixture，確認 `graph_core` 原樣保留 ID 與座標順序，並檢查清單數量、唯一性與互斥性。

## TDD 與測試

先新增 `tests/test_graph_core.py`，在模型模組尚不存在時執行，得到預期失敗：`ModuleNotFoundError: No module named 'flycall_data.graph_core'`。之後新增實作，再修正兩處 fixture 時序／測試梯度清理假設；本次補入使用實際 manifest ID 的合成 fixture。最終專用測試通過 **13/13**。

測試命令：

```sh
PYTHONPATH=src /private/tmp/flycall-m31-preflight-venv/bin/python -c 'import resource, unittest; suite=unittest.defaultTestLoader.discover("tests", pattern="test_graph_core.py"); result=unittest.TextTestRunner(verbosity=2).run(suite); print("ru_maxrss_bytes", resource.getrusage(resource.RUSAGE_SELF).ru_maxrss); raise SystemExit(not result.wasSuccessful())'
```

結果：`Ran 13 tests ... OK`。涵蓋有向傳遞及反向無邊、T=2／T=4 傳播深度、實際 manifest ID 與 ordered 座標、Fly A／B 維度與類別順序、self-loop 與固定入度、每 target prior、無效 weight／不可參數化 prior 明確失敗、非邊沒有參數、正值 gain、Fly A／B edge gain 獨立、edge 梯度與實際更新、拓樸更新前後不變、graph edge 改變對 logits 的影響、distance loss／cross-entropy、Fly A 凍結，以及 checkpoint 載入一致和不相容設定拒絕。

### 實際 M1.3 I/O 清單檢查

- 檔案：`.scratch/1999-connectome-demo/m1-3/engineering-demo-io-v1.0-20261016/io_manifest.json`
- 讀取欄位：`io_selection.input_node_ids`、`io_selection.output_node_ids`。
- Input 32 個、Output 32 個；兩份清單各自唯一、彼此互斥，且 ID 均為整數。
- 將兩份 ordered list 以 compact JSON（`input_node_ids` 後接 `output_node_ids`）序列化後的 SHA-256：`2f3ff12d2437309d7f06edd3b9396e9ffa8cbf6dcda8a964ce212a82ddb85d40`。這是 ID 清單內容摘要，不是整份 manifest 的 checksum。
- 專用測試只以 manifest ID 組成 32 條合成 `(input_id, output_id, weight)` 邊，weight 交替為 1／3；不使用正式 edge rows。測試通過 graph core、Fly A 與 Fly B 的 `input_node_ids`／`output_node_ids` 順序相等檢查；另用座標定向的合成 drives 驗證 Fly A 第 j 個 ordered output 經 Fly B 第 j 個 ordered input 到達指定 logits。
- 此合成圖 64 nodes／32 edges，topology SHA-256：`587583447cd79267987910574eb8e9af68728d1ca8ea003d34617907bf7fa542`。

## 實作摘要

- `SparseGraphCore` 使用稀疏 edge list，沒有建立 dense adjacency。節點 state 為 scalar，初始為零；每步沿 `source_id → target_id` 聚合並注入 input drive，edge gains 在各時間步共享。T=2 為 fixture 主設定，另以 T=4 驗證較長路徑傳播。
- 初始化逐字依 M3.0 契約：`r=log1p(weight)`；每 target 的 incoming `r` 除以該 target incoming mean；以 `inverse_softplus(prior - 1e-6)` 得 raw parameter，gain 為 `1e-6 + softplus(raw)`。零 prior mean、非有限／負 weight 或 `prior <= epsilon` 會明確失敗；沒有 clipping 或替代公式。
- Fly A 將合成 d 維向量 L2 normalize，經 trainable `d→32` projection 和 tanh，再讀出 ordered 32 維並 L2 normalize。Fly B 依輸入清單順序接收 32 維值，經獨立 `32→32` adapter、獨立 graph core 和 `32→5` readout；類別順序固定。
- Checkpoint metadata 包含 ordered node IDs、edge list／topology SHA-256、T、weight init／aggregation 說明、參數量及 label order；載入時嚴格比對 metadata。
- Fixture topology SHA-256：`a50ce3a09c1e41abf7bd8a04815c717354ca3cccfc61aee1450d10dcd4f2fe89`。Fixture 有 64 個合成 node IDs（32 input、32 output），32 條一對一有向 edge，weight 交錯為 1／3；輸入與輸出 ID 座標刻意使用非排序順序。

本 fixture 的可訓練參數量：

| 模組 | Adapter／projection | Graph core | Readout | 合計 |
|---|---:|---:|---:|---:|
| Fly A（d=4 fixture） | 160 | 32 | 0 | 192 |
| Fly B | 1,056 | 32 | 165 | 1,253 |

此處的 32-edge 小型圖只用於驗證程式行為，不能代表正式 500-node graph 的參數量或效能。

## 資源與依賴

- 實體 RAM：`8,589,934,592` bytes（`sysctl -n hw.memsize`）。
- 執行前的程序檢查沒有發現 Python／uv／pip／torch 工作程序；篩選結果只有 macOS `UVCAssistant` 與 VS Code `pet` 輔助程序。
- 執行環境：Python `3.14.8`，PyTorch `2.14.1` CPU wheel；CUDA 與 MPS 均不可用。未安裝 NumPy；PyTorch import 會提示 NumPy 不存在，但本測試未使用 NumPy，12 項均通過。
- 解析後套件：`torch==2.14.1`、`filelock==4.2.0`、`fsspec==2026.9.0`、`jinja2==3.1.6`、`markupsafe==3.0.4`、`mpmath==1.3.0`、`networkx==3.7`、`setuptools==84.0.0`、`sympy==1.14.0`、`typing-extensions==4.16.0`。下載合計 `137,670,603` bytes（`131.29 MiB`）；未安裝 GPU 套件或模型。
- 依賴只安裝在 `/private/tmp/flycall-m31-preflight-venv/`，環境大小 `638,288 KiB`。專案所在磁碟最新快照可用 `23,283,396 KiB`（約 `22.2 GiB`），高於至少保留 `4 GiB` 的要求。
- 最新專用測試執行 `1.087 s`，`resource.getrusage(RUSAGE_SELF).ru_maxrss = 290,045,952 bytes`（約 `276.6 MiB`）。沒有大型圖或正式資料進入記憶體。
- 前一個專用測試執行前後可用空間由 `23,288,556 KiB` 變為 `23,283,396 KiB`，減少 `5,160 KiB`；暫存 checkpoint 位於測試的 temporary directory，結束時清除。沒有專案資料或正式輸出被寫入。
- 完成實際 manifest fixture 後的可用磁碟快照為 `23,275,204 KiB`（約 `22.20 GiB`）；本次未安裝套件、未建立正式輸出。

## 檔案與雜湊

- 新增 `src/flycall_data/graph_core.py`：SHA-256 `98e57fe16ade264266387d970eba626548505c7af205c8bd325dfb719441eac8`
- 新增 `tests/test_graph_core.py`：SHA-256 `25a37c282dde187f7c0d5d1ce4780a2577e50d06a36e8793404d23d0bafa979b`

## 驗收結論

實際 M1.3 I/O 清單的 32+32 數量、唯一性、互斥性及有序傳遞已由專用 fixture 檢查；M3.1 ticket 其餘驗收亦通過。Ticket 已更新為 `completed`。這只代表 fixture 工程驗收完成，不是正式資料訓練、模型效能或生物學主張。

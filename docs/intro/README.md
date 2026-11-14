# 專案介紹頁的原始檔

`outputs/FlyCall-1999_專案介紹.html` 由這個資料夾的檔案組成，**不要直接改輸出檔**（下次組裝會被覆蓋）。

## 改內容

| 想改的地方 | 檔案 |
|---|---|
| 某個分頁的文字、表格 | `tabs/0-overview.html` … `tabs/6-tickets.html`（一個分頁一個檔） |
| 外框（標題列、分頁按鈕、頁尾） | `page.html` |
| 樣式 | `css/main.css`；訓練時間區塊另在 `css/training_time.css` |
| 互動（分頁、主題、動畫、圖庫） | `js/main.js`；訓練時間的 T 切換在 `js/training_time.js` |

改完執行：

```bash
python scripts/build_intro_html.py
```

`python scripts/build_intro_html.py --check` 只檢查輸出檔是否和原始檔一致（不一致時結束代碼為 1）。

## 由程式產生的部分

下面的檔案由 run 資料夾的結果自動產生，要改請改產生程式後重跑，不要手改：

| 檔案 | 產生程式 | 資料來源 |
|---|---|---|
| `sections/training_time.html` | `scripts/build_intro_training_time.py` | `independent-tuning-*` 的 `results.json`、`timings.json` |
| `sections/brain_table.html`、`sections/brain_figs.html` | `scripts/build_intro_brain_section.py` | `fly-ab-brain-comparison-*` 的 `results.json`（文字沿用分析報告的 `figure_points()`） |
| `data/bfs_data.json` | `scripts/build_intro_bfs_data.py` | 子圖檔與本機重建的 MaleCNS `edges.parquet`（需要 DuckDB） |

組裝時另外嵌入：

- 腦部比較圖：4 個版本（資料 v1／v2 × T=2／T=4）各 17 張 PNG，轉成無損 WebP（`build_intro_html.py` 的 `FIGURE_SETS`）。
- 訊號傳遞頁：`outputs/FlyCall-1999_連接圖訊號傳遞.html`，在「Fly 的圖」分頁以 iframe 顯示。

## 標記

原始檔中的 `<!--INCLUDE:路徑-->` 會被換成 `docs/intro/` 下對應檔案的內容（可巢狀）；`<!--DATA:bfs|figures|signal-->` 會被換成上面的資料。

## 需要的套件

組裝需要 Pillow（轉 WebP）；產生 `brain_*` 與訓練時間區塊只需要標準函式庫；`bfs_data.json` 需要 DuckDB。

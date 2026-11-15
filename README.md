# FlyCall-1999

**用果蠅腦的連接圖當模型骨架，能不能做好臺北 1999 客服案件分類？** 這個研究專案用合成的客服通話逐字稿做五類分類，把果蠅模型和一般機器學習方法放在同一套規則下比較。

```
通話逐字稿 ──E5──▶ 384 維向量 ──Fly A──▶ 32 維 ──Fly B──▶ 五類之一
                  （文字嵌入，固定）  （降維）        （分類）
```

- **Fly A** 和 **Fly B** 是兩個以果蠅連接圖（MaleCNS v1.0 中挑出的 500 個神經元）為結構的模型：哪些神經元相連固定不變，只訓練每條連線的強弱。
- 對照組是不用連接圖的一般方法：LDA（降維）、SVM、邏輯迴歸、MLP（分類）。
- 資料是合成的，結果屬研究性質，不代表真實 1999 業務的表現，也不連接真實派工。

## 主要結論

| | 果蠅模型 | 對照：LDA → SVM |
|---|---|---|
| 第一代（G0 子圖、資料 v1，validation） | 0.660 | 0.900 |
| 第二代最佳（有正負號的子圖、資料 v2，validation） | 0.938 | 0.913 |
| **一次性 test**（資料 v2，依事先定好的規則選出的果蠅模型） | **0.887 ± 0.018** | **0.899** |

數字是 Macro-F1（五類 F1 的平均），果蠅模型為三個 seed 平均。

1. **果蠅連接圖可以完成分類，表現和傳統方法大致同一水準**，但還沒有穩定勝過 LDA → SVM。
2. **最大的改進來自訓練目標，不是圖本身**：讓 Fly A 同時保留距離與類別（SupCon），是從 0.66 提升到 0.9 左右的關鍵。
3. **Fly A 和 Fly B 學成很不一樣的「腦」**：分類的 Fly B 大幅改寫連線，降維的 Fly A 幾乎維持原樣。
4. **換子圖、加抑制性神經元、增加傳遞步數（T=2 → T=4）的效果都不大**，而且會隨資料版本改變。
5. **限制**：資料未經人工複核；validation 與 test 各只有 150 筆；子圖起點用可重現的抽籤規則決定，尚未驗證換起點後結論是否相同。

## 從哪裡開始看

| 想知道 | 看這裡 |
|---|---|
| 完整的圖文介紹（建議從這裡開始） | [`outputs/FlyCall-1999_專案介紹.html`](outputs/FlyCall-1999_專案介紹.html)（下載後用瀏覽器開啟） |
| 名詞是什麼意思（Fly A／B、G0–G2、T、SupCon…） | [CONTEXT.md](CONTEXT.md) |
| Fly A／Fly B 兩個腦的差異分析 | [`outputs/FlyCall-1999_FlyA_FlyB_分析報告.html`](outputs/FlyCall-1999_FlyA_FlyB_分析報告.html) |
| 最初的規格與設計理由 | [1999-connectome-demo-spec.md](1999-connectome-demo-spec.md) |
| 每個階段的決策、數據與結論 | [`.scratch/1999-connectome-demo/issues/`](.scratch/1999-connectome-demo/issues/)（工作票，檔名以編號開頭） |
| 資料夾與檔案用途 | [docs/PROJECT_FILE_GUIDE.md](docs/PROJECT_FILE_GUIDE.md) |

名稱中的「demo」是歷史沿用：專案最初定位為可行性展示，後來發展成完整的研究流程。

## 資料

五個類別：人行道維護、道路凹陷／不平、公園綠地維護、垃圾車清運、路面清潔，每類 200 筆，共 1,000 筆，固定切成 train 700／validation 150／test 150。同一種情境的紀錄一定在同一個 split。

| 版本 | 產生方式 | 狀態 |
|---|---|---|
| [v2.0.0](data/1999_synthetic/formal/v2.0.0/)（目前主要使用） | 由 Claude 逐筆撰寫，加入口語、台語夾雜、具體地點，移除捷徑詞 | 自動品質檢查通過，未經人工複核；已知問題見 [KNOWN_ISSUES.md](data/1999_synthetic/formal/v2.0.0/KNOWN_ISSUES.md)。test 已評估一次，**不得重開** |
| [v1.0.0](data/1999_synthetic/formal/v1.0.0/) | 模板組合產生，句型重複率高 | 第一代實驗與目前鎖定的推論模型使用此版 |

類別定義與切分設定在 [`data/1999_synthetic/taxonomy/current/`](data/1999_synthetic/taxonomy/current/)；各版本、草案與封存檔的完整索引見 [data/1999_synthetic/README.md](data/1999_synthetic/README.md)。

## 專案進度

| 里程碑 | 內容 | 狀態 |
|---|---|---|
| M0 | 連接圖與神經傳導物質（正負號）的來源確認 | 完成 |
| M1 | 匯入 MaleCNS、挑出 500 點子圖（G0；有正負號的 G1／G2／G2-glu+） | 完成 |
| M2 | E5 文字嵌入與基準模型（LR、MLP、LDA），一次性 test 機制 | 完成 |
| M3 | Fly A／Fly B 訓練、交叉實驗、獨立調參、T=2 vs T=4、資料 v2 與 test | 完成 |
| M4 | 本機推論 CLI（Streamlit 展示介面已於 2026-11-14 移除） | 完成 |

主要工作票：17 交叉實驗、20 獨立調參、21 有正負號子圖、22 四張圖比較、23 跳數修正、24 T=2 vs T=4、25 資料 v2。

## 執行

### 環境與測試

需要 Python，並安裝 `requirements-connectome.txt`（DuckDB 1.5.6、PyArrow 26.0.0）。Windows PowerShell 範例：

```powershell
$env:FLYCALL_PYTHON = 'path\to\venv\Scripts\python.exe'
uv pip install --python $env:FLYCALL_PYTHON -r requirements-connectome.txt
$env:PYTHONPATH = "$PWD\src;$PWD\tests;$PWD\scripts"
& $env:FLYCALL_PYTHON -m unittest discover -s tests
```

### 推論一筆逐字稿

CLI 只接受鎖定 manifest 指定的模型（E5 → MLP，seed 42，資料 v1 訓練），輸出五類分數並標示「模擬派送」。需要固定版本的 E5 snapshot。

```powershell
python scripts\predict_flycall.py `
  --model-manifest .scratch\1999-connectome-demo\runs\m2-2b-e5-seed-42-current-runner-20261026\locked_model_manifest.json `
  --e5-snapshot path\to\pinned-e5-snapshot `
  --text '在此放入一筆逐字稿'
```

細節見 [工作票 14](.scratch/1999-connectome-demo/issues/14-m4-1-locked-predictor.md)。

### 重新產生專案介紹頁

專案介紹頁由 [`docs/intro/`](docs/intro/README.md) 的原始檔組成，不要直接改輸出檔。修改後執行：

```bash
python scripts/build_intro_html.py
```

### 重建連接圖資料

MaleCNS 原始檔（約 1.05 GB）和匯入後的 Parquet（約 654 MB）太大，不放進 Git。換一台電腦 clone 後，用以下步驟下載固定版本並重建：

```sh
mkdir -p data/connectome/malecns_v1.0
curl --fail --location --show-error \
  'https://storage.googleapis.com/flyem-male-cns/v1.0/connectome-data/flat-connectome/connectome-weights-male-cns-v1.0-minconf-0.5.feather?generation=1780494887545976' \
  --output data/connectome/malecns_v1.0/connectome-weights-male-cns-v1.0-minconf-0.5.feather
shasum -a 256 data/connectome/malecns_v1.0/connectome-weights-male-cns-v1.0-minconf-0.5.feather
python3 -m pip install -r requirements-connectome.txt
python3 scripts/import_malecns_v1.py
python3 scripts/verify_malecns_import.py
```

下載檔的 SHA-256 應為 `e35da783d1c686b2b58b3b87cd6a403ae43bfcfba8bff28e08ef752c1a56afc1`。來源、授權（CC BY 4.0）與版本見 [`source_manifest.yaml`](data/connectome/malecns_v1.0/source_manifest.yaml)。已挑好的子圖小檔案有放在 Git 裡，只跑模型不需要重建。

## 資料夾結構

| 資料夾 | 內容 |
|---|---|
| `data/` | 合成通話資料、類別定義、連接圖來源 manifest 與子圖 |
| `src/flycall_data/` | 主要程式：資料載入、子圖挑選、圖核心、Fly A／B 訓練、評估 |
| `scripts/` | 執行實驗、產生報告與專案介紹頁的腳本 |
| `tests/` | 單元測試 |
| `outputs/` | 給人看的成果：專案介紹、分析報告、複核資料包 |
| `docs/` | 專案介紹頁原始檔、檔案導覽 |
| `.scratch/1999-connectome-demo/` | 工作票（`issues/`）、研究筆記（`research/`）、每次實驗的結果（`runs/`） |

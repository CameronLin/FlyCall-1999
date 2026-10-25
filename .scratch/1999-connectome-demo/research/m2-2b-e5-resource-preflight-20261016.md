# M2.2b E5 資源閘門唯讀預檢

## 最新唯讀資源閘門重查（2026-10-21，Asia/Taipei）

**判定：blocked；本次只讀檢查，沒有下載、安裝、載入模型或執行 embedding。** 資源分項在下方標明量測、既有紀錄與估算。系統快照採樣時間約 00:54–00:59；swap 讀值為 00:59:16、專案磁碟讀值為 00:59:47，Activity Monitor 圖表約於 00:58 檢視。

### 即時資源與程序（實測）

| 項目 | 讀值 | 來源／說明 |
|---|---:|---|
| 實體 RAM | 8,589,934,592 bytes（8 GiB） | `sysctl hw.memsize`／系統記憶體工具 |
| 記憶體 free percentage | 32% | `memory_pressure -Q`／`vm_stat`；不是 Activity Monitor 顏色判定 |
| 記憶體壓力顏色 | 黃／琥珀色 | Activity Monitor 圖表目視檢查；**非綠色** |
| Activity Monitor 記憶體使用量 | 約 7.14–7.16 GB | 檢查時畫面讀值，會隨時間變動 |
| swap | total 16,384 MiB；used 15,756 MiB；free 628 MiB | `sysctl vm.swapusage`，2026-10-21 00:59:16；free 低於 1 GiB 門檻 |
| 專案所在磁碟可用空間 | 32,396,312 KiB，約 30.90 GiB | `df -Pk .`，2026-10-21 00:59:47 |
| E5／PyTorch／套件安裝程序 | Activity Monitor 以 `python`、`pip`、`uv`、`torch`、`install` 名稱篩選均未見符合列 | 只代表檢查時這些篩選結果為空；不推論其他名稱的程序狀態 |

記憶體壓力明確不是綠色，且 swap free 為 628 MiB（約 0.61 GiB），低於要求的 1 GiB。因此即使磁碟估算有餘裕，本次也**不得解除資源閘門**。要重試，需由使用者在 Activity Monitor 確認壓力圖為綠色，並確認 swap free 至少 1 GiB；之後再刷新即時快照。

### 本機模型快取（唯讀路徑／大小盤點）

找到指定目標 `intfloat/multilingual-e5-small` 的常見 Hugging Face cache：

`/Users/linyifen/.cache/huggingface/hub/models--intfloat--multilingual-e5-small`

`du -sk` 為 481,764 KiB（493,326,336 bytes，約 470.48 MiB）。指定 revision 目錄 `snapshots/614241f622f53c4eeff9890bdc4f31cfecc418b3/` 存在，9 個必要檔案的 cache entry／blob 均可見；大小與既有官方 metadata 記錄一致：

| 檔案 | bytes |
|---|---:|
| `model.safetensors` | 470,641,600 |
| `tokenizer.json` | 17,082,730 |
| `sentencepiece.bpe.model` | 5,069,051 |
| `config.json` | 655 |
| `modules.json` | 387 |
| `sentence_bert_config.json` | 57 |
| `1_Pooling/config.json` | 200 |
| `tokenizer_config.json` | 443 |
| `special_tokens_map.json` | 167 |
| **必要集合合計** | **492,795,290（469.97 MiB）** |

這是檔案存在與大小盤點，不是內容雜湊、revision 完整性或模型載入驗證；cache entries 使用 blob 連結，未讀取權重內容。另查常見 Torch、Sentence Transformers 與使用者 Hugging Face cache 路徑時，Torch／Sentence Transformers 專用 cache 及 `~/Library/Caches/huggingface` 不存在。不得只因檔案在 cache 就宣稱可安全載入。

### 套件與磁碟容量（估算，不是本次安裝實測）

現有 CPython 3.13 的 M2.2a 環境套件 metadata 顯示 PyTorch、Sentence Transformers、Transformers、SentencePiece、Tokenizers、Safetensors、Hugging Face Hub 尚未安裝；NumPy 與 scikit-learn 已有。沒有任何套件安裝。本報告沿用已記錄的 PyPI wheel metadata 解析：CPython 3.13 完整 42-wheel 閉包 198,701,986 bytes（189.50 MiB），CPython 3.14 為 198,750,040 bytes（189.54 MiB）；這是 wheel 大小估算，不是下載量或解壓 footprint 實測。指定 9 個模型檔合計 469.97 MiB；目前 cache 有相同檔案大小，但 checksum 未驗證。

以當下 30.90 GiB 可用磁碟估算：

| 情境／項目 | 預估空間 | 計算方式與限制 |
|---|---:|---|
| 套件 wheel 下載 | 189.50 MiB | CPython 3.13 已解析 bytes |
| wheel 下載暫存／另一份 cache 副本 | 最多再預留 189.50 MiB | 保守按下載與 staging 同時存在估算，尚未實測 |
| 整合隔離環境安裝目錄 | 1.50 GiB | 沿用舊規劃額度，未安裝驗證，不是硬上界 |
| 本機模型 cache 已佔用 | 470.48 MiB | `du` 實測；已反映於 `df` 可用空間，**不可再次從可用量扣除** |
| cache 命中時模型額外下載／複製 | 暫按 0 MiB | 只有在內容完整性核對後才能採用此情境；目前 checksum 未核對 |
| embedding cache 與 metadata | 16 MiB | 規劃上限估算；本次未建立 |
| 執行／其他暫存 | 256 MiB | 規劃額度，未實測 |
| **已見 cache 且可重用的增量預算** | **約 2.13 GiB** | 只作估算；不含未知安裝或 cache 行為超額 |
| cache 未能重用、另下載並暫存模型 | 939.94 MiB | 模型檔 469.97 MiB × 下載／cache 同時存在兩份的保守額度 |
| **cache 不可重用的保守增量預算** | **約 3.05 GiB** | 上列 939.94 MiB + 379.00 MiB wheels／staging + 1.50 GiB venv + 16 MiB cache + 256 MiB temp |

在保守 cache 不可重用情境下，30.90 GiB 減 3.05 GiB，估計剩約 27.85 GiB，高於 4 GiB 保留線。這只表示按上述假設的**磁碟規劃值**有餘裕；venv、staging、暫存和其他程序造成的實際峰值仍未量測，也未證明這些估算為硬上界。

### 分類與下一步

- **實測通過／有資料：** 8 GiB 實體 RAM、約 30.90 GiB 磁碟可用量；指定 revision cache 路徑及 9 檔大小；未見上述程序名稱篩選結果。
- **不通過：** Activity Monitor 壓力圖呈黃／琥珀色；swap free 628 MiB，低於 1 GiB。
- **尚未實測：** 單一整合環境實際 wheel 下載量與安裝 footprint、模型檔 checksum／載入完整性、runtime peak RSS、執行期記憶體壓力、batch=1 embedding smoke test。
- **本次未讀取：** 正式資料列、Pilot、connectome 產物與 test rows；未執行 M2.3 fixture 測試。

所以 M2.2b E5 資源閘門與 ticket 均維持 **blocked**。只有 Activity Monitor 壓力明確為綠色、swap free ≥1 GiB，且重新估算的安裝後最壞磁碟情境仍可保留 ≥4 GiB，才可重新考慮使用者已核准的受限環境驗證；本次沒有進行該驗證。

日期：2026-10-16  
原始預檢狀態：**E5 部分維持 blocked；等待使用者核准下載與安裝**

## 2026-10-21 模型選擇更新

使用者已選定 `intfloat/multilingual-e5-small` 作為本專案唯一文字嵌入目標，不再使用 `multilingual-e5-large` 作為候選。目標設定為 model ID `intfloat/multilingual-e5-small`、revision `614241f622f53c4eeff9890bdc4f31cfecc418b3`、prefix `query: `、`max_seq_length=512`、output dimension 384、masked mean pooling、`normalize_embeddings=true`；受限試跑使用 CPU、`batch_size=1`。

這是設定選擇，**不是**下載、安裝、載入或本機輸出驗證。M2.2b 資源閘門仍為 blocked。以下 2026-10-16 的容量、wheel 與 batch 4 RSS 數字均保留為當時的預檢紀錄；batch 4 估值不作為目前 batch 1 的實測或安全上界。實際受限驗證前仍須刷新即時 RAM／磁碟／記憶體壓力，並完成單一隔離環境與模型載入的受限量測；至少保留 4 GiB 可用磁碟，程序 RSS 超過 3.5 GiB 或出現記憶體壓力即停止。

## 範圍與結果摘要

本次只檢查官方模型／套件中繼資料、既有隔離環境、實體 RAM 與可用磁碟，並估算後續資源。沒有下載模型或 wheel、安裝套件、載入模型、執行 embedding／訓練，亦未讀取正式資料或 test rows。`uv pip compile` 只解析套件索引中繼資料；使用 `--only-binary :all:`、`--no-cache`、`--no-python-downloads`，結果輸出至 stdout。為解析建立的暫存 requirements 檔已移除。

官方 model card／revision 與 PyPI 中繼資料已足以確認模型設定、Python 3.13／3.14 的套件解析結果及 wheel 下載 bytes。當下磁碟容量在列出的保守預算下高於 4 GiB 保留線。仍未通過 E5 閘門的原因是：**整合環境尚未安裝／runtime 驗證；實際 E5 load／batch inference peak RSS 未量測；1.5 GiB 安裝目錄配置和模型下載暫存配置是規劃估值而非已證明上限。** 不得據此自行解除 blocked。

## 官方模型與前處理查核（2026-10-16）

預檢查核的模型為 `intfloat/multilingual-e5-small`，revision `614241f622f53c4eeff9890bdc4f31cfecc418b3`。該 immutable revision 的官方檔案頁標示 MIT；model card 說明將 embedding 作為 feature／linear probing 時使用固定 `query: ` prefix，tokenizer 最多 512 tokens，model hidden size 與 Sentence Transformers pooling 維度均為 384。Pooling config 是 mean tokens；model card 範例使用 attention mask 做 masked mean pooling，並對最後向量做 L2 normalization。[官方 revision 檔案樹](https://huggingface.co/intfloat/multilingual-e5-small/tree/614241f622f53c4eeff9890bdc4f31cfecc418b3)、[revision model card](https://huggingface.co/intfloat/multilingual-e5-small/blob/614241f622f53c4eeff9890bdc4f31cfecc418b3/README.md)、[model config](https://huggingface.co/intfloat/multilingual-e5-small/blob/614241f622f53c4eeff9890bdc4f31cfecc418b3/config.json)、[pooling config](https://huggingface.co/intfloat/multilingual-e5-small/blob/614241f622f53c4eeff9890bdc4f31cfecc418b3/1_Pooling/config.json)。

### SentenceTransformer 推論路徑的必要檔案

以下為採用 repo 內 `modules.json` 建立 Transformer + mean-pooling 模組、使用 fast tokenizer 並保留 SentencePiece slow-tokenizer fallback 的保守必要集合。bytes 與大型檔案 SHA-256 來自指定 revision 的官方檔案 metadata；本機沒有下載副本，故未做本機雜湊。

| 檔案 | 推論用途 | bytes | MiB | 官方 SHA-256（若 API 提供） |
|---|---|---:|---:|---|
| `model.safetensors` | float32 模型權重；採用此檔即可排除重複 `.bin` | 470,641,600 | 448.84 | `1a55775f53449dac10a2bcbc312469fac40b96d53198c407081a831f81c98477` |
| `tokenizer.json` | fast tokenizer | 17,082,730 | 16.29 | `0b44a9d7b51c3c62626640cda0e2c2f70fdacdc25bbbd68038369d14ebdf4c39` |
| `sentencepiece.bpe.model` | slow tokenizer fallback | 5,069,051 | 4.83 | `cfc8146abe2a0488e9e2a0c56de7952f7c11ab059eca145a0a727afce0db2865` |
| `config.json` | Transformer 架構、hidden size、tokenizer 設定 | 655 | <0.01 | 官方 API 未提供此小檔 SHA-256 |
| `modules.json` | SentenceTransformer 模組清單 | 387 | <0.01 | 官方 API 未提供此小檔 SHA-256 |
| `sentence_bert_config.json` | SentenceTransformer 模組設定 | 57 | <0.01 | 官方 API 未提供此小檔 SHA-256 |
| `1_Pooling/config.json` | 384 維 masked mean pooling 設定 | 200 | <0.01 | 官方 API 未提供此小檔 SHA-256 |
| `tokenizer_config.json` | tokenizer 載入設定 | 443 | <0.01 | 官方 API 未提供此小檔 SHA-256 |
| `special_tokens_map.json` | tokenizer special-token 對照 | 167 | <0.01 | 官方 API 未提供此小檔 SHA-256 |
| **必要集合合計** |  | **492,795,290** | **469.97** |  |

必要集合包含哪些 tokenizer fallback 檔案仍須在獲准後，以實際凍結的 loader（`SentenceTransformer`／fast tokenizer 設定）做 runtime 核對；若最後固定 `use_fast=True` 並證明不需 slow fallback，SentencePiece 模型檔可能可省略，這裡先按保守完整集合估算。完整 repository 頁面顯示約 2.28 GB；其中有替代權重 `pytorch_model.bin`（470,681,649 bytes）、ONNX／OpenVINO 變體與 README 等。它們不屬於上述必要推論集合，不應整庫下載；官方檔案樹證實 `.safetensors` 與 `.bin` 是兩套權重，保留一種即可。

## 單一隔離環境的 Python／依賴解析

實測平台為 macOS 14.5、arm64。現有環境盤點：

- M2.2a 隔離環境：CPython 3.13.0、NumPy 2.5.4、scikit-learn 1.9.1；缺 PyTorch、Transformers、Sentence Transformers、SentencePiece、Tokenizers、Safetensors、Hugging Face Hub。
- M3.1 fixture 環境：CPython 3.14.8、PyTorch 2.14.1 CPU fixture 使用；缺 NumPy、scikit-learn 及 E5／Transformer 套件。
- 以上是兩個分開的環境，**不能視為已整合**。本次分別以兩個 interpreter 當解析目標，針對同一份 6 個直接需求執行 `uv pip compile`；兩者都解析成功，均得到同一組 42 個套件版本。這證明有相容 wheel 且 resolver 能找到一致閉包，不代表安裝後 import、SentenceTransformer 載入或 embedding runtime 已驗證。

直接需求輸入（固定已用版本；E5 套件在本次解析時選出的候選版）：

```text
torch==2.14.1
sentence-transformers
transformers
sentencepiece
numpy==2.5.4
scikit-learn==1.9.1
```

解析命令（依序以實際 CPython 3.13／3.14 interpreter 作為 `--python`）：

```sh
uv pip compile <temporary-requirements.in> --python <target-interpreter> \
  --only-binary :all: --no-cache --no-python-downloads \
  --no-annotate --no-header -o -
```

`uv 0.12.9` 以 PyPI dependency metadata 解析；再依 PyPI JSON API 每個 release 的 wheel `size` 欄位、Python ABI 及 macOS arm64 platform tags 選取相容 wheel。沒有請求 distribution URL。直接需求 6 個；轉依賴 36 個。版本會隨 index 更新，獲准安裝前須重跑解析、核對版本與下載量，不能把這次結果當永久 lock。

### 直接需求的 wheel bytes

| 套件 | 解析版本 | CPython 3.13 wheel bytes | CPython 3.14 wheel bytes |
|---|---:|---:|---:|
| `numpy` | 2.5.4 | 5,445,803 | 5,455,617 |
| `scikit-learn` | 1.9.1 | 8,262,364 | 8,279,175 |
| `sentence-transformers` | 6.1.0 | 740,560 | 740,560 |
| `sentencepiece` | 0.2.2 | 1,347,267 | 1,348,056 |
| `torch` | 2.14.1 | 127,315,286 | 127,325,330 |
| `transformers` | 5.20.0 | 12,826,514 | 12,826,514 |
| **直接需求合計** | **6** | **155,937,794** | **155,975,252** |

macOS PyTorch 使用 PyPI 的 arm64 macOS wheel（3.13 為 `torch-2.14.1-cp313-cp313-macosx_14_0_arm64.whl`；3.14 為 `torch-2.14.1-cp314-cp314-macosx_14_0_arm64.whl`）；不使用 CUDA/GPU wheel。未來程式仍須明確設 `device="cpu"`。初次使用 uv 的 `--torch-backend cpu` 解析失敗，因該 CPU wheel index 沒有此 macOS 發行檔；改用符合本機 macOS tag 的 PyPI wheel 後解析成功。這不是安裝或載入測試。

### 轉依賴 wheel bytes

| 套件 | 解析版本 | CPython 3.13 bytes | CPython 3.14 bytes |
|---|---:|---:|---:|
| `annotated-doc` | 0.0.5 | 5,302 | 5,302 |
| `anyio` | 4.15.1 | 132,079 | 132,079 |
| `certifi` | 2026.7.22 | 136,983 | 136,983 |
| `click` | 8.5.0 | 125,251 | 125,251 |
| `cloudpickle` | 3.1.2 | 22,228 | 22,228 |
| `filelock` | 4.2.0 | 135,032 | 135,032 |
| `fsspec` | 2026.9.0 | 221,738 | 221,738 |
| `h11` | 0.16.0 | 37,515 | 37,515 |
| `hf-xet` | 1.7.0 | 3,560,352 | 3,560,352 |
| `httpcore` | 1.0.9 | 78,784 | 78,784 |
| `httpx` | 0.28.1 | 73,517 | 73,517 |
| `huggingface-hub` | 1.33.0 | 846,435 | 846,435 |
| `idna` | 3.20 | 69,583 | 69,583 |
| `jinja2` | 3.1.6 | 134,899 | 134,899 |
| `joblib` | 1.6.0 | 306,115 | 306,115 |
| `markdown-it-py` | 4.2.0 | 91,687 | 91,687 |
| `markupsafe` | 3.0.4 | 12,061 | 12,061 |
| `mdurl` | 0.1.2 | 9,979 | 9,979 |
| `mpmath` | 1.3.0 | 536,198 | 536,198 |
| `narwhals` | 2.27.1 | 483,211 | 483,211 |
| `networkx` | 3.7 | 2,142,205 | 2,142,205 |
| `packaging` | 26.3 | 129,956 | 129,956 |
| `pygments` | 2.21.0 | 1,250,147 | 1,250,147 |
| `pyyaml` | 6.0.3 | 173,252 | 173,809 |
| `regex` | 2026.9.29 | 293,472 | 293,518 |
| `rich` | 15.0.0 | 310,654 | 310,654 |
| `safetensors` | 0.8.0 | 484,562 | 484,562 |
| `scipy` | 1.18.1 | 20,456,846 | 20,466,839 |
| `setuptools` | 84.0.0 | 818,216 | 818,216 |
| `shellingham` | 1.5.4 | 9,755 | 9,755 |
| `sympy` | 1.14.0 | 6,299,353 | 6,299,353 |
| `threadpoolctl` | 3.7.0 | 26,362 | 26,362 |
| `tokenizers` | 0.23.3 | 3,101,381 | 3,101,381 |
| `tqdm` | 4.70.1 | 80,199 | 80,199 |
| `typer` | 0.27.3 | 123,312 | 123,312 |
| `typing-extensions` | 4.16.0 | 45,571 | 45,571 |
| **轉依賴合計** | **36** | **42,764,192** | **42,774,788** |
| **完整 wheel 合計** | **42** | **198,701,986** | **198,750,040** |

換算：完整套件 wheel 量為 CPython 3.13 `189.50 MiB`（198.702 MB），CPython 3.14 `189.54 MiB`（198.750 MB）。這是依 PyPI JSON `size` 欄位計算的 wheel bytes 合計，不含 HTTPS 傳輸協定額外量、安裝後解壓檔案、pip/uv 暫存以外的系統檔，也不是目前 cache 增量實測。

## 當下資源與分項估算

### 實測快照

- 實體 RAM：`sysctl -n hw.memsize` 回傳 `8,589,934,592` bytes；`system_profiler SPHardwareDataType` 顯示 8 GB。設備為 Apple M3、arm64、macOS 14.5。
- 專案磁碟最新 `df -Pk .`：可用 `21,162,832 KiB` = `21,670,739,968 bytes` = `20.18 GiB`。同一預檢較早快照為 `23,260,176 KiB`；累計相差 `2,097,344 KiB`（約 2.00 GiB），原因未查明，本報告不歸因於任何特定程序，也不假設空間穩定。
- 現有 `~/.cache/uv`：`1,207,952 KiB`（約 `1.15 GiB`）；M3.1 fixture venv：`638,288 KiB`（約 `623.33 MiB`）。這些已占用空間已反映在 `df` 可用值內。M2.2a report 另記其 CPython 3.13 sklearn 環境約 147 MiB。兩個環境互不整合，數值不能直接當成新整合環境安裝大小。
- 既有 fixture-only 測試峰值：M2.2a sklearn smoke `265,682,944 bytes`，M3.1 PyTorch fixture `290,045,952 bytes`；二者均未載入 E5，且來自不同環境，不能加總或當 E5 peak RSS。

### 磁碟預算（估算，不是 install/download 實測）

| 項目 | 規劃量 | 性質／假設 |
|---|---:|---|
| 必要模型檔持久 cache | 469.97 MiB | 官方 revision API 精確 bytes 合計 |
| 模型下載暫存副本 | 469.97 MiB | 保守假設完整必要集合另有一份暫存副本；未驗證 HF cache 的實際 staging 行為 |
| 42 個 CPU/macOS arm64 套件 wheels | 189.50 MiB（3.13）／189.54 MiB（3.14） | PyPI metadata 精確 wheel bytes 合計；不含解壓安裝 footprint |
| 單一整合 venv 解壓安裝目錄 | 1.50 GiB 預算 | 未實測；為現有分開環境與新增 ST/Transformers 留餘裕，並非可證明上界 |
| train+validation embedding 原始 cache | 1.25 MiB | `850 × 384 × float32 = 1,305,600 bytes`；cache 格式、索引及 metadata 額外預留至 16 MiB |
| run／下載外的暫存與報告 | 256 MiB 預算 | 保守工作區額度，未實測 |
| **規劃峰值合計** | **約 2.87 GiB** | 含模型完整重複暫存副本、wheel cache 與安裝目錄同時存在 |

以最新 `20.18 GiB` 可用空間減去 `2.87 GiB` 資源預算，規劃剩餘約 `17.31 GiB`。另將預檢期間觀察到的 `2.00 GiB` 累計變化保守視為波動 reserve，剩餘約 `15.31 GiB`，比 `4 GiB` 保留線多約 `11.31 GiB`。**磁碟估算在列明假設及已觀察波動 reserve 下通過**；但安裝目錄預算、模型 staging 方式及未來未觀察的空間變化仍非已證明上界。

### RAM／峰值 RSS（估算，未量測）

- 模型 float32 權重本身至少約 `448.84 MiB`（對應官方 470,641,600-byte safetensors 檔）。Tokenizer 及 384 維 embedding 的內部表示會再占額外 RAM。
- 作為容量估算而非凍結設定，採 batch 4、512 tokens 上限。單層 attention score 尺寸約 `4×12×512×512×4 = 48 MiB`；score/probability 暫存、Q/K/V、FFN（約 12 MiB/層的中間張量）會增加當層工作集。
- 規劃值：整合 Python／PyTorch／Transformers／sklearn runtime 與 tokenizer 0.5–1.0 GiB；模型權重 0.45 GiB；載入過程額外一份權重暫存最多先按 0.45 GiB；batch activations 0.2–0.5 GiB；分類器與 embedding/cache 工作區低於 0.1 GiB。按高端預留後，**預算 E5 程序 peak RSS 約 2.5–3.0 GiB**。
- 這個數字由張量尺寸和不同 fixture 環境量級外推，不是 E5 實測或數學上界；模型載入策略、tokenizer runtime、PyTorch allocator、系統背景程序及記憶體壓力尚未量測。8 GiB 實體 RAM 下看似有空間，但本次不能保證實際 peak RSS。

## Python 版本判斷

| 版本 | 同一 42 套件閉包能否解析出 arm64 macOS wheels | 現有環境是否已整合 | 評估 |
|---|---|---|---|
| CPython 3.13.0 | 是 | 否；現有 M2.2a 環境有 NumPy/sklearn，缺 PyTorch/E5 stack | 建議做為後續單一環境候選，延續 M2.2a Python 版本；需另建隔離整合環境並實測 imports/load。 |
| CPython 3.14.8 | 是 | 否；現有 M3.1 環境有 PyTorch，缺 NumPy/sklearn/E5 stack | resolver 相容；需同樣整合安裝與 runtime 驗證。 |

因此兩者都通過**套件 resolver/wheel 相容性**，但目前沒有現成的整合環境。推薦未來以 3.13 作候選以延續 M2 基線版本，不視為已凍結決定。

## 資源閘門判定與解除條件

**判定：blocked。** 使用者已核准受限環境驗證，但 2026-10-16 執行前的即時記憶體檢查觸發停止條件；本次未下載或安裝。先前磁碟估算仍不能取代當下的記憶體安全檢查。

1. 單一乾淨隔離環境中的安裝後實際 footprint、整套 import smoke 與版本相容性；目前只有 no-install resolver 成功，兩個舊環境仍分離。
2. E5 load 與明確 batch／token 上限下的實測 peak RSS；不下載／載入的限制使本次無法量測。
3. 實際模型快取／部分下載檔 staging 行為及整合 venv 大小；本次用 1.5 GiB 環境預算與完整模型第二份暫存副本估算，仍非硬性上界。
4. 獲准前須刷新 RAM、available disk；已觀察同一預檢的 disk snapshot 有約 1.00 GiB 差異，原因未知。任何後續操作必須在完成最壞情境需求後保留至少 4 GiB；低於保留線即停止。
5. 下載後應對固定 revision 的本機模型檔核對 SHA-256，並以運行中的 encoder 驗證 384 維、mean pooling、prefix、512-token truncation 記錄。此處只確認官方 metadata，未做本機檔案驗證。

本次沒有 test、正式資料、split 或 connectome data 使用；沒有模型／wheel 下載或套件安裝。正式資料仍為 `pending_manual_review`；即使後續獲准，也只能依 ticket 既定規則先做 train／validation `smoke_test`／`provisional`，test 不可進入 encoder、cache、fit、transform、predict 或指標流程。

## 參考來源

- [官方模型 revision 檔案樹與 license](https://huggingface.co/intfloat/multilingual-e5-small/tree/614241f622f53c4eeff9890bdc4f31cfecc418b3)
- [官方 model card（prefix、pooling、512 tokens、384 維）](https://huggingface.co/intfloat/multilingual-e5-small/blob/614241f622f53c4eeff9890bdc4f31cfecc418b3/README.md)
- [官方模型 config](https://huggingface.co/intfloat/multilingual-e5-small/blob/614241f622f53c4eeff9890bdc4f31cfecc418b3/config.json)
- [官方 pooling config](https://huggingface.co/intfloat/multilingual-e5-small/blob/614241f622f53c4eeff9890bdc4f31cfecc418b3/1_Pooling/config.json)
- [Hugging Face revision API（檔案 size／LFS SHA metadata）](https://huggingface.co/api/models/intfloat/multilingual-e5-small/revision/614241f622f53c4eeff9890bdc4f31cfecc418b3?blobs=true)
- [PyPI JSON API 說明](https://docs.pypi.org/api/json/)
- [PyTorch macOS／Python 支援說明](https://pytorch.org/get-started/locally/)

## 受限環境驗證執行前停機（2026-10-16）

使用者已明確核准下載必要套件與 multilingual-e5-small 指定 revision 的 9 個推論檔案，建立獨立環境並量測載入資源。本次先依要求重做唯讀預檢；因即時 swap 狀態顯示顯著記憶體壓力，於任何環境建立、套件下載或模型下載之前停止。

### 當次實測快照

| 項目 | 實測值 | 判讀 |
|---|---:|---|
| 實體 RAM | `8,589,934,592 bytes`（8 GiB） | `sysctl -n hw.memsize` |
| 專案所在磁碟可用空間 | `21,767,932 KiB`（`22,290,362,368 bytes`，約 `20.76 GiB`） | `df -Pk .`；高於 4 GiB 保留線 |
| macOS memory free percentage | `30%` | `memory_pressure -Q`；單獨此值不足以解除停機 |
| Swap | 總量 `15,360 MiB`；已用 `14,854.06 MiB`（約 `14.51 GiB`）；可用 `505.94 MiB`（約 `0.49 GiB`） | `sysctl vm.swapusage` |
| 相關程序 | 未發現 M2.2b、E5、Hugging Face、PyTorch 或 uv 安裝／下載程序 | 升權唯讀 process-list 篩選只見 VS Code Python environment helper 與 Pylance 等非本任務程序 |

本次較早的同一輪磁碟快照為 `20,091,832 KiB` 可用；其後快照增加 `1,676,100 KiB`（約 `1.60 GiB`）。原因未確認，不作歸因。兩次快照都高於保留線，但空間變動仍需在日後操作前重新檢查。

### 停止結果

- **記憶體閘門未通過**：15 GiB swap 中約 14.51 GiB 已用、僅約 0.49 GiB 可用。依「系統出現記憶體壓力即停止」條件，不以 30% free percentage 抵銷此風險。
- 未建立驗證 venv 或工作目錄；未下載任何 wheel、模型檔或其他檔案；未安裝或載入套件／模型；未建立 embedding cache；未讀取正式資料或 test rows。
- 沒有修改既有 Python 環境，也沒有執行 embedding、訓練或指標計算。
- 未產生任何部分模型下載或安裝輸出，因此未清理檔案。
- M2.2b E5 資源閘門維持 **blocked**。之後需在系統記憶體壓力解除、swap 狀況穩定且重新通過 RAM／磁碟檢查後，才能重新評估受限驗證；不得把本次視為下載／載入驗證通過。

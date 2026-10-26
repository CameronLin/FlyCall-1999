# 09: M2.2b 凍結 E5 嵌入與一般分類比較

**What to build:** 依 spec v0.2 建立可重現的 `intfloat/multilingual-e5-small` 凍結嵌入流程與 embedding cache，比較 `embedding → Logistic Regression`、`embedding → MLP`、`embedding → PCA(k) → MLP`。此 ticket 將 spec M2.2 與 M2.3 的前三項必要 baseline 收在同一實作工作；不包含 Fly A／Fly B、LDA、共用正式 evaluator 或一次性 test 評估。

**Blocked by:** 01 M2.1 資料契約與唯讀 loader (completed); E5 Windows resource gate passed on 2026-10-26. The 2026-10-21 macOS swap/Activity Monitor snapshot below is historical and does not describe this computer.

**Status:** completed for provisional M2.2b scope (Windows E5 gate, train/validation comparison, and runtime/cache regression coverage passed; formal test evaluation remains gated by M2.4 and manual review)

**Latest resource gate:** passed for this Windows x64 CPU environment; 6.33 GiB RAM and 4.80 GiB commit were available before model load, full-run peak working set was 1.24 GiB, and project disk free stayed above 774 GiB. See [Windows gate and provisional run report](../research/m2-2b-e5-windows-gate-and-provisional-run-20261026.md).

## 依賴與邊界

- M2.1 loader 已完成，是資料契約稽核入口；沿用 frozen manifest 中的既有 split，不重切資料。
- M2.2a 已完成，僅作為既有 TF-IDF smoke baseline 的參考，不是本 ticket 的依賴，也不覆寫其程式、結果或報告。
- 不依賴 M1.1／M1.2／M1.3。正式資料仍為合成資料且 `review_status=pending_manual_review`。
- 在人工複核門檻通過前，任何正式資料上的執行只可標示 `smoke_test`／`provisional`；不得產生正式效能結論或使用 test。
- 本 ticket 不修改正式資料、Pilot、split、taxonomy、M1.1／M1.2／M1.3 產物或 M2.2a 結果。不得另行 random split。

## 已選定且已 runtime 驗證的模型目標

2026-10-16 查核官方 Hugging Face model card 與檔案樹：

- 使用者於 2026-10-21 選定唯一專案目標 `intfloat/multilingual-e5-small`；不再把 multilingual-e5-large 作為候選。官方頁面標示 MIT license。
- 目標 revision：`614241f622f53c4eeff9890bdc4f31cfecc418b3`；prefix：`query: `；`max_seq_length=512`；output dimension：384；pooling：masked mean pooling；`normalize_embeddings=true`。
- Windows 受限執行已確認 CPU、`batch_size=1`，載入成功；固定 384 維、mean pooling、Normalize module 與 tokenizer 行為均於本機核對。
- 官方 `main` 的該 revision 已有前次唯讀查核紀錄。使用前仍須在資源閘門允許時確認不可變 commit、必要檔案及 SHA-256，並於執行時驗證模型輸出維度及 tokenizer 行為。
- 2026-10-16 官方 revision API 列出 SentenceTransformer 推論保守必要集合共 9 檔、`492,795,290` bytes（`469.97 MiB`）：`model.safetensors`、`config.json`、`modules.json`、`sentence_bert_config.json`、`1_Pooling/config.json`、`tokenizer.json`、`tokenizer_config.json`、`special_tokens_map.json`、`sentencepiece.bpe.model`。其中 `sentencepiece.bpe.model` 是 slow-tokenizer fallback；若日後固定 fast-only loader 並 runtime 證明不需 fallback，才可重新核定最小集合。當時未有本機副本；2026-10-21 唯讀盤點已在 Hugging Face cache 找到該 revision 的 9 個檔案及相符大小，但尚未核對本機 checksum 或載入。完整 repository 約 2.28 GB，含替代 `pytorch_model.bin`、ONNX／OpenVINO 檔案及 README；不能直接下載整個 repository。
- 官方頁面及檔案參考：
  - [Model card at selected revision](https://huggingface.co/intfloat/multilingual-e5-small/blob/614241f622f53c4eeff9890bdc4f31cfecc418b3/README.md)
  - [Observed immutable repository revision](https://huggingface.co/intfloat/multilingual-e5-small/tree/614241f622f53c4eeff9890bdc4f31cfecc418b3)
  - [Model config](https://huggingface.co/intfloat/multilingual-e5-small/blob/614241f622f53c4eeff9890bdc4f31cfecc418b3/config.json)
  - [Mean-pooling config](https://huggingface.co/intfloat/multilingual-e5-small/blob/614241f622f53c4eeff9890bdc4f31cfecc418b3/1_Pooling/config.json)

官方檔案 bytes、metadata SHA、CPU wheel 解析及估算已記於 [M2.2b E5 資源閘門唯讀預檢](../research/m2-2b-e5-resource-preflight-20261016.md)。2026-10-21 在本機 cache 僅核對路徑與大小；沒有執行模型載入或 embedding，也沒有安裝套件。

## 資源閘門

**目前狀態以最新 Windows 執行為準：passed。** 2026-10-26 CPython 3.14.3 x64；模型載入前可用 RAM 6.33 GiB、commit 4.80 GiB、Windows memory load 59%、專案磁碟可用約 774.98 GiB。完整 E5 embedding run 峰值 working set 1.24 GiB，峰值 pagefile 2.24 GiB；執行後可用 RAM 5.66 GiB、commit 4.10 GiB、磁碟約 774.94 GiB。各項均高於現行停止線。詳見 [Windows gate report](../research/m2-2b-e5-windows-gate-and-provisional-run-20261026.md)。以下 2026-10-16／21 資源資料均為舊 macOS 電腦的歷史快照，不再代表目前執行環境。

### Historical macOS preflight notes (superseded by the Windows run above)

2026-10-16 最新唯讀預檢：實測 RAM `8,589,934,592` bytes；macOS 14.5 arm64；最新 `df -Pk .` 可用 `21,161,712 KiB`（`20.18 GiB`）。預檢較早磁碟快照為 `23,260,176 KiB`，累計相差 `2,098,464 KiB`（約 2.00 GiB）；原因未查明，不推測為特定程序。`~/.cache/uv` 實測 `1,207,952 KiB`，已計入磁碟佔用。M2.2a CPython 3.13.0 環境已有 NumPy 2.5.4／scikit-learn 1.9.1；M3.1 CPython 3.14.8 環境已有 PyTorch 2.14.1；兩者分開，均缺其餘 E5 stack，不可視為整合環境。

已知磁碟量級（非資源放行）：模型／tokenizer 所列檔案約 493.17 MB，需作為持久 cache 空間下限；若下載途中一份約 471 MB 的權重 partial 與完整快照同時存在，已知模型相關佔用可到約 964.17 MB，尚未含套件 wheel／安裝副本、cache metadata 與分類 run 暫存。上述 partial-file 情境只是容量規劃假設，下載器實際行為仍須核對。官方 config 顯示 float32；約 471 MB 的權重檔只代表磁碟量級，不能當作程序峰值 RSS，也未包含 tokenizer、runtime、activations 或分類模型。此前 peak RSS 容量估算採 batch 4；它是歷史外推，不能視為目前 batch 1 設定的實測或安全上界。

本次以 PyPI metadata 為來源、以實際 CPython 3.13 與 3.14 interpreter 執行 `uv pip compile --only-binary :all: --no-cache --no-python-downloads`，兩者各自成功解析同一組 42 個版本。wheel bytes 合計分別為 `198,701,986` bytes（3.13）及 `198,750,040` bytes（3.14）；已在資源報告逐一列出 direct／transitive 套件及 wheel bytes。這是索引 metadata 計算，不是 wheel 下載或安裝實測。依保守預算（模型 cache 469.97 MiB、等量下載 staging、套件 wheels 189.5 MiB、venv 解壓配置 1.5 GiB、embedding/cache 16 MiB、run/temp 256 MiB），以最新 `20.18 GiB` 可用量扣除資源預算及預檢中已觀察的 `2.00 GiB` 波動 reserve，估計仍剩 `15.31 GiB`，高於 4 GiB 線；其中 venv、staging 及波動 reserve 都不是未來硬性上界。

截至 2026-10-21，E5 peak RSS 只有按 float32 權重、batch 4／512 token 張量尺寸與非 E5 fixture RSS 推估約 2.5–3.0 GiB，當時尚未載入模型，因此資源閘門仍 blocked。以下是該次歷史快照的下載前檢查清單；Windows 實測已於 2026-10-26 通過並取代這個狀態：

1. 記錄 Python 版本、架構及當下 RAM／磁碟快照；確認既有隔離環境，不改系統 Python。
2. 使用者核准後，在單一隔離環境安裝選定並鎖定的 CPU 執行版本；量測安裝目錄、wheel cache／暫存實際值與整合 import。
3. 使用者核准模型載入後，先用受限的小型 fixture、CPU、`batch_size=1` 與 512-token 上限量測 E5 peak RSS；列出權重、tokenizer、forward activations、runtime 與 classifier 工作區。過往 batch 4 的容量估計不代表目前設定的峰值或安全上限。若無法建立可信上限，維持 blocked。
4. 執行前再次刷新 RAM／磁碟，將模型快取、下載 staging、wheel、venv、embedding cache、run outputs／temp 實測或已核實估算相加；最壞峰值後仍須至少保留 4 GiB，任一空間波動或項目不明即停止。
5. 完成實際下載後核對本機必要檔案 SHA-256、revision、384 維 mean pooling、prefix 與 truncation 行為；沒有本機檔案 hash 前不得宣稱模型 cache 完整。

僅供容量規劃的已知下限：float32 embedding 矩陣 train+validation 850×384 約 1,305,600 bytes（約 1.25 MiB），不含 ID、manifest、格式開銷或 PCA／模型工作區。模型檔與 tokenizer 的約 493.17 MB 不是套件與暫存總需求；不能以此宣稱已通過資源閘門。

## 資料與前處理契約

- 唯一文字特徵為 `transcript`；不把 ID、label、scenario、scenario_family_id、split、generator、prompt、review 狀態或其他管理欄位送入 tokenizer／encoder／分類器。保留 `R:`／`L:`、繁體字、原標點及來源 Unicode code-point 序列，使用嚴格 UTF-8；不自行做 NFC／NFKC／簡繁轉換，不添加案件類別提示。依 M3.0 契約記錄 tokenizer 內部 normalization。
- 對每筆 train／validation 文字加固定 `query: ` 前綴；encoder 凍結，批次輸出維度必須核對為 384 並做 L2 normalization。記錄前處理版本、prefix、tokenizer／encoder revision、token limit、實際截斷筆數與比例。過長輸入須先產生可稽核診斷並依明確政策處理，禁止靜默截斷。
- Test 的文字不得進入 tokenizer、encoder、embedding cache、PCA、任何模型的 fit／transform／predict 或指標流程。M2.1 loader 如被用來做全資料契約稽核，僅限稽核用途；模型流程邊界須以明確的 train／validation-only 介面及 fixture 測試保證。Test 一次性閘門不在此 ticket 執行。
- Embedding cache 位於 `.scratch/1999-connectome-demo/` 下的專用 cache 目錄，不納入正式資料、不提交模型權重或大型 cache。cache key 至少包含 transcript SHA-256、model ID、不可變 revision／檔案 hashes、tokenizer revision、prefix、前處理版本、`max_seq_length`／截斷政策、pooling、normalization、dtype 與輸出 dimension；目前 key 亦包含受限裝置及 batch size。相同 key 可重用；文字或任一設定／來源版本改變必須失效。cache manifest 記錄資料來源 checksum、record ID、split、模型／套件版本與輸出 checksum；不得為了預先填 cache 而處理 test。

## 比較流程

沿用 frozen manifest 的 train／validation split 與 label 順序：

1. `embedding → Logistic Regression`
2. `embedding → MLP`
3. `embedding → PCA(k) → MLP`

Encoder 保持凍結。所有有擬合狀態的轉換只可 `fit` train；validation 只可使用已在 train fit 的轉換呼叫 `transform`，並用於預先列出的候選選擇。PCA 的 k 與 MLP／Logistic Regression 候選設定須在檢視 validation 結果前登錄，且不得超過 train 可用 rank；不得使用 test 選特徵、調參、選模或選 seed。Smoke 執行可用一個預先固定 seed；每次 run 記錄實際參數、版本、source hashes 與 seed。

報告 train／validation 的 Accuracy、Macro-F1、固定五類順序的 precision／recall／F1、support、confusion matrix、fit／transform 時間、peak RSS 與磁碟變化。資料仍未人工複核時，報告與預測均標示 `synthetic`、`pending_manual_review`、`smoke_test`／`provisional`；不可寫成正式模型效能。

## 可先用 fixture 完成

- 不使用 E5 權重的可注入 fake encoder、文字前處理、token 長度／截斷診斷、cache key／命中／失效與 manifest 格式。
- 驗證固定 384 維契約、L2-normalization 的資料流、train-only fit／validation-only transform、PCA rank 邊界、label 順序、同家族不跨 split 的資料介面、reproducible seed／輸出。
- 用 sentinel／會在被呼叫時失敗的 test fixture 證明 test transcript 不會交給 tokenizer、encoder、cache、PCA 或分類器；不得讀取正式 test rows。
- 可建立隔離環境需求檔草案與不下載的資源盤點工具；在 resolver 估算和資源閘門通過前不安裝依賴。

## 人工複核前禁止

- 不得把 pending 資料的分數寫成正式效能、不得將 AI 複核當人工通過。
- 不得將任何 test transcript 傳給模型或 tokenizer，不得產生 test 預測或指標；M2.4 的一次性 test 評估必須等人工複核品質閘門、候選清單及設定都核准並鎖定後另行處理。
- 依 spec 7.3，正式評估前至少每類人工抽查 20 筆並涵蓋三個 split；複核包中所有 AI revise 與需人工特別確認項目須有人工處置。此閘門未通過時只能做明確標示的 train／validation smoke/provisional 工作。

## 產物與驗收條件

預期產物：可測試的 embedding／cache／baseline 模組及隔離依賴宣告、fixture tests、train／validation-only smoke runner、embedding manifest、三個候選的 provisional 比較報告。所有生成檔寫在 `.scratch/1999-connectome-demo/`；不改正式資料或 M2.2a 既有輸出。

- [x] 在安裝／模型下載前完成即時資源閘門並在隔離環境通過；記錄必要 model files、CPU dependency lock、venv/cache、peak RSS 與保留空間。詳見 Windows gate report。
- [x] 將不可變 model revision、license/source、每個必要檔案 SHA-256、`query: ` prefix、512-token 上限、masked mean pooling／384 維與實際 L2-normalization 寫入 encoder／embedding manifest；執行時核對實際輸出維度。
- [x] 以 TDD 測試前處理、截斷報告、可重現 cache key、cache 命中及失效、維度／標籤順序與錯誤輸入；fixture 不下載或載入 E5。
- [x] 以測試證明所有估計參數只在 train fit，validation 僅 transform；test transcript 不會到達 tokenizer、encoder、cache、任何 fit／transform／predict 或指標程式。
- [x] 驗證三個 classifier 流程只接收 train／validation，沿用 frozen scenario-family split，不重新切分；seed 42、PCA k=32、候選參數與依賴版本先行登錄。
- [x] 通過資源閘門後，以 frozen train／validation 執行固定 seed 的 `smoke_test`／`provisional` 比較；記錄契約稽核、split counts、來源 SHA、模型與套件版本、截斷、指標、耗時、peak RSS 與磁碟變化。Test downstream input、預測及指標皆為零／`not_run`。
- [x] 正式 JSONL、CSV、taxonomy、split manifest 及其餘凍結輸入執行前後 checksum 不變；未更改 `review_status`。
- [x] 報告及輸出標示合成資料、`pending_manual_review`、`smoke_test`／`provisional`；沒有產生正式效能結論。

## 尚未建立的後續工作

M2.3 LDA baseline 與 M2.4 evaluator/test gate 已各有獨立 tickets 11 與 10。本 ticket 不執行 test 評估；新 runtime 與 model-file SHA cache key 的 regression coverage 完成前，狀態維持 in-progress。

## Fixture-only 進度（2026-10-16）

**已完成，限於合成 fixtures：**

- 新增 `src/flycall_data/embedding_pipeline.py`：可注入 `Encoder` 的 `embed_texts(...)`、內容定址 JSON cache、明確 train／validation `SplitTexts` 與 `SplitEmbeddings` 型別、`run_baseline(...)` 入口及固定 label order 的 metrics。
- Cache key 含原始 transcript SHA-256、model ID／revision、tokenizer revision、prefix、前處理版本、sequence length／截斷政策、pooling、normalization、dtype、維度、device 與 batch size。cache entry 原子寫入；相同輸入及設定可命中，不同文字或設定會失效。
- `SplitTexts` 在建構時拒絕 `test`；`embed_texts` 接收明確 split batch，故 test 文字不能進 encoder/cache。`SplitEmbeddings` 與 `run_baseline` 也拒絕 test，baseline 介面沒有 test 參數。Train／validation 的 record ID、family ID、特徵維度與標籤順序會檢查；validation family 不得與 train 重疊。
- 三種 fixture 候選已實作：scikit-learn Logistic Regression；PyTorch CPU MLP；PyTorch train-only PCA(k)→MLP。PCA 僅以 train fit，validation 僅 transform／predict；rank 不足時明確失敗。結果提供固定 label order 的 Accuracy、Macro-F1、per-class precision／recall／F1、support 與 confusion matrix。
- 新增 `tests/test_embedding_pipeline.py`、`tests/test_embedding_logistic.py`、`tests/test_embedding_torch.py`。Mock encoder 僅對短小合成繁體中文及合成向量工作；cache 使用測試 temporary directory。

**既有隔離環境與測試結果：**

- M2.2a 環境：CPython 3.13.0 arm64，NumPy 2.5.4、scikit-learn 1.9.1；用於共同介面與 Logistic Regression fixtures。沒有安裝 PyTorch。
- M3.1 環境：CPython 3.14.8 arm64，PyTorch 2.14.1 CPU；用於共同介面、MLP 與 PCA→MLP fixtures。沒有安裝 NumPy 或 scikit-learn；Torch 測試遇到其可選 NumPy 初始化警告，但全部僅用 Python lists 與 PyTorch tensors 並通過。沒有建立新環境或安裝／下載套件。
- TDD 先紅後綠：共同介面測試先因 `embedding_pipeline` 不存在而失敗；LR 測試先因 `run_baseline` 尚不存在而失敗；PyTorch 測試先因 MLP 設定介面尚不存在而失敗。完成實作後，新 fixture 測試共 10 個不同案例均通過；共同介面各在兩個環境各跑一次，總計 **15 test executions passed**。
- 執行命令：

  ```sh
  PYTHONPATH=src .scratch/1999-connectome-demo/env/m2-2a-smoke/bin/python -m unittest discover -s tests -p 'test_embedding_pipeline.py' -v
  PYTHONPATH=src .scratch/1999-connectome-demo/env/m2-2a-smoke/bin/python -m unittest discover -s tests -p 'test_embedding_logistic.py' -v
  PYTHONPATH=src /private/tmp/flycall-m31-preflight-venv/bin/python -m unittest discover -s tests -p 'test_embedding_pipeline.py' -v
  PYTHONPATH=src /private/tmp/flycall-m31-preflight-venv/bin/python -m unittest discover -s tests -p 'test_embedding_torch.py' -v
  ```

**目前仍未完成／阻塞：**

- [x] E5 Windows 資源閘門與固定 revision runtime 已通過；九個必要檔案 checksum、整合 CPU runtime、peak working set 與可用空間均已核對，見 2026-10-26 Windows gate report。
- [x] 實際 E5 tokenizer、512-token 截斷統計、masked mean pooling、384 維輸出與 unit norm 已核對；850 筆 train／validation inputs 中 0 筆截斷。
- [x] Frozen split 上 700 train／150 validation 的 E5 embeddings 與四個 provisional 候選已執行，test 下游輸入／預測／指標為 0／`not_run`；資料與結果仍是 synthetic／pending manual review／provisional。
- [x] Fixture regression coverage for the new runtime and model-file SHA cache key is complete; `test_e5_runtime` and `test_embedding_pipeline` passed.
- [x] 人工複核品質閘門尚未通過；不可發布正式效能或 test 結果。M2.4 test 一次性 evaluator 不屬於本 ticket。

既有 fixture 測試不等於 E5 結果；目前 E5 train／validation run 也只可用作暫行流程驗證，不能代表通過人工複核或正式分類效能。整張 ticket 維持 `in-progress`，直到 runtime/cache regression coverage 及其他 ticket 範圍完成。

## Comments

- 2026-10-16：依 spec v0.2、M2.1、M2.2a、M3.0 契約及現有程式盤點建立。確認目前只有 01 M2.1 與 06 M2.2a 涵蓋 M2 工作；M2.2a 不取代 spec M2.2／M2.3。沒有修改 spec、資料、split、connectome 產物或既有模型結果，沒有讀取 test rows、下載／載入模型、安裝依賴、執行 embedding 或訓練。
- 同日：官方卡片核實 MIT、`query: `、512-token cap；model config／pooling config 顯示 384 維 mean pooling。環境中 E5／PyTorch 依賴缺失。模型與 tokenizer 公開檔案大小可做初步估算，但實際 CPU 依賴解析 bytes 與 8 GiB 下峰值 RSS 尚無可信估算，因此 E5 執行階段保持 blocked；fixture-only 工作可先開始。
- 同日：依使用者指示先確認並重用 M2.2a scikit-learn 環境及 M3.1 PyTorch fixture 環境；不建環境、不重複安裝。完成 TDD fixture-only cache／encoder／LR／MLP／PCA→MLP，10 個不同測試案例通過（含跨環境重跑）；未讀正式資料、test rows、E5 或 connectome 產物，未下載／載入模型、安裝套件或訓練正式資料。更新 fixture 子項完成紀錄；E5 resource gate、實際 E5 embeddings 與正式資料流程仍 blocked，整張 ticket 未完成。
- 2026-10-16：完成唯讀 E5 resource preflight，詳見 `../research/m2-2b-e5-resource-preflight-20261016.md`。核對指定官方 revision 的 9 檔保守必要集合、bytes／可用 SHA、MIT、`query: `、512 tokens、384 維 mean pooling；PyPI metadata resolver 對 CPython 3.13／3.14 arm64 各解析 42 個 wheel，合計分別 198,701,986／198,750,040 bytes。沒有下載任何 wheel／模型或安裝套件。最新 RAM 8,589,934,592 bytes、磁碟可用 21,162,832 KiB；扣除明列資源預算與預檢期間觀察到的 2.00 GiB 波動 reserve 後估計仍餘 15.31 GiB。E5 RSS、整合 runtime 及安裝／cache footprint 仍未實測或證明上界，故資源閘門及 ticket 保持 `blocked`，等待使用者核准下載與安裝。
- 2026-10-16：使用者核准受限環境驗證後，重新執行唯讀資源預檢。RAM 為 8,589,934,592 bytes，磁碟可用 21,767,932 KiB；`memory_pressure -Q` 顯示 30% free，但 `sysctl vm.swapusage` 顯示 15,360 MiB 中 14,854.06 MiB 已用、僅 505.94 MiB 可用。依停止條件判定有顯著記憶體壓力，在建立環境、下載／安裝套件或模型之前停止。沒有修改現有 Python 環境、下載或清理任何檔案，也沒有讀取正式資料、test、載入模型或執行 embedding。詳見 `../research/m2-2b-e5-resource-preflight-20261016.md` 的「受限環境驗證執行前停機」；E5 gate 與整張 ticket 保持 `blocked`。
- 2026-10-21：使用者選定 multilingual-e5-small 為專案唯一嵌入目標，並指定固定 revision、query prefix、512 tokens、384 維、masked mean pooling、L2 normalization、CPU／batch 1 受限試跑。新增中央設定 `src/flycall_data/model_config.py`，並將 cache settings 的 key 欄位明確化為 model ID、revision、prefix、preprocessing、截斷、pooling、normalization、dtype、輸出維度及執行裝置／batch；mock fixture 測試確認 small／large 與 revision 不共用 cache。TDD 先因設定模組及新欄位缺失而失敗，再完成實作後通過 7 個相關測試。未下載、安裝或載入模型／依賴，未讀正式資料／Pilot／connectome／test rows，未執行 embedding、訓練或分類評估。small 僅為使用者選定，未通過本機驗證；資源閘門及整張 ticket 維持 `blocked`。
- 2026-10-21：依使用者要求完成 M2.2b E5 small 唯讀資源重查，詳見資源預檢報告「最新唯讀資源閘門重查」。實測 RAM 8,589,934,592 bytes、swap total 16,384 MiB／used 15,756 MiB／free 628 MiB、專案磁碟可用約 30.90 GiB；Activity Monitor 壓力圖為黃／琥珀色，非綠色。程序名稱篩選 `python`、`pip`、`uv`、`torch`、`install` 均未見符合列。指定 revision 的 Hugging Face cache 路徑存在，9 個必要檔案大小合計 492,795,290 bytes；僅核對路徑與大小，未核對 checksum 或載入。沿用 CPython 3.13 wheel 閉包估算 189.50 MiB；保守磁碟增量情境約 3.05 GiB，推估剩約 27.85 GiB，但 venv／staging／暫存尚未實測且非硬上界。因 swap free 低於 1 GiB 且壓力非綠色，資源閘門與 ticket 維持 `blocked`。沒有下載／安裝／載入、embedding、正式資料／Pilot／connectome／test rows 存取或 M2.3 fixture 測試。
- 2026-10-26：在新 Windows 11 x64 電腦完成即時資源檢查、CPython 3.14.3 隔離環境安裝與模型 runtime 驗證；資源閘門通過。九個 pinned model files（492,795,290 bytes）逐一通過大小/SHA；Sentence Transformers 6 runtime 確認 XLM-R tokenizer、normalizer fingerprint、512-token right truncation、masked mean pooling、384 維及 unit norm。使用固定候選與設定指紋，只處理 700 train／150 validation；850 筆中 0 筆截斷。完成 E5→LR、E5→MLP、E5→PCA(32)→MLP 及後續 ticket 11 的 E5→LDA(4)→LR provisional runs。完整 embedding cache 增加 6,873,061 bytes，peak working set 1,332,563,968 bytes；執行後可用 RAM 5.66 GiB、commit 4.10 GiB、磁碟約 774.94 GiB。來源 checksums 不變，test downstream count/prediction/metrics 為零／`not_run`。詳見 Windows gate report 與兩個 run artifacts。此結果仍為 synthetic／pending_manual_review／smoke_test／provisional；新 runtime 與 cache hash 的 fixture regression coverage 尚待補齊，因此 ticket 維持 in-progress。


- 2026-10-26 regression closeout: the selected M2 suite passed 58 tests: E5 runtime (7), evaluation/ledger (17), embedding pipeline (9), embedding Logistic Regression (3), embedding PyTorch baselines (2), LDA baseline (6), text baselines (5), and frozen dataset loader contract (9). Loader tests validated frozen source contracts; no formal test rows entered tokenization, embedding, model fitting/prediction, or formal test metrics. Windows CSV fixture newline handling was corrected so multiline transcripts compare consistently. M2.2b provisional scope is complete; outputs remain synthetic, pending manual review, smoke-test/provisional only.
- 2026-10-26 cache provenance correction: audit found that re-normalizing a cached vector changed 236/850 per-record hashes in the 20261025T185218Z rerun. Cache hits now validate unit norm and return the exact stored values. Corrected run `m2-2b-e5-provisional-20261026T015843Z` verifies all 850 cache vectors against its manifest with zero mismatches, no cache writes, and unchanged frozen data checksums. Its per-candidate validation accuracy/Macro-F1 matches the full run: LR 0.873/0.868, MLP 0.920/0.918, PCA(32)-MLP 0.907/0.906, and LDA(4)-LR 0.900/0.900. Test remains `not_run`.
- 2026-10-26 multi-seed closeout: reran the current M2.2b runner for seeds 42, 1337, and 2026. Each run completed all four E5 baselines, saved and reload-verified candidate checkpoints, and produced fixed-taxonomy-order train/validation logits. The three manifests report zero tokenizer test inputs, embeddings, predictions, and metrics; all recorded output hashes pass. These runs feed the M3.4 validation-only comparison and remain provisional/pending manual review.

# 1999 案件分類：雙果蠅 Connectome 可行性 Demo Spec

版本：0.2｜日期：2026-10-12｜狀態：資料與切分已凍結；MaleCNS v1.0 已確認為來源起點；資料檔選擇與研究決策仍待查核

本文件依據 10/6 討論及後續對話，參考 Matt Pocock 的 to-spec 七章模板撰寫。未取得既有程式庫、領域詞彙表或 ADR，因此以下模組與介面為提案；建立 tickets 前仍需由 Codex 檢查現行專案結構並沿用已有慣例。本版供後續建立 tickets 使用，不會自動建立或提交 issue。

## 版本紀錄

- v0.2（2026-10-12）：將已完成的 1,000 筆正式合成資料、現有 schema、frozen split 與複核狀態納入規格；確認 MaleCNS v1.0 為 connectome 來源起點並標出仍待核對的資料細節；明確 M2 可先行、M0/M1 為 Fly A/B 前置；將後續工作改寫為含依賴與驗收條件的 tickets。原始 v0.1 未覆寫，另存為獨立檔案 `1999-connectome-demo-spec-v0.1.md`。

## Problem Statement

研究者需要將老師提出的「兩個保留果蠅神經連接結構的模型，分別執行降維與案件分類」轉成可執行、可重現、可量測的初步實驗。第一階段所需的五類、1,000 筆合成案件已完成，並依情境家族切分為 train、validation、test。50 筆 Pilot 為獨立資料，不併入正式資料。

正式資料仍是合成資料，且目前資料列的 review_status 為 pending_manual_review。可先用於流程 smoke test 與初步 baseline；正式報告須揭露人工複核狀態及合成資料限制，不能將合成資料上的高分類分數視為真實 1999 業務成效。

已找到官方 MaleCNS v1.0 資料入口；仍需驗證本專案要使用的檔案、欄位、checksum、存取方式及模型化選擇。子圖選取、文字向量與神經元的對應方式，以及降維目標仍是工程假設，需透過 prototype 建立可行性證據，再與老師討論。不得將人工生成圖的結果當成真實 connectome 結果。

## Solution

建立可離線重複執行的研究流程：既有案件文字資料 → 固定文字嵌入模型 → 一般分類 baseline，以及在 connectome 來源與子圖通過查核後的 Fly A 低維表示 → Fly B 五類分類 → 指標與展示結果。

正式資料已存在；訓練流程必須讀取既有資料與 frozen split manifest，不得在訓練過程重新生成或重新切分資料。Fly A 與 Fly B 使用相同子圖拓樸、各自獨立的權重；保留原始有向連線，僅訓練既有邊。另建立一般分類與降維 baseline，將模型是否跑通、降維品質、分類品質及運算成本分開報告。

首版成功條件：完成可追溯的 connectome 來源查核與子圖轉換，在拓樸約束下完成有限且非零的梯度更新，產生五類分類結果、完整評估報告及可載入的 checkpoint。一般 baseline 可先於 connectome 來源查核獨立執行。分類勝過 baseline 不是首版必要條件。

## User Stories

1. 身為研究者，我希望查核 connectome 來源、版本與授權，以確保模型確實使用可追溯的生物連接資料。
2. 身為研究者，我希望匯入 neuron 與 connection 資料，以建立一致的有向圖表示。
3. 身為研究者，我希望保留原始 neuron ID 與內部索引對照，以追蹤子圖來源。
4. 身為研究者，我希望以固定 seed 選取子圖，以重現相同實驗。
5. 身為研究者，我希望看到節點數、邊數、連通性與可達性，以判斷子圖是否能傳遞輸入資訊。
6. 身為研究者，我希望先以 500 個節點驗證流程，再比較 1,000 與 2,000 節點，以評估資源成本。
7. 【先決條件已完成】身為研究者，我使用已核對的五類 taxonomy，避免把其他分類版本誤稱為官方分類。
8. 【先決條件已完成】身為研究者，我使用既有五類、1,000 筆合成案件執行分類；本專案不再建立或重生成這批資料。
9. 【先決條件已完成】身為研究者，我保留逐筆生成 metadata、scenario family 與人工複核狀態，以追溯資料來源；不假設資料一定有 label rationale 欄位。
10. 【先決條件已完成】身為研究者，我直接使用依情境家族凍結的既有 split，降低測試洩漏；訓練流程不重新切分。
11. 身為研究者，我希望快取文字向量，以避免重複執行昂貴的嵌入計算。
12. 身為研究者，我希望訓練保留距離的 Fly A，以檢驗低維映射品質。
13. 身為研究者，我希望另行測試類別導向的表示學習，以比較不同降維目的。
14. 身為研究者，我希望單獨訓練 Fly B，以量測固定表示下的分類效果。
15. 身為研究者，我希望訓練後原本不存在的邊仍不存在、存在的邊仍非零，以符合老師的拓樸要求。
16. 身為研究者，我希望比較一般模型與隨機拓樸，以區分降維、稀疏性與生物拓樸的影響。
17. 身為研究者，我希望看到 Macro-F1、混淆矩陣與錯誤案例，以避免只看整體 Accuracy。
18. 身為研究者，我希望記錄參數量、記憶體與時間，以判斷自己的設備是否可執行。
19. 身為研究者，我希望重新載入 checkpoint 能得到一致結果，以供展示與後續研究。
20. 身為展示者，我希望輸入案件後看到接電話、低維表示、送公文與預測類別，以向老師說明完整流程。
21. 身為展示者，我希望看到模型版本與模擬派送提示，以避免把 Demo 誤認為正式派工系統。
22. 身為開發者，我希望缺少資料、維度不符或訓練失敗時得到明確錯誤，以快速排除問題。

## Implementation Decisions

### 1. 決策狀態與開發順序

已完成並凍結：五類共 1,000 筆正式合成資料、每類 200 筆、70/15/15 的 record-level split、66 個有效情境家族及 frozen split manifest。資料位於 data/1999_synthetic/formal/v1.0.0/；Pilot 50 筆另存，不納入正式訓練。訓練工作不得重新生成資料、修改標籤或重新切分。taxonomy 與資料整理的先決工作不重開 tickets。

Connectome 來源已初步確認為 MaleCNS v1.0：MaleCNS 官方下載頁列有 `male-cns:v1.0`、bulk download 與連線資料檔；官方 release notes 記錄 v1.0 日期為 2026-06-08，官方下載頁標示資料採 CC-BY。Google Research 於 2026-09-03 的公告描述該圖譜超過 166,000 個神經元及 125 million 個突觸連線。這些規模只作背景，不作程式中的固定驗收數字。

M0.1 仍須決定並記錄專案實際使用的資料檔／API、連線欄位解讀、最低信心篩選、存取方式、檔案 checksum 及完整 attribution。已知官方起點： [MaleCNS v1.0 下載頁](https://male-cns.janelia.org/download/)｜[版本說明](https://male-cns.janelia.org/release/)｜[Google Research 公告](https://research.google/blog/a-connectomics-milestone-mapping-the-complete-male-fruit-fly-brain/)。

仍屬暫定或待實驗：connectome 子圖規模、輸入／輸出節點數、T、k=32、distance-preserving loss、文字 encoder 的本機 runtime 驗證、recurrent message passing 細節及模型超參數。E5 small 的目標設定已由使用者選定，但未完成下載或本機驗證；不得將其描述為已通過的執行結果。這些設定須寫入設定與 run manifest，不應描述為已證實的研究結論。

開發依賴：
- M2 資料讀取、embedding 與一般 baseline 可立即開始，並可與 M0/M1 平行。
- M0 查核 connectome 來源後，M1 才能匯入圖、選取子圖並驗證 I/O 可達性。
- M3 Fly A/B 依賴 M1 的有效子圖；M3 同時使用 M2 的資料、embedding 與評估介面。
- M4 Demo 依賴可載入的 checkpoint 與共用 predict 介面。
- M1 未完成前，可完成 M2 與一般 baseline；不得用人工生成圖冒稱真實 connectome 實驗。

### 2. 技術與模組邊界

使用 Python、uv、PyTorch、NumPy/SciPy、scikit-learn、sentence-transformers 與 Streamlit；版本在首次可運行後鎖定。CPU 為必要支援，CUDA/MPS 為可選加速，稀疏算子不相容時明確回退 CPU。

模組責任：來源匯入、子圖建構、案件資料驗證與切分、嵌入與快取、connectome 計算核心、訓練編排、baseline、評估、checkpoint 與推論、展示。展示呼叫共同推論介面，不重複實作前處理或模型邏輯。

頂層操作包括 prepare-connectome、prepare-data、embed、train、evaluate、predict、demo。prepare-data 只讀取、驗證既有正式資料及 frozen manifest，不生成資料或重新切分。以單一設定描述實驗；操作輸入為設定與必要資料，輸出為 run ID、產物位置及摘要。不存在的來源或 checkpoint 應拒絕執行。

### 3. Connectome 匯入合約

來源紀錄包含官方 URL、MaleCNS release、下載日期、授權與 attribution、存取條件、使用的檔案/API、檔案 checksum、節點及邊欄位定義。官方 MaleCNS v1.0 下載頁提供 neuPrint API 及 bulk connectivity table；開發者需比較兩種路徑並固定一種可重現方案。只下載必要資料表；不要求完整顯微影像。

標準 neuron 欄位為 neuron_id，以及可選 region、cell_type；標準 edge 欄位為 source_id、target_id、synapse_count，以及可選 neurotransmitter。ID 保持字串或無損整數，禁止轉成浮點後再轉回。

source → target 表示訊號方向；若輸出矩陣，明確定義 A[target, source]。重複 neuron pair 聚合為一條邊，synapse_count 加總。缺失節點、非正計數、方向未定義須報錯或輸出明確清洗紀錄。預設不篩邊、不移除自迴圈，任何篩選均需記錄；子圖保留所選節點間所有原始邊。

### 4. 子圖選取與 I/O 可達性

先從指定腦區的候選節點選 seed；沒有可靠區域資訊則從完整候選集選取。以無向視圖 BFS 擴張，固定排序與 seed，抽取 500 個節點後建立有向 induced subgraph。無向視圖只用於選取，不改變模型邊方向。

若所在連通分量不足 N，依固定順序更換 seed；不得從不相連分量湊數。輸出節點與邊清單、選取策略、seed、checksum、弱／強連通分量、孤立點、密度及度數分布。

弱連通不保證有向訊號可達。須選取不同的 input 與 output 節點集合，並檢驗每個 output 能在 T 步內由至少一個 input 到達。暫定各 32 個 I/O 節點、T=4；不足時調整 T 或重新選圖，記錄決策，不靜默繼續。500→1,000→2,000 的比較採相同 seed 的巢狀擴張；不將其解讀為特定腦區功能的生物學證據。

### 5. 有向循環圖的計算模型

採共享邊權重、固定步數的 recurrent message passing，保留有向循環，禁止為配合普通分層網路而將圖改成 DAG。初始 hidden state 為零。外部向量經 trainable input adapter，只注入選定 input 節點；每一步沿既有 source → target 邊傳訊，以固定入度正規化聚合，加上輸入驅動後經 tanh 更新。T 步後只讀取 output 節點，經 readout 輸出。

Fly A 接收 d 維 embedding 並輸出 k 維；Fly B 接收 k 維並輸出 C 個 logits。adapter、readout 及必要節點 bias 屬外部人工介面，獨立記錄參數量，不聲稱它們來自 connectome。不得加入繞過圖核心、直接把 input 送到 readout 的捷徑。Fly A/B 拓樸相同、權重不共享。

以 edge list 與每條既有邊一個 trainable parameter 實作，不配置完整 N×N 可訓練矩陣；使用 scatter 聚合或已驗證的 sparse 算子。狀態記憶體約 O(batch×N)，邊參數約 O(E)，每步工作量約 O(batch×E)。

### 6. 嚴格保留零與非零

單純 mask 只能保證不存在的邊為零，不能保證存在的邊永遠非零。因此首版將既有邊有效權重定義為固定符號 ×（epsilon + softplus(raw_weight)），epsilon 暫定 1e-6；非邊不配置參數。raw_weight 有界化以避免數值溢位，訓練時檢查有限值。

首版若來源只有正 synapse_count，採全正符號並註明此限制，不自行推定抑制性。若後續有可信神經傳遞物質註解，可新增固定符號策略。此參數化限制既有邊的符號改變，需列入老師討論事項。初始化可使用正規化的 log(1+synapse_count)；確保每條邊的有效幅度至少 epsilon，避免與 loss 中的正規化混淆。

### 7. 案件資料與防洩漏

#### 7.1 現有正式資料與不可變條件

正式資料已生成，使用：
- JSONL：data/1999_synthetic/formal/v1.0.0/formal_dataset_v1.0.0.jsonl
- CSV：data/1999_synthetic/formal/v1.0.0/formal_dataset_v1.0.0.csv
- 標籤來源：data/1999_synthetic/taxonomy/current/taxonomy_v1.3.yaml
- frozen split manifest：data/1999_synthetic/taxonomy/current/formal_split_manifest_frozen_v1.0.yaml

正式資料為 1,000 筆、五類各 200 筆；每類 train/validation/test 為 140/30/30，全體為 700/150/150。66 個 scenario_family_id 各自只屬於一個 split。家族數配置依類別為：人行道 7/3/4、道路 7/3/4、公園 8/3/4、垃圾車 7/2/3、路面清潔 4/3/4。垃圾車的家族配置不同於早期草案；以 frozen manifest 為唯一依據，不得重新平衡家族或重新切分。

50 筆 Pilot 獨立保存，不併入正式訓練。正式資料與 Pilot 的 review_status 目前為 pending_manual_review。初步 smoke test 與 baseline 可使用現有資料，但須標為初步結果；不得把 AI 建議或自動掃描當成逐筆人工核准。

#### 7.2 資料欄位與特徵邊界

正式資料以實際 JSONL/CSV schema 為準。核心欄位包括 id、text、label_id、label_name、scenario_id、scenario_family_id、split、is_synthetic、generator_model、prompt_version、review_status；實作前仍須讀取實檔核對欄位名稱、型別、空值及 label_id 對照，不得因舊版規劃中的欄位名稱不同而改寫資料。generation_batch、source_type、label_rationale 等只有在來源檔實際存在時才可選用，不得假設必然存在。

分類模型只以逐字稿 text 作輸入，以 label_id 作目標。保留 R: 與 L: 角色標示。label_name、id、scenario_id、scenario_family_id、split、generator_model、prompt_version、review_status 及其他管理 metadata 不可作為模型特徵。scenario_family_id 與 split 僅用於分組、防洩漏及評估。

#### 7.3 複核狀態

正式資料人工複核包目前包含 399 筆：validation 150、test 150、train 99（33 個 train 家族各抽 3 筆，seed 20261012）。AI 欄位含 375 筆 pass、24 筆 revise、0 筆 reject；103 筆標示需人工特別確認。人工決定欄仍全部 pending，AI 建議不代表核准。

可立即跑結構 smoke test、train/validation 的探索性 baseline；這些結果必須標示 `provisional`，並揭露資料仍為合成且 `review_status=pending_manual_review`。Test 在所有模型、超參數及選模規則鎖定前不得檢視；鎖定後對預先聲明的模型一次性執行最終比較，不可依 test 結果再調整模型或資料。

正式報告的人工複核門檻沿用原規格：每類至少人工抽查 20 筆，涵蓋 train、validation、test；AI 複核包中所有 `需人工特別確認` 與 AI `revise` 的紀錄都須有人工處置。可用既有 399 筆複核包協助抽查；人工決定需另行記錄，不可把 AI 建議或程式掃描改寫為人工通過，也不可更改正式資料列的 `review_status`。未達門檻時只輸出 provisional report，清楚列出已複核數量、未複核項目及其限制。

#### 7.4 既有 split 與防洩漏

正式資料的 split 已按情境家族凍結，manifest 為：
`data/1999_synthetic/taxonomy/current/formal_split_manifest_frozen_v1.0.yaml`

訓練流程直接讀取資料中的 split，並在啟動時核對 manifest；不得另行 random split。檢查 scenario_family_id 無跨 split、每類筆數及各 split 配額與 manifest 相符。若資料與 manifest 不一致，停止訓練並回報，不得自動修補或靜默重新切分。

重複文字與高度相似案例的既有檢查結果應保留於驗證報告。若訓練程式發現重複或相似案例，不要自行移除、改寫或重分組正式資料；輸出問題清單並另開資料修訂任務。

### 8. 嵌入合約

使用者於 2026-10-21 選定 `intfloat/multilingual-e5-small`，不再把 multilingual-e5-large 作為本專案候選。目標設定為 revision `614241f622f53c4eeff9890bdc4f31cfecc418b3`、prefix `query: `、`max_seq_length=512`、輸出 384 維、masked mean pooling、L2 normalization；受限試跑指定 CPU、`batch_size=1`。此為目標設定，模型尚未在本機下載、安裝或載入；實際維度、pooling 與 tokenizer 行為仍須在 M2.2b 資源閘門通過後驗證。保持 encoder 凍結，批次產生向量並 L2 正規化。不得把設定值當成已完成 runtime 驗證。

記錄截斷長度、截斷比例與前處理版本；過長文字不可靜默丟失。快取 key 包含文字 hash、encoder revision、prefix、正規化與前處理設定。任何需要估計參數的轉換只在 training split fit。

### 9. Fly A 目標與 Fly B 訓練

第一個必要版本採 distance-preserving loss。以已 L2 正規化的 embedding 及 L2 正規化的低維輸出計算 pairwise Euclidean distance，最小化批次中不同樣本 pair 的距離平方誤差；排除對角線。兩端尺度一致，loss 使用 pair 平均，記錄 sampling seed。近零輸出需監測表示塌縮。

暫定 k=32；視覺化的二維投影另做，不能把 2D 圖當作模型實際分類輸入。可選第二版本使用 supervised contrastive loss，明確稱為「類別導向表示學習」，不冒稱 classical LDA。真正的 LDA 作為獨立 baseline，其輸出維度至多 C−1，五類最多四維。

先用 training split 訓練 Fly A，以 validation distance stress 選 checkpoint；凍結 Fly A 後訓練 Fly B，以 validation Macro-F1 選 checkpoint。首版不聯合微調，避免分類梯度改變降維目標。Fly B 輸出 logits，以 cross-entropy 訓練；softmax 分數稱為模型分數，不直接稱為校準機率。

暫定 Adam、learning rate=1e-3、batch=32、最多100 epochs、patience=10、gradient clipping=1.0、CPU、seed=42；均可設定。loss/gradient 非有限立即停止，保留錯誤與最後有效 checkpoint。選模規則固定，test 僅用於最終評估。

### 10. Baseline 與實驗表

| 優先度 | 流程 | 用途 |
|---|---|---|
| 必要 | Embedding → Logistic Regression | 原始表示分類基準 |
| 必要 | Embedding → MLP | 一般神經分類基準 |
| 必要 | Embedding → PCA(k) → MLP | 一般低維表示比較 |
| 必要 | Embedding → Fly A → Fly B | 老師提出的雙模型 |
| 第二階段 | Embedding → Fly A → MLP；Embedding → PCA(k) → Fly B | 分離 A、B 的影響 |
| 第二階段 | Embedding → LDA(≤C−1) → classifier | 監督式線性降維比較 |
| 第二階段 | 與真實圖相同 N/E 的隨機有向圖 | 區分稀疏性與拓樸影響 |

所有流程共用資料切分、embedding、指標與選模原則。超參數搜尋成本需記錄；PCA 的 k 不超過 training sample/feature 的可用 rank。LDA 與 k=32 的結果不能聲稱為同維度公平比較。

初版先跑一個 seed；正式比較結論至少使用三個訓練 seed，報告平均與標準差，分清圖抽樣 seed 與訓練 seed。模型與超參數依 validation 決定並鎖定後，才對預先聲明的候選流程一次性計算 test 指標；不得用 test 回頭選模型。隨機圖需明確記錄是否匹配度數分布；只匹配 N/E 的對照不能排除度數差異。

### 11. 結果與重現

每個 run 記錄完整設定、程式版本（有 Git 時用 commit）、依賴鎖定資訊、來源與子圖 checksum、split manifest、encoder revision、種子、設備、batch、T、k、訓練曲線及 checkpoint。

分類報告包含 Accuracy、Macro-F1、各類 precision/recall/F1/support、混淆矩陣與錯誤案例。降維報告包含 test distance stress、距離相關係數、輸出變異與範數；相關係數遇零變異回報 undefined，不填成零。大型 pair 評估可用固定 sampling 並記錄樣本數。

成本包含圖核心／adapter／readout 參數量、訓練耗時、warm-up 後 batch=1 的推論 p50/p95 及峰值記憶體。嵌入、A、B 的時間分項記錄，註明快取、設備及測量方法；GPU 計時須同步，不混同比較不同設備。

checkpoint 包含拓樸、I/O 節點、方向約定、模型配置、類別順序、encoder 資訊、權重與訓練狀態。推論時檢查 checksum、d/k/C 與類別順序一致；不相容拒絕載入。

### 12. 推論與展示合約

共同 predict 介面接收非空案件文字與已選 run，回傳 run ID、輸入／表示維度、label ID/name、依固定類別順序排列的模型分數、分項耗時及模擬派送資訊。空白、超長或模型不相容應有清楚錯誤；不得回傳看似成功的預設類別。

本機 Streamlit 顯示：民眾文字 → 果蠅 A 接電話與 d→k → 果蠅 B 送公文與五類分數 → 模擬分類結果。可提供幾個示例。僅顯示已查核的類別；若派送單位未查核，顯示「待人工確認」而非猜測機關。

標記「合成資料訓練／研究 Demo／模擬派送」。如顯示活化圖，限定抽樣規模與選取規則，稱為人工模型節點活化，不稱為真實果蠅神經活動。UI 最後開發，模型可先從 CLI 執行。

## Testing Decisions

優先以共同 pipeline／CLI 與 predict 介面測外部行為；只有方向、梯度及拓樸這些無法由最終分類分數辨識的核心性質，增加小圖專項測試。尚無既有程式庫，故沒有可引用的現有測試慣例。

| 驗收項目 | 測試方式與通過條件 |
|---|---|
| 來源可追溯 | manifest 含來源、版本、授權與 checksum；缺任一必要欄位拒絕正式真實圖實驗 |
| 有向資料正確 | 人工小圖含單向邊、迴圈、重複 pair；匯入後方向正確、計數聚合正確、未知節點報錯 |
| 子圖可重現 | 同來源與 seed 輸出相同 node/edge checksum；節點數為指定 N，保留所有 induced edges |
| I/O 有效 | 所有 output 在 T 步內可由 input 到達；失敗有明確報錯或紀錄後的重新選取 |
| 拓樸嚴格保持 | 比較訓練前後的有效邊支援集合，非邊仍無權重、每個既有邊有限且幅度≥epsilon |
| 能學習 | 小圖可完成 forward/backward/update；圖邊參數有有限非零梯度且至少一條實際更新；不能僅 adapter 更新 |
| 核心確實參與 | 小圖改動可達邊權重能改變預測或表示；驗證沒有繞過圖的 input→readout 捷徑 |
| 防洩漏 | scenario_family_id 不跨 split，完全重複文字不跨 split；fit 操作只取得 train；載入的 split 與 frozen manifest 一致 |
| 現有資料契約 | JSONL/CSV 筆數、label_id 對照、split 配額及 family 隔離符合 frozen manifest；資料檔 SHA-256 在訓練流程中不變 |
| 人工複核狀態 | pending_manual_review 不被程式改成 pass；AI 建議與人工決定分欄處理；初步結果明確標示尚未完成複核 |
| 嵌入快取 | 相同設定命中；revision、prefix、文字或正規化改變則失效；維度不符報錯 |
| 端到端 | 小型固定測試資料跑完嵌入替身、A/B 訓練、checkpoint、evaluate、predict，輸出維度與類別順序一致且有限 |
| checkpoint 一致 | 相同 CPU/eval 模式載入前後 logits 在明訂容差內一致；不相容配置拒絕載入 |
| 指標可信 | 使用已知 predictions 的 fixture 驗證 Macro-F1、support 與混淆矩陣；零變異距離相關不假造數字 |
| 展示一致 | UI 使用同一 predict 介面，示例結果與 CLI 一致；空白輸入有提示、模擬派送標示可見 |
| 真實資料 smoke test | 真實 500-node 圖與少量案件完成至少一個訓練 epoch，輸出完整來源與成本紀錄 |

小圖與少量資料驗證是必要的 correctness tests；1,000 筆完整訓練屬實驗，不要求每次 CI 重跑。非確定 GPU 算子與跨設備結果採容差比較，不承諾 bitwise 相同。分類分數門檻不是 correctness test，不能為了過測試修改 test 資料。

## Ticket 拆分與依賴

以下是可直接建立 issue 的範圍草案；每項已列依賴、產物與可驗收條件。未列入的工作（例如重新生成 1,000 筆、修改 taxonomy 或重切 split）不得由 Agent 自行新增。M2 可先行，不需等待 connectome 或人工複核；`provisional` 結果與正式報告依 7.3 的複核門檻區分。

| Ticket | 工作範圍與產物 | Depends on | 驗收條件 |
|---|---|---|---|
| M2.1 資料契約與唯讀 loader | 讀取既有 JSONL/CSV、taxonomy、frozen manifest；產生資料稽核摘要及可重用 loader。 | — | 驗證 1,000 筆、五類各 200、各 split 700/150/150、逐類 140/30/30、family 不跨 split、label 對照正確；資料檔唯讀且 checksum 不變；不符即明確失敗。 |
| M2.2 Encoder 與 embedding cache | 固定 multilingual-e5-small revision、prefix、前處理及實際 d；產生快取與 embedding manifest。 | M2.1 | 相同設定可命中快取；文字或設定改變會失效；只 fit train-only 轉換；記錄截斷與實際維度。 |
| M2.3 一般分類 baseline | 建立 Logistic Regression、MLP、PCA(k)→MLP、LDA(≤4)→classifier 訓練流程。 | M2.2 | 僅 train fit；依 validation 選模；輸出固定類別順序的 logits/predictions、設定與 checkpoint；提供至少一個 seed 的可重現 smoke run。 |
| M2.4 評估器與 provisional 報告 | 建立共用指標、混淆矩陣、錯誤案例、成本計量及報告產生器。 | M2.1–M2.3 | 通過已知 prediction fixture；可產生 train/validation 的 provisional 報告並標示複核限制；提供 test 一次性執行閘門，未鎖定模型清單、設定或人工複核門檻時拒絕產生正式 test 報告。 |
| M0.1 MaleCNS 資料來源 manifest | 固定 MaleCNS v1.0 的 API 或 bulk connectivity file；記錄 license/attribution、實際 schema、方向、信心欄位／篩選、存取步驟及 checksum。 | — | 小量下載或 API probe 可重跑；來源 manifest 欄位齊全；明確選定使用的 connection weight 及語意；不下載不需要的影像；遇存取或授權問題提供證據並停止真實圖支線。 |
| M1.1 有向圖匯入器 | 轉換所選官方 connectivity 資料為標準 neuron/edge 表。 | M0.1 | 保留原 neuron ID；方向依 source→target 合約；聚合重複 pair；缺節點、無效計數及未知欄位明確處理；小圖 fixture 驗證方向。 |
| M1.2 確定性子圖選取 | 固定 seed 選取 500 節點，輸出 induced directed subgraph；支援後續 1,000/2,000 節點巢狀比較。 | M1.1 | 相同資料及設定產生一致 node/edge checksum；保留所選節點間全部來源邊；選取策略、seed、N/E 及圖摘要寫入 manifest。 |
| M1.3 I/O 可達性與 graph manifest | 選定 input/output 節點並檢查 T-step 有向可達性。 | M1.2 | 每個 output 在指定 T 內可由至少一個 input 到達；失敗時按規則重選或明確停止；manifest 含 I/O IDs、T、方向、連通摘要及 checksum。 |
| M3.1 Sparse recurrent 圖核心 | 實作固定步數的有向 recurrent message passing 與 edge parameterization。 | M1.3 | 通過 Testing Decisions 的拓樸、非零、梯度及無捷徑測試；不建立 dense N×N 可訓練矩陣。 |
| M3.2 Fly A 訓練 | 使用固定 embedding 與圖核心學 d→k 距離保留表示。 | M2.2、M3.1 | train-only 更新；validation stress 選 checkpoint；有限 loss/gradient；輸出 d、k、seed、設定及 checkpoint。 |
| M3.3 Fly B 訓練 | 凍結 Fly A，訓練 k→5 logits 分類器。 | M3.2、M2.1 | cross-entropy 訓練；validation Macro-F1 選 checkpoint；不聯合微調 A/B；分類順序與 taxonomy 一致。 |
| M3.4 預先聲明的模型比較 | 比較 baseline、Fly A→B 與必要對照，產生比較報告與候選選定紀錄。 | M2.4、M3.3 | 先用 validation 完成選模；鎖定候選與設定、並滿足 7.3 人工複核門檻後，對預先聲明流程一次性評估 test；正式比較至少三個 training seeds，報告平均與標準差；不得用 test 反覆調參。 |
| M4.1 Checkpoint 與共同 predict API | 以選定 checkpoint 載入模型，提供 CLI/API 推論及版本檢查。 | M3.4 | 重載 logits 符合容差；驗證 checksum、d/k/C、類別順序；空白或不相容輸入明確報錯；含測試與簡短使用說明。 |
| M4.2 Streamlit 展示 | 串接共同 predict，顯示輸入、A/B 流程、五類分數及模擬派送。 | M4.1 | UI 與 CLI 同一筆輸入結果一致；標示「合成資料訓練／研究 Demo／模擬派送」；錯誤狀態與待人工確認資訊可見。 |

依賴圖：M2.1→M2.2→M2.3→M2.4；M0.1→M1.1→M1.2→M1.3→M3.1；M2.2 與 M3.1 完成後進入 M3.2→M3.3；M2.4 與 M3.3 完成後進入 M3.4→M4.1→M4.2。M2 與 M0/M1 可平行。M2.4 可先輸出 train/validation provisional 報告；正式 test 報告需完成模型與設定鎖定並滿足 7.3。

## Out of Scope

- 完整果蠅 CNS 的訓練、完整生物動力學或真實果蠅行為模擬。
- 電話接聽、語音辨識、串接正式 1999 系統、正式機關派工與公文寄送。
- 使用真實含個資通話、正式上線、帳號權限或雲端部署。
- 訓練 embedding encoder、聯合微調 A/B、神經拓樸搜尋與自動新增／刪除邊。
- 首版多訴求分類、未知類別拒答、分數校準與全面超參數搜尋。
- 宣稱生物拓樸優越、可替代人工分類，或從合成結果推論真實市民案件成效。

## Further Notes

### 待老師討論

1. 第一隻模型優先保留距離，還是以類別分離為目標？LDA 若指 classical LDA，需確認最多 C−1 維的限制；神經網路 contrastive learning 不等同 LDA。
2. 子圖是否應限定腦區／細胞類型？目前 BFS 是工程取樣，沒有功能對應的生物學主張。
3. 「非零維持非零」是否包含固定符號？首版正值參數化保證嚴格非零，但也限制權重符號。
4. 是否接受人工 input adapter、readout 與 recurrent dynamics？connectome 本身不是已定義好的 NLP 模型。
5. 是否沿用 AI-based MDS 題目，或改為 connectome 約束表示學習與分類？

### 開發 Agent 交接要求

依 Ticket 拆分表執行：M2 可先與 M0/M1 平行；M0 完成後才進入 M1，M1 與 M2 所需介面通過後才開始 M3，模型比較與 checkpoint 選定後完成 M4。每階段交付可重現命令、完成項目、驗收結果、耗時與限制。遇到未確認事項先採本文暫定值並寫入設定與 run manifest；來源不存在、授權不可用、資料欄位不明或架構無法符合拓樸要求時，停下受阻部分並回報證據，繼續獨立工作。不得默默換成隨機圖或其他 connectome 卻沿用原資料名稱。

首版交付應包括：設定與鎖定環境、來源與子圖 manifest、案件和切分紀錄、嵌入快取、baseline 與 A/B checkpoint、機器可讀指標、供老師閱讀的結果摘要、可操作的本機 Demo。

參考模板：https://github.com/mattpocock/skills/tree/main/skills/engineering/to-spec

來源： [MaleCNS 官方下載頁](https://male-cns.janelia.org/download/)｜[MaleCNS release notes](https://male-cns.janelia.org/release/)｜[Google Research 公告（2026-09-03）](https://research.google/blog/a-connectomics-milestone-mapping-the-complete-male-fruit-fly-brain/)

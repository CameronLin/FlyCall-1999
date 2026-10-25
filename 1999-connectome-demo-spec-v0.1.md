# 1999 案件分類：雙果蠅 Connectome 可行性 Demo Spec

版本：0.1｜日期：2026-10-07｜狀態：可開始分階段開發；研究決策待實驗與老師討論

本文件依據 10/6 討論及後續對話，參考 Matt Pocock 的 to-spec 七章模板撰寫。未取得既有程式庫、領域詞彙表或 ADR，因此以下模組與介面為新專案提案。交付為獨立開發規格，不涉及 issue tracker 發布。

## Problem Statement

研究者需要將老師提出的「兩個保留果蠅神經連接結構的模型，分別執行降維與案件分類」轉成可執行、可重現、可量測的初步實驗。應用主軸為 1999 市民專線案件文字，第一階段使用約 1,000 筆合成案件、五個類別。

目前尚未確定實際 connectome 來源、子圖選取方法、文字向量與神經元的對應方式，以及降維目標。需透過 prototype 建立可行性證據，再與老師討論。不能將合成資料的高分類分數視為真實 1999 業務成效，也不能預設生物拓樸優於一般模型。

## Solution

建立可離線重複執行的研究流程：案件文字 → 固定文字嵌入模型 → Fly A 低維表示 → Fly B 五類分類 → 指標與展示結果。

Fly A 與 Fly B 使用相同子圖拓樸、各自獨立的權重；保留原始有向連線，僅訓練既有邊。另建立一般分類與降維 baseline，將模型是否跑通、降維品質、分類品質及運算成本分開報告。

首版成功條件：完成真實資料來源查核與子圖轉換，在拓樸約束下完成有限且非零的梯度更新，產生五類分類結果、完整評估報告及可載入的 checkpoint。分類勝過 baseline 不是首版必要條件。

## User Stories

1. 身為研究者，我希望查核 connectome 來源、版本與授權，以確保模型確實使用可追溯的生物連接資料。
2. 身為研究者，我希望匯入 neuron 與 connection 資料，以建立一致的有向圖表示。
3. 身為研究者，我希望保留原始 neuron ID 與內部索引對照，以追蹤子圖來源。
4. 身為研究者，我希望以固定 seed 選取子圖，以重現相同實驗。
5. 身為研究者，我希望看到節點數、邊數、連通性與可達性，以判斷子圖是否能傳遞輸入資訊。
6. 身為研究者，我希望先以 500 個節點驗證流程，再比較 1,000 與 2,000 節點，以評估資源成本。
7. 身為研究者，我希望查核官方案件類別，以避免將自訂類別誤稱為官方分類。
8. 身為研究者，我希望建立五類平衡的合成案件，以快速測試文字分類流程。
9. 身為研究者，我希望保留生成來源、情境群組與標籤理由，以審查資料品質。
10. 身為研究者，我希望將相近情境分配至相同資料切分，以降低測試洩漏。
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

已確定：1999 主軸、兩個神經網路、固定內部拓樸、可訓練既有邊權重、建立可行性 Demo。

暫定：五類共 1,000 筆、500 節點、32 維表示、距離保持 loss、兩階段分開訓練、Streamlit 本機展示。這些是工程起點，不是老師已核定的研究結論。

待查核：實際 connectome release、下載方式、授權、官方類別與嵌入模型。對話曾提及 MaleCNS、Google 2026/9 及相關規模，開發者必須查核官方資料，不能直接當成已驗證事實或硬編碼規模。

依序交付：M0 來源查核 → M1 子圖與拓樸 smoke test → M2 資料與 baseline → M3 Fly A/B 訓練評估 → M4 本機展示。M1 未完成前可獨立開發資料與一般 baseline；不得把人工生成圖的結果當成真實 connectome 結果。

### 2. 技術與模組邊界

使用 Python、uv、PyTorch、NumPy/SciPy、scikit-learn、sentence-transformers 與 Streamlit；版本在首次可運行後鎖定。CPU 為必要支援，CUDA/MPS 為可選加速，稀疏算子不相容時明確回退 CPU。

模組責任：來源匯入、子圖建構、案件資料驗證與切分、嵌入與快取、connectome 計算核心、訓練編排、baseline、評估、checkpoint 與推論、展示。展示呼叫共同推論介面，不重複實作前處理或模型邏輯。

頂層操作包括 prepare-connectome、prepare-data、embed、train、evaluate、predict、demo。以單一設定描述實驗；操作輸入為設定與必要資料，輸出為 run ID、產物位置及摘要。不存在的來源或 checkpoint 應拒絕執行。

### 3. Connectome 匯入合約

來源紀錄包含官方 URL、release、下載日期、授權或存取條件、檔案 checksum、節點及邊欄位定義。只下載必要資料表；不要求完整顯微影像。

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

選一個城市的官方 1999／陳情分類架構，整理五類的 label ID、官方名稱、來源、定義、正例與容易混淆的邊界。先前路燈、噪音、道路等只是候選，未查核前不得標為官方 taxonomy。

案件紀錄包含 id、text、label、scenario_group、generation_batch、template_family、source_type、label_rationale 與 split。生成的是模擬民眾來電文字，不包含分類答案提示或應派送單位。使用虛構地點與個人資訊；首版單一主要訴求，混合訴求留作後續測試。

每類 200 筆，目標 train/validation/test=70/15/15，按情境與模板群組分割並盡量維持類別比例。先切分情境族，再生成各 split；同情境改寫不可跨 split。重複文字及高度相似案例需檢查並回到群組重新切分；不得參考 test 分數調整生成內容。每類人工抽查至少 20 筆、涵蓋所有 split，另審查所有標記的模糊案例；保留修正紀錄。

可匯入事先生成的 JSONL/CSV；不強制綁定 LLM 供應商或在訓練時呼叫 API。記錄生成模型、prompt 版本、時間與 seed（供應商不支援 seed 時註明）。報告註明合成資料、類別平衡及情境覆蓋限制。

### 8. 嵌入合約

初始候選為 intfloat/multilingual-e5-small；採用前查核官方 model card、授權、revision、prefix 與實際向量維度。保持 encoder 凍結，批次產生向量並 L2 正規化；d 必須由模型輸出驗證，不假定為 768。

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

初版先跑一個 seed；比較結論至少使用三個訓練 seed，報告平均與標準差，分清圖抽樣 seed 與訓練 seed。隨機圖需明確記錄是否匹配度數分布；只匹配 N/E 的對照不能排除度數差異。

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
| 防洩漏 | split ID 無重疊，scenario/template group 不跨 split，完全重複文字不跨 split；fit 操作只取得 train |
| 嵌入快取 | 相同設定命中；revision、prefix、文字或正規化改變則失效；維度不符報錯 |
| 端到端 | 小型固定測試資料跑完嵌入替身、A/B 訓練、checkpoint、evaluate、predict，輸出維度與類別順序一致且有限 |
| checkpoint 一致 | 相同 CPU/eval 模式載入前後 logits 在明訂容差內一致；不相容配置拒絕載入 |
| 指標可信 | 使用已知 predictions 的 fixture 驗證 Macro-F1、support 與混淆矩陣；零變異距離相關不假造數字 |
| 展示一致 | UI 使用同一 predict 介面，示例結果與 CLI 一致；空白輸入有提示、模擬派送標示可見 |
| 真實資料 smoke test | 真實 500-node 圖與少量案件完成至少一個訓練 epoch，輸出完整來源與成本紀錄 |

小圖與少量資料驗證是必要的 correctness tests；1,000 筆完整訓練屬實驗，不要求每次 CI 重跑。非確定 GPU 算子與跨設備結果採容差比較，不承諾 bitwise 相同。分類分數門檻不是 correctness test，不能為了過測試修改 test 資料。

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

依 M0→M4 執行，每階段交付可重現命令、完成項目、驗收結果、耗時與限制。遇到未確認事項先採本文暫定值並寫入設定與 run manifest；來源不存在、授權不可用、資料欄位不明或架構無法符合拓樸要求時，停下受阻部分並回報證據，繼續獨立工作。不得默默換成隨機圖或其他 connectome 卻沿用原資料名稱。

首版交付應包括：設定與鎖定環境、來源與子圖 manifest、案件和切分紀錄、嵌入快取、baseline 與 A/B checkpoint、機器可讀指標、供老師閱讀的結果摘要、可操作的本機 Demo。

參考模板：https://github.com/mattpocock/skills/tree/main/skills/engineering/to-spec

來源查核起點（尚待開發者驗證內容與可下載版本）：https://research.google/blog/a-connectomics-milestone-mapping-the-complete-male-fruit-fly-brain/

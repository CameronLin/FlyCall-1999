# M3.0 Fly A／Fly B 資料流與訓練契約

版本：v1.5｜日期：2026-10-26｜狀態：工程契約已確認；三個 M3.2 provisional train/validation seeds 與 M3.4 validation-only 比較已完成，人工複核與 test gate 仍未通過
依據：`1999-connectome-demo-spec-v0.2.md`、M1.2 engineering demo manifest、M1.3 I/O manifest、M2.1 loader 契約及 M2.2a smoke test 報告。此文件只凍結首版工程介面，不代表生物學主張或正式模型效能；M3.1 fixture core 已另行完成，M3.2 狀態見本文件更新。

v1.4 更新：Windows checkout 的 CRLF 曾造成 M1.2/M1.3 manifest 工作目錄 bytes 與 pin 不同；LF-normalized manifest bytes 與 pins 及 Git HEAD 完全相符，故 runner 現以正規化文字內容檢查 pin，未更動 manifest 或 digest，Parquet 仍以原始 bytes 驗證。PyArrow 26.0.0 在後續實際 run 成功讀取固定 graph，沒有 policy bypass。M3.2 seed 42／1337／2026 的 train/validation runs 均完成（500 nodes、2,216 edges、700/150 split、checkpoint reload max absolute difference 0.0；test `not_run`／0 model inputs）。M2.2b 同三 seed 及五候選的 M3.4 比較亦已完成，暫定 validation winner 為 MLP；所有結果仍 synthetic／pending_manual_review，candidate lock 與 test gate 保持關閉。細節見 [M3.2 follow-up report](../../.scratch/1999-connectome-demo/research/m3-2-pyarrow-application-control-block-20261026.md)、[M3.2 work ticket](../../.scratch/1999-connectome-demo/issues/12-m3-2-fly-ab-provisional-training.md) 與 [M3.4 validation report](../../.scratch/1999-connectome-demo/runs/m3-4-validation-comparison-seeds-42-1337-20261026/report.md)。

v1.3 更新（歷史狀態）：補記 Windows x64 CPU 上已完成的 E5 資源閘門、固定 revision runtime、tokenizer／pooling／輸出驗證及 train/validation 暫行 run。當時 M3.2 runner 停於 manifest pin mismatch，PyArrow 也遭 Windows Application Control 阻擋；後續以 v1.4 記錄的 CRLF 調查與實際 run 更新狀態。

v1.2 更新（歷史狀態）：記錄使用者選定的 multilingual-e5-small revision 與受限試跑設定；當時尚未下載、安裝或載入模型，M2.2b 資源閘門仍為 blocked。

v1.1 初版記錄未修改 spec、案件資料、split 或 M1.1／M1.2／M1.3 產物。v1.2 僅依使用者決定更新 spec 的嵌入設定，未修改案件資料、split 或 connectome 產物；未下載／安裝／載入模型、訓練或使用 test 指標。

## 1. 與 spec v0.2 的核對

未發現使用者確認的契約與 spec v0.2 的硬性要求衝突。以下是把 spec 中暫定／抽象要求具體化：

- spec 的 frozen encoder、trainable input adapter、shared-weight recurrent message passing、固定入度正規化、既有 edge trainable parameter、Fly A/B 分階段訓練及 validation checkpoint selection，均保留。
- `T=2` 作首版主設定、`T=4` 作預先聲明的 validation ablation，補足 spec 未固定模型 T 的部分；M1.3 的 `T=4` 仍只代表拓樸可達性檢查。
- Fly B 的 trainable `32→32` input adapter 是 spec 所允許的外部 adapter 在 B 端的具體化；它不構成繞過圖核心的捷徑。
- Edge initialization 將 spec 的 normalized `log1p(weight)` prior 具體化為每個 target 的 incoming prior 平均值 1，再以正值參數化；message aggregation 仍使用固定入度正規化。這與來源 weight 的生物語意無關。

若日後需要改變上述契約，需先更新決策文件與 ticket；實作不得自行替換公式或結構。

## 2. 已確認事實與限制

| 項目 | 核對結果 |
|---|---|
| 正式資料 | 1,000 筆、五類各 200；每類 train／validation／test 為 140／30／30；全體 700／150／150；依 66 個 `scenario_family_id` 凍結切分。資料仍為 `pending_manual_review`。 |
| 類別順序 | `sidewalk_maintenance`、`road_surface_defect`、`park_general_maintenance`、`waste_truck_service`、`street_cleaning`，沿用 frozen taxonomy 順序。 |
| 圖子集 | M1.2 `engineering-demo-v1.0` 有 500 個 endpoint nodes、2,216 條 directed edges；它是工程 demo 子圖，不具生物學代表性，500 不是最佳規模。 |
| I/O nodes | M1.3 manifest 固定 32 個 input IDs 與 32 個 output IDs，集合互斥；依 manifest 清單順序對應向量座標。這些是合成工程 I/O nodes，不代表神經元、腦區或功能。 |
| 可達性 | M1.3 在 `source_id→target_id`、最多 4 hops 的檢查中，32/32 outputs 可由至少一個 input 到達；9 個最短 1 hop、23 個最短 2 hops。這不證明有用訊號、分類效果或每個 input 都能到達每個 output。 |
| Edge weight | M1.1／M1.2 的整數 weight 是來源提供的連線數量／postsynaptic-density 類計數，不是校準的突觸效能；不推定抑制性或其他生物功能。未知的 `minconf-0.5` upstream predicate 不追加推論或篩選。 |
| 既有 baseline | M2.2a 是 pending 合成資料上的字元／短片語 TF-IDF train／validation smoke test，不是 E5 或 Fly A／B 證據；其 test 指標為 `not_run`。 |

M1.2 manifest SHA-256：`5300c6cefdc6b84a854545e64f4131baa3fc42f0bde97a83f68fcc1c3769cf40`。M1.3 I/O manifest SHA-256：`48148a1d64cc5402b17db99dff61ad42a3c29bef8d422ebfa6a25e375e07f585`。M1.2 nodes／edges SHA-256 分別為 `a8ad1e6a42c0a386d4bdef517ac628c29a5b7b8f023c51b43cce8e0354087428`、`afa69be2078eaf136d00511539145dc82ea54af5aa2f52ffdcb87501488e2175`。每個模型 run 都須記錄圖、I/O manifest、資料與 split manifest 的 checksum。

## 3. 首版已確認工程契約

### 3.1 文字到 Fly A input nodes

1. 唯一文字特徵來源是正式資料的 transcript `text`；不得把 label、ID、scenario／family、split 或其他 metadata 當模型特徵。Pilot 不併入正式資料流程。
2. 使用者於 2026-10-21 選定 `intfloat/multilingual-e5-small`，不再把 multilingual-e5-large 作為本專案候選。目標為 revision `614241f622f53c4eeff9890bdc4f31cfecc418b3`、384 維、masked mean pooling。2026-10-26 已在本機 Windows x64 CPU 隔離環境通過下載前資源閘門並驗證固定 revision runtime；本機核對結果見 M2.2b Windows gate report。未來新增／重建環境或改變 batch、sequence length、裝置、模型檔案時，仍須重新核對官方 model card、授權、檔案大小、CPU 套件解析下載量、峰值 RAM、即時可用磁碟與安裝後空間，並保留至少 4 GiB；未通過即停止。
3. 前處理保留原始繁體中文、標點及 `R:`／`L:` 標記，不刪除或改寫聲道角色、不轉簡體、不添加案件類別提示。以嚴格 UTF-8 解碼；保持來源 Unicode code-point 序列，不做 NFC／NFKC／NFKD 轉換。任何無效文字需明確失敗。
4. 目標 prefix 固定為 `query: `，token 上限為 512；目標 pooling 是 attention-mask-aware masked mean pooling，輸出維度為 384，輸出做 L2 normalization。2026-10-26 runtime 已核對 tokenizer class、`Precompiled` normalizer fingerprint、right truncation、masked mean pooling、384 維與 unit norm；每筆 prefix、revision、token limit、實際 `d`、截斷政策及截斷情況寫入 embedding manifest。M3.1 前處理不自行正規化 Unicode；E5 tokenizer 內部 normalization fingerprint 已記錄。不得靜默截斷。受限試跑裝置為 CPU、`batch_size=1`；模型輸入僅限 train／validation，人工複核前維持 provisional，test 不得進入 encoder 或 cache。
5. Encoder 輸出 `e∈R^d` 先做 L2 normalization，再送入 trainable affine projection `W_A∈R^(32×d), b_A∈R^32`，以 `tanh(W_A e+b_A)` 產生連續 FP32 drives。projection 只由 train split 的 Fly A loss 更新；validation 只 transform，test 不 fit、不選模。
6. 32 個 drives 依 M1.3 `input_node_ids` 清單順序注入對應合成 input nodes；不得把 node ID 數值當特徵，也不得對 nodes 賦予生物語意。

### 3.2 Fly A／Fly B recurrent graph core

- 兩個 Fly 都使用同一份 500-node 固定有向拓樸與相同 M1.3 I/O node order；Fly A 與 Fly B 的 edge gains 各自獨立，不共享參數。
- 每個 graph node 使用 scalar state，初始 `h_v^0=0`。每個時間步都在指定 input nodes 加入該步的 input drive，沿 `source_id→target_id` 有向邊傳遞訊息；每條 edge gain 在同一 Fly 的所有步數共享。
- 固定入度 `deg_in(v)` 是拓樸中指向 v 的既有 edge 數，自連線計入。每步聚合為 `m_v^t = (1/deg_in(v)) Σ_(u→v) g_uv h_u^t`；若入度為 0，`m_v^t=0`。更新為 `h_v^(t+1)=tanh(m_v^t+x_v)`，其中 `x_v` 是該步注入的 drive，非 input node 為 0。入度分母固定，不隨可訓練 edge gain 改變；不建立 dense `N×N` 矩陣。
- 首版主要設定 `T=2`。`T=4` 只能作事先列明的 validation ablation；不得看 test 選 T。T=4 拓樸可達性不構成分類效能證據。
- Fly A 在 T 步後依 M1.3 `output_node_ids` 順序讀出 32 個值，組成 `z_A∈R^32` 並做 L2 normalization。零範數需明確報錯，不做靜默替代。
- Fly B 收到按相同 manifest 座標順序排列的 normalized `z_A`，先經獨立可訓練 affine `32→32` adapter，再將 32 個 drives 對應到 Fly B 的 32 個 input nodes。之後以 Fly B 自己的 edge gains 傳遞，依 output 清單讀出 32 維向量，再由 trainable linear `32→5` readout 產生 logits。Label 順序固定為 frozen taxonomy 順序。
- 不存在任何從 encoder／Fly A adapter／Fly B adapter 直接連到 classifier readout 的捷徑。所有 logits 必須經過對應 Fly 的 graph core。合成 I/O nodes 與 readout 類別均不具生物學語意。
- 首版不加入額外 per-node trainable bias；若未來要加入，須先修訂契約並增加參數量與測試，不能默默擴充。

### 3.3 Edge gains 與來源 weight

對每條既有有向 edge `e=(u,v)`，只保留一個該 Fly 專屬、可訓練且嚴格正值的 gain；非邊沒有參數，自連線保留。來源 weight 只作初始化先驗，不稱為突觸效能：

```text
r_e = log1p(source_weight_e)
prior_e = r_e / mean({r_j : j targets to v})
raw_e_init = inverse_softplus(prior_e - epsilon)
gain_e = epsilon + softplus(raw_e)
epsilon = 1e-6
```

因此每個 target 的 incoming prior 平均為 1，初始有效 gain 對應該 prior；Fly A／B 各自有一套 edge parameters。自連線包含於 target incoming prior 的平均計算及固定入度。weight 必須是有限、非負且可用 `log1p` 處理；若 incoming prior 平均為零，或任一 `prior_e <= epsilon` 使 inverse softplus 無法產生有限參數，preflight 明確失敗並回報，不得改公式、加 clipping 或刪 edge。聚合另使用 §3.2 的固定入度 normalization，不以 gains 總和替代。

正值參數化保留既有拓樸但不能表示負向／抑制性連線；這是工程限制，不作生物推論。若實作公式與此契約不一致，停止並回報，不自行替換。

### 3.4 首版參數量記錄

以 M1.2 的 2,216 edges、500 nodes 計，首版沒有 per-node bias：

- Fly A projection：`32d+32`；Fly A graph edge gains：`2,216`。
- Fly B input adapter：`32×32+32=1,056`；Fly B graph edge gains：`2,216`；Fly B readout：`5×32+5=165`。
- 合計可訓練參數：`32d+5,685`；凍結 encoder 不計入 trainable count。每個 run 應報 adapter、graph core、readout 分項參數量與實際 `d`。

這些參數量不是峰值 RAM 估計；8 GiB 下的實際 RSS、embedding cache、autograd、套件及 encoder 開銷仍須實測／預估。模型下載 gate 見 §6。

## 4. 訓練與 checkpoint 規則

### Fly A

- 使用 train-only pairwise distance-preserving loss；embedding 與 `z_A` 各 L2-normalize，對 batch 中不同樣本 pair `i<j` 最小化 Euclidean distance 差的平方平均，不含對角線；記錄 pair sampling seed。Fly A loss 不用 label。
- 只有 Fly A projection、Fly A edge gains 可更新；encoder 凍結。監控有限 loss／gradient、輸出變異與零範數；發生非有限值立即停止並保留最後有效 checkpoint。
- Validation 僅計算 distance stress，不更新參數。以最低 validation stress 選 checkpoint，平手選較早 epoch。

### Fly B

- 凍結 Fly A 的 encoder、projection、graph 與 checkpoint；Fly B 只接收凍結後的 Fly A 32 維輸出。
- 用 train label 的 cross-entropy 更新 Fly B 32→32 adapter、Fly B edge gains、32→5 readout；test 不參與。
- Validation 以 Macro-F1 選 checkpoint；平手先選較低 validation loss，再選較早 epoch。softmax 若輸出，稱模型分數，不稱校準機率。

Fixture／除錯固定一個 training seed。正式模型比較須至少三個預先記錄的 training seeds，報告平均與標準差；graph/subgraph seed 與 training seed 分開記錄。Adam、`lr=1e-3`、batch 32、最多 100 epochs、patience 10、gradient clipping 1.0、CPU、seed 42 延續 spec 作為初版候選設定；任何變更須在正式 run 前鎖定並記錄。

## 5. 資料品質閘門及 test 使用

正式 1,000 筆目前仍為 `pending_manual_review`。M3.1 只使用小型手工 fixture 與合成向量，不載入正式資料，不訓練正式模型；任何 fixture 結果不能當資料集效能。M2.1 loader 的全檔契約稽核與模型輸入要分開，模型不可取得 test rows。

人工複核門檻沿用 spec：每類至少人工抽查 20 筆且涵蓋 train／validation／test；所有 AI 標為需特別確認及 revise 的列均需人工處置。門檻未通過前，不得發布正式評估，train／validation 模型運行只可標示 `smoke_test`／`provisional`。門檻通過、候選模型與全部設定鎖定後，test 才能對預先列明的候選一次性評估；不得用 test 調參、選 T、重訓或重排候選。若 test 已接觸後發現程式錯誤，需記錄曝光並由使用者決定新 holdout 或其他有效評估方式。

## 6. 資源及下載閘門

實測實體 RAM 為 `8,589,934,592` bytes（8 GiB，M2.2a run report）。M3.0 草案記錄的磁碟可用量 `22,543,347,712` bytes 是當時快照；M2.2a 報告中的 `23,655,501,824` bytes 是另一時間點。兩者都不是目前可用空間，下載前必須刷新即時值。受限試跑的目標設定為 CPU、`batch_size=1`；過去以 batch 4 作出的估算不可當成 batch 1 的實測或安全上界。

M2.2a 隔離環境原本沒有 PyTorch／E5 encoder。2026-10-26 在 `%TEMP%` 建立的另一個隔離 CPU 環境已通過 M2.2b gate 並載入固定 E5 revision；該次峰值與空間證據見 M2.2b Windows gate report。M3.1 fixture 可在既有環境下進行；若其他工作需要新增套件，先列出精確需求與資源預檢。M3.2 的 PyArrow native extension 目前被 Windows Application Control 阻擋，不能讀取 Parquet graph table，需等待可核准的 runtime。

圖核心採 sparse edge list；不用完整 connectome、不建 dense adjacency、不重讀 M1.1 原始檔。任何提高 batch、T、state width 或加入 encoder 都須重新估算資源。

## 7. 推論與 checkpoint 最低契約

Checkpoint／run manifest 至少保存：encoder ID、官方 revision、license/source、prefix literal、token limit、Unicode／文字前處理、實際 `d`、embedding normalization、截斷統計；A projection、Fly A/B 的 `T` 與 recurrent 定義；M1.2 graph checksum、M1.3 manifest checksum、source→target 方向、有序 I/O IDs、edge prior／inverse-softplus 初始化／epsilon／固定入度規則；A/B adapter、core、readout 參數量；taxonomy label IDs／順序、split manifest／資料 checksum、seed、optimizer、checkpoint 選取規則、依賴版本及 run 的 `smoke_test`／`provisional` 狀態。

單筆推論重用相同 tokenizer／encoder／prefix／截斷／Unicode 規則，依序執行 E5→A projection→Fly A→ordered normalized 32-vector→Fly B adapter→Fly B→固定 5-logit readout。空白／無效文字、全截斷、零範數、維度／checksum／label order 不符時明確拒絕，不靜默回退。

## 8. M3.0 完成狀態與後續

首版架構、train／validation／test 邊界、weight semantics、resource gate 與人工複核限制已由使用者確認並記錄。M3.0 契約與 M3.1 fixture core 已完成。M3.2 三個 real-graph train/validation provisional seeds 與 M3.4 validation-only comparison 均已執行；暫定比較候選尚未人工鎖定。正式資料仍為 `pending_manual_review`，不得產生正式效能結論或 test 指標。


## v1.5 exploratory Fly A/B diagnosis (2026-10-26)

The three-seed M3.4 report remains the authoritative provisional comparison and still names MLP as the validation winner. A separate diagnosis found that a frozen Fly A 32-D output retained less label signal than raw E5. A separate gated E5 residual into the Fly B graph, with a four-configuration train/validation sweep, reached mean validation Macro-F1 0.9048 and accuracy 0.9089 across the three seeds. This selected-on-validation candidate does not replace the M3.4 winner, is not locked, and has not used test data. Full measurements, source hashes, checkpoint hashes, and tests are in [issue 16](../../.scratch/1999-connectome-demo/issues/16-fly-ab-representation-diagnosis.md) and the [diagnosis report](../../.scratch/1999-connectome-demo/runs/fly-ab-diagnosis-20261026/report.md).

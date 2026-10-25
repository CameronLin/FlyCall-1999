# 正式 1,000 筆生成計畫 v1.1（切分稽核草案）

狀態：規劃文件，尚未開始生成；建議切分方案及逐家族 manifest 均為草案，未凍結。  
正式目標：5 個主類別各 200 筆，共 1,000 筆。  
基準：目前索引所列 v1.2.1 pilot 與 taxonomy；新家族須先通過 taxonomy 審查，且 pilot 50 筆須有明確人工通過紀錄。  
分離原則：v1.2.1 的 50 筆為 `split="pilot"` 的獨立試產，不納入正式配額，不合併到正式 JSONL。

## 正式逐筆規格

- 每通為完整多輪客服與民眾對話，總計約 8–14 個 R/L 發言回合（逐行計），雙方多次往返。
- 每筆至少 200 個中文字；建議控制在 220–350 字，避免用重複話術湊長度。
- 只保留一個主要案件問題；追問只釐清該問題的地點概略、時間、狀況、變化及影響。
- 固定聲道：`R=客服`、`L=來電民眾`，逐筆及跨資料集都不得交換。第一個客服發言中性，不先說案件主題。
- 客服可詢問、重述理解並說明會記錄；不得判定案件結果、承諾修復／清運時間、提供未查證資訊或說明內部分派。
- 不寫姓名、電話、身分證、門牌、精確地址組合或可定位到單一地點的具名路口／地標；使用行政區或公共空間概略位置即可。
- 繼續保留目前 12 個必要欄位：`id`、`transcript`、`label_id`、`label_name`、`scenario_id`、`scenario_family_id`、`split`、`is_synthetic`、`speaker_map`、`generator_model`、`prompt_version`、`review_status`。正式資料的 `split` 僅用 `train`、`validation`、`test`。
- 每筆 `is_synthetic=true`；生成時 `review_status=pending_manual_review`。只有完成並記錄人工複核後，才可依明確審核規則更新狀態。

## ID 與檔名

使用不與 `P001`、`V11`、`V12` pilot ID 混淆的永久序號：

- `id`: `TPE1999-FORMAL-<CAT>-<SEQ4>`，例如 `TPE1999-FORMAL-SW-0001`。
- `scenario_id`: `SCENARIO-FORMAL-<CAT>-<SEQ4>`，與該筆 ID 一對一。
- `<CAT>` 固定為 `SW`（人行道）、`RD`（道路）、`PK`（公園）、`WT`（垃圾車）、`SC`（路面清潔）；各類序號 `0001` 至 `0200`。
- `scenario_family_id` 使用經核准 taxonomy 中的穩定 ID；同一 ID 不可在不同主類別重用。
- 生成前在 manifest 預先分配每個 ID、label、family、split、預期筆數和批次路徑。重跑不重新編號、不改 split。

建議目錄與批次命名：

```text
data/1999_synthetic/formal/
  batches/<split>/<CAT>/formal_v1.0.0_<FAMILY-ID>.jsonl
  formal_v1.0.0.jsonl
  formal_manifest_v1.0.0.yaml
  validation_report_formal_v1.0.0.md
  manual_review_formal_v1.0.0.md
```

一個家族一個 shard，不混合 split 或 label。依下列計畫共 75 個 family shard；每份 shard 的預期筆數寫在 manifest。最終 JSONL 只由通過批次驗證的正式 shard 合併產生，pilot 不在此目錄或合併清單中。

## 家族分組與切分稽核

taxonomy 擴充草案規劃每類 15 個家族，共 75 個；目前家族邊界未核准。以下比較固定每類 9 個 train、3 個 validation、3 個 test 家族的三種比例。逐一分配的 `scenario_family_id`、split 及筆數列在 [`formal_split_manifest_draft_v1.0.yaml`](formal_split_manifest_draft_v1.0.yaml)。manifest 目前為 `draft_unfrozen`，生成前須待 taxonomy 核准、pilot 複核通過後另行凍結。

| 方案 | 每類 train／validation／test 筆數 | 全體 train／validation／test 筆數 | 每類各 split 家族數 | 每家族預計筆數範圍（train／validation／test） | 訓練量與評估取捨 |
|---|---:|---:|---:|---|---|
| 80/10/10 | 160／20／20 | 800／100／100 | 9／3／3 | 17–18／6–7／6–7 | 每類訓練 160 筆最多；train 每家族 17–18 筆，holdout 每家族 6–7 筆，訓練家族約為 holdout 的 2.4–3 倍。validation/test 各只有 20 筆、3 個家族，指標易受個別樣本和家族影響。 |
| 70/15/15 | 140／30／30 | 700／150／150 | 9／3／3 | 15–16／10／10 | 每類仍有 140 筆訓練資料；train 每家族 15–16 筆、holdout 每家族 10 筆，差異較 80/10/10 小。每個 holdout split 有 30 筆，是訓練量和評估穩定度的折衷。 |
| 60/20/20 | 120／40／40 | 600／200／200 | 9／3／3 | 13–14／13–14／13–14 | 每類 holdout 最大且 train、holdout 每家族都約 13–14 筆，三個 split 的家族負載最接近；訓練資料降至每類 120 筆，可能限制模型學習量。 |

### 建議與限制

建議採 **70/15/15**：五類分類任務每類保留 140 筆訓練資料，同時比 80/10/10 多 10 筆／類的 validation 與 test 樣本；相較 60/20/20，每類多保留 20 筆訓練樣本。此建議兼顧訓練量和 holdout 樣本數，不是只依比例整除決定。

所有方案在 9/3/3 配置下都只有每類 3 個 validation 家族及 3 個 test 家族。test 分數反映的是這少數未見家族，不等於涵蓋全部 15 個家族；家族間難度差異可能使結果波動。若要求更廣的 holdout 家族覆蓋，需核准更多具實質差異的家族或增加資料目標後按完整家族重排。不得拆分家族以符合任何比例。

manifest 逐類、逐家族列出 split 和預計筆數，目標總量為每類 200、全體 1,000；每個 family ID 僅出現一次。現有分配把明顯相近的候選家族盡量放在同 split，但 taxonomy 邊界審查可能改變家庭清單及分配；重審後須重新驗算，manifest 凍結前不得生成。

## 逐類逐家族切分表（建議 70/15/15 草案）

以下預計筆數在 manifest 中逐列登錄；manifest 未凍結，taxonomy 審查後可能重排。

### 人行道維護 (`sidewalk_maintenance`)

| scenario_family_id | split | 預計筆數 |
|---|---|---:|
| `FAM-SW-TILE-MOVEMENT` | train | 16 |
| `FAM-SW-MISSING-PAVERS` | train | 16 |
| `FAM-SW-TACTILE-PAVING` | train | 16 |
| `FAM-SW-TACTILE-ALIGNMENT` | train | 16 |
| `FAM-SW-RAMP-SURFACE` | train | 16 |
| `FAM-SW-CURB-RAMP-LANDING` | train | 15 |
| `FAM-SW-LEVEL-SETTLEMENT` | train | 15 |
| `FAM-SW-SLAB-JOINT-GAP` | train | 15 |
| `FAM-SW-CURB-EDGE` | train | 15 |
| `FAM-SW-CONCRETE-SPALLING` | validation | 10 |
| `FAM-SW-FLAT-SURFACE-SLIPPERY` | validation | 10 |
| `FAM-SW-EDGE-CRUMBLING` | validation | 10 |
| `FAM-SW-UTILITY-RESTORATION` | test | 10 |
| `FAM-SW-DRIVEWAY-CROSSING` | test | 10 |
| `FAM-SW-PEDESTRIAN-DECK` | test | 10 |

### 道路凹陷、不平、有高低差 (`road_surface_defect`)

| scenario_family_id | split | 預計筆數 |
|---|---|---:|
| `FAM-ROAD-INTERSECTION-DENT` | train | 16 |
| `FAM-ROAD-DEEP-POTHOLE` | train | 16 |
| `FAM-ROAD-WHEEL-TRACK` | train | 16 |
| `FAM-ROAD-WIDESPREAD-UNDULATION` | train | 16 |
| `FAM-ROAD-REPAIR-JOINT` | train | 16 |
| `FAM-ROAD-PATCH-BREAKUP` | train | 15 |
| `FAM-ROAD-FATIGUE-CRACKING` | train | 15 |
| `FAM-ROAD-SURFACE-CRACKING` | train | 15 |
| `FAM-ROAD-BINDER-BLEEDING` | train | 15 |
| `FAM-ROAD-CROSSING-APPROACH` | validation | 10 |
| `FAM-ROAD-SURFACE-RAVELING` | validation | 10 |
| `FAM-ROAD-UTILITY-CUT-SETTLEMENT` | validation | 10 |
| `FAM-ROAD-LONGITUDINAL-TRANSITION` | test | 10 |
| `FAM-ROAD-PAVEMENT-HEAVE` | test | 10 |
| `FAM-ROAD-SHOULDER-EDGE-DROP` | test | 10 |

### 一般公園綠地管理及設施維護 (`park_general_maintenance`)

| scenario_family_id | split | 預計筆數 |
|---|---|---:|
| `FAM-PARK-SEATING` | train | 16 |
| `FAM-PARK-PLAY-EQUIPMENT` | train | 16 |
| `FAM-PARK-SPORTS-EQUIPMENT` | train | 16 |
| `FAM-PARK-COURT-SURFACE` | train | 16 |
| `FAM-PARK-GREENERY` | train | 16 |
| `FAM-PARK-PLANTING-BED` | train | 15 |
| `FAM-PARK-TRAIL-SURFACE-EROSION` | train | 15 |
| `FAM-PARK-VEHICLE-ENTRY` | train | 15 |
| `FAM-PARK-FENCE-GATE` | train | 15 |
| `FAM-PARK-STAIR-HANDRAIL` | validation | 10 |
| `FAM-PARK-RESTROOM-DOOR-PARTITION` | validation | 10 |
| `FAM-PARK-DRINKING-FOUNTAIN` | validation | 10 |
| `FAM-PARK-SHELTER-ROOF` | test | 10 |
| `FAM-PARK-INFORMATION-SIGN` | test | 10 |
| `FAM-PARK-LIGHTING-EQUIPMENT` | test | 10 |

### 垃圾車清運及服務事項 (`waste_truck_service`)

| scenario_family_id | split | 預計筆數 |
|---|---|---:|
| `FAM-WASTE-MISSED-STOP` | train | 16 |
| `FAM-WASTE-ROUTE-SEGMENT-OMISSION` | train | 16 |
| `FAM-WASTE-SCHEDULED-DAY-OMISSION` | train | 16 |
| `FAM-WASTE-ALLEY-ACCESS` | train | 16 |
| `FAM-WASTE-ACCESS-INTERRUPTION` | train | 16 |
| `FAM-WASTE-ARRIVAL-TIME` | train | 15 |
| `FAM-WASTE-ROUTE-ORDER-CHANGE` | train | 15 |
| `FAM-WASTE-STOP-LOCATION` | train | 15 |
| `FAM-WASTE-TEMP-STOP-RELOCATION` | train | 15 |
| `FAM-WASTE-PARTIAL-COLLECTION` | validation | 10 |
| `FAM-WASTE-SHORT-DWELL` | validation | 10 |
| `FAM-WASTE-COLLECTION-CUE-FAILURE` | validation | 10 |
| `FAM-WASTE-WEEKEND-SCHEDULE` | test | 10 |
| `FAM-WASTE-HOLIDAY-SCHEDULE` | test | 10 |
| `FAM-WASTE-RECYCLABLE-STREAM-SERVICE` | test | 10 |

### 路面清潔（含行人果皮箱、菸蒂、狗便） (`street_cleaning`)

| scenario_family_id | split | 預計筆數 |
|---|---|---:|
| `FAM-CLEAN-BIN-OVERFLOW` | train | 16 |
| `FAM-CLEAN-BIN-DAMAGE` | train | 16 |
| `FAM-CLEAN-WIND-DISPERSED-LITTER` | train | 16 |
| `FAM-CLEAN-DOG-WASTE` | train | 16 |
| `FAM-CLEAN-DOG-WASTE-PERSISTENT-RESIDUE` | train | 16 |
| `FAM-CLEAN-SURFACE-DEBRIS` | train | 15 |
| `FAM-CLEAN-MUD-SILT-FILM` | train | 15 |
| `FAM-CLEAN-REACCUMULATING-DEBRIS` | train | 15 |
| `FAM-CLEAN-POST-SWEEP-RESIDUE` | train | 15 |
| `FAM-CLEAN-EVENT-PACKAGING` | validation | 10 |
| `FAM-CLEAN-CIGARETTE` | validation | 10 |
| `FAM-CLEAN-GUM-ADHERED-RESIDUE` | validation | 10 |
| `FAM-CLEAN-SHARP-GLASS` | test | 10 |
| `FAM-CLEAN-STORM-BRANCH-DEBRIS` | test | 10 |
| `FAM-CLEAN-LOOSE-GRIT` | test | 10 |

## 可分批生成流程

1. **前置關卡**：完成 v1.2.1 全部 50 筆人工複核；確認 5 個 label 的官方對照仍適用；審核並凍結 15 家族／類草案、排除規則、生成提示詞、聲道、ID manifest 及切分表。這些條件未完成前不啟動正式生成。
2. **凍結清單**：為 1,000 個 ID 預先配置 label、family、split 和 shard。記錄 prompt 版本、generator model、schema 版本、預期筆數及每批輸出 checksum 欄位。
3. **逐家族生成**：每次只生成一個 shard（依建議 70/15/15 方案為 10–16 筆），不跨 label、family 或 split。先寫入 staging 檔，不直接 append 到正式總檔。
4. **自動批次驗證**：檢查 JSONL 解析、預期筆數、必要欄位、ID／scenario_id 唯一、label/family/split 與 manifest 一致、R/L 固定交替、8–14 行、200 字下限、單一主訴提示、無精確地址／PII、無客服先行揭露主題、無明顯重複或填充內容。
5. **人工批次複核**：逐批檢查自然度、追問是否承接、時間／地點自洽、分類邊界、與同家族差異及客服沒有對案件作實質回答。未通過批次不進入合併清單。
6. **原子收件**：驗證和複核通過後，把 staging shard 移入正式批次資料夾，記錄 SHA-256、筆數、ID 範圍及審核狀態至 manifest。未通過版本保留在 `rejected/` 或隔離目錄，絕不與通過版同時合併。
7. **失敗重跑**：只重跑失敗的 shard 或個別 ID，使用原先保留的 ID、family、split 和 prompt 版本；以 attempt 記錄區分，不追加第二份同 ID。先保存舊失敗輸出，再驗新輸出，通過後才替換 manifest 中唯一的 accepted artifact。若更動 prompt，建立新 prompt 版本並重驗受影響批次。
8. **最終合併與稽核**：按固定類別及 ID 排序合併 accepted shards；產生總表、checksum、驗證報告及人工複核清單。合併前後核對 manifest 和實際資料行數。

## 最終 1,000 筆驗收清單

- 正式總檔恰有 1,000 行有效 JSON；ID 與 `scenario_id` 各 1,000 個且唯一。
- 五個 `label_id` 各恰 200 筆，官方 `label_name` 對應一致。
- 每類 train／validation／test 分別 140／30／30；全體 700／150／150。
- 每個 `scenario_family_id` 僅映射一個 split；沒有家族跨 split，也沒有 family ID 缺失。
- `split="pilot"` 的 50 筆不在 manifest、正式 shard 或總檔；正式 ID 前綴與 pilot 不重疊。
- 每筆 8–14 個發言行、至少 200 個中文字、R/L 角色正確、必要欄位齊備、無精確地址或直接個資；所有正式資料均有人工複核紀錄。
- 凍結 manifest 的 accepted shard 筆數加總等於總檔行數；每類、每 split 的 manifest 數量與總檔重新計數一致。

本次只建立規劃文件和未凍結的 split manifest；沒有生成 shard 或任何正式通話逐字稿。

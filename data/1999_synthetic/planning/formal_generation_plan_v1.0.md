# 正式 1,000 筆生成計畫 v1.0

狀態：規劃文件，尚未開始生成。  
正式目標：5 個主類別各 200 筆，共 1,000 筆。  
基準：目前索引所列 v1.2.1 pilot 與 taxonomy；新家族須先通過 taxonomy 審查。  
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

## 家族分組與切分

taxonomy 草案規劃每類 15 個家族，共 75 個。先完成家族邊界審查、合併重疊家族，再凍結 split manifest；同一 `scenario_family_id` 的所有筆數只屬於一個 split。每類下列數量可精確達到 80／10／10，且不拆家族：

| 每類 split | 家族組成 | 每類筆數 | 五類合計 |
|---|---:|---:|---:|
| train | 7 個家族各 18 筆，2 個家族各 17 筆（9 個家族） | 160 | 800 |
| validation | 2 個家族各 7 筆，1 個家族 6 筆（3 個家族） | 20 | 100 |
| test | 2 個家族各 7 筆，1 個家族 6 筆（3 個家族） | 20 | 100 |
| **合計** | **15 個不同家族** | **200** | **1,000** |

每個 label 都套用同一配額。家族分配到哪個 split 必須在生成前寫入 manifest，不能看生成結果或模型分數後再搬動。validation/test 每類各覆蓋 3 個家族；train 覆蓋其餘 9 個。若 taxonomy 合併、移除家族或實際配額改變，先按完整家族重算並在報告列出每類實際筆數與相對 80／10／10 的差額；絕不為湊比例拆分家族。

此切分設計是候選方案，必須在 taxonomy 凍結時確認代表性。若候選家族合併後不足 15 個／類，需重新規劃群組與比例，不能沿用上表假設。

## 可分批生成流程

1. **前置關卡**：完成 v1.2.1 全部 50 筆人工複核；確認 5 個 label 的官方對照仍適用；審核並凍結 15 家族／類草案、排除規則、生成提示詞、聲道、ID manifest 及切分表。這些條件未完成前不啟動正式生成。
2. **凍結清單**：為 1,000 個 ID 預先配置 label、family、split 和 shard。記錄 prompt 版本、generator model、schema 版本、預期筆數及每批輸出 checksum 欄位。
3. **逐家族生成**：每次只生成一個 shard（約 6–18 筆，依該家族所屬 split），不跨 label、family 或 split。先寫入 staging 檔，不直接 append 到正式總檔。
4. **自動批次驗證**：檢查 JSONL 解析、預期筆數、必要欄位、ID／scenario_id 唯一、label/family/split 與 manifest 一致、R/L 固定交替、8–14 行、200 字下限、單一主訴提示、無精確地址／PII、無客服先行揭露主題、無明顯重複或填充內容。
5. **人工批次複核**：逐批檢查自然度、追問是否承接、時間／地點自洽、分類邊界、與同家族差異及客服沒有對案件作實質回答。未通過批次不進入合併清單。
6. **原子收件**：驗證和複核通過後，把 staging shard 移入正式批次資料夾，記錄 SHA-256、筆數、ID 範圍及審核狀態至 manifest。未通過版本保留在 `rejected/` 或隔離目錄，絕不與通過版同時合併。
7. **失敗重跑**：只重跑失敗的 shard 或個別 ID，使用原先保留的 ID、family、split 和 prompt 版本；以 attempt 記錄區分，不追加第二份同 ID。先保存舊失敗輸出，再驗新輸出，通過後才替換 manifest 中唯一的 accepted artifact。若更動 prompt，建立新 prompt 版本並重驗受影響批次。
8. **最終合併與稽核**：按固定類別及 ID 排序合併 accepted shards；產生總表、checksum、驗證報告及人工複核清單。合併前後核對 manifest 和實際資料行數。

## 最終 1,000 筆驗收清單

- 正式總檔恰有 1,000 行有效 JSON；ID 與 `scenario_id` 各 1,000 個且唯一。
- 五個 `label_id` 各恰 200 筆，官方 `label_name` 對應一致。
- 每類 train／validation／test 分別 160／20／20；全體 800／100／100。
- 每個 `scenario_family_id` 僅映射一個 split；沒有家族跨 split，也沒有 family ID 缺失。
- `split="pilot"` 的 50 筆不在 manifest、正式 shard 或總檔；正式 ID 前綴與 pilot 不重疊。
- 每筆 8–14 個發言行、至少 200 個中文字、R/L 角色正確、必要欄位齊備、無精確地址或直接個資；所有正式資料均有人工複核紀錄。
- manifest 的 accepted shard 筆數加總等於總檔行數；每類、每 split 的 manifest 數量與總檔重新計數一致。

本次只建立計畫，尚未生成 shard、manifest 或任何正式通話逐字稿。

# 正式 1,000 筆生成計畫 v1.2

狀態：草案，未核准、未凍結、未開始生成。  
正式資料目標：**另外新增 1,000 筆**，五類各 200 筆。  
Pilot：v1.2.1 與 v1.2.2 是同一組 50 筆資料的基準／修訂草案版本；不重複計數、不計入正式配額，也不自動合併至正式資料。  
逐家族配置草案：[`formal_split_manifest_draft_v1.1.yaml`](formal_split_manifest_draft_v1.1.yaml)。

## 生成前必要條件

- v1.2.2 的 50 筆目前仍全部 `pending_manual_review`；逐筆明確人工複核並保留通過紀錄前，不開始正式生成。
- taxonomy 草案的 15 個 revise 家族及 10 個條件式合併規則尚未人工核准；不得先視為可用正式家族。
- 家族清單與合併規則定案後，重新核對 split、配額與家族隔離，並另行人工凍結 manifest。
- 凍結 ID、prompt、模型、批次規格及驗證門檻後才可排程生成。

## 正式逐筆規格

- 完整多輪客服與民眾對話，約 8–14 個發言回合，至少 200 個中文字；自然變化，不以重複話術灌長度。
- 每筆只有一個主要案件問題；追問只釐清該問題，不另外引入案件。
- 固定聲道 `R=客服`、`L=來電民眾`，不得交換。第一個客服發言中性，不先透露案件主題。
- 客服可確認和釐清來電者描述，並說明會記錄；不得作案件實質判定、承諾處理時程或提供未查證答案。
- 不含姓名、電話、身分證、門牌、精確地址組合或可定位單一地點的路口／地標；僅保留理解情境所需的行政區及公共空間線索。
- 保留 12 個必要欄位：`id`、`transcript`、`label_id`、`label_name`、`scenario_id`、`scenario_family_id`、`split`、`is_synthetic`、`speaker_map`、`generator_model`、`prompt_version`、`review_status`。正式 split 為 `train`、`validation`、`test`。
- `is_synthetic=true`；新生成資料先設 `review_status=pending_manual_review`，僅在有人工記錄後更新。

## ID、檔案與家族規則

- `id` 使用 `TPE1999-FORMAL-<CAT>-<SEQ4>`，`scenario_id` 使用 `SCENARIO-FORMAL-<CAT>-<SEQ4>`；類別代碼 SW、RD、PK、WT、SC，各類序號 0001–0200。
- 生成前逐筆預排唯一 ID、scenario_id、label、family、split、預期筆數及批次路徑。失敗重跑沿用原 ID 與 split。
- 一個 family 一個 shard，不混類別或 split：`data/1999_synthetic/formal/batches/<split>/<CAT>/formal_v1.0.0_<FAMILY-ID>.jsonl`。只有驗證通過的 shard 才能合併至正式檔。
- Pilot 留在正式目錄以外，不進正式合併清單。

## 70/15/15 family-held-out 配置草案

| 類別 | 家族數 train／validation／test | 筆數 train／validation／test | 每家族預計筆數 train／validation／test |
|---|---:|---:|---:|
| 人行道維護 | 8／3／3 | 140／30／30 | 17–18／10／10 |
| 道路凹陷、不平、有高低差 | 8／3／3 | 140／30／30 | 17–18／10／10 |
| 一般公園綠地管理及設施維護 | 9／3／3 | 140／30／30 | 15–16／10／10 |
| 垃圾車清運及服務事項 | 5／3／3 | 140／30／30 | 28／10／10 |
| 路面清潔 | 5／3／3 | 140／30／30 | 28／10／10 |
| **全體** | **35／15／15** | **700／150／150** | — |

70/15/15 保留每類 140 筆訓練資料，並讓 validation、test 各有 30 筆、每類三個未見家族。代價是每個 holdout split 每類只有三個家族，代表性與穩定性有限。11 家族類別的 5/3/3 配置會令 train 的五個家族各承載 28 筆，而 holdout 家族各 10 筆；訓練樣本在家族間較集中。若調整家族數，須重新核對精確配額和家族隔離，不可拆分家族湊數。

目前把部分概念相近或條件式合併的目標放在同一 split，例如人行道沉陷／管線回填、道路補面接縫／管線切割回填、垃圾車可及性案例、狗便／清掃殘留。這是降低近似概念跨 split 影響的草案安排，仍需人工核定。

## 分批生成與驗收

1. **凍結前審查**：完成 Pilot 人工複核，核准 taxonomy 與 merge map，確認 family 分組；核定 prompt、模型、ID 規則、批次大小和驗證門檻，記錄版本與批准資訊。
2. **預排配額**：逐筆建立 manifest；先機械核對五類各 200、每類 split 140/30/30、全體 split 700/150/150，並確認 family 不跨 split。
3. **分批生成**：按一個 family shard 生成，建議每批 10–20 筆。先寫暫存 shard，檢查通過後才標記完成。
4. **逐批驗證**：檢查 JSONL、必要欄位、唯一 ID、類別與 family 對照、speaker、行數與中文字數、單一主訴、客服行為、個資／地址、完全與近似重複；對家族邊界和自然度作人工抽查。
5. **失敗重跑**：只重跑失敗列或 shard；固定原 ID、label、family 和 split，保留失敗版本及錯誤摘要。重跑後重驗該 shard，不覆寫已驗證批次。
6. **最終驗收**：正式 JSONL 恰 1,000 行，五類各 200；split 共 700/150/150；ID 與 scenario_id 全唯一；每個 family 僅一個 split；沒有 Pilot 記錄。保存最終報告和人工複核清單。

## 目前狀態

`pilot_v1.2.2.jsonl` 是草案，50 筆待人工複核。Split manifest 為 `draft_unfrozen`。本文件只作規劃，沒有開始正式資料生成。

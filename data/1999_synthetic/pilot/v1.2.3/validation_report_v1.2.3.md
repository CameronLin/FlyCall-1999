# v1.2.3 草案更新驗證報告

日期：2026-10-12

## 來源版本與決定核對

- 實際來源：`pilot_v1.2.2.jsonl`（50 筆）、`taxonomy_expansion_draft_v1.1.md`（75 個家族）、`formal_split_manifest_draft_v1.1.yaml`（`draft_unfrozen`），以及指定的決定 XLSX／Markdown。
- XLSX 與 Markdown 的 Pilot revise ID、18 個 family revise ID／規則、9 個 merge 來源／目標一致；Pilot 為 pass 46、revise 4、reject 0，family 為 pass 48、revise 18、merge 9。
- 決定活頁簿的原人工決定欄全為 `pending`；本次只依助理決定建立草案，沒有修改人工決定或人工意見。

## 新增草案檔

- `pilot_v1.2.3.jsonl`
- `taxonomy_expansion_draft_v1.3.md`
- `family_merge_map_draft_v1.1.yaml`
- `formal_split_manifest_draft_v1.2.yaml`
- `validation_report_v1.2.3.md`

## Pilot 驗證

- 共 50 筆、五類各 10 筆，ID 唯一。只有 V12-037、V12-038、V12-048、V12-050 的逐字稿變動；其餘 46 筆逐字稿完全相同。全部標籤、`scenario_id`、`scenario_family_id`、`split`、`speaker_map` 及其他欄位均與 v1.2.2 相同。
- 全部維持 `split="pilot"`、`review_status="pending_manual_review"`；`R=客服`、`L=來電民眾`，每筆 10–14 個交替發言行。
- 每筆 11–13 行、302–375 個中文字（按 CJK 字元計），全部至少 280 字。
- 電話、門牌／巷弄門牌及姓名標示格式篩查未命中；該格式篩查不取代人工語意複核。
- 全文沒有完全重複；正規化全文相似度最高為 0.269（TPE1999-V12-015／TPE1999-V12-016）。

## Taxonomy 與 merge 驗證

- v1.3 有效家族 ID 共 66 個且唯一：人行道 14、道路 14、公園 15、垃圾車 12、路面清潔 11。18 個 revise 規則已寫入對應家族界線；9 個 merge 來源從有效表移除，目標與分流條件記錄在 taxonomy 及 merge map。
- 所有 merge 目標都存在於 66 個有效家族中；條件式合併依唯一主要問題分派。

## Split 配額與隔離

- manifest YAML 可解析，`status: draft_unfrozen`；正式目標另外新增 1,000 筆，Pilot 不計入。每類 train／validation／test 為 140／30／30，全體為 700／150／150。
- 同一 `scenario_family_id` 只出現在一個 split；66 個家族分配為 train 31、validation 15、test 20。
- 人行道維護：家族 7/3/4；筆數 140/30/30。
- 道路凹陷、不平、有高低差：家族 7/3/4；筆數 140/30/30。
- 一般公園綠地管理及設施維護：家族 8/3/4；筆數 140/30/30。
- 垃圾車清運及服務事項：家族 5/3/4；筆數 140/30/30。
- 路面清潔（含行人果皮箱、菸蒂、狗便）：家族 4/3/4；筆數 140/30/30。
- `FAM-ROAD-LONGITUDINAL-TRANSITION`、`FAM-ROAD-PAVEMENT-HEAVE`、`FAM-ROAD-WIDESPREAD-UNDULATION` 同列 test；`FAM-WASTE-HOLIDAY-SCHEDULE` 與 `FAM-WASTE-WEEKEND-SCHEDULE` 同列 test。原可回收物服務家族及原定期服務日家族的條件式分流目標也各自放在同一 split。

## 未解決事項

- Pilot 50 筆仍待人工複核；這些助理獨立建議不代表人工通過。
- 18 個家族邊界修訂與 9 個合併仍待人工決定。
- manifest 維持未凍結；正式 1,000 筆資料尚未生成。

## 原始檔未覆寫證據

下列來源在建立新檔前已計算 SHA-256，建立完成後再次計算，雜湊完全相同：

| 來源檔 | SHA-256 |
|---|---|
| `data/1999_synthetic/pilot_v1.2.2.jsonl` | `2b5db10dd64abfdb202a4bc3b084b8d5fc51af7ee4448c75fb86cc7e8d574a7b` |
| `data/1999_synthetic/taxonomy_expansion_draft_v1.1.md` | `9f3f206434884c3bffb4edaa4db2db6620024c335d118849eb3ea6b747f40401` |
| `data/1999_synthetic/formal_split_manifest_draft_v1.1.yaml` | `e6e3c7619e725ae216f9283f86bf42fe1631a64610b8973efd1f7196b0baf4cc` |
| `outputs/flycall-1999-review-decisions-v1/FlyCall_1999_助理獨立複核決定_v1.0.xlsx` | `04d22ffbfbfd59bd4870916d8c2793ef9c66cbfbcab5cd1e9c0526f00c29e74e` |
| `outputs/flycall-1999-review-decisions-v1/independent_review_decisions_v1.0.md` | `77cd24215212f98feb3960a64dee48929ce1e0674290e312df5d73b4b7e0e442` |

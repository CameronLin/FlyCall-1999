# 正式生成前檢查與凍結紀錄 v1.0

日期：2026-10-12

## 來源核對

| 檔案 | SHA-256 |
|---|---|
| `pilot_v1.2.3.jsonl` | `ece9d147088c901aa16d5249b4199638329848d88123824c6796d83df0a75b08` |
  | `taxonomy_expansion_draft_v1.3.md` | `221a39a61dc5de14e423ac3f2985b751ffb30070464660270b3e177c98917f5c` |
  | `family_merge_map_draft_v1.1.yaml` | `933c29507ba1f9aaa5a1ecfaa69a25abd1f1122a21f57be0ccfccbd276172eb0` |
  | `formal_split_manifest_draft_v1.2.yaml` | `7e070248c856cce6756b7b520001e6c6194b4b895d1253e4d1aa5757c2a47e02` |
  | `taxonomy_v1.2.1.yaml` | `a4049235521203d011cae81019ffbf89cde7234a9611dfc26a8d167463581613` |
  | `independent_review_decisions_v1.0.md` | `77cd24215212f98feb3960a64dee48929ce1e0674290e312df5d73b4b7e0e442` |
  | `FlyCall_1999_助理獨立複核決定_v1.0.xlsx` | `04d22ffbfbfd59bd4870916d8c2793ef9c66cbfbcab5cd1e9c0526f00c29e74e` |

- Pilot v1.2.3：50 筆，五類各 10 筆，全部 `split=pilot` 且 `review_status=pending_manual_review`。
- 與 v1.2.2 逐 ID 比對：只有 V12-037、038、048、050 的 `transcript` 欄改變；其餘 46 筆逐字稿與全部欄位不變。沒有標籤、scenario ID 或 family ID 變更。
- 複核 XLSX 與獨立複核 Markdown 的建議一致：Pilot pass 46／revise 4／reject 0；家族 pass 48／revise 18／merge 9。家族 revise IDs 與 taxonomy v1.3 的修訂列一致；9 個 merge 來源皆不在 active taxonomy，所有目標均有效。
- 活動家族數：人行道 14、道路 14、公園 15、垃圾車 12、路面清潔 11；共 66 個唯一 ID。

## 草案問題及處置

- `formal_split_manifest_draft_v1.2.yaml` 中 `waste_stop_presence` 有 train 與 validation 兩種 split。正式版將該群組四個家族全置 train，並將垃圾車家族配置改為 7/2/3；每類資料筆數仍精確為 140/30/30。
- v1.2 manifest 的 park `label_name` 為縮短版；正式版採 taxonomy v1.2.1 與 Pilot v1.2.3 的完整 canonical label。
- WIND litter 條件分流在正式 merge map 明確分成「一般散落物／來源不明」、「確認果皮箱滿溢外漏」、「確認箱體破損外漏」。另兩項條件合併依可觀察主訴明確路由；不再有未處理條件路由。

## 凍結配置

| 類別 | 家族數 train/validation/test | 筆數 train/validation/test |
|---|---:|---:|
| 人行道維護 | 7/3/4 | 140/30/30 |
  | 道路凹陷、不平、有高低差 | 7/3/4 | 140/30/30 |
  | 一般公園綠地管理及設施維護（含車輛違規進入） | 8/3/4 | 140/30/30 |
  | 垃圾車清運及服務事項 | 7/2/3 | 140/30/30 |
  | 路面清潔（含行人果皮箱、菸蒂、狗便） | 4/3/4 | 140/30/30 |
| **全體** | **33/14/19** | **700/150/150** |

- Pilot 50 筆完全獨立，不在上述配額內。正式 manifest 狀態 `frozen`。
- 原始草案、Pilot、決定 workbook/Markdown 均保留，沒有覆寫或刪除。

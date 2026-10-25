# 01: M2.1 資料契約與唯讀 loader

**What to build:** 研究流程可以唯讀載入既有正式資料，並在開始後續分析前確認資料欄位、標籤、切分與情境家族符合凍結契約；不符合時提供明確差異，避免流程使用錯誤資料。

**Blocked by:** None

**Status:** completed

- [x] 核對正式資料實際 JSONL／CSV schema、欄位型別、空值狀況、label 對照，以及 taxonomy 與 frozen manifest 的欄位，不假設規格草案中的欄名與實檔完全一致。
- [x] 提供可重用的唯讀 loader、資料契約檢查及機器可讀或 Markdown 稽核摘要，記錄來源版本與檢查結果。
- [x] 驗證正式資料共 1,000 筆、五類各 200 筆；全體 train／validation／test 為 700／150／150，各類為 140／30／30。
- [x] 驗證每筆標籤與 taxonomy 對應正確、`scenario_family_id` 不跨 split，且資料中的 split 與 frozen manifest 一致。
- [x] 遇到缺欄、欄位型別不符、標籤不符、配額不符或家族跨 split 時停止並指出差異，不自動修補資料或重新切分。
- [x] 執行前後正式 JSONL、CSV、taxonomy 與 frozen manifest 的 SHA-256 相同；流程不生成、修改、重標或重新切分既有資料。
- [x] 提供自動化測試，涵蓋成功載入、契約不符及唯讀不變性。

## Comments

- 2026-10-12：完成 `src/flycall_data/` 唯讀 loader 與暫存路徑測試。`PYTHONPATH=src python3 -m unittest discover -s tests -v` 通過 9 項測試。
- 使用正式檔案執行 `load_frozen_dataset` 成功：1,000 筆、五類各 200、全體 split 700／150／150、各類 140／30／30、66 個家族；JSONL、CSV、taxonomy、frozen manifest 與工作前 SHA-256 一致。
- 不修改正式資料、Pilot、taxonomy 或 manifest；沒有自動修補或重新切分。

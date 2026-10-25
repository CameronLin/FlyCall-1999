# 檔案整理與清理紀錄

整理日期：2026-10-11（Asia/Taipei）  
專案根目錄：`/Users/linyifen/Desktop/coding/FlyCall-1999`  
Git：此目錄不是 Git 專案，無法記錄 `git status --short`。

歷史 pilot、taxonomy、人工複核清單及驗證報告移至封存目錄，保留原檔名與內容。沒有刪除任何檔案；沒有移動或修改 v1.2.1 基準檔。v1.1 舊報告以相對路徑連到 `taxonomy.yaml`，因此未版本化資料與具名 v1.1 檔案集中在 `archive/pre_v1.2/`，保留既有相對連結。SHA-256 均以原始資料夾盤點值和封存後內容比對，確認完全一致。

| 原路徑 | 最終封存路徑 | 理由 | 位元組 | 原始 SHA-256 | 封存 SHA-256 | 結果 |
|---|---|---|---:|---|---|---|
| `data/1999_synthetic/manual_review.md` | `data/1999_synthetic/archive/pre_v1.2/manual_review.md` | 未版本化舊複核清單；封存以保留早期審閱紀錄與相對連結。 | 2718 | `8ef4e2496c6dc356d3015106c174b9b993362fa1b818714e7ce8d6a83e820ef6` | `8ef4e2496c6dc356d3015106c174b9b993362fa1b818714e7ce8d6a83e820ef6` | 相同 |
| `data/1999_synthetic/pilot.jsonl` | `data/1999_synthetic/archive/pre_v1.2/pilot.jsonl` | 早期 pilot（prompt_version v1.0）；不是 v1.2.1 基準，保留原始 50 筆。 | 76112 | `c0c1bc1b2c9ff5925f8da45db08ed1b0dc36a887e98c002383cdc9a525150f07` | `c0c1bc1b2c9ff5925f8da45db08ed1b0dc36a887e98c002383cdc9a525150f07` | 相同 |
| `data/1999_synthetic/taxonomy.yaml` | `data/1999_synthetic/archive/pre_v1.2/taxonomy.yaml` | 舊 taxonomy，內容版本 1.1 但檔名未帶版本；保留原名及來源資料。 | 12414 | `39c5edb2971c96ecf5125b46b1f296242830c2c3eebf05ed0edfcc1c9426f226` | `39c5edb2971c96ecf5125b46b1f296242830c2c3eebf05ed0edfcc1c9426f226` | 相同 |
| `data/1999_synthetic/validation_report.md` | `data/1999_synthetic/archive/pre_v1.2/validation_report.md` | 未版本化舊驗證報告；封存保留歷史檢查結果。 | 2970 | `1066b5bd922847b5c891422e2cfaa315a8019a57549b5ef3d7c20aa293a4ef1e` | `1066b5bd922847b5c891422e2cfaa315a8019a57549b5ef3d7c20aa293a4ef1e` | 相同 |
| `data/1999_synthetic/manual_review_v1.1.md` | `data/1999_synthetic/archive/pre_v1.2/manual_review_v1.1.md` | v1.1 舊複核清單；非目前基準，保留版本紀錄。 | 2320 | `0ed9a2e17220f7f51c375e8406073b081bb1bf8ba04605f20925c54e4bd21b22` | `0ed9a2e17220f7f51c375e8406073b081bb1bf8ba04605f20925c54e4bd21b22` | 相同 |
| `data/1999_synthetic/pilot_v1.1.jsonl` | `data/1999_synthetic/archive/pre_v1.2/pilot_v1.1.jsonl` | v1.1 舊 pilot；非目前基準，保留 50 筆原始資料。 | 63796 | `b8561576dcbd4573d928fd7901b07088315670965d2db70125faa2991b56425f` | `b8561576dcbd4573d928fd7901b07088315670965d2db70125faa2991b56425f` | 相同 |
| `data/1999_synthetic/validation_report_v1.1.md` | `data/1999_synthetic/archive/pre_v1.2/validation_report_v1.1.md` | v1.1 舊驗證報告；非目前基準，保留檢查紀錄。 | 2481 | `058374e47ad9c83b8fc6728bf995e37abd8671d5bbfb6e28451a8da37754265d` | `058374e47ad9c83b8fc6728bf995e37abd8671d5bbfb6e28451a8da37754265d` | 相同 |
| `data/1999_synthetic/manual_review_v1.2.md` | `data/1999_synthetic/archive/v1.2/manual_review_v1.2.md` | v1.2 舊複核清單；非目前基準，保留逐筆審閱要求。 | 3331 | `bed81eea41b85ce28e99ea37dcf13725f60d32fb12f788b7cdafdd963ff73c4e` | `bed81eea41b85ce28e99ea37dcf13725f60d32fb12f788b7cdafdd963ff73c4e` | 相同 |
| `data/1999_synthetic/pilot_v1.2.jsonl` | `data/1999_synthetic/archive/v1.2/pilot_v1.2.jsonl` | v1.2 舊 pilot；非目前基準，保留 50 筆原始資料。 | 89608 | `90fbfe5e7ac16d9c66382fc1f53c906ed62b7d15e3cac3b8be8f12fe57c8cc7c` | `90fbfe5e7ac16d9c66382fc1f53c906ed62b7d15e3cac3b8be8f12fe57c8cc7c` | 相同 |
| `data/1999_synthetic/taxonomy_v1.2.yaml` | `data/1999_synthetic/archive/v1.2/taxonomy_v1.2.yaml` | v1.2 舊 taxonomy；非目前基準，保留分類版本及規則。 | 14425 | `345f932a21bf619eb3e164fa06d7883e1b282371840350abdb65bb6a5c9aebd9` | `345f932a21bf619eb3e164fa06d7883e1b282371840350abdb65bb6a5c9aebd9` | 相同 |
| `data/1999_synthetic/validation_report_v1.2.md` | `data/1999_synthetic/archive/v1.2/validation_report_v1.2.md` | v1.2 舊驗證報告；非目前基準，保留檢查紀錄。 | 3341 | `2fe21bb6c48fa81cebf484518227ddbd38ef9638a848bbb37472e89c047a299b` | `2fe21bb6c48fa81cebf484518227ddbd38ef9638a848bbb37472e89c047a299b` | 相同 |

## 整理結果

- `archive/pre_v1.2/` 含未帶版本號的早期資料與具名 v1.1 檔案；其中 `taxonomy.yaml` 明載版本 1.1，而未版本化 `pilot.jsonl` 使用 v1.0 prompt。目錄名表示兩者均早於目前 v1.2.1 基準，不表示內容同版。
- `archive/v1.2/` 含 v1.2 完整四件套。
- 封存 11 個檔案；刪除 0 個檔案。未作重複副本刪除，也未移除任何版本的 pilot、taxonomy、複核清單或驗證報告。

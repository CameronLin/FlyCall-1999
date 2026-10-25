# FlyCall-1999 專案

本專案整理臺灣 1999 客服與民眾的合成通話資料，用於市政服務案件分類研究。正式資料使用 `R=客服`、`L=來電民眾`；Pilot 僅供試產與複核，與正式資料分開。

專案也包含 MaleCNS v1.0 connectome 的來源稽核、匯入、子圖可行性檢查，以及只使用小型 fixture 的圖分類模型核心。各階段範圍與限制記錄在 `1999-connectome-demo-spec-v0.2.md` 及 `.scratch/1999-connectome-demo/issues/`。

## 目前正式資料

- 正式資料 v1.0.0：1,000 筆、五類各 200 筆。主要檔案為 [JSONL](data/1999_synthetic/formal/v1.0.0/formal_dataset_v1.0.0.jsonl) 與 [CSV](data/1999_synthetic/formal/v1.0.0/formal_dataset_v1.0.0.csv)。Pilot 50 筆不計入此資料集。
- 正式分類設定：[taxonomy v1.3](data/1999_synthetic/taxonomy/current/taxonomy_v1.3.yaml)、[family merge map v1.0](data/1999_synthetic/taxonomy/current/family_merge_map_v1.0.yaml)、[frozen split manifest v1.0](data/1999_synthetic/taxonomy/current/formal_split_manifest_frozen_v1.0.yaml)。
- 自動驗證結果：[正式資料驗證報告](data/1999_synthetic/formal/v1.0.0/validation_report_v1.0.md)為 PASS；正式逐字稿仍待人工複核，程式檢查不代表人工簽核。
- Pilot 最新檔：[pilot v1.2.3](data/1999_synthetic/pilot/v1.2.3/pilot_v1.2.3.jsonl)，50 筆，保持 `pending_manual_review`，不屬於正式資料。

## 文字嵌入目標設定

專案目前選定 `intfloat/multilingual-e5-small`；集中設定位於 [model_config.py](src/flycall_data/model_config.py)。這只是目標設定：E5 尚未下載、安裝或載入，M2.2b 資源閘門仍為 blocked。不得將其視為已通過本機驗證。

## 檔案索引

資料版本、草案、封存檔、正式生成歷程、複核包、逐檔用途、搬移路徑與 SHA-256，請見[合成資料詳細索引](data/1999_synthetic/README.md)。舊路徑相容連結供歷史文件解析；新文件請使用索引中的新路徑。

## Connectome 開發資料

Git repository 保留來源 manifest、匯入程式、測試用小型子圖與驗證記錄；MaleCNS 原始 Feather（約 1.05 GB）及完整匯入 Parquet（約 654 MB）不納入 Git，避免超過 GitHub 的單檔大小限制。另一台電腦 clone 後，可依以下步驟取得固定版本並重建匯入資料：

```sh
mkdir -p data/connectome/malecns_v1.0
curl --fail --location --show-error \
  'https://storage.googleapis.com/flyem-male-cns/v1.0/connectome-data/flat-connectome/connectome-weights-male-cns-v1.0-minconf-0.5.feather?generation=1780494887545976' \
  --output data/connectome/malecns_v1.0/connectome-weights-male-cns-v1.0-minconf-0.5.feather
shasum -a 256 data/connectome/malecns_v1.0/connectome-weights-male-cns-v1.0-minconf-0.5.feather
python3 -m pip install -r requirements-connectome.txt
python3 scripts/import_malecns_v1.py
python3 scripts/verify_malecns_import.py
```

下載檔的預期 SHA-256 為 `e35da783d1c686b2b58b3b87cd6a403ae43bfcfba8bff28e08ef752c1a56afc1`。完整來源、授權 attribution、版本 generation 與匯入契約見 [`source_manifest.yaml`](data/connectome/malecns_v1.0/source_manifest.yaml)；匯入輸出的兩個大型 Parquet 也由 `.gitignore` 排除，可在各電腦本機重建。

# 07: M3.0 Connectome 分類資料流與訓練契約決策

**What to build:** 在 M3.1 sparse graph core 與後續 Fly A／Fly B 前，完成可審查的首版工程契約。此 ticket 僅涵蓋設計、決策記錄及與 spec 對照，不含模型實作、訓練或下載。

**Blocked by:** 01 M2.1 資料契約與唯讀 loader (completed); 05 M1.3 I/O 可達性與 graph manifest (completed)

**Status:** completed

## 範圍

以 spec v0.2、M2.1 資料契約、M1.2 engineering demo 子圖及 M1.3 I/O manifest 為依據，記錄 Fly A／Fly B 的資料流、圖計算、edge weight、訓練、驗證、資料品質及資源限制。2026-10-21 依使用者最新決定更新 spec v0.2 的 E5 目標設定；正式案件資料、Pilot、M1.1／M1.2／M1.3 產物保持不變。

## 產物

- 首版契約：[docs/research/m3-0-connectome-classifier-contract.md](../../../docs/research/m3-0-connectome-classifier-contract.md)（v1.4；E5 runtime 與三 seed M3.2 train/validation runs 已通過；M3.4／人工複核狀態見各工作票）
- 下一項獨立實作工作：08 M3.1 小型 fixture 模型核心。

## 驗收條件

- [x] 記錄使用者選定的 E5 small 目標 revision、prefix、512-token limit、384 維 masked mean pooling、L2 normalization 及 CPU／batch 1 受限試跑設定；先 L2-normalize 再以 train-only affine `d→32` projection 加 `tanh` 產生 Fly A input drives，並規定 R/L、Unicode、截斷與 fit 邊界。明確註記模型尚未本機下載／安裝／載入。
- [x] 記錄固定 scalar state、每步注入 input drive、共享時間步 edge gains、`source_id→target_id`、`T=2` 主設定及 `T=4` validation-only ablation；M1.3 可達性不當作分類效果證據。
- [x] 記錄 Fly A 的 32 個 output 值做 L2 normalization，按 M1.3 固定順序送入 Fly B；Fly B 使用獨立 trainable `32→32` adapter 及 `32→5` linear readout，label 順序固定為 taxonomy 順序。
- [x] 禁止繞過 graph core 的 input-to-output shortcut，記錄 A/B adapter、graph core、readout 參數量及合成 I/O nodes 不具生物學語意。
- [x] 固定每條既有 edge 一個獨立正值 gain、非邊無參數、自連線保留、`log1p(weight)` per-target mean-1 prior、`epsilon + softplus(raw)` 且 `epsilon=1e-6`、固定入度 normalization，以及不一致或無法初始化時 fail closed。說明來源 weight 是連線數，不是校準突觸效能；不推定抑制性或生物功能。
- [x] 記錄 Fly A train-only pairwise distance-preserving loss、validation stress 最小化及較早 epoch tie-break；凍結 A 後 Fly B 用 train cross-entropy，validation Macro-F1 選模，平手依較低 validation loss、較早 epoch。
- [x] 記錄 fixture／除錯一個固定 seed、正式比較至少三個事先記錄的 training seeds，報告平均與標準差；test 只在人工複核門檻及設定鎖定後對預先聲明候選一次性使用。
- [x] 記錄正式資料仍 pending_manual_review；M3.1 僅用小型 fixtures，不使用正式資料訓練；下載／安裝／載入前需核對官方 model card、revision、檔案與套件下載量、峰值 RAM、即時磁碟空間並保留至少 4 GiB。
- [x] 核對使用者確認的契約與現行 spec v0.2；沒有硬性衝突。將 spec 暫定項目具體化；2026-10-21 僅更新 E5 目標設定文字，未修改程式以外的任何資料或模型產物，未安裝套件、下載／載入模型、訓練或使用 test 指標。

## E5 與後續狀態

E5 的目標 model card／license、revision、prefix、tokenizer 上限及輸出維度已有官方來源查核並由使用者選定；2026-10-26 已通過 Windows 資源閘門及 runtime 驗證，見 M2.2b report。M3.2 graph provenance 已確認是 Windows CRLF checkout 造成表面 bytes 差異；正規化後仍完全匹配原 pin。PyArrow 26.0.0 在後續實際 run 可正常讀圖，三個 provisional seeds 均完成。沒有修改 pin、manifest 或 Windows trust policy；人工複核與 test gate 仍未完成。

## 後續關係

M3.1 小型 fixture 模型核心依賴本 ticket 與 M1.3 I/O manifest；本 ticket 的完成不代表 M3.1 已開始或已驗證。

## Comments

- 2026-10-16：初版 M3.0 契約草案完成，等待使用者決策。
- 2026-10-16：使用者確認首版工程契約；更新契約至 v1.1，記錄資料流、T、A/B adapter 與 readout、edge prior／正值參數化、固定入度聚合、訓練與選模、資料品質 gate 及資源 gate。逐項比對 spec v0.2，確認無硬性衝突；未修改 spec 或任何資料／模型產物。M3.0 驗收條件全數完成，狀態設為 completed。
- 同日建立 08 M3.1「小型 fixture 模型核心」ticket；未開始其實作。
- 2026-10-21：依使用者選定的 multilingual-e5-small 設定更新 spec v0.2 與契約至 v1.2，並更新本 ticket 的設定與資源閘門說明。模型未下載、安裝或載入；M2.2b 維持 blocked，M3.0 ticket 狀態仍為 completed。

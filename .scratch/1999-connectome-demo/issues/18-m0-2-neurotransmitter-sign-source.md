# 18: M0.2 神經傳導物質與突觸符號資料來源

**Blocked by:** None

**Status:** completed (2026-11-13)

## 背景

使用者希望子圖由「增強點」和「抑制點」組成，訓練時只改連線大小、不改正負（見工作票 19、21、22）。但目前匯入的 `connectome-weights-male-cns-v1.0-minconf-0.5.feather` 只有 `body_pre`、`body_post`、`weight` 三個欄位，**沒有任何神經傳導物質或符號資訊**。規格書 §3 有預留可選的 `neurotransmitter` 欄位，但從未匯入。

## 要做的事

- 查核 MaleCNS v1.0 官方是否提供每個神經元的預測神經傳導物質；如果有，找出檔案或 API、欄位名稱、信心欄位、版本／generation、checksum 及授權 attribution。不要從記憶推測欄位名稱，以官方文件和小量 probe 為準。
- 比照 M0.1 寫一份 source manifest（`data/connectome/malecns_v1.0/` 下新增或擴充），記錄存取步驟與可重跑的 probe。
- 依下列規則，把神經傳導物質對應成神經元層級的符號（+1／−1／排除）：
  - ACh → +1（增強）
  - GABA → −1（抑制）
  - **D2（已決定）：** 麩胺酸（Glu）→ **−1（抑制）**，作為主要規則。另外產出 Glu → +1 的敏感度版本，供工作票 22 對照。
    - 理由：果蠅中樞的麩胺酸多經 GluClα 氯離子通道產生抑制；肌肉接點的增強作用不在腦部 connectome 內。
    - 常見全腦建模做法也把 Glu 當抑制。執行時要找到並引用原始文獻（例如 Shiu et al. 2024 FlyWire 全腦模型），確認後才寫入 manifest，不可只憑記憶。
  - **D2b（已決定）：** 多巴胺、血清素、章魚胺等調節型 → **排除**（不進入子圖）。
  - 預測信心低於門檻或缺值 → 排除（門檻在 manifest 中寫定）。
- 輸出 neuron→sign 表（Parquet），每列保留原始 neuron ID、預測傳導物質、信心值，以及兩個符號欄位：`sign_glu_inhibitory`（主要）與 `sign_glu_excitatory`（敏感度）。大檔不進 Git，比照現有 Parquet 處理。

## 驗收條件

- manifest 欄位齊全；probe 可重跑；checksum 與來源一致。
- 統計並報告：各傳導物質的神經元數、+1／−1／排除的數量、與 M1.1 節點表的對應覆蓋率。
- 如果官方沒有提供可用的傳導物質資料，或授權不允許，就停止並回報證據；不得自行改用其他資料集，卻沿用 MaleCNS 的名稱。

## Comments

- 2026-11-13：使用者採用建議。D2 麩胺酸 = 抑制，並加一組麩胺酸 = 增強的敏感度對照；D2b 調節型傳導物質 = 排除。
- 2026-11-13：完成。
  - **來源：** 官方 `body-neurotransmitters-male-cns-v1.0.feather`。
    - generation `1780894899156750`，43,282,834 bytes，SHA-256 `95c92892…8879621`；本機 MD5 與伺服器一致。
    - 使用者同意後下載；檔案不進 Git。
  - **使用欄位：** 官方建議的 `consensus_nt`。依 Berg et al. 2026 Cell STAR Methods：
    - 信心 < 0.5 或突觸太少的會標為 `unclear`。
    - 有實驗 ground truth 的 cell type 會覆蓋模型預測。
    - 因此不再加第二道信心門檻。
  - **D2 依據：** Shiu et al. 2024 Nature 的 Methods 已確認，預設把 GABA 和麩胺酸當抑制，另外測試麩胺酸當增強。差異：Shiu 把調節型當增強，本專案排除。
  - **新增決策 D2c：** 資料中出現組織胺（histamine），使用者決定算 −1（抑制）。
  - **規則：** ACh +1；GABA −1；組織胺 −1；麩胺酸主要版本 −1、敏感度版本 +1；DA／OA／5-HT 排除；unclear 排除；未知標籤直接報錯。
  - **全表統計（1,835,518 列）：**

    | 版本 | 增強 | 抑制 | 排除 |
    |---|---:|---:|---:|
    | 主要（麩胺酸 = −1） | 104,193 | 59,663 | 1,671,662 |
    | 敏感度（麩胺酸 = +1） | 133,636 | 30,220 | 1,671,662 |

  - **重要發現：** 目前 G0 的 500 點中，**360 點不在表內**，可能是片段對片段連線圖中的非神經元片段。只有 130 點有符號（主要版本 73 增強、57 抑制、10 排除）；32 個輸入點中有 21 個不在表內。
  - **產物：**
    - `data/connectome/malecns_v1.0/neurotransmitter_source_manifest.yaml`
    - `data/connectome/derived/malecns_v1.0/neuron_signs_v1.0_summary.json`
    - 符號表 Parquet（不進 Git，用 `python scripts/build_neurotransmitter_signs.py` 重建）
    - `src/flycall_data/neurotransmitter_signs.py`
    - `tests/test_neurotransmitter_signs.py`（5 項）
  - **測試：** 完整套件 162 項中 160 項通過；另 2 項是已知的 Streamlit 問題，暫時跳過。
  - **未完成：** 本機沒有 1.05 GB 連線檔與 `nodes.parquet`，未計算對 M1.1 全節點表的覆蓋率。

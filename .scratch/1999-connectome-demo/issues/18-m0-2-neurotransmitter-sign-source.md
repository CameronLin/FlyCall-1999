# 18: M0.2 神經傳導物質與突觸符號資料來源

**Blocked by:** None（來源查核可立即開始）。最後的符號對應規則需要使用者決定：決策 D2（麩胺酸）與 D2b（調節型傳導物質）。

**Status:** needs-decision（查核可開始；對應規則待決定）

## 背景

使用者希望子圖由「增強點」和「抑制點」組成，訓練時只改連線大小、不改正負（見工作票 19、21、22）。但目前匯入的 `connectome-weights-male-cns-v1.0-minconf-0.5.feather` 只有 `body_pre`、`body_post`、`weight` 三個欄位，**沒有任何神經傳導物質或符號資訊**。規格書 §3 有預留可選的 `neurotransmitter` 欄位，但從未匯入。

## 要做的事

- 查核 MaleCNS v1.0 官方是否提供每個神經元的預測神經傳導物質；如果有，找出檔案或 API、欄位名稱、信心欄位、版本／generation、checksum 及授權 attribution。不要從記憶推測欄位名稱，以官方文件和小量 probe 為準。
- 比照 M0.1 寫一份 source manifest（`data/connectome/malecns_v1.0/` 下新增或擴充），記錄存取步驟與可重跑的 probe。
- 依使用者決定的規則，把神經傳導物質對應成神經元層級的符號（+1／−1／排除）：
  - ACh → +1（增強）
  - GABA → −1（抑制）
  - **D2：** 麩胺酸（Glu）→ 待使用者決定（在果蠅中樞常是抑制性，但不是絕對）
  - **D2b：** 多巴胺、血清素、章魚胺等調節型 → 待使用者決定（排除或另行處理）
  - 預測信心低於門檻或缺值 → 排除（門檻在 manifest 中寫定）
- 輸出 neuron→sign 表（Parquet），每列保留原始 neuron ID、預測傳導物質、信心值與符號；大檔不進 Git，比照現有 Parquet 處理。

## 驗收條件

- manifest 欄位齊全；probe 可重跑；checksum 與來源一致。
- 統計並報告：各傳導物質的神經元數、+1／−1／排除的數量、與 M1.1 節點表的對應覆蓋率。
- 如果官方沒有提供可用的傳導物質資料，或授權不允許，就停止並回報證據；不得自行改用其他資料集，卻沿用 MaleCNS 的名稱。

## Comments

# 20: M3.7 Fly A／Fly B 各自調到最好的訓練流程

**Blocked by:** None（流程可以先在現有 500 點／2,216 邊的圖上建立）。Fly A 的訓練目標需要使用者決定：決策 D4。

**Status:** completed (2026-11-13; validation only, test `not_run`)

## 背景

使用者的中心思想：維持架構，只改 Fly A 與 Fly B 的參數，讓兩者分別在降維與分類上達到目前能做到的最好表現。工作票 17 的交叉實驗顯示兩件事：

- Fly A 是主要瓶頸：分類器固定為 SVM 時，Fly A 比 LDA 低 0.108。
- Fly B 在 M3.2 的訓練預算下沒練完；給予較長訓練後，在 Fly A 輸入上與 SVM 沒有明確差距。

因此兩者要分開調參、分開評分，並且事先寫定規則。

## 要做的事

- **評分量尺（從工作票 17 沿用）：**
  - Fly A：輸出接固定的 SVM（StandardScaler＋RBF，C=1），用 Macro-F1 評分；同時報告保留距離的程度（validation stress）。
  - Fly B：先接 LDA 4-D，測它本身的分類能力；再接選定的 Fly A。以「同一份輸入下接近 SVM」當作練到位的標準。
- **Fly A 訓練目標（D4，待決定）：**
  - (a) 維持只保留距離、不看類別
  - (b) 改成也參考類別（例如保留距離＋類別分離）
  - (c) 兩者都跑，各自報告
- **調參不碰 validation：** 在 700 筆 train 上做依 `scenario_family_id` 分組的 k-fold 交叉驗證，選出設定後，才在 validation 上確認一次。test 保持 `not_run`。
- **事先寫定的設定組合**（執行前寫進預註冊，不在看過結果後增加）：
  - Fly A：學習率 {0.001, 0.003, 0.01}，最多 200 epoch，patience 25
  - Fly B：學習率 {0.001, 0.003, 0.01}，最多 200 epoch，patience 25
- Fly A 先選定、凍結，再調 Fly B（不聯合微調，符合規格書）。
- 三個 seed（42、1337、2026）；報告平均、樣本標準差，以及每個 fold 的分數。
- 圖必須能替換，以便工作票 22 在三張圖上重用同一套流程。

## 驗收條件

- 預註冊在執行前寫好並加入版本控制。
- train-fold／held-out-fold 的家族不重疊；validation 只在最後確認時讀一次；test 讀取數為 0。
- 在現有的圖上跑完一輪，產出報告。Fly B 接 LDA、接 Fly A 時，各自與 SVM 的差距都要列出。
- 選定設定、checkpoint 雜湊、source 雜湊都寫進 `results.json`。

## Comments

- 2026-11-13：使用者決定 D4 =（c）兩種都跑。
  - `distance`：原距離保留損失。
  - `distance_supcon`：距離保留＋SupCon，λ=1、τ=0.1。
  - 預註冊：[independent-fly-a-fly-b-tuning-preregistration-20261113.md](../research/independent-fly-a-fly-b-tuning-preregistration-20261113.md)。
  - 由於每個 epoch 約 0.05 秒，交叉驗證改為三個 seed 都跑（原計畫只用 seed 42）。
  - 最終訓練用交叉驗證得到的中位數 epoch 固定訓練，不再用 validation 做 early stopping，因此 validation 只讀一次。
- 2026-11-13：**完成**，與工作票 22 同一次執行（`scripts/run_independent_tuning.py`，四張圖合計 68 分 13 秒）。報告：[report.md](../runs/independent-tuning-20261113/report.md)；另有 `results.json`、`timings.json`、`progress.log`，以及最終 checkpoints（60 個）。
  - **流程：** Fly A、Fly B 各自用 train 分組 5-fold × 3 seed 選學習率，最終以固定 epoch 訓練；validation 每個模型只讀一次。
  - **Fly B 已練到位：** 新圖上 LDA→Fly B（0.896–0.907）≈ LDA→SVM（0.900）；Fly A→Fly B 也與 Fly A→SVM 相當。原本 Fly B 訓練不足的問題已排除。
  - **Fly A 訓練目標：** 加入 SupCon 後，Fly A→SVM 在 G0（+0.117）、G2（+0.031）、G2-glu+（+0.039）一致提升，G1 則不明確。代價是距離保留明顯變差：validation stress 約從 0.003 升到 0.15。
  - **注意事項：**
    - 交叉驗證的 OOF 分數（約 0.96–0.99）明顯高於 validation（約 0.86–0.92），交叉驗證偏樂觀；應以 validation 為準。
    - Fly B on SupCon-Fly A 選到的訓練長度在 G1／G2／G2-glu+ 達到 198–200，碰到上限 200，可能還沒收斂。
    - 已用新程式驗證 `GraphDefinition(node_signs=…)` 可直接訓練新圖；新 runner 依 manifest 驗證圖檔，不使用寫死 2,216 邊的 `validate_engineering_graph`。
  - **測試：** 新增 `tests/test_independent_tuning.py` 6 項；完整套件 175 項中 173 項通過，另 2 項是已知的 Streamlit 問題。
- 2026-11-13：**修正後語意重跑**（工作票 23），結果見工作票 22。Fly B on SupCon-Fly A 選到的訓練長度仍碰到 199–200 的上限。
- 2026-11-13：**Fly A／Fly B 腦部比較（事後分析）**：`scripts/compare_fly_a_fly_b_brains.py`，報告：[report.md](../runs/fly-ab-brain-comparison-t-hops-20261113/report.md)，含 17 張圖，耗時 532 秒；完好模型分數與調參結果差異為 0。
  - **連線：Fly B 大幅改寫圖，Fly A 幾乎不動。** 邊強度改變量的 SD：Fly A 為 0.01–0.05，Fly B 為 0.22–0.38。Fly A 主要靠 384→32 的轉接層（12,320 個參數）完成降維，圖上的連線幾乎維持初始的 connectome 強度。Fly B 的改變在不同 seed 間相當一致（ρ 0.40–0.89），但和 Fly A 的改變幾乎無關（ρ −0.08–0.24），代表這是分類任務特有的改寫。
  - **活化：Fly B 的神經元高度類別選擇性。** η² 中位數：Fly B 0.76–0.83；Fly A（distance）0.24–0.38；Fly A（+SupCon）0.91–0.95，加入類別目標後變得和 Fly B 一樣。Fly A 有 350–460 個神經元幾乎不活動，Fly B 只有 2–123 個。「哪些神經元較活躍」在 A、B 之間高度相關（新圖 ρ 0.76–0.87，接近換 seed 的基準），主要由圖的結構決定。
  - **損傷：單一神經元幾乎不重要，表示資訊是分散儲存的。** 關掉單一神經元後掉 ≥ 0.02 的只有 0–9 個；A、B 的損傷影響互不相關，最重要 20 個神經元的重疊也和換 seed 差不多。拿掉 G2 的全部抑制邊後，distance 模型的 Fly A→SVM 掉 0.097、Fly B 掉 0.056，代表抑制連線確實被使用；SupCon 模型則幾乎不受影響。
  - **限制：** 損傷影響在 150 筆 validation 上量測，1 筆約等於 0.007，小差異可能是雜訊；A、B 的輸入與轉接層不同，差異不全來自圖。

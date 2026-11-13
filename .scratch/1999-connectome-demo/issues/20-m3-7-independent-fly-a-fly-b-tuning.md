# 20: M3.7 Fly A／Fly B 各自調到最好的訓練流程

**Blocked by:** None（流程可以先在現有 500 點／2,216 邊的圖上建立）。Fly A 的訓練目標需要使用者決定：決策 D4。

**Status:** needs-decision（流程可開始；Fly A 目標待決定）

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

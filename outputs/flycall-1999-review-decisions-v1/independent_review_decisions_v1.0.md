# FlyCall-1999 助理獨立複核決定 v1.0

日期：2026-10-12

## 決定摘要

- Pilot v1.2.2：50 筆，pass 46、revise 4、reject 0。四筆待修訂：V12-037、V12-038、V12-048、V12-050。
- 情境家族：75 個，pass 48、revise 18、merge 9。
- 正式資料目標仍是另外新增 1,000 筆；Pilot 不計入。建議維持 70/15/15，即每類 140/30/30、全體 700/150/150。
- 合併後保留 66 個家族；目前 manifest v1.1 的 65 個家族數不再符合，需按本決定重算。

## Pilot 待修訂

| ID | 理由 | 建議修訂 |
|---|---|---|
| TPE1999-V12-037 | 等候位置不明是單一主訴，但來電者連續排除漏收、路線原因與其他類型，呈現為替分類消歧而寫的說明，口語自然度不足。 | 保留「新住戶不確定固定等候點」；刪減多句排除其他案件的文字，改成自然詢問附近固定停靠位置。 |
| TPE1999-V12-038 | 停靠位置改變與等候點不明的主訴清楚，但結尾特別聲明不是整區未服務，屬不自然的分類排除提示。 | 保留最近看到停靠位置改變、居民等候位置不一致；刪除「不是整個區域沒有服務」等分類提示。 |
| TPE1999-V12-048 | 公共人行道狗便清理屬單一主訴；「不是要找飼主或詢問裁罰」直接提示另一分類邊界，削弱真實來電感。 | 保留狗便反覆出現在公共通行面及行人避讓；刪除裁罰／飼主對照句，不必交代未提出的需求。 |
| TPE1999-V12-050 | 落葉泥土清潔是主要問題，但主動補充排水口未堵及「主要是步道表面需要清理」直接排除其他分類，構成語意提示。 | 聚焦雨後落葉泥土濕滑、範圍與行人通行情況；刪除排水口狀態及明示「主要問題」的分類提示。 |

其餘 46 筆建議 pass：目前標籤與單一主訴相符，對話基本連貫，未發現足以退回的個資或高相似問題。整批仍有較規整的追問節奏與記錄式結尾，正式生成時應增加句型與互動變化。

## 情境家族 revise（18）

- `FAM-SW-UTILITY-RESTORATION`：保留須有可觀察的開挖回填帶及其表面沉陷／接合缺陷；只描述一般沉陷時歸 FAM-SW-LEVEL-SETTLEMENT。
- `FAM-SW-CURB-RAMP-LANDING`：限坡道頂端或平台的平面幾何、坡向或轉向空間缺陷；排除坡面材料破損及一般鋪面沉陷。
- `FAM-SW-FLAT-SURFACE-SLIPPERY`：限固定平面鋪面長期磨光造成的乾濕摩擦差；排除液體／泥污，並明確與 FAM-SW-RAMP-SURFACE 區分。
- `FAM-SW-EDGE-CRUMBLING`：界定為人行鋪面外緣本體碎裂；排除緣石本體破損與平面表層剝落，避免與 FAM-SW-CONCRETE-SPALLING 混用。
- `FAM-SW-PEDESTRIAN-DECK`：限定公共人行橋或架高通道的行走面板缺陷；明確排除園內一般步道及橋體結構安全問題。
- `FAM-ROAD-BINDER-BLEEDING`：只納入有路面材料本體特徵的瀝青黏結料上浮；不得僅憑發亮／濕滑推定，排除外來液體或油污。
- `FAM-ROAD-PAVEMENT-HEAVE`：限局部或片狀車行鋪面隆起；排除線狀接縫高差及孔蓋凸起，並與 FAM-ROAD-LONGITUDINAL-TRANSITION 明確分界。
- `FAM-ROAD-UTILITY-CUT-SETTLEMENT`：要求可辨認管線開挖回填範圍且低槽位於回填帶內；若問題只在補面接邊，歸 FAM-ROAD-REPAIR-JOINT。
- `FAM-ROAD-WIDESPREAD-UNDULATION`：只納入跨一段路面的連續波狀起伏，不以路段長度作判準；排除單一輪跡槽、接縫及局部隆起。
- `FAM-ROAD-LONGITUDINAL-TRANSITION`：目前「長條或斜向高低轉換」與廣泛波狀起伏、局部隆起界線重疊；收斂為可辨識的單一線狀接合／轉換帶，並排除廣域波動與片狀隆起。與 FAM-ROAD-WIDESPREAD-UNDULATION 同 split，避免相近情境跨資料集。
- `FAM-PARK-LIGHTING-EQUIPMENT`：要求可確認照明設備位於一般公園範圍內；明確排除道路路燈及其他不屬公園設施的照明。
- `FAM-PARK-STAIR-HANDRAIL`：家族核心限定扶手或固定支撐件鬆脫／損壞；階梯踏面破損需另列公園鋪面／設施情境，不納入本家族。
- `FAM-WASTE-SHORT-DWELL`：必須有車輛曾在正常停靠點停靠但停留不足的觀察；若車未到，歸 FAM-WASTE-MISSED-STOP。
- `FAM-WASTE-ROUTE-ORDER-CHANGE`：必須有至少兩個停靠點的先後次序改變證據；只有到達時間早晚不同時歸 FAM-WASTE-ARRIVAL-TIME。
- `FAM-WASTE-HOLIDAY-SCHEDULE`：保留為國定假日／連假期間停收、調整或補收的詢問；排除一般週末例行時段，且不得生成未經查證的官方班表答案。與 FAM-WASTE-WEEKEND-SCHEDULE 放在同一 split。
- `FAM-WASTE-ACCESS-INTERRUPTION`：主訴須是臨時通行限制造成當次收運服務受影響；不把道路封閉或施工管理本身分類成垃圾車案件。
- `FAM-CLEAN-REACCUMULATING-DEBRIS`：要求觀察到清掃後有新垃圾再次累積；排除同一舊污未清及果皮箱來源，後兩者分別歸清掃殘留或果皮箱家族。
- `FAM-CLEAN-LOOSE-GRIT`：限定外來、鬆散且可清掃的沙粒／碎石；排除由鋪面自身剝落形成的碎屑及大型物料外洩。

## 情境家族 merge（9）

- `FAM-SW-DRIVEWAY-CROSSING` → FAM-SW-LEVEL-SETTLEMENT。僅限人行道與車道出入口銜接處出現可描述的高低差；將目標家族納入界線補上出入口銜接落差。
- `FAM-ROAD-CROSSING-APPROACH` → FAM-ROAD-INTERSECTION-DENT。停靠／穿越位置前的局部車道路面凹陷作為路口局部凹陷的相對位置變化。
- `FAM-WASTE-TEMP-STOP-RELOCATION` → FAM-WASTE-STOP-LOCATION。臨時停靠點移動屬停靠位置資訊變動。
- `FAM-WASTE-SCHEDULED-DAY-OMISSION` → FAM-WASTE-MISSED-STOP 或 FAM-WASTE-ROUTE-SEGMENT-OMISSION。單一停靠點／住戶未服務歸 MISSED-STOP；整段街廓未服務歸 ROUTE-SEGMENT-OMISSION。
- `FAM-WASTE-RECYCLABLE-STREAM-SERVICE` → FAM-WASTE-ARRIVAL-TIME／FAM-WASTE-MISSED-STOP／FAM-WASTE-STOP-LOCATION。依唯一主要訴求分派：時段不明、未到點或停靠位置不明；排除回收物分類與政策諮詢。
- `FAM-CLEAN-EVENT-PACKAGING` → FAM-CLEAN-SURFACE-DEBRIS。活動後包裝與紙屑作為一般公共路面散落物的來源變化，不獨立成家族。
- `FAM-CLEAN-WIND-DISPERSED-LITTER` → FAM-CLEAN-SURFACE-DEBRIS；可確認來源時改派至 FAM-CLEAN-BIN-OVERFLOW 或 FAM-CLEAN-BIN-DAMAGE。不得只因來電者推測有風就分派；能描述的散落物先歸一般路面髒污，來源確證為果皮箱時才改派。
- `FAM-CLEAN-GUM-ADHERED-RESIDUE` → FAM-CLEAN-SURFACE-DEBRIS。黏著殘留是一般路面髒污的污物型態，不另立服務家族。
- `FAM-CLEAN-DOG-WASTE-PERSISTENT-RESIDUE` → FAM-CLEAN-DOG-WASTE 或 FAM-CLEAN-POST-SWEEP-RESIDUE。新出現／不同點位的狗便清理歸 DOG-WASTE；確認同一舊痕清掃後仍留存才歸 POST-SWEEP-RESIDUE。

## Pass 家族（48）

其餘未列於 revise／merge 的 48 個家族建議 pass。決定表保留原核心、納入／排除界線、第二次複核建議與理由，供逐項追溯。

## Split 建議

| 類別家族數 | train／validation／test 家族數 | train／validation／test 筆數 |
|---:|---:|---:|
| 14 | 7／3／4 | 140／30／30 |
| 14 | 7／3／4 | 140／30／30 |
| 15 | 8／3／4 | 140／30／30 |
| 12 | 5／3／4 | 140／30／30 |
| 11 | 4／3／4 | 140／30／30 |
| **66** | **31／15／20** | **700／150／150** |

這項配置增加 test 家族涵蓋；代價是 train 家族數較少、每個 train 家族需生成較多逐字稿。正式 manifest 必須按已修訂的家族邊界重算，並確保相近的道路縱向轉換、隆起與波狀起伏不跨 split。垃圾車假日家族與一般週末家族建議同 split。

## 核准狀態與範圍

本決定是助理獨立複核，不是使用者本人簽核。人工決定欄維持 pending。未修改來源 Pilot JSONL、taxonomy 或 manifest；未凍結 manifest，也未生成正式資料。Pilot revise 與 family revise 必須完成實際內容修訂及再驗證後，才能視為通過。

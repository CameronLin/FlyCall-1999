# Dataset v2.0.0 validation report

**Status:** frozen. 自動品質檢查通過，未經人工複核（ticket 25, D-V2-4）。

## Contents

- Records: 1000 (5 labels × 200); families, splits and per-family quotas unchanged from v1.0.0.
- Splits: train 700, validation 150, test 150.
- Per label: sidewalk_maintenance 140/30/30; road_surface_defect 140/30/30; park_general_maintenance 140/30/30; waste_truck_service 140/30/30; street_cleaning 140/30/30 (train/val/test).
- `review_status`: `automated_qa_passed_no_manual_review`; `prompt_version`: `flycall1999-formal-v2.0.0`.

## Automated QA results

| Check | Result | Target |
|---|---:|---|
| Rule flags (format, 7–17 lines, ≥200 CJK, PII, own-label fragments, agent promises) | 0 | 0 |
| Near-duplicate pairs (char 3-gram Jaccard ≥ 0.72) | 0 | 0 |
| Max pairwise Jaccard | 0.2613 | < 0.72 (v1: 0.48) |
| Share of lines reused | 19.6% | < 20% (v1: ~70%) |
| Distinct opening lines | 1000 | (v1: 8) |
| Distinct closing lines | 755 | (v1: 24) |
| Mean CJK characters | 240.5 | ≥ 200 each |
| Line-count histogram | {'9': 111, '10': 58, '11': 204, '12': 198, '13': 335, '14': 18, '15': 73, '16': 3} | 7–17 |
| Leave-family-out classifier accuracy (char TF-IDF + LR) | 0.982 | — |
| High-confidence (p ≥ 0.6) other-label predictions | 3 | reviewed |

## Shortcut n-grams (precision ≥ 0.9, coverage ≥ 0.3 within a label)

Template artefacts found in the hand-written batches were removed by `scripts/v2_vary_stock_lines.py`
(e.g. the agent question 「請問是哪一區的公園？」 in 98% of park calls, 「的方向，」 in road calls,
「公尺範圍」 in cleaning recaps). What remains is the subject vocabulary of each label, accepted as
inherent rather than a label-name echo (v1's 「一般公園」):

- waste_truck_service: 「垃圾車」 0.92/1.00, 「圾車」 0.92/1.00, 「停靠」 0.75/0.92, 「垃圾的」 0.47/0.97, 「圾的」 0.47/0.97, 「停靠點」 0.47/1.00, 「靠點」 0.47/1.00, 「丟垃圾」 0.35/0.99, 「丟垃」 0.35/0.99, 「個停靠」 0.31/0.98
- park_general_maintenance: 「的公園」 0.62/1.00, 「公園。R」 0.55/1.00, 「園。R:」 0.55/1.00, 「園。R」 0.55/1.00, 「公園。」 0.55/1.00, 「園。」 0.55/1.00, 「公園，」 0.51/0.97, 「園，」 0.51/0.95, 「園的」 0.38/0.93, 「公園的」 0.36/0.94
- street_cleaning: 「垃圾桶」 0.37/1.00, 「圾桶」 0.37/1.00, 「桶，」 0.34/0.98, 「垃圾桶，」 0.33/1.00, 「圾桶，」 0.33/1.00

## Label-consistency review

Records predicted as another label with p ≥ 0.6 by a classifier trained without their own family were read by Claude:

- TPE1999-V2-SC-0001 (FAM-CLEAN-LOOSE-GRIT): predicted road_surface_defect p=0.631 — kept; single complaint inside its family boundary (intended hard boundary case).
- TPE1999-V2-SW-0154 (FAM-SW-UTILITY-RESTORATION): predicted road_surface_defect p=0.607 — kept; single complaint inside its family boundary (intended hard boundary case).
- TPE1999-V2-SW-0170 (FAM-SW-UTILITY-RESTORATION): predicted road_surface_defect p=0.669 — kept; single complaint inside its family boundary (intended hard boundary case).

## Files and SHA-256

- `data/1999_synthetic/formal/v2.0.0/formal_dataset_v2.0.0.jsonl` `2217855d7d874b794063027b53abf79399dff184117f2ae8942bf52e6489c470`
- `data/1999_synthetic/formal/v2.0.0/formal_dataset_v2.0.0.csv` `10c8826b49f115a9a82995e96f91eff46652a7c89eadf7c854c147f99cca16ec`
- `data/1999_synthetic/taxonomy/current/taxonomy_v1.3_dataset_v2.yaml` `fbbbb7a945ecd0bebe23f7bfddc0e16f8b4c70fdfe21edb4acdf6772531db96c`
- `data/1999_synthetic/taxonomy/current/formal_split_manifest_frozen_v1.0.yaml` `d60f97f9948da568fbdf9ff00953f088ddbc117ce99ed64ebc10a00b4cad87fb`

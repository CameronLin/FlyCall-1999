# Classification evaluation report

- Status: `smoke_test/provisional`
- Data: `synthetic`
- Review status: `pending_manual_review`
- Candidate: `mlp`
- Confusion matrix orientation: rows = actual; columns = predicted.

## train

- Status: `evaluated`
- Records: 700
- Accuracy: 0.991429
- Macro-F1: 0.991427

### Per-class metrics

| Label | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| sidewalk_maintenance | 1.000000 | 0.985714 | 0.992806 | 140 |
| road_surface_defect | 0.972222 | 1.000000 | 0.985915 | 140 |
| park_general_maintenance | 0.985915 | 1.000000 | 0.992908 | 140 |
| waste_truck_service | 1.000000 | 1.000000 | 1.000000 | 140 |
| street_cleaning | 1.000000 | 0.971429 | 0.985507 | 140 |

### Confusion matrix

| Actual \ Predicted | sidewalk_maintenance | road_surface_defect | park_general_maintenance | waste_truck_service | street_cleaning |
|---|---:|---:|---:|---:|---:|
| sidewalk_maintenance | 138 | 1 | 1 | 0 | 0 |
| road_surface_defect | 0 | 140 | 0 | 0 | 0 |
| park_general_maintenance | 0 | 0 | 140 | 0 | 0 |
| waste_truck_service | 0 | 0 | 0 | 140 | 0 |
| street_cleaning | 0 | 3 | 1 | 0 | 136 |

### Error record IDs

- `TPE1999-V2-SW-0037`: `sidewalk_maintenance` → `park_general_maintenance`
- `TPE1999-V2-SW-0045`: `sidewalk_maintenance` → `road_surface_defect`
- `TPE1999-V2-SC-0125`: `street_cleaning` → `park_general_maintenance`
- `TPE1999-V2-SC-0137`: `street_cleaning` → `road_surface_defect`
- `TPE1999-V2-SC-0142`: `street_cleaning` → `road_surface_defect`
- `TPE1999-V2-SC-0170`: `street_cleaning` → `road_surface_defect`

## validation

- Status: `evaluated`
- Records: 150
- Accuracy: 0.946667
- Macro-F1: 0.946117

### Per-class metrics

| Label | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| sidewalk_maintenance | 0.925926 | 0.833333 | 0.877193 | 30 |
| road_surface_defect | 0.878788 | 0.966667 | 0.920635 | 30 |
| park_general_maintenance | 0.967742 | 1.000000 | 0.983607 | 30 |
| waste_truck_service | 1.000000 | 1.000000 | 1.000000 | 30 |
| street_cleaning | 0.965517 | 0.933333 | 0.949153 | 30 |

### Confusion matrix

| Actual \ Predicted | sidewalk_maintenance | road_surface_defect | park_general_maintenance | waste_truck_service | street_cleaning |
|---|---:|---:|---:|---:|---:|
| sidewalk_maintenance | 25 | 4 | 0 | 0 | 1 |
| road_surface_defect | 1 | 29 | 0 | 0 | 0 |
| park_general_maintenance | 0 | 0 | 30 | 0 | 0 |
| waste_truck_service | 0 | 0 | 0 | 30 | 0 |
| street_cleaning | 1 | 0 | 1 | 0 | 28 |

### Error record IDs

- `TPE1999-V2-SW-0173`: `sidewalk_maintenance` → `road_surface_defect`
- `TPE1999-V2-SW-0176`: `sidewalk_maintenance` → `road_surface_defect`
- `TPE1999-V2-SW-0178`: `sidewalk_maintenance` → `street_cleaning`
- `TPE1999-V2-SW-0187`: `sidewalk_maintenance` → `road_surface_defect`
- `TPE1999-V2-SW-0195`: `sidewalk_maintenance` → `road_surface_defect`
- `TPE1999-V2-RD-0194`: `road_surface_defect` → `sidewalk_maintenance`
- `TPE1999-V2-SC-0181`: `street_cleaning` → `sidewalk_maintenance`
- `TPE1999-V2-SC-0185`: `street_cleaning` → `park_general_maintenance`

## test

- Status: `not_run`

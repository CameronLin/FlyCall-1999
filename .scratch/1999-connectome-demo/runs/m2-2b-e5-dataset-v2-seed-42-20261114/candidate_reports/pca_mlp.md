# Classification evaluation report

- Status: `smoke_test/provisional`
- Data: `synthetic`
- Review status: `pending_manual_review`
- Candidate: `pca_mlp`
- Confusion matrix orientation: rows = actual; columns = predicted.

## train

- Status: `evaluated`
- Records: 700
- Accuracy: 0.982857
- Macro-F1: 0.982820

### Per-class metrics

| Label | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| sidewalk_maintenance | 0.978571 | 0.978571 | 0.978571 | 140 |
| road_surface_defect | 0.972028 | 0.992857 | 0.982332 | 140 |
| park_general_maintenance | 0.985816 | 0.992857 | 0.989324 | 140 |
| waste_truck_service | 0.992857 | 0.992857 | 0.992857 | 140 |
| street_cleaning | 0.985294 | 0.957143 | 0.971014 | 140 |

### Confusion matrix

| Actual \ Predicted | sidewalk_maintenance | road_surface_defect | park_general_maintenance | waste_truck_service | street_cleaning |
|---|---:|---:|---:|---:|---:|
| sidewalk_maintenance | 137 | 1 | 2 | 0 | 0 |
| road_surface_defect | 1 | 139 | 0 | 0 | 0 |
| park_general_maintenance | 0 | 0 | 139 | 0 | 1 |
| waste_truck_service | 0 | 0 | 0 | 139 | 1 |
| street_cleaning | 2 | 3 | 0 | 1 | 134 |

### Error record IDs

- `TPE1999-V2-SW-0037`: `sidewalk_maintenance` → `park_general_maintenance`
- `TPE1999-V2-SW-0045`: `sidewalk_maintenance` → `road_surface_defect`
- `TPE1999-V2-SW-0117`: `sidewalk_maintenance` → `park_general_maintenance`
- `TPE1999-V2-RD-0036`: `road_surface_defect` → `sidewalk_maintenance`
- `TPE1999-V2-PK-0072`: `park_general_maintenance` → `street_cleaning`
- `TPE1999-V2-WT-0090`: `waste_truck_service` → `street_cleaning`
- `TPE1999-V2-SC-0137`: `street_cleaning` → `road_surface_defect`
- `TPE1999-V2-SC-0142`: `street_cleaning` → `road_surface_defect`
- `TPE1999-V2-SC-0159`: `street_cleaning` → `sidewalk_maintenance`
- `TPE1999-V2-SC-0160`: `street_cleaning` → `waste_truck_service`
- `TPE1999-V2-SC-0165`: `street_cleaning` → `sidewalk_maintenance`
- `TPE1999-V2-SC-0170`: `street_cleaning` → `road_surface_defect`

## validation

- Status: `evaluated`
- Records: 150
- Accuracy: 0.920000
- Macro-F1: 0.920097

### Per-class metrics

| Label | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| sidewalk_maintenance | 0.806452 | 0.833333 | 0.819672 | 30 |
| road_surface_defect | 0.882353 | 1.000000 | 0.937500 | 30 |
| park_general_maintenance | 0.962963 | 0.866667 | 0.912281 | 30 |
| waste_truck_service | 1.000000 | 1.000000 | 1.000000 | 30 |
| street_cleaning | 0.964286 | 0.900000 | 0.931034 | 30 |

### Confusion matrix

| Actual \ Predicted | sidewalk_maintenance | road_surface_defect | park_general_maintenance | waste_truck_service | street_cleaning |
|---|---:|---:|---:|---:|---:|
| sidewalk_maintenance | 25 | 4 | 0 | 0 | 1 |
| road_surface_defect | 0 | 30 | 0 | 0 | 0 |
| park_general_maintenance | 4 | 0 | 26 | 0 | 0 |
| waste_truck_service | 0 | 0 | 0 | 30 | 0 |
| street_cleaning | 2 | 0 | 1 | 0 | 27 |

### Error record IDs

- `TPE1999-V2-SW-0178`: `sidewalk_maintenance` → `street_cleaning`
- `TPE1999-V2-SW-0179`: `sidewalk_maintenance` → `road_surface_defect`
- `TPE1999-V2-SW-0187`: `sidewalk_maintenance` → `road_surface_defect`
- `TPE1999-V2-SW-0194`: `sidewalk_maintenance` → `road_surface_defect`
- `TPE1999-V2-SW-0195`: `sidewalk_maintenance` → `road_surface_defect`
- `TPE1999-V2-PK-0172`: `park_general_maintenance` → `sidewalk_maintenance`
- `TPE1999-V2-PK-0180`: `park_general_maintenance` → `sidewalk_maintenance`
- `TPE1999-V2-PK-0183`: `park_general_maintenance` → `sidewalk_maintenance`
- `TPE1999-V2-PK-0186`: `park_general_maintenance` → `sidewalk_maintenance`
- `TPE1999-V2-SC-0181`: `street_cleaning` → `sidewalk_maintenance`
- `TPE1999-V2-SC-0182`: `street_cleaning` → `sidewalk_maintenance`
- `TPE1999-V2-SC-0185`: `street_cleaning` → `park_general_maintenance`

## test

- Status: `not_run`

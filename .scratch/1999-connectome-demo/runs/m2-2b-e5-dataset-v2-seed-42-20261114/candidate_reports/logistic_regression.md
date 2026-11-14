# Classification evaluation report

- Status: `smoke_test/provisional`
- Data: `synthetic`
- Review status: `pending_manual_review`
- Candidate: `logistic_regression`
- Confusion matrix orientation: rows = actual; columns = predicted.

## train

- Status: `evaluated`
- Records: 700
- Accuracy: 0.981429
- Macro-F1: 0.981400

### Per-class metrics

| Label | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| sidewalk_maintenance | 0.992754 | 0.978571 | 0.985612 | 140 |
| road_surface_defect | 0.952381 | 1.000000 | 0.975610 | 140 |
| park_general_maintenance | 0.972028 | 0.992857 | 0.982332 | 140 |
| waste_truck_service | 1.000000 | 0.992857 | 0.996416 | 140 |
| street_cleaning | 0.992481 | 0.942857 | 0.967033 | 140 |

### Confusion matrix

| Actual \ Predicted | sidewalk_maintenance | road_surface_defect | park_general_maintenance | waste_truck_service | street_cleaning |
|---|---:|---:|---:|---:|---:|
| sidewalk_maintenance | 137 | 2 | 1 | 0 | 0 |
| road_surface_defect | 0 | 140 | 0 | 0 | 0 |
| park_general_maintenance | 0 | 1 | 139 | 0 | 0 |
| waste_truck_service | 0 | 0 | 0 | 139 | 1 |
| street_cleaning | 1 | 4 | 3 | 0 | 132 |

### Error record IDs

- `TPE1999-V2-SW-0037`: `sidewalk_maintenance` → `park_general_maintenance`
- `TPE1999-V2-SW-0045`: `sidewalk_maintenance` → `road_surface_defect`
- `TPE1999-V2-SW-0162`: `sidewalk_maintenance` → `road_surface_defect`
- `TPE1999-V2-PK-0163`: `park_general_maintenance` → `road_surface_defect`
- `TPE1999-V2-WT-0090`: `waste_truck_service` → `street_cleaning`
- `TPE1999-V2-SC-0125`: `street_cleaning` → `park_general_maintenance`
- `TPE1999-V2-SC-0126`: `street_cleaning` → `park_general_maintenance`
- `TPE1999-V2-SC-0137`: `street_cleaning` → `road_surface_defect`
- `TPE1999-V2-SC-0142`: `street_cleaning` → `road_surface_defect`
- `TPE1999-V2-SC-0147`: `street_cleaning` → `road_surface_defect`
- `TPE1999-V2-SC-0153`: `street_cleaning` → `sidewalk_maintenance`
- `TPE1999-V2-SC-0166`: `street_cleaning` → `park_general_maintenance`
- `TPE1999-V2-SC-0170`: `street_cleaning` → `road_surface_defect`

## validation

- Status: `evaluated`
- Records: 150
- Accuracy: 0.953333
- Macro-F1: 0.952927

### Per-class metrics

| Label | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| sidewalk_maintenance | 1.000000 | 0.800000 | 0.888889 | 30 |
| road_surface_defect | 0.833333 | 1.000000 | 0.909091 | 30 |
| park_general_maintenance | 0.967742 | 1.000000 | 0.983607 | 30 |
| waste_truck_service | 1.000000 | 1.000000 | 1.000000 | 30 |
| street_cleaning | 1.000000 | 0.966667 | 0.983051 | 30 |

### Confusion matrix

| Actual \ Predicted | sidewalk_maintenance | road_surface_defect | park_general_maintenance | waste_truck_service | street_cleaning |
|---|---:|---:|---:|---:|---:|
| sidewalk_maintenance | 24 | 6 | 0 | 0 | 0 |
| road_surface_defect | 0 | 30 | 0 | 0 | 0 |
| park_general_maintenance | 0 | 0 | 30 | 0 | 0 |
| waste_truck_service | 0 | 0 | 0 | 30 | 0 |
| street_cleaning | 0 | 0 | 1 | 0 | 29 |

### Error record IDs

- `TPE1999-V2-SW-0176`: `sidewalk_maintenance` → `road_surface_defect`
- `TPE1999-V2-SW-0178`: `sidewalk_maintenance` → `road_surface_defect`
- `TPE1999-V2-SW-0186`: `sidewalk_maintenance` → `road_surface_defect`
- `TPE1999-V2-SW-0194`: `sidewalk_maintenance` → `road_surface_defect`
- `TPE1999-V2-SW-0195`: `sidewalk_maintenance` → `road_surface_defect`
- `TPE1999-V2-SW-0200`: `sidewalk_maintenance` → `road_surface_defect`
- `TPE1999-V2-SC-0185`: `street_cleaning` → `park_general_maintenance`

## test

- Status: `not_run`

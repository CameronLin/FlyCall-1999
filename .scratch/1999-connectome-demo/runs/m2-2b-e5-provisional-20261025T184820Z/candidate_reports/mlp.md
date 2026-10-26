# Classification evaluation report

- Status: `smoke_test/provisional`
- Data: `synthetic`
- Review status: `pending_manual_review`
- Candidate: `mlp`
- Confusion matrix orientation: rows = actual; columns = predicted.

## train

- Status: `evaluated`
- Records: 700
- Accuracy: 0.998571
- Macro-F1: 0.998571

### Per-class metrics

| Label | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| sidewalk_maintenance | 1.000000 | 0.992857 | 0.996416 | 140 |
| road_surface_defect | 1.000000 | 1.000000 | 1.000000 | 140 |
| park_general_maintenance | 1.000000 | 1.000000 | 1.000000 | 140 |
| waste_truck_service | 1.000000 | 1.000000 | 1.000000 | 140 |
| street_cleaning | 0.992908 | 1.000000 | 0.996441 | 140 |

### Confusion matrix

| Actual \ Predicted | sidewalk_maintenance | road_surface_defect | park_general_maintenance | waste_truck_service | street_cleaning |
|---|---:|---:|---:|---:|---:|
| sidewalk_maintenance | 139 | 0 | 0 | 0 | 1 |
| road_surface_defect | 0 | 140 | 0 | 0 | 0 |
| park_general_maintenance | 0 | 0 | 140 | 0 | 0 |
| waste_truck_service | 0 | 0 | 0 | 140 | 0 |
| street_cleaning | 0 | 0 | 0 | 0 | 140 |

### Error record IDs

- `TPE1999-FORMAL-SW-0108`: `sidewalk_maintenance` → `street_cleaning`

## validation

- Status: `evaluated`
- Records: 150
- Accuracy: 0.920000
- Macro-F1: 0.918150

### Per-class metrics

| Label | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| sidewalk_maintenance | 0.884615 | 0.766667 | 0.821429 | 30 |
| road_surface_defect | 0.909091 | 1.000000 | 0.952381 | 30 |
| park_general_maintenance | 0.967742 | 1.000000 | 0.983607 | 30 |
| waste_truck_service | 1.000000 | 1.000000 | 1.000000 | 30 |
| street_cleaning | 0.833333 | 0.833333 | 0.833333 | 30 |

### Confusion matrix

| Actual \ Predicted | sidewalk_maintenance | road_surface_defect | park_general_maintenance | waste_truck_service | street_cleaning |
|---|---:|---:|---:|---:|---:|
| sidewalk_maintenance | 23 | 2 | 0 | 0 | 5 |
| road_surface_defect | 0 | 30 | 0 | 0 | 0 |
| park_general_maintenance | 0 | 0 | 30 | 0 | 0 |
| waste_truck_service | 0 | 0 | 0 | 30 | 0 |
| street_cleaning | 3 | 1 | 1 | 0 | 25 |

### Error record IDs

- `TPE1999-FORMAL-SW-0071`: `sidewalk_maintenance` → `road_surface_defect`
- `TPE1999-FORMAL-SW-0080`: `sidewalk_maintenance` → `street_cleaning`
- `TPE1999-FORMAL-SW-0083`: `sidewalk_maintenance` → `street_cleaning`
- `TPE1999-FORMAL-SW-0088`: `sidewalk_maintenance` → `street_cleaning`
- `TPE1999-FORMAL-SW-0171`: `sidewalk_maintenance` → `street_cleaning`
- `TPE1999-FORMAL-SW-0177`: `sidewalk_maintenance` → `road_surface_defect`
- `TPE1999-FORMAL-SW-0180`: `sidewalk_maintenance` → `street_cleaning`
- `TPE1999-FORMAL-SC-0106`: `street_cleaning` → `road_surface_defect`
- `TPE1999-FORMAL-SC-0112`: `street_cleaning` → `sidewalk_maintenance`
- `TPE1999-FORMAL-SC-0115`: `street_cleaning` → `sidewalk_maintenance`
- `TPE1999-FORMAL-SC-0174`: `street_cleaning` → `park_general_maintenance`
- `TPE1999-FORMAL-SC-0199`: `street_cleaning` → `sidewalk_maintenance`

## test

- Status: `not_run`

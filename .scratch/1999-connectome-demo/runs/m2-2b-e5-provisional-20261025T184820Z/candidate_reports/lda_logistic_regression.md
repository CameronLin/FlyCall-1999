# Classification evaluation report

- Status: `smoke_test/provisional`
- Data: `synthetic`
- Review status: `pending_manual_review`
- Candidate: `lda_logistic_regression`
- Confusion matrix orientation: rows = actual; columns = predicted.

## train

- Status: `evaluated`
- Records: 700
- Accuracy: 1.000000
- Macro-F1: 1.000000

### Per-class metrics

| Label | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| sidewalk_maintenance | 1.000000 | 1.000000 | 1.000000 | 140 |
| road_surface_defect | 1.000000 | 1.000000 | 1.000000 | 140 |
| park_general_maintenance | 1.000000 | 1.000000 | 1.000000 | 140 |
| waste_truck_service | 1.000000 | 1.000000 | 1.000000 | 140 |
| street_cleaning | 1.000000 | 1.000000 | 1.000000 | 140 |

### Confusion matrix

| Actual \ Predicted | sidewalk_maintenance | road_surface_defect | park_general_maintenance | waste_truck_service | street_cleaning |
|---|---:|---:|---:|---:|---:|
| sidewalk_maintenance | 140 | 0 | 0 | 0 | 0 |
| road_surface_defect | 0 | 140 | 0 | 0 | 0 |
| park_general_maintenance | 0 | 0 | 140 | 0 | 0 |
| waste_truck_service | 0 | 0 | 0 | 140 | 0 |
| street_cleaning | 0 | 0 | 0 | 0 | 140 |

### Error record IDs

- None

## validation

- Status: `evaluated`
- Records: 150
- Accuracy: 0.900000
- Macro-F1: 0.899802

### Per-class metrics

| Label | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| sidewalk_maintenance | 0.852941 | 0.966667 | 0.906250 | 30 |
| road_surface_defect | 0.714286 | 0.833333 | 0.769231 | 30 |
| park_general_maintenance | 1.000000 | 1.000000 | 1.000000 | 30 |
| waste_truck_service | 1.000000 | 1.000000 | 1.000000 | 30 |
| street_cleaning | 1.000000 | 0.700000 | 0.823529 | 30 |

### Confusion matrix

| Actual \ Predicted | sidewalk_maintenance | road_surface_defect | park_general_maintenance | waste_truck_service | street_cleaning |
|---|---:|---:|---:|---:|---:|
| sidewalk_maintenance | 29 | 1 | 0 | 0 | 0 |
| road_surface_defect | 5 | 25 | 0 | 0 | 0 |
| park_general_maintenance | 0 | 0 | 30 | 0 | 0 |
| waste_truck_service | 0 | 0 | 0 | 30 | 0 |
| street_cleaning | 0 | 9 | 0 | 0 | 21 |

### Error record IDs

- `TPE1999-FORMAL-SW-0071`: `sidewalk_maintenance` → `road_surface_defect`
- `TPE1999-FORMAL-RD-0042`: `road_surface_defect` → `sidewalk_maintenance`
- `TPE1999-FORMAL-RD-0045`: `road_surface_defect` → `sidewalk_maintenance`
- `TPE1999-FORMAL-RD-0185`: `road_surface_defect` → `sidewalk_maintenance`
- `TPE1999-FORMAL-RD-0188`: `road_surface_defect` → `sidewalk_maintenance`
- `TPE1999-FORMAL-RD-0191`: `road_surface_defect` → `sidewalk_maintenance`
- `TPE1999-FORMAL-SC-0106`: `street_cleaning` → `road_surface_defect`
- `TPE1999-FORMAL-SC-0107`: `street_cleaning` → `road_surface_defect`
- `TPE1999-FORMAL-SC-0108`: `street_cleaning` → `road_surface_defect`
- `TPE1999-FORMAL-SC-0109`: `street_cleaning` → `road_surface_defect`
- `TPE1999-FORMAL-SC-0110`: `street_cleaning` → `road_surface_defect`
- `TPE1999-FORMAL-SC-0112`: `street_cleaning` → `road_surface_defect`
- `TPE1999-FORMAL-SC-0113`: `street_cleaning` → `road_surface_defect`
- `TPE1999-FORMAL-SC-0114`: `street_cleaning` → `road_surface_defect`
- `TPE1999-FORMAL-SC-0115`: `street_cleaning` → `road_surface_defect`

## test

- Status: `not_run`

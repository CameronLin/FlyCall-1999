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
- Accuracy: 0.906667
- Macro-F1: 0.906767

### Per-class metrics

| Label | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| sidewalk_maintenance | 0.800000 | 0.800000 | 0.800000 | 30 |
| road_surface_defect | 0.852941 | 0.966667 | 0.906250 | 30 |
| park_general_maintenance | 0.964286 | 0.900000 | 0.931034 | 30 |
| waste_truck_service | 1.000000 | 1.000000 | 1.000000 | 30 |
| street_cleaning | 0.928571 | 0.866667 | 0.896552 | 30 |

### Confusion matrix

| Actual \ Predicted | sidewalk_maintenance | road_surface_defect | park_general_maintenance | waste_truck_service | street_cleaning |
|---|---:|---:|---:|---:|---:|
| sidewalk_maintenance | 24 | 5 | 0 | 0 | 1 |
| road_surface_defect | 1 | 29 | 0 | 0 | 0 |
| park_general_maintenance | 2 | 0 | 27 | 0 | 1 |
| waste_truck_service | 0 | 0 | 0 | 30 | 0 |
| street_cleaning | 3 | 0 | 1 | 0 | 26 |

### Error record IDs

- `TPE1999-V2-SW-0172`: `sidewalk_maintenance` → `road_surface_defect`
- `TPE1999-V2-SW-0173`: `sidewalk_maintenance` → `road_surface_defect`
- `TPE1999-V2-SW-0176`: `sidewalk_maintenance` → `road_surface_defect`
- `TPE1999-V2-SW-0177`: `sidewalk_maintenance` → `street_cleaning`
- `TPE1999-V2-SW-0183`: `sidewalk_maintenance` → `road_surface_defect`
- `TPE1999-V2-SW-0200`: `sidewalk_maintenance` → `road_surface_defect`
- `TPE1999-V2-RD-0197`: `road_surface_defect` → `sidewalk_maintenance`
- `TPE1999-V2-PK-0172`: `park_general_maintenance` → `sidewalk_maintenance`
- `TPE1999-V2-PK-0183`: `park_general_maintenance` → `street_cleaning`
- `TPE1999-V2-PK-0186`: `park_general_maintenance` → `sidewalk_maintenance`
- `TPE1999-V2-SC-0175`: `street_cleaning` → `park_general_maintenance`
- `TPE1999-V2-SC-0177`: `street_cleaning` → `sidewalk_maintenance`
- `TPE1999-V2-SC-0178`: `street_cleaning` → `sidewalk_maintenance`
- `TPE1999-V2-SC-0199`: `street_cleaning` → `sidewalk_maintenance`

## test

- Status: `not_run`

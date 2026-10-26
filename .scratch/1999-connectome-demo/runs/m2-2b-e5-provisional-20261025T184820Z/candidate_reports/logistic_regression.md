# Classification evaluation report

- Status: `smoke_test/provisional`
- Data: `synthetic`
- Review status: `pending_manual_review`
- Candidate: `logistic_regression`
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
- Accuracy: 0.873333
- Macro-F1: 0.867795

### Per-class metrics

| Label | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| sidewalk_maintenance | 0.814815 | 0.733333 | 0.771930 | 30 |
| road_surface_defect | 0.769231 | 1.000000 | 0.869565 | 30 |
| park_general_maintenance | 0.909091 | 1.000000 | 0.952381 | 30 |
| waste_truck_service | 1.000000 | 1.000000 | 1.000000 | 30 |
| street_cleaning | 0.904762 | 0.633333 | 0.745098 | 30 |

### Confusion matrix

| Actual \ Predicted | sidewalk_maintenance | road_surface_defect | park_general_maintenance | waste_truck_service | street_cleaning |
|---|---:|---:|---:|---:|---:|
| sidewalk_maintenance | 22 | 6 | 0 | 0 | 2 |
| road_surface_defect | 0 | 30 | 0 | 0 | 0 |
| park_general_maintenance | 0 | 0 | 30 | 0 | 0 |
| waste_truck_service | 0 | 0 | 0 | 30 | 0 |
| street_cleaning | 5 | 3 | 3 | 0 | 19 |

### Error record IDs

- `TPE1999-FORMAL-SW-0071`: `sidewalk_maintenance` → `road_surface_defect`
- `TPE1999-FORMAL-SW-0074`: `sidewalk_maintenance` → `road_surface_defect`
- `TPE1999-FORMAL-SW-0077`: `sidewalk_maintenance` → `road_surface_defect`
- `TPE1999-FORMAL-SW-0080`: `sidewalk_maintenance` → `street_cleaning`
- `TPE1999-FORMAL-SW-0083`: `sidewalk_maintenance` → `street_cleaning`
- `TPE1999-FORMAL-SW-0171`: `sidewalk_maintenance` → `road_surface_defect`
- `TPE1999-FORMAL-SW-0177`: `sidewalk_maintenance` → `road_surface_defect`
- `TPE1999-FORMAL-SW-0180`: `sidewalk_maintenance` → `road_surface_defect`
- `TPE1999-FORMAL-SC-0106`: `street_cleaning` → `road_surface_defect`
- `TPE1999-FORMAL-SC-0107`: `street_cleaning` → `road_surface_defect`
- `TPE1999-FORMAL-SC-0109`: `street_cleaning` → `sidewalk_maintenance`
- `TPE1999-FORMAL-SC-0112`: `street_cleaning` → `road_surface_defect`
- `TPE1999-FORMAL-SC-0113`: `street_cleaning` → `sidewalk_maintenance`
- `TPE1999-FORMAL-SC-0115`: `street_cleaning` → `sidewalk_maintenance`
- `TPE1999-FORMAL-SC-0168`: `street_cleaning` → `park_general_maintenance`
- `TPE1999-FORMAL-SC-0171`: `street_cleaning` → `park_general_maintenance`
- `TPE1999-FORMAL-SC-0174`: `street_cleaning` → `park_general_maintenance`
- `TPE1999-FORMAL-SC-0193`: `street_cleaning` → `sidewalk_maintenance`
- `TPE1999-FORMAL-SC-0199`: `street_cleaning` → `sidewalk_maintenance`

## test

- Status: `not_run`

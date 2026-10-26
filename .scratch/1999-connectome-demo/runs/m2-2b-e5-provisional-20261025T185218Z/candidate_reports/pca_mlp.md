# Classification evaluation report

- Status: `smoke_test/provisional`
- Data: `synthetic`
- Review status: `pending_manual_review`
- Candidate: `pca_mlp`
- Confusion matrix orientation: rows = actual; columns = predicted.

## train

- Status: `evaluated`
- Records: 700
- Accuracy: 0.997143
- Macro-F1: 0.997143

### Per-class metrics

| Label | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| sidewalk_maintenance | 1.000000 | 0.985714 | 0.992806 | 140 |
| road_surface_defect | 1.000000 | 1.000000 | 1.000000 | 140 |
| park_general_maintenance | 1.000000 | 1.000000 | 1.000000 | 140 |
| waste_truck_service | 1.000000 | 1.000000 | 1.000000 | 140 |
| street_cleaning | 0.985915 | 1.000000 | 0.992908 | 140 |

### Confusion matrix

| Actual \ Predicted | sidewalk_maintenance | road_surface_defect | park_general_maintenance | waste_truck_service | street_cleaning |
|---|---:|---:|---:|---:|---:|
| sidewalk_maintenance | 138 | 0 | 0 | 0 | 2 |
| road_surface_defect | 0 | 140 | 0 | 0 | 0 |
| park_general_maintenance | 0 | 0 | 140 | 0 | 0 |
| waste_truck_service | 0 | 0 | 0 | 140 | 0 |
| street_cleaning | 0 | 0 | 0 | 0 | 140 |

### Error record IDs

- `TPE1999-FORMAL-SW-0096`: `sidewalk_maintenance` → `street_cleaning`
- `TPE1999-FORMAL-SW-0124`: `sidewalk_maintenance` → `street_cleaning`

## validation

- Status: `evaluated`
- Records: 150
- Accuracy: 0.906667
- Macro-F1: 0.905503

### Per-class metrics

| Label | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| sidewalk_maintenance | 0.781250 | 0.833333 | 0.806452 | 30 |
| road_surface_defect | 0.852941 | 0.966667 | 0.906250 | 30 |
| park_general_maintenance | 1.000000 | 1.000000 | 1.000000 | 30 |
| waste_truck_service | 1.000000 | 1.000000 | 1.000000 | 30 |
| street_cleaning | 0.916667 | 0.733333 | 0.814815 | 30 |

### Confusion matrix

| Actual \ Predicted | sidewalk_maintenance | road_surface_defect | park_general_maintenance | waste_truck_service | street_cleaning |
|---|---:|---:|---:|---:|---:|
| sidewalk_maintenance | 25 | 3 | 0 | 0 | 2 |
| road_surface_defect | 1 | 29 | 0 | 0 | 0 |
| park_general_maintenance | 0 | 0 | 30 | 0 | 0 |
| waste_truck_service | 0 | 0 | 0 | 30 | 0 |
| street_cleaning | 6 | 2 | 0 | 0 | 22 |

### Error record IDs

- `TPE1999-FORMAL-SW-0071`: `sidewalk_maintenance` → `road_surface_defect`
- `TPE1999-FORMAL-SW-0077`: `sidewalk_maintenance` → `road_surface_defect`
- `TPE1999-FORMAL-SW-0083`: `sidewalk_maintenance` → `street_cleaning`
- `TPE1999-FORMAL-SW-0174`: `sidewalk_maintenance` → `street_cleaning`
- `TPE1999-FORMAL-SW-0177`: `sidewalk_maintenance` → `road_surface_defect`
- `TPE1999-FORMAL-RD-0191`: `road_surface_defect` → `sidewalk_maintenance`
- `TPE1999-FORMAL-SC-0106`: `street_cleaning` → `road_surface_defect`
- `TPE1999-FORMAL-SC-0107`: `street_cleaning` → `sidewalk_maintenance`
- `TPE1999-FORMAL-SC-0110`: `street_cleaning` → `road_surface_defect`
- `TPE1999-FORMAL-SC-0113`: `street_cleaning` → `sidewalk_maintenance`
- `TPE1999-FORMAL-SC-0114`: `street_cleaning` → `sidewalk_maintenance`
- `TPE1999-FORMAL-SC-0171`: `street_cleaning` → `sidewalk_maintenance`
- `TPE1999-FORMAL-SC-0174`: `street_cleaning` → `sidewalk_maintenance`
- `TPE1999-FORMAL-SC-0196`: `street_cleaning` → `sidewalk_maintenance`

## test

- Status: `not_run`

# Classification evaluation report

- Status: `smoke_test/provisional`
- Data: `synthetic`
- Review status: `pending_manual_review`
- Candidate: `mlp`
- Confusion matrix orientation: rows = actual; columns = predicted.

## train

- Status: `evaluated`
- Records: 700
- Accuracy: 0.997143
- Macro-F1: 0.997143

### Per-class metrics

| Label | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| sidewalk_maintenance | 0.992857 | 0.992857 | 0.992857 | 140 |
| road_surface_defect | 0.992908 | 1.000000 | 0.996441 | 140 |
| park_general_maintenance | 1.000000 | 1.000000 | 1.000000 | 140 |
| waste_truck_service | 1.000000 | 0.992857 | 0.996416 | 140 |
| street_cleaning | 1.000000 | 1.000000 | 1.000000 | 140 |

### Confusion matrix

| Actual \ Predicted | sidewalk_maintenance | road_surface_defect | park_general_maintenance | waste_truck_service | street_cleaning |
|---|---:|---:|---:|---:|---:|
| sidewalk_maintenance | 139 | 1 | 0 | 0 | 0 |
| road_surface_defect | 0 | 140 | 0 | 0 | 0 |
| park_general_maintenance | 0 | 0 | 140 | 0 | 0 |
| waste_truck_service | 1 | 0 | 0 | 139 | 0 |
| street_cleaning | 0 | 0 | 0 | 0 | 140 |

### Error record IDs

- `TPE1999-FORMAL-SW-0049`: `sidewalk_maintenance` → `road_surface_defect`
- `TPE1999-FORMAL-WT-0051`: `waste_truck_service` → `sidewalk_maintenance`

## validation

- Status: `evaluated`
- Records: 150
- Accuracy: 0.880000
- Macro-F1: 0.870568

### Per-class metrics

| Label | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| sidewalk_maintenance | 0.681818 | 1.000000 | 0.810811 | 30 |
| road_surface_defect | 1.000000 | 1.000000 | 1.000000 | 30 |
| park_general_maintenance | 0.933333 | 0.933333 | 0.933333 | 30 |
| waste_truck_service | 1.000000 | 1.000000 | 1.000000 | 30 |
| street_cleaning | 0.875000 | 0.466667 | 0.608696 | 30 |

### Confusion matrix

| Actual \ Predicted | sidewalk_maintenance | road_surface_defect | park_general_maintenance | waste_truck_service | street_cleaning |
|---|---:|---:|---:|---:|---:|
| sidewalk_maintenance | 30 | 0 | 0 | 0 | 0 |
| road_surface_defect | 0 | 30 | 0 | 0 | 0 |
| park_general_maintenance | 0 | 0 | 28 | 0 | 2 |
| waste_truck_service | 0 | 0 | 0 | 30 | 0 |
| street_cleaning | 14 | 0 | 2 | 0 | 14 |

### Error record IDs

- `TPE1999-FORMAL-PK-0136`: `park_general_maintenance` → `street_cleaning`
- `TPE1999-FORMAL-PK-0143`: `park_general_maintenance` → `street_cleaning`
- `TPE1999-FORMAL-SC-0106`: `street_cleaning` → `sidewalk_maintenance`
- `TPE1999-FORMAL-SC-0107`: `street_cleaning` → `sidewalk_maintenance`
- `TPE1999-FORMAL-SC-0109`: `street_cleaning` → `sidewalk_maintenance`
- `TPE1999-FORMAL-SC-0110`: `street_cleaning` → `sidewalk_maintenance`
- `TPE1999-FORMAL-SC-0112`: `street_cleaning` → `sidewalk_maintenance`
- `TPE1999-FORMAL-SC-0113`: `street_cleaning` → `sidewalk_maintenance`
- `TPE1999-FORMAL-SC-0114`: `street_cleaning` → `sidewalk_maintenance`
- `TPE1999-FORMAL-SC-0115`: `street_cleaning` → `sidewalk_maintenance`
- `TPE1999-FORMAL-SC-0171`: `street_cleaning` → `park_general_maintenance`
- `TPE1999-FORMAL-SC-0174`: `street_cleaning` → `park_general_maintenance`
- `TPE1999-FORMAL-SC-0191`: `street_cleaning` → `sidewalk_maintenance`
- `TPE1999-FORMAL-SC-0193`: `street_cleaning` → `sidewalk_maintenance`
- `TPE1999-FORMAL-SC-0196`: `street_cleaning` → `sidewalk_maintenance`
- `TPE1999-FORMAL-SC-0197`: `street_cleaning` → `sidewalk_maintenance`
- `TPE1999-FORMAL-SC-0199`: `street_cleaning` → `sidewalk_maintenance`
- `TPE1999-FORMAL-SC-0200`: `street_cleaning` → `sidewalk_maintenance`

## test

- Status: `not_run`

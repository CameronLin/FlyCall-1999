# Classification evaluation report

- Status: `smoke_test/provisional`
- Data: `synthetic`
- Review status: `pending_manual_review`
- Candidate: `pca_mlp`
- Confusion matrix orientation: rows = actual; columns = predicted.

## train

- Status: `evaluated`
- Records: 700
- Accuracy: 0.994286
- Macro-F1: 0.994275

### Per-class metrics

| Label | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| sidewalk_maintenance | 0.992754 | 0.978571 | 0.985612 | 140 |
| road_surface_defect | 0.992908 | 1.000000 | 0.996441 | 140 |
| park_general_maintenance | 1.000000 | 0.992857 | 0.996416 | 140 |
| waste_truck_service | 1.000000 | 1.000000 | 1.000000 | 140 |
| street_cleaning | 0.985915 | 1.000000 | 0.992908 | 140 |

### Confusion matrix

| Actual \ Predicted | sidewalk_maintenance | road_surface_defect | park_general_maintenance | waste_truck_service | street_cleaning |
|---|---:|---:|---:|---:|---:|
| sidewalk_maintenance | 137 | 1 | 0 | 0 | 2 |
| road_surface_defect | 0 | 140 | 0 | 0 | 0 |
| park_general_maintenance | 1 | 0 | 139 | 0 | 0 |
| waste_truck_service | 0 | 0 | 0 | 140 | 0 |
| street_cleaning | 0 | 0 | 0 | 0 | 140 |

### Error record IDs

- `TPE1999-FORMAL-SW-0096`: `sidewalk_maintenance` → `street_cleaning`
- `TPE1999-FORMAL-SW-0108`: `sidewalk_maintenance` → `road_surface_defect`
- `TPE1999-FORMAL-SW-0186`: `sidewalk_maintenance` → `street_cleaning`
- `TPE1999-FORMAL-PK-0012`: `park_general_maintenance` → `sidewalk_maintenance`

## validation

- Status: `evaluated`
- Records: 150
- Accuracy: 0.880000
- Macro-F1: 0.878740

### Per-class metrics

| Label | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| sidewalk_maintenance | 0.727273 | 0.800000 | 0.761905 | 30 |
| road_surface_defect | 0.875000 | 0.933333 | 0.903226 | 30 |
| park_general_maintenance | 1.000000 | 0.966667 | 0.983051 | 30 |
| waste_truck_service | 0.937500 | 1.000000 | 0.967742 | 30 |
| street_cleaning | 0.875000 | 0.700000 | 0.777778 | 30 |

### Confusion matrix

| Actual \ Predicted | sidewalk_maintenance | road_surface_defect | park_general_maintenance | waste_truck_service | street_cleaning |
|---|---:|---:|---:|---:|---:|
| sidewalk_maintenance | 24 | 2 | 0 | 1 | 3 |
| road_surface_defect | 2 | 28 | 0 | 0 | 0 |
| park_general_maintenance | 1 | 0 | 29 | 0 | 0 |
| waste_truck_service | 0 | 0 | 0 | 30 | 0 |
| street_cleaning | 6 | 2 | 0 | 1 | 21 |

### Error record IDs

- `TPE1999-FORMAL-SW-0071`: `sidewalk_maintenance` → `waste_truck_service`
- `TPE1999-FORMAL-SW-0077`: `sidewalk_maintenance` → `road_surface_defect`
- `TPE1999-FORMAL-SW-0080`: `sidewalk_maintenance` → `street_cleaning`
- `TPE1999-FORMAL-SW-0083`: `sidewalk_maintenance` → `street_cleaning`
- `TPE1999-FORMAL-SW-0174`: `sidewalk_maintenance` → `street_cleaning`
- `TPE1999-FORMAL-SW-0177`: `sidewalk_maintenance` → `road_surface_defect`
- `TPE1999-FORMAL-RD-0049`: `road_surface_defect` → `sidewalk_maintenance`
- `TPE1999-FORMAL-RD-0191`: `road_surface_defect` → `sidewalk_maintenance`
- `TPE1999-FORMAL-PK-0136`: `park_general_maintenance` → `sidewalk_maintenance`
- `TPE1999-FORMAL-SC-0106`: `street_cleaning` → `road_surface_defect`
- `TPE1999-FORMAL-SC-0110`: `street_cleaning` → `road_surface_defect`
- `TPE1999-FORMAL-SC-0111`: `street_cleaning` → `sidewalk_maintenance`
- `TPE1999-FORMAL-SC-0113`: `street_cleaning` → `sidewalk_maintenance`
- `TPE1999-FORMAL-SC-0114`: `street_cleaning` → `sidewalk_maintenance`
- `TPE1999-FORMAL-SC-0171`: `street_cleaning` → `sidewalk_maintenance`
- `TPE1999-FORMAL-SC-0174`: `street_cleaning` → `sidewalk_maintenance`
- `TPE1999-FORMAL-SC-0196`: `street_cleaning` → `sidewalk_maintenance`
- `TPE1999-FORMAL-SC-0199`: `street_cleaning` → `waste_truck_service`

## test

- Status: `not_run`

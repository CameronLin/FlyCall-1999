# M3.2 Fly A/B provisional train-validation run

- Run ID: `m3-2-fly-ab-seed-42-crlf-fix-20261026`
- Status: `completed_provisional`
- Data: synthetic; manual review pending; provisional only.
- Test: `not_run`; no test transcript, embedding, prediction, or metric.

## Selected checkpoints

- Fly A epoch: 17; validation distance stress: 0.00721865.
- Fly B epoch: 100; validation Macro-F1: 0.654127.
- Fly A parameters: {'adapter': 12320, 'graph_core': 2216, 'readout': 0, 'total': 14536}; Fly B parameters: {'adapter': 1056, 'graph_core': 2216, 'readout': 165, 'total': 3437}.
- Checkpoint reload comparison: validation representations/logits match within `1e-6`.

## Classification metrics

### Train (n=700)

Accuracy: 0.7700; Macro-F1: 0.7627.

| Label | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| `sidewalk_maintenance` | 0.6040 | 0.4357 | 0.5062 | 140 |
| `road_surface_defect` | 0.6624 | 0.7429 | 0.7003 | 140 |
| `park_general_maintenance` | 0.8699 | 0.9071 | 0.8881 | 140 |
| `waste_truck_service` | 0.9203 | 0.9071 | 0.9137 | 140 |
| `street_cleaning` | 0.7595 | 0.8571 | 0.8054 | 140 |

Confusion matrix (rows: actual; columns: predicted):

| Actual / Predicted | `sidewalk_maintenance` | `road_surface_defect` | `park_general_maintenance` | `waste_truck_service` | `street_cleaning` |
|---|---:|---:|---:|---:|---:|
| `sidewalk_maintenance` | 61 | 43 | 5 | 1 | 30 |
| `road_surface_defect` | 28 | 104 | 7 | 0 | 1 |
| `park_general_maintenance` | 0 | 10 | 127 | 3 | 0 |
| `waste_truck_service` | 0 | 0 | 6 | 127 | 7 |
| `street_cleaning` | 12 | 0 | 1 | 7 | 120 |

### Validation (n=150)

Accuracy: 0.6733; Macro-F1: 0.6541.

| Label | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| `sidewalk_maintenance` | 0.3704 | 0.3333 | 0.3509 | 30 |
| `road_surface_defect` | 0.4906 | 0.8667 | 0.6265 | 30 |
| `park_general_maintenance` | 0.9310 | 0.9000 | 0.9153 | 30 |
| `waste_truck_service` | 0.9375 | 1.0000 | 0.9677 | 30 |
| `street_cleaning` | 0.8889 | 0.2667 | 0.4103 | 30 |

Confusion matrix (rows: actual; columns: predicted):

| Actual / Predicted | `sidewalk_maintenance` | `road_surface_defect` | `park_general_maintenance` | `waste_truck_service` | `street_cleaning` |
|---|---:|---:|---:|---:|---:|
| `sidewalk_maintenance` | 10 | 18 | 1 | 0 | 1 |
| `road_surface_defect` | 4 | 26 | 0 | 0 | 0 |
| `park_general_maintenance` | 0 | 2 | 27 | 1 | 0 |
| `waste_truck_service` | 0 | 0 | 0 | 30 | 0 |
| `street_cleaning` | 13 | 7 | 1 | 1 | 8 |

Classification details are also saved in `metrics.json`.

## Provenance and limits

See `run_manifest.json` for source hashes, resource readings, timings, dependency versions and locked configuration.

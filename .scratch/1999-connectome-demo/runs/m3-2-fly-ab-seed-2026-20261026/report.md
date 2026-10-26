# M3.2 Fly A/B provisional train-validation run

- Run ID: `m3-2-fly-ab-seed-2026-20261026`
- Status: `completed_provisional`
- Data: synthetic; manual review pending; provisional only.
- Test: `not_run`; no test transcript, embedding, prediction, or metric.

## Selected checkpoints

- Fly A epoch: 10; validation distance stress: 0.00701145.
- Fly B epoch: 57; validation Macro-F1: 0.739337.
- Fly A parameters: {'adapter': 12320, 'graph_core': 2216, 'readout': 0, 'total': 14536}; Fly B parameters: {'adapter': 1056, 'graph_core': 2216, 'readout': 165, 'total': 3437}.
- Checkpoint reload comparison: validation representations/logits match within `1e-6`.

## Classification metrics

### Train (n=700)

Accuracy: 0.8471; Macro-F1: 0.8445.

| Label | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| `sidewalk_maintenance` | 0.7817 | 0.7929 | 0.7872 | 140 |
| `road_surface_defect` | 0.8690 | 0.9000 | 0.8842 | 140 |
| `park_general_maintenance` | 0.8079 | 0.8714 | 0.8385 | 140 |
| `waste_truck_service` | 0.9459 | 1.0000 | 0.9722 | 140 |
| `street_cleaning` | 0.8246 | 0.6714 | 0.7402 | 140 |

Confusion matrix (rows: actual; columns: predicted):

| Actual / Predicted | `sidewalk_maintenance` | `road_surface_defect` | `park_general_maintenance` | `waste_truck_service` | `street_cleaning` |
|---|---:|---:|---:|---:|---:|
| `sidewalk_maintenance` | 111 | 18 | 5 | 1 | 5 |
| `road_surface_defect` | 14 | 126 | 0 | 0 | 0 |
| `park_general_maintenance` | 0 | 0 | 122 | 3 | 15 |
| `waste_truck_service` | 0 | 0 | 0 | 140 | 0 |
| `street_cleaning` | 17 | 1 | 24 | 4 | 94 |

### Validation (n=150)

Accuracy: 0.7867; Macro-F1: 0.7393.

| Label | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| `sidewalk_maintenance` | 0.7500 | 0.9000 | 0.8182 | 30 |
| `road_surface_defect` | 0.6591 | 0.9667 | 0.7838 | 30 |
| `park_general_maintenance` | 0.8485 | 0.9333 | 0.8889 | 30 |
| `waste_truck_service` | 0.9677 | 1.0000 | 0.9836 | 30 |
| `street_cleaning` | 0.6667 | 0.1333 | 0.2222 | 30 |

Confusion matrix (rows: actual; columns: predicted):

| Actual / Predicted | `sidewalk_maintenance` | `road_surface_defect` | `park_general_maintenance` | `waste_truck_service` | `street_cleaning` |
|---|---:|---:|---:|---:|---:|
| `sidewalk_maintenance` | 27 | 3 | 0 | 0 | 0 |
| `road_surface_defect` | 1 | 29 | 0 | 0 | 0 |
| `park_general_maintenance` | 0 | 0 | 28 | 0 | 2 |
| `waste_truck_service` | 0 | 0 | 0 | 30 | 0 |
| `street_cleaning` | 8 | 12 | 5 | 1 | 4 |

Classification details are also saved in `metrics.json`.

## Provenance and limits

See `run_manifest.json` for source hashes, resource readings, timings, dependency versions and locked configuration.

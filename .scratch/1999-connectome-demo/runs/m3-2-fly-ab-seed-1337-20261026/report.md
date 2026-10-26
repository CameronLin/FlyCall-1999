# M3.2 Fly A/B provisional train-validation run

- Run ID: `m3-2-fly-ab-seed-1337-20261026`
- Status: `completed_provisional`
- Data: synthetic; manual review pending; provisional only.
- Test: `not_run`; no test transcript, embedding, prediction, or metric.

## Selected checkpoints

- Fly A epoch: 37; validation distance stress: 0.00567240.
- Fly B epoch: 17; validation Macro-F1: 0.586714.
- Fly A parameters: {'adapter': 12320, 'graph_core': 2216, 'readout': 0, 'total': 14536}; Fly B parameters: {'adapter': 1056, 'graph_core': 2216, 'readout': 165, 'total': 3437}.
- Checkpoint reload comparison: validation representations/logits match within `1e-6`.

## Classification metrics

### Train (n=700)

Accuracy: 0.6657; Macro-F1: 0.5837.

| Label | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| `sidewalk_maintenance` | 0.0000 | 0.0000 | 0.0000 | 140 |
| `road_surface_defect` | 0.6029 | 0.9000 | 0.7221 | 140 |
| `park_general_maintenance` | 0.7071 | 1.0000 | 0.8284 | 140 |
| `waste_truck_service` | 0.6832 | 0.9857 | 0.8070 | 140 |
| `street_cleaning` | 0.7654 | 0.4429 | 0.5611 | 140 |

Confusion matrix (rows: actual; columns: predicted):

| Actual / Predicted | `sidewalk_maintenance` | `road_surface_defect` | `park_general_maintenance` | `waste_truck_service` | `street_cleaning` |
|---|---:|---:|---:|---:|---:|
| `sidewalk_maintenance` | 0 | 81 | 21 | 20 | 18 |
| `road_surface_defect` | 0 | 126 | 8 | 6 | 0 |
| `park_general_maintenance` | 0 | 0 | 140 | 0 | 0 |
| `waste_truck_service` | 0 | 1 | 0 | 138 | 1 |
| `street_cleaning` | 10 | 1 | 29 | 38 | 62 |

### Validation (n=150)

Accuracy: 0.6667; Macro-F1: 0.5867.

| Label | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| `sidewalk_maintenance` | 0.0000 | 0.0000 | 0.0000 | 30 |
| `road_surface_defect` | 0.5185 | 0.9333 | 0.6667 | 30 |
| `park_general_maintenance` | 0.6744 | 0.9667 | 0.7945 | 30 |
| `waste_truck_service` | 0.9091 | 1.0000 | 0.9524 | 30 |
| `street_cleaning` | 0.6500 | 0.4333 | 0.5200 | 30 |

Confusion matrix (rows: actual; columns: predicted):

| Actual / Predicted | `sidewalk_maintenance` | `road_surface_defect` | `park_general_maintenance` | `waste_truck_service` | `street_cleaning` |
|---|---:|---:|---:|---:|---:|
| `sidewalk_maintenance` | 0 | 15 | 8 | 1 | 6 |
| `road_surface_defect` | 0 | 28 | 0 | 2 | 0 |
| `park_general_maintenance` | 0 | 0 | 29 | 0 | 1 |
| `waste_truck_service` | 0 | 0 | 0 | 30 | 0 |
| `street_cleaning` | 0 | 11 | 6 | 0 | 13 |

Classification details are also saved in `metrics.json`.

## Provenance and limits

See `run_manifest.json` for source hashes, resource readings, timings, dependency versions and locked configuration.

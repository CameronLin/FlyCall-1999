# M4 matched-budget validation comparison

- Status: `matched_budget_validation_only_complete_pending_manual_review`
- Data: `synthetic`; review: `pending_manual_review`
- Test: `not_run`; test inputs: `0`
- Same frozen seeds: `42, 1337, 2026`; each candidate fits train only and selects/checks on validation.

| Candidate | Macro-F1 mean | Sample SD | Accuracy mean | Sample SD |
|---|---:|---:|---:|---:|
| mlp_matched_budget | 0.9104 | 0.0302 | 0.9133 | 0.0267 |
| fly_a_to_fly_b_matched_budget | 0.8040 | 0.0218 | 0.8244 | 0.0077 |
| gated_e5_residual | 0.9048 | 0.0084 | 0.9089 | 0.0077 |

## Per-seed validation metrics

| Candidate | Seed | Macro-F1 | Accuracy | Selected epoch |
|---|---:|---:|---:|---:|
| mlp_matched_budget | 42 | 0.9389 | 0.9400 | 91 |
| mlp_matched_budget | 1337 | 0.9137 | 0.9133 | 36 |
| mlp_matched_budget | 2026 | 0.8787 | 0.8867 | 78 |
| fly_a_to_fly_b_matched_budget | 42 | 0.7965 | 0.8200 | 134 |
| fly_a_to_fly_b_matched_budget | 1337 | 0.8286 | 0.8333 | 90 |
| fly_a_to_fly_b_matched_budget | 2026 | 0.7869 | 0.8200 | 62 |
| gated_e5_residual | 42 | 0.8952 | 0.9000 | 67 |
| gated_e5_residual | 1337 | 0.9108 | 0.9133 | 68 |
| gated_e5_residual | 2026 | 0.9084 | 0.9133 | 81 |

The original registered M3.4 comparison remains authoritative for candidate selection. This matched-budget run is a validation-only diagnostic; no test data were opened.

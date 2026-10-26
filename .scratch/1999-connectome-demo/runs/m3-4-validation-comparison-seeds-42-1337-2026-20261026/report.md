# M3.4 validation-only candidate comparison

- Status: `validation_complete_pending_manual_review`
- Data: `synthetic`
- Review: `pending_manual_review`
- Seeds: `42, 1337, 2026`
- Selection rule: highest mean validation Macro-F1 across the predeclared seeds; ties use higher mean validation accuracy, then candidate name in ascending lexical order
- Validation winner: `mlp` (pending manual review)
- Formal test eligible: `false`
- Test: `not_run`

| Candidate | Validation Macro-F1 mean | Sample SD | Accuracy mean | Sample SD |
|---|---:|---:|---:|---:|
| `logistic_regression` | 0.8678 | 0.0000 | 0.8733 | 0.0000 |
| `mlp` | 0.9022 | 0.0274 | 0.9067 | 0.0231 |
| `pca_mlp` | 0.8965 | 0.0154 | 0.8978 | 0.0154 |
| `lda_logistic_regression` | 0.8998 | 0.0000 | 0.9000 | 0.0000 |
| `fly_a_to_fly_b` | 0.6601 | 0.0765 | 0.7089 | 0.0674 |

## Per-seed validation metrics

| Candidate | Seed | Validation Macro-F1 | Validation accuracy |
|---|---:|---:|---:|
| `logistic_regression` | 42 | 0.8678 | 0.8733 |
| `logistic_regression` | 1337 | 0.8678 | 0.8733 |
| `logistic_regression` | 2026 | 0.8678 | 0.8733 |
| `mlp` | 42 | 0.9181 | 0.9200 |
| `mlp` | 1337 | 0.9179 | 0.9200 |
| `mlp` | 2026 | 0.8706 | 0.8800 |
| `pca_mlp` | 42 | 0.9055 | 0.9067 |
| `pca_mlp` | 1337 | 0.9054 | 0.9067 |
| `pca_mlp` | 2026 | 0.8787 | 0.8800 |
| `lda_logistic_regression` | 42 | 0.8998 | 0.9000 |
| `lda_logistic_regression` | 1337 | 0.8998 | 0.9000 |
| `lda_logistic_regression` | 2026 | 0.8998 | 0.9000 |
| `fly_a_to_fly_b` | 42 | 0.6541 | 0.6733 |
| `fly_a_to_fly_b` | 1337 | 0.5867 | 0.6667 |
| `fly_a_to_fly_b` | 2026 | 0.7393 | 0.7867 |

This report reads saved train/validation metrics and provenance only. It does not read test rows, test predictions, or test metrics. Candidate selection remains provisional until the required manual review and configuration lock are recorded.

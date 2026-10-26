# M2.2b / M2.3 E5 provisional train/validation run

- Status: `smoke_test` / `provisional`
- Dataset: synthetic; `review_status=pending_manual_review`
- E5: `intfloat/multilingual-e5-small` at the pinned revision; frozen CPU inference, batch size 1.
- Split: frozen manifest train/validation only; no re-split.
- Test: `not_run`; no test transcript entered tokenizer, encoder, cache, fit, transform, predict, or metrics.
- Model candidates and settings were registered before the dataset was loaded; no validation tuning was performed.

## Split audit

- Records: 1000
- Train: 700; validation: 150; test audit count: 150.
- Model inputs: 700 train and 150 validation records; 0 test records.
- Family split isolation: verified by the frozen loader and model batch contracts.

## Candidate comparison

| Candidate | Train accuracy | Train Macro-F1 | Validation accuracy | Validation Macro-F1 | Fit/transform timing |
|---|---:|---:|---:|---:|---|
| logistic_regression | 1.0000 | 1.0000 | 0.8733 | 0.8678 | fit_transform_predict_wall_seconds=0.0503s |
| mlp | 0.9986 | 0.9986 | 0.9200 | 0.9181 | fit_transform_predict_wall_seconds=0.0986s |
| pca_mlp | 0.9971 | 0.9971 | 0.9067 | 0.9055 | fit_transform_predict_wall_seconds=0.1246s |
| lda_logistic_regression | 1.0000 | 1.0000 | 0.9000 | 0.8998 | lda_fit_and_train_transform=0.0972s, lda_validation_transform=0.0003s, classifier_fit=0.0060s, prediction_and_scores=0.0012s |

Full fixed-order logits and predictions are in `predictions.csv`; per-class metrics, supports, confusion matrices, and error record IDs are in `metrics.json` and `candidate_reports/`.

## Runtime and resource measurements

- Model load: 10.32s; tokenization diagnostics: 0.22s; embeddings: 0.55s.
- Peak process working set: 1.252 GiB; peak pagefile: 2.228 GiB.
- Cache added: 0 bytes; cache total: 6873061 bytes.
- Project disk free: 830857986048 bytes before and 830856024064 bytes after; 4 GiB reserve preserved.

## Limits

The dataset is synthetic and has not passed manual review. These train/validation values are workflow smoke results, not formal model performance. Do not use them to claim real 1999 service outcomes or to unlock the test set.

## Artifacts

- `pre_registered_candidates.json` — fixed candidate settings and configuration fingerprint.
- `embedding_manifest.json` — model/checksum/package contract, source hashes, per-record cache/output hashes and token counts.
- `tokenization_diagnostics.csv` — train/validation token counts and explicit truncation flags.
- `predictions.csv` — train/validation predictions and fixed-order logits only.
- Four `m2-<candidate>-checkpoint.joblib` artifacts — model settings, source/configuration fingerprints, and reload-verified predictor objects.
- `m2-3-lda-logistic-checkpoint.joblib` — reloaded and checked against saved validation predictions and scores.
- `run_manifest.json` — resource data, source checksums, environment and output checksums.

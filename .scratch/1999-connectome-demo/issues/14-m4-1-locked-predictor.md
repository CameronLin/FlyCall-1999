# 14: M4.1 locked checkpoint and common prediction API

**What to build:** Load the validation-selected, configuration-locked model behind one local prediction API and CLI. Validate model/run/checkpoint SHA-256, the candidate registration fingerprint, embedding dimension, Fly d/k or baseline dimensions/C, fixed label order and checkpoint reload evidence. Reject blank and incompatible inputs.

**Formal test gate:** Manual review and final approval are still required before any one-time test evaluation. The user authorized a development/demo candidate and configuration lock to complete M4 technical acceptance.

**Status:** M4.1 technical acceptance passed with the actual seed-42 MLP checkpoint and pinned E5 snapshot. The development/demo manifest records the MLP selection; formal manual review and final test approval remain pending.

## Implemented

- `src/flycall_data/predictor.py` validates an explicit `model_locked_for_demo` manifest, run-manifest SHA, preregistration fingerprint, selected checkpoint hashes, E5 revision/files and fixed class order. It supports E5 baseline artifacts and M3.2 Fly A→B artifacts. The API accepts a single user transcript and creates only train-time model inputs; it has no dataset or test-split loader.
- Baseline inference returns fixed-order logits and softmax scores. The Fly path loads the saved graph definition, checks its source hashes, reloads Fly A and B checkpoints, then returns the same result contract.
- `scripts/predict_flycall.py` provides text argument and stdin CLI modes. Empty, incompatible, unapproved, or checksum-mismatched requests fail closed.
- Every result identifies `synthetic`, `pending_manual_review`, `simulated_only`, and `human_confirmation_required=true`.
- M2.2b runner now saves and reload-verifies Logistic Regression, MLP, PCA→MLP and LDA checkpoints, and exports each train/validation logit in fixed label order. M3.2 success artifacts now include a checksummed graph definition for checkpoint reload.

## Locked model manifest contract

The development/demo manifest records the selected candidate and configuration at the user's direction; it must keep `review_status=pending_manual_review` until formal review is complete. Place it beside the selected run artifacts. Required fields:

- `schema_version=1`, `status=model_locked_for_demo`, `candidate_list_locked=true`, `configuration_locked=true`, and a non-empty `approval_reference`.
- `candidate_name`, `label_order`, `data_status=synthetic`, `review_status=pending_manual_review`, and an `embedding` object with pinned E5 model ID, revision and all model-file hashes.
- `model.configuration_fingerprint`, `model.run_manifest_path`, `model.run_manifest_sha256`, and `model.seed`.
- For an E5 baseline: `model.kind=e5_baseline`, `model.checkpoint_path`, and `model.checkpoint_sha256`.
- For Fly A→B: `model.kind=fly_a_to_fly_b`, `model.graph_definition_path` / SHA-256, and Fly A/B checkpoint paths / SHA-256 values.

This demo lock does not authorize reading the test split. The durable one-time test gate remains separate and closed.

## Remaining acceptance conditions

- [x] Complete M3.2 graph provenance and Windows Parquet runtime gates.
- [x] Produce and compare at least three M2 and Fly seeds; the validation-only provisional comparison is complete.
- [x] Record the user-directed development/demo selection: MLP, seed 42, hidden size 16, 80 epochs, learning rate 0.02; keep formal review pending.
- [x] Load the actual selected run through its locked manifest and pinned E5 runtime; the run has checkpoint reload evidence.
- [x] Verify CLI, direct API and Streamlit AppTest with the actual checkpoint; logits and probabilities match exactly for a fixed synthetic input.
- [ ] Complete formal manual review and approval before the one-time test gate.

## Comments

- 2026-10-26: Added a common predictor and CLI with synthetic artifact tests. Test data remains `not_run` and the formal data review remains pending.

- 2026-10-26: User-directed M4 development/demo selection locked to the registered MLP seed-42 checkpoint. Actual E5-to-checkpoint inference passed; CLI/API/Streamlit AppTest returned identical labels, logits and probabilities (maximum absolute delta 0.0). Synthetic data, review pending, and test `not_run`; see `../runs/m4-matched-budget-validation-20261026/m4_live_acceptance_report.md`.

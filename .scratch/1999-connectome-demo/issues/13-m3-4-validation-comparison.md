# 13: M3.4 multi-seed validation comparison

**What to build:** Compare the four registered E5 baselines with the Fly A→B candidate using only frozen train/validation outputs. Require at least three declared seeds, verify source/configuration/output checksums and fixed label/split contracts, report mean and sample standard deviation, and write a provisional validation winner for manual review.

**Blocked by:** The three-seed validation comparison is complete. Formal selection, a deployable M4 model lock, manual-review sign-off and any one-time test evaluation remain gated on human review and explicit candidate/configuration approval.

**Status:** three-seed M2.2b/M3.2/M3.3 comparison remains validation-only with provisional winner `mlp`. A user-directed development/demo lock now records the MLP seed-42 checkpoint; formal manual review/approval is still pending. Test is `not_run` and `formal_test_eligible=false`.

## Implemented

- `scripts/run_m2_2b_e5_provisional.py --seed N` registers the same seed across all four E5 baselines before dataset access.
- `scripts/run_m3_2_fly_ab_provisional.py --seed N` registers the seed and seed-specific Fly candidate before preflight or data access.
- `src/flycall_data/comparison.py` aggregates saved validation metrics across at least three declared seeds. It validates the preregistration fingerprint, M2/M3 run status, metrics output checksum and byte size, shared frozen dataset hashes, shared E5 identity, shared Fly graph hashes, 700/150 split counts, five-class support, confusion-matrix consistency and test `not_run` status.
- `scripts/compare_m3_4_validation.py` writes `pre_registered_comparison.json` before it opens any run metrics. On success it writes a comparison, provisional candidate-selection record and Markdown summary. Failure preserves the preregistration and records an incomplete result.
- The Markdown summary includes both aggregate mean/sample-SD metrics and one validation Macro-F1/accuracy row for every candidate and seed, making checkpoint-seed review possible without opening source metrics manually.
- The selection rule uses mean validation Macro-F1, then mean validation accuracy, then candidate name. Reported variability is sample standard deviation.
- Comparison output is explicitly `pending_manual_review`, `formal_test_eligible=false`, and `test=not_run`. The tool does not read test rows, test predictions or test metrics.

## Remaining acceptance conditions

- [x] Reconcile and pass the M3.2 graph/runtime gates.
- [x] Produce completed, provenance-checked M2.2b and M3.2 train/validation runs for seeds 42, 1337 and 2026.
- [x] Run the comparison against the four E5 baselines and Fly A→B; the report records mean and sample standard deviation.
- [ ] Human review the comparison report and confirm the validation-selected candidate, checkpoint seed and configuration.
- [ ] Complete the formal dataset manual review and record candidate/configuration approval before any one-time test evaluation.
- [ ] Keep the durable one-time test reservation/evaluation flow closed until all required reviews and explicit authorization are recorded.

## Reproducible comparison command

```powershell
python scripts/compare_m3_4_validation.py `
  --seed 42 --seed 1337 --seed 2026 `
  --run-dir .scratch/1999-connectome-demo/runs/m2-2b-e5-seed-42-current-runner-20261026 `
  --run-dir .scratch/1999-connectome-demo/runs/m3-2-fly-ab-seed-42-crlf-fix-20261026 `
  --run-dir .scratch/1999-connectome-demo/runs/m2-2b-e5-seed-1337-current-runner-20261026 `
  --run-dir .scratch/1999-connectome-demo/runs/m3-2-fly-ab-seed-1337-20261026 `
  --run-dir .scratch/1999-connectome-demo/runs/m2-2b-e5-seed-2026-current-runner-20261026 `
  --run-dir .scratch/1999-connectome-demo/runs/m3-2-fly-ab-seed-2026-20261026 `
  --output-id seeds-42-1337-2026-20261026
```

Each M2 run contains the four text/embedding baselines; each M3 run contains the Fly A→B metrics for that seed.

## Human review required before formal test

Spec v0.2 section 7.3 requires at least 20 manually reviewed records per class spanning train, validation and test, plus a human disposition for every record flagged `需人工特別確認` and every AI `revise` record. The frozen review pack contains 399 rows (validation 150, test 150, train 99); its AI labels are suggestions, not approval. Record decisions separately and do not change dataset `review_status` fields. The test portion must remain unopened until the candidate, checkpoint seed, settings and selection rule are locked. The existing workbook is [正式資料人工複核資料包 v1.0](../../../outputs/flycall-1999-formal-review-pack-v1.0/FlyCall_1999_正式資料人工複核資料包_v1.0.xlsx).

## Comments

- 2026-10-26: Added validation-only aggregation and synthetic fixture coverage. The fixture exercises three seeds and all five candidates; it does not represent model performance.
- 2026-10-26: Verified the existing seed-42 M2.2b artifact against the new schema; it passes its saved provenance and metrics checks, then correctly stops because seeds 1337 and 2026 are not yet present. No test data was accessed.
- 2026-10-26: Completed all three M2.2b seeds with the current checkpoint/logit runner and all three real-graph M3.2 seeds. The comparison is saved at `../runs/m3-4-validation-comparison-seeds-42-1337-20261026/report.md`; the validation-only provisional winner is MLP (Macro-F1 mean 0.9022, sample SD 0.0274; accuracy mean 0.9067, sample SD 0.0231). Candidate selection remains unlocked and pending human review; test metrics were not produced.
- 2026-10-26: Added per-seed validation metrics for all five candidates to the human-readable report. Regenerated the existing report from its saved `comparison.json` without rereading any run metrics; added coverage that checks each candidate/seed row. Full suite passed 131/131 tests, and report still states test `not_run` / formal test eligibility false.

- 2026-10-26: Added a matched-budget diagnostic for MLP, pure Fly A?B and gated residual. MLP led validation means by 0.0056 Macro-F1 over the residual; residual remains exploratory because four settings were selected on the same validation set. The M4 development/demo lock and live CLI/API/Streamlit acceptance now pass; formal review and test remain pending.

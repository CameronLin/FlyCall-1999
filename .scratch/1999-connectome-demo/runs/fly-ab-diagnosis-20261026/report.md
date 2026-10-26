# Fly A→B validation diagnosis

- Status: `fly_a_probe_and_gated_e5_residual_complete`
- Data: `synthetic`; review: `pending_manual_review`
- Test: `not_run`; model inputs: `0`
- Inputs: saved train/validation E5 cache vectors, checksummed M3.2 Fly A checkpoints, and M3.2 train/validation predictions only.

## Frozen Fly A representation probes

| Representation | Probe | Mean validation Macro-F1 | Sample SD | Mean validation accuracy | Sample SD |
|---|---|---:|---:|---:|---:|
| raw_e5 | logistic_regression | 0.8678 | 0.0000 | 0.8733 | 0.0000 |
| raw_e5 | mlp | 0.9022 | 0.0274 | 0.9067 | 0.0231 |
| fly_a_32d | logistic_regression | 0.7958 | 0.0321 | 0.8156 | 0.0214 |
| fly_a_32d | mlp | 0.7758 | 0.0434 | 0.7956 | 0.0482 |

### Per-seed probe Macro-F1

| Seed | Raw E5 LR | Raw E5 MLP | Fly A LR | Fly A MLP |
|---:|---:|---:|---:|---:|
| 42 | 0.8678 | 0.9181 | 0.7864 | 0.7300 |
| 1337 | 0.8678 | 0.9179 | 0.8316 | 0.8162 |
| 2026 | 0.8678 | 0.8706 | 0.7695 | 0.7812 |

Fly A label-signal decision: `add_e5_residual_to_fly_b_graph`. Mean Fly A MLP Macro-F1 0.7758; raw E5 MLP mean 0.9022; gap 0.1264.

## Gated E5 residual candidate

The candidate combines `FlyB.input_adapter(FlyA(E5)) + sigmoid(g) * W(E5)` immediately before the Fly B graph core. All logits still pass through that graph core and readout; Fly A remains frozen.

Training: Adam, LR `0.001`, batch `32`, max epochs `100`, patience `10`, clip `1.0`; same three seeds.

| Candidate | Mean validation Macro-F1 | Sample SD | Mean accuracy | Sample SD | Δ Macro-F1 vs original | Mean learned gate |
|---|---:|---:|---:|---:|---:|---:|
| gated E5 residual → Fly B graph | 0.7507 | 0.1619 | 0.7844 | 0.1202 | +0.0907 | 0.5245 |

### Per-seed comparison

| Seed | Original F1 | Residual F1 | Δ F1 | Original accuracy | Residual accuracy | Δ accuracy | Selected epoch | Gate |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 42 | 0.6541 | 0.7861 | +0.1320 | 0.6733 | 0.7933 | +0.1200 | 100 | 0.6856 |
| 1337 | 0.5867 | 0.5741 | -0.0126 | 0.6667 | 0.6600 | -0.0067 | 15 | 0.1934 |
| 2026 | 0.7393 | 0.8919 | +0.1526 | 0.7867 | 0.9000 | +0.1133 | 99 | 0.6946 |

This is a separate exploratory validation candidate, not a replacement M3.2/M3.4 result. Checkpoint selection used this validation set, so its score is not an unbiased final estimate.

## Test and review boundary

No test rows, transcripts, embeddings, predictions, or metrics were read. Formal data remains synthetic and pending manual review. The new candidate remains unlocked and test-ineligible.

See `diagnosis.json` for source checksums, per-seed train/validation metrics, all schedules, and checkpoint hashes.

## Residual stability follow-up

All configurations were preregistered in `fly-a-b-diagnostic-preregistration-20261026.md` before this sweep. Every result uses the same three train/validation seeds.

| Configuration | Gate init | LR | Epochs | Patience | Mean validation Macro-F1 | Sample SD | Mean accuracy | Sample SD | Δ F1 vs original | Δ F1 vs first residual |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| residual_gate_m2_long | -2.0 | 0.001 | 200 | 25 | 0.8945 | 0.0111 | 0.9000 | 0.0115 | +0.2345 | +0.1438 |
| residual_gate_m2_lr3_long | -2.0 | 0.003 | 200 | 25 | 0.9017 | 0.0145 | 0.9067 | 0.0133 | +0.2416 | +0.1510 |
| residual_gate_0_long | 0.0 | 0.001 | 200 | 25 | 0.8977 | 0.0082 | 0.9022 | 0.0077 | +0.2377 | +0.1470 |
| residual_gate_0_lr3_long | 0.0 | 0.003 | 200 | 25 | 0.9048 | 0.0084 | 0.9089 | 0.0077 | +0.2447 | +0.1541 |

### Per-seed results

| Configuration | Seed | Original F1 | First residual F1 | Follow-up F1 | Δ vs original | Δ vs residual | Accuracy | Epoch | Gate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| residual_gate_m2_long | 42 | 0.6541 | 0.7861 | 0.8861 | +0.2320 | +0.1000 | 0.8933 | 197 | 0.8485 |
| residual_gate_m2_long | 1337 | 0.5867 | 0.5741 | 0.8903 | +0.3036 | +0.3162 | 0.8933 | 155 | 0.7722 |
| residual_gate_m2_long | 2026 | 0.7393 | 0.8919 | 0.9071 | +0.1678 | +0.0152 | 0.9133 | 132 | 0.7444 |
| residual_gate_m2_lr3_long | 42 | 0.6541 | 0.7861 | 0.8861 | +0.2320 | +0.1000 | 0.8933 | 62 | 0.8245 |
| residual_gate_m2_lr3_long | 1337 | 0.5867 | 0.5741 | 0.9040 | +0.3173 | +0.3299 | 0.9067 | 83 | 0.8097 |
| residual_gate_m2_lr3_long | 2026 | 0.7393 | 0.8919 | 0.9149 | +0.1755 | +0.0229 | 0.9200 | 62 | 0.7797 |
| residual_gate_0_long | 42 | 0.6541 | 0.7861 | 0.8885 | +0.2344 | +0.1024 | 0.8933 | 200 | 0.9562 |
| residual_gate_0_long | 1337 | 0.5867 | 0.5741 | 0.9040 | +0.3173 | +0.3299 | 0.9067 | 192 | 0.9408 |
| residual_gate_0_long | 2026 | 0.7393 | 0.8919 | 0.9007 | +0.1613 | +0.0087 | 0.9067 | 145 | 0.9303 |
| residual_gate_0_lr3_long | 42 | 0.6541 | 0.7861 | 0.8952 | +0.2411 | +0.1091 | 0.9000 | 67 | 0.9490 |
| residual_gate_0_lr3_long | 1337 | 0.5867 | 0.5741 | 0.9108 | +0.3241 | +0.3367 | 0.9133 | 68 | 0.9363 |
| residual_gate_0_lr3_long | 2026 | 0.7393 | 0.8919 | 0.9084 | +0.1690 | +0.0164 | 0.9133 | 81 | 0.9422 |

Highest validation mean: `residual_gate_0_lr3_long`. This used the same validation split for configuration comparison, so report it as exploratory. No test split was read; the candidate remains unlocked.

## Diagnostic and software test log

1. The first artifact preflight found the historical M3.2 `data_status` and `review_status` fields nested under `dataset_audit`; the reader was corrected to match the existing M3.4 comparison logic and retained all fail-closed provenance checks.
2. The first report render exposed a mismatch between the evaluator's `splits.validation.metrics` shape and the renderer; the renderer was corrected and the generated train/validation report was rechecked.
3. All three initial residual runs and their reports/checkpoints completed, but the Windows console rejected the Chinese character in the absolute output path at the final print. Console output was changed to use the ASCII relative path. The completed artifacts were consumed by the residual stability sweep; training was not repeated for this display-only fix.
4. Focused tests passed: diagnostic guardrails 4/4, Fly A/B trainer 8/8, graph core 15/15. Full suite: `PYTHONPATH=src python -m unittest discover -s tests -v` ? 141 tests passed. `py_compile` passed for added/changed Python files; `git diff --check` passed.

All experiment paths stayed on train/validation. The run manifest, embedding manifest, predictions and checkpoints were checksummed; test status remained `not_run` with zero model inputs.

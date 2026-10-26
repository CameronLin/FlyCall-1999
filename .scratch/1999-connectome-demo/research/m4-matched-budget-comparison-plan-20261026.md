# M4 candidate confirmation: matched-budget validation plan

- Status: preregistered before the matched-budget runs
- Spec: v0.2 §§7.3, 9, 11. Train/validation only; test access prohibited.
- Purpose: compare the registered MLP, pure Fly A→B, and the already-run gated E5 residual under the same three frozen seeds and a maximum 200-epoch budget before preparing an M4 demo lock.

## Candidates and settings

| Candidate | Input | Model/settings | Epoch selection |
|---|---|---|---|
| `mlp_matched_budget` | raw 384-D E5 | hidden 16, Adam, LR 0.02, full-batch, max 200 epochs, patience 25 | validation Macro-F1, then lower validation loss; earliest tie |
| `fly_a_to_fly_b_matched_budget` | frozen original seed-matched Fly A 32-D output | Adam, LR 0.003, batch 32, max 200 epochs, patience 25, clip 1.0 | existing Fly B validation Macro-F1, then lower loss; earliest tie |
| `gated_e5_residual` | prior preregistered result, raw E5 residual fused before Fly B graph | gate init 0, Adam LR 0.003, batch 32, max 200 epochs, patience 25, clip 1.0 | existing validation checkpoint selection |

Seeds are `42, 1337, 2026`. Reuse only the frozen 700/150 E5 cache and M3.2 train/validation labels/families. Verify artifact hashes, label order and family isolation. Each estimator fits train only and uses validation only for checkpoint selection/reporting. Do not open dataset transcripts or any test artifact.

The previously reported M3.4 MLP result remains the registered comparison. This matched-budget result is a diagnostic follow-up; it does not replace M3.4 or become a formal test result. Select the M4 development candidate by the registered M3.4 outcome (MLP) unless the matched-budget diagnostic exposes a material defect; document the selected seed/configuration and keep review status pending.

## Required checks and outputs

- Report all three candidates for each seed, means and sample SD; report per-class metrics and selected epochs.
- Save pure Fly A→B checkpoints only in the diagnostic output folder and verify reload equality.
- Record code/source/checkpoint checksums, `test=not_run`, and zero test inputs.
- Final test remains closed pending the user's manual review and explicit final evaluation authorization.

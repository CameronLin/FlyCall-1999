# 16: Fly A→B representation diagnosis and gated E5 residual

**Blocked by:** Formal dataset review and model/configuration lock remain requirements for final selection or a test run; they do not block this validation-only diagnosis.

**Status:** Fly A probe, separate gated residual implementation, three-seed control, and preregistered residual stability sweep completed. The new candidate remains exploratory and unlocked. Test is `not_run`; test input count is `0`.

## Findings

- Spec basis: v0.2 §§7.3, 9, 11. Original M3.2/M3.4 artifacts and the M3.4 provisional winner (`mlp`) were preserved.
- Frozen representation probe: raw E5 MLP mean validation Macro-F1 `0.9022` (SD `0.0274`); Fly A's frozen 32-D output MLP `0.7758` (SD `0.0434`), a `0.1264` gap. Therefore, the registered decision rule skipped B-only schedule changes.
- First gated-residual control: mean validation Macro-F1 `0.7507` (SD `0.1619`), accuracy `0.7844` (SD `0.1202`), mean Δ F1 vs original Fly A→B `+0.0907`; it improved two seeds and regressed seed 1337, so a preregistered stability sweep followed.
- Best of four residual settings: gate logit init `0`, Adam LR `0.003`, batch `32`, maximum `200` epochs, patience `25`, gradient clip `1.0`; mean validation Macro-F1 `0.9048` (SD `0.0084`), accuracy `0.9089` (SD `0.0077`). This is `+0.2447` F1 and `+0.2000` accuracy versus original Fly A→B, and within `0.0026` F1 / `0.0022` accuracy of the saved MLP validation mean.
- Best-setting seed F1: `0.8952`, `0.9108`, `0.9084` for seeds `42`, `1337`, `2026`; all three exceed their original Fly A→B results. Mean learned residual gate is about `0.942`.

The best setting was identified by looking across four configurations on the same validation split. It is a development result, not an unbiased final performance estimate. Dataset remains synthetic and pending manual review; these values are not real service-call performance. Do not lock a production model or read test data from this issue.

## Implementation

- Added `FlyBWithE5Residual`: a bias-free `384→32` E5 projection with a trainable sigmoid gate, added to the normal Fly B adapter drives immediately before Fly B's graph core. There is no encoder-to-classifier shortcut; all logits still pass through Fly B's graph and readout.
- Added a separate train-only trainer and provenance-checked checkpoint loader. Fly A is frozen. The original `FlyB` model and original M3.2 checkpoints remain unchanged.
- Added train/validation-only diagnosis and residual-sweep CLIs, reports, and guardrail/model/trainer tests.

## Recorded artifacts

- Plan and results: [Fly A/B diagnostic preregistration and run log](../research/fly-a-b-diagnostic-preregistration-20261026.md)
- Per-seed results: [diagnosis report](../runs/fly-ab-diagnosis-20261026/report.md)
- Machine-readable results: `diagnosis.json`, `residual_followup.json`, and `artifact_manifest.json` in the same run directory.

## Verification

The diagnostic verifies exactly 700 train and 150 validation rows, 850 E5 cache entries, no test entries, input/checkpoint checksums, train/validation family isolation, fixed taxonomy, and checkpoint reload max logit difference `0.0` for every residual-sweep seed/configuration. Unit coverage includes test-split rejection before checkpoint creation, frozen Fly A, finite gradients to both E5 residual and Fly B graph, shape validation, and checkpoint equality.

Verification passed: focused guardrail/trainer/graph suites (4 + 8 + 15 tests) and the full `python -m unittest discover -s tests -v` suite (141 tests); `py_compile` and `git diff --check` also passed.

# Fly A→B validation diagnosis and tuning plan

- Status: `exploratory_plan_written_before_new_probe_runs`
- Data status: `synthetic`; review status: `pending_manual_review`
- Scope: train/validation only. Test transcript, embedding, prediction, and metric access is prohibited.
- Spec reference: `1999-connectome-demo-spec-v0.2.md`, §§7.3, 9, 11. The original M3.2/M3.4 runs and configuration remain immutable reference results.
- Existing reference: Fly A→B validation Macro-F1 mean 0.6601 (sample SD 0.0765), accuracy mean 0.7089 (SD 0.0674); MLP Macro-F1 mean 0.9022 (SD 0.0274), accuracy mean 0.9067 (SD 0.0231), across seeds 42, 1337, and 2026.

## Ordered experiment

1. Load only the 850 train/validation embeddings listed in the frozen E5 embedding manifest, expected labels/families from the three train/validation-only M3 predictions files, pinned graph definitions, and each matching Fly A checkpoint. Reject any manifest or prediction artifact that declares a test row.
2. For each of the three saved Fly A checkpoints, freeze Fly A and fit two diagnostic probes on its 32-dimensional output: the registered Logistic Regression baseline, and the existing registered 16-hidden-unit MLP (80 epochs, learning rate 0.02). Also run these probes on raw 384-dimensional E5 vectors as a pipeline control. All estimators fit train only and score train/validation; no transcript is read.
3. Interpret Fly A as retaining enough label information when the mean Fly A-output MLP validation Macro-F1 is at least 0.85 and no more than 0.10 below the raw E5 MLP probe. If it meets that rule, keep the pure Fly A→B data flow and test Fly B optimization schedules. Otherwise, treat Fly A representation loss as the primary suspect and do not claim that B-only tuning can recover discarded information; report that a separate E5-to-Fly-B-core residual candidate needs its own design and registration.
4. If step 3 selects B tuning, compare the existing `Adam` schedule against three predeclared schedules on each matching seed/checkpoint: `(learning_rate=0.001, max_epochs=200, patience=25)`, `(0.003, 200, 25)`, `(0.01, 200, 25)`. Keep batch size 32, gradient clip 1.0, CPU, topology, label order, Fly A checkpoint, and training seed fixed. Select each B checkpoint by the existing validation Macro-F1 then validation-loss rule. Report all runs, including seeds/configurations that regress; do not read test.
5. Any selected tuned result is an exploratory validation result selected on the same frozen validation set. It is not an M3.4 result, a locked model, or eligible for formal test evaluation. Do not replace original M3.2 artifacts or mutate dataset/splits.

## Planned correctness checks

- Exact 700/150 train/validation coverage, no duplicate/cross-split IDs or families, all five labels, and exactly 850 manifest entries with zero test entries.
- Verify E5 cache vectors against manifest dimension, normalization, and per-vector SHA-256; verify each Fly A checkpoint against the run's pinned source hashes and each run artifact against its manifest checksum.
- Verify the probe's fit IDs equal train IDs and validation IDs equal validation IDs; only the training function receives train labels for fitting.
- Verify the tuning runner accepts only the literal `train` and `validation` splits and its output says `test=not_run` with zero test inputs.
- Run focused unit tests and the full repository unit suite after implementation.

## Probe-triggered architecture amendment

The first probe completed under the rule above: raw E5 MLP mean validation Macro-F1 `0.9022`; frozen Fly A 32-D MLP mean `0.7758`; gap `0.1264`. This fails both parts of the predeclared retention rule, so the next step is a separately identified gated-residual candidate rather than B-only schedule tuning.

- Candidate: `E5 → gated residual → Fly B graph`, fused with the normal `Fly A → Fly B adapter` drives immediately before Fly B's graph core: `B_adapter(z_A) + sigmoid(g) * W_E5(e)`. Initialize `g=-2`; use a trainable bias-free `384→32` E5 projection. The residual has no classifier/readout shortcut; all logits still pass through Fly B's graph core and readout.
- Freeze the selected Fly A checkpoint. Train the Fly B adapter, graph edge gains, readout, E5 projection, and gate from train labels only.
- Keep the original M3.2 Fly B optimizer schedule fixed for a controlled architecture comparison: Adam, LR `0.001`, batch `32`, maximum `100` epochs, patience `10`, gradient clipping `1.0`, CPU, same three seeds and topology. Select each checkpoint using the existing validation Macro-F1 then validation-loss rule.
- Compare the residual candidate with each original seed's saved validation predictions. Report all seed-level changes, mean and sample SD, checkpoints, parameter counts, and a test-never-opened assertion. Do not replace M3.2/M3.4 artifacts or claim formal performance.
- Add tests for graph-only output flow, residual and graph gradient flow, A freezing, deterministic checkpoint reload, test-split rejection, and fixed taxonomy.

## Residual stability follow-up

The first fixed-schedule residual candidate completed: validation Macro-F1 mean `0.7507` (sample SD `0.1619`), accuracy mean `0.7844` (SD `0.1202`), mean change from the original Fly A→B `+0.0907`. Per-seed Macro-F1 was `0.7861`, `0.5741`, `0.8919`; seed 1337 regressed by `0.0126`. Since the residual direction improved the mean but was unstable, compare the following predeclared residual-only settings, each across the same three seeds, against the first residual run and original Fly A→B:

| Candidate | Gate logit init | LR | Max epochs | Patience |
|---|---:|---:|---:|---:|
| `residual_gate_m2_long` | -2 | 0.001 | 200 | 25 |
| `residual_gate_m2_lr3_long` | -2 | 0.003 | 200 | 25 |
| `residual_gate_0_long` | 0 | 0.001 | 200 | 25 |
| `residual_gate_0_lr3_long` | 0 | 0.003 | 200 | 25 |

All other settings remain batch 32, gradient clip 1.0, CPU, Adam, same frozen Fly A checkpoint and fixed graph. Compare complete three-seed results and report the full spread; do not select a final candidate or access test.

## Results log

New probe and tuning measurements will be appended after execution. Baseline values above were read from the existing M3.4 report before this diagnostic plan was written; they are references only and will not be reselected or modified.

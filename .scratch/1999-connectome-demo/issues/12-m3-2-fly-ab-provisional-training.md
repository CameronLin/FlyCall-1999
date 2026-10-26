# 12: M3.2 Fly A / Fly B provisional train-validation run

**What to build:** Apply the confirmed M3.0 recurrent sparse graph contract to the pinned M1.3 500-node, 2,216-edge engineering graph. Reuse the verified frozen E5 cache; train Fly A on train-only pairwise distance preservation, freeze its selected checkpoint, then train Fly B on train-only labels. Report validation distance stress and classification metrics as provisional synthetic-data evidence.

**Blocked by:** The graph/runtime pre-run gates are now passing in the current Windows environment. Formal performance claims and any test use remain blocked by pending human review and candidate/configuration approval.

**Status:** three real-graph train/validation-only provisional runs completed for seeds 42, 1337 and 2026. All selected checkpoints reload exactly; test remains `not_run` with zero model inputs. Outputs are synthetic-data evidence pending human review, not formal performance results.

## Dependencies and boundaries

- M1.3 engineering I/O manifest is the source of the ordered 32 input IDs and 32 output IDs. Verify its pinned node/edge checksums before building either graph core. These endpoints are synthetic engineering coordinates, not biologically typed nodes.
- M2.2b supplies the E5 small revision `614241f622f53c4eeff9890bdc4f31cfecc418b3` embeddings and cache manifest. The encoder remains frozen and is not part of either Fly's trainable parameters.
- M2.1 performs the full source contract audit. The model pipeline may construct batches only from train and validation; no test transcript, embedding, prediction, or metric may be produced.
- Formal synthetic data is still `pending_manual_review`; all outputs are `smoke_test` / `provisional`.
- The three-seed runs do not establish biological function, a real 1999 business outcome, or final model selection.
- Do not change the graph, I/O IDs, weights, source artifacts, data, frozen split, label order, or previous M2 outputs.

## Locked first-run configuration

- CPU only; one PyTorch thread; first run seed 42; train batch 32; maximum 100 epochs; patience 10; Adam at `1e-3`; gradient norm clipping `1.0`. The runner accepts a positive `--seed` to pre-register later multi-seed runs; the other settings stay fixed.
- Both sparse graph cores use the same 500-node directed support, ordered M1.3 I/O IDs, shared edge gain across steps, fixed indegree normalization and M3.0 positive `log1p(weight)` prior. Fly A and Fly B own separate parameters.
- Primary recurrent setting is `T=2`. Do not run a T=4 ablation in this ticket.
- Fly A is selected by lowest full-validation pairwise distance stress; exact ties keep the earlier epoch. Its loss uses train batches only and does not read labels.
- Freeze the selected Fly A checkpoint before fitting Fly B. Select Fly B by validation Macro-F1, then lower validation cross-entropy, then earlier epoch.
- Non-finite losses or gradients stop training and preserve the latest valid checkpoint. A zero-norm Fly A output is an error.

## Artifacts

- Hash-locked Windows CPU dependency input for PyArrow plus the verified E5/PyTorch environment.
- A reproducible, pre-registered train/validation-only runner; no dataset re-split. It writes run registration before source loading, stops on provenance mismatch, records the environment/resources, saves checkpoints/history/predictions/metrics/report, and leaves test `not_run`.
- M1.3 graph and I/O verification summary, dataset source hashes, embedding manifest/cache provenance, epoch curves, train/validation metrics, selected epochs, parameter counts, CPU timing and peak memory.
- Fly A and Fly B checkpoint files with topology, ordered IDs, source and model checksums, seed, optimizer, epoch selection rules and label order. Reload each checkpoint and compare selected validation outputs.
- A Markdown report marked synthetic, pending manual review and provisional. Test remains `not_run`.

## Reproducible command after both pre-run gates pass

```powershell
python -m pip install --require-hashes -r .scratch/1999-connectome-demo/requirements-m3-2-fly-ab-windows.lock
python scripts/run_m3_2_fly_ab_provisional.py
```

The runner pre-registers before opening dataset or graph inputs and exits without model inputs when graph provenance or the approved Parquet runtime gate fails.

## Acceptance conditions

- [x] Reconcile pinned M1.2/M1.3 manifest hashes before loading graph rows. The original pins match Git HEAD and the LF-normalized content exactly; only Windows checkout CRLF differed. Code now normalizes CRLF for manifest content only. Raw Parquet SHA-256 values remain byte-exact. The three real runs then decoded the schema and validated graph rows.
- [x] Corrected E5 run manifest/cache provenance was rechecked: 850 exact cache entries, 700 train / 150 validation, 384 dimensions, nine pinned model-file hashes, no cache-vector hash mismatch, and test counts zero / `not_run`.
- [x] The implemented cache input loader was run against the frozen dataset and corrected E5 cache: it returned Fly A and Fly B splits with 700 train / 150 validation, 384 dimensions, and zero test records. No encoder/model was called in this check.
- [x] Real-graph runner uses 700/150 splits for training and validation across all three seeds; each manifest records test count 0 and test `not_run`, with zero test inputs reaching a model, prediction, or metric.
- [x] M3.0 Fly A and Fly B parameters follow the recurrent graph contract; unit tests cover sparse edge support, no bypass, gradients, topology, and dimensions.
- [x] Fly A training is label-free, uses train batches only, records train loss and validation stress, and selects the lowest-stress checkpoint. Fly A is frozen before Fly B training.
- [x] Fly B fits only train labels and records train/validation Macro-F1, per-class metrics, supports, confusion matrix, and deterministic selected epoch.
- [x] Checkpoints reload on CPU and reproduce selected validation representations/logits exactly (max absolute difference 0.0 in all three runs); incompatible provenance/topology/I/O order/dimension/class order is rejected.
- [x] Resource, timing, parameter-count, source checksum and output checksum evidence is saved; pinned graph and dataset inputs were verified unchanged.
- [x] Each report states synthetic / pending_manual_review / smoke_test-provisional; no test prediction or formal performance claim was produced.

## Executed real-graph runs

All three preregistered runs completed on the 500-node / 2,216-edge M1.3 engineering graph, using 700 train and 150 validation records. The selected checkpoint metadata and validation-only results are:

| Seed | Fly A selected epoch | Validation stress | Fly B selected epoch | Validation accuracy | Validation Macro-F1 | Reload | Test |
|---:|---:|---:|---:|---:|---:|---|---|
| 42 | 17 | 0.00721865 | 100 | 0.6733 | 0.654127 | passed (≤1e-6) | `not_run`; 0 inputs |
| 1337 | 37 | 0.00567240 | 17 | 0.6667 | 0.586714 | passed (≤1e-6) | `not_run`; 0 inputs |
| 2026 | 10 | 0.00701145 | 57 | 0.7867 | 0.739337 | passed (≤1e-6) | `not_run`; 0 inputs |

Every output file's byte count and SHA-256 match its run manifest. These are completed training and validation runs on synthetic data; they remain provisional pending the Spec v0.2 manual-review gate.

## Spec v0.2 M3.3 coverage

Spec v0.2 lists Fly B training as M3.3. This ticket records M3.2 and M3.3 together because one real-graph run must first select and freeze Fly A before training Fly B on the same preregistered seed and train/validation inputs.

- [x] Fly B loads the source-checked selected Fly A checkpoint and keeps all Fly A parameters frozen during classification training.
- [x] Fly B fits only train labels; validation Macro-F1, then validation loss and earlier epoch select its checkpoint. No joint Fly A/Fly B fine-tuning occurs.
- [x] Per-class metrics, confusion matrix, fixed taxonomy order, selected checkpoint and reload agreement are recorded for seeds 42, 1337 and 2026.
- [x] All three run manifests record zero test inputs and `test=not_run`; the M3.4 validation comparison consumes only their saved validation outputs.

## Comments

- 2026-10-26: Opened after verifying the Windows E5 gate, M2.2b train/validation embeddings, M2.3 checkpoint, and M1.3 32+32 I/O manifest. The first run is pinned to T=2 and seed 42 per Spec v0.2; no test text has been sent to any model.
- 2026-10-26: Installed the hash-locked PyArrow 26.0.0 wheel only in the isolated `%TEMP%/flycall-m22b/venv` environment. Importing `pyarrow.parquet` failed because Windows Application Control blocked `pyarrow.lib` (`DLL load failed ... 應用程式控制原則已封鎖此檔案`). No Parquet rows were opened and schema/row validation did not begin; no Fly A/B training or test-split access occurred. See [M3.2 Windows Parquet runtime gate report](../research/m3-2-pyarrow-application-control-block-20261026.md). Resume only with an approved runtime; no policy workaround was attempted.
- 2026-10-26: Follow-up read-only SHA-256 preflight hashed raw file bytes without decoding Parquet. `nodes.parquet` (`a8ad1e6a…87428`) and `edges.parquet` (`afa69be2…e2175`) match the M1.2 output hashes. Current M1.2 `manifest.json` is `4edcb82d…b7a88` versus the pinned `5300c6ce…69cf40`; current M1.3 `io_manifest.json` is `440f6876…cbab8` versus the pinned `48148a1d…e07f585`. The I/O manifest itself still refers to the old M1.2 manifest hash. No data rows were parsed, and no graph tensors or training artifacts were produced. Provenance needs reconciliation; the mismatch is not silently accepted.
- 2026-10-26: Implemented `src/flycall_data/fly_ab_training.py` as a train/validation-only trainer seam. Fly A is label-free and selected by minimum validation distance stress; Fly B loads a source-checked Fly A checkpoint, freezes it, and selects by validation Macro-F1 / loss / epoch. Checkpoints preserve the latest valid state atomically and record source hashes and training settings. Six synthetic in-memory trainer tests pass, including test-split rejection, deterministic A reload, frozen A, provenance mismatch rejection, non-finite failure preservation, and train/validation family isolation. These tests do not construct or train on the M1.3 graph.
- 2026-10-26: Revalidated the corrected E5 cache manifest without reading transcripts: 850 entries resolve to cache, 700 train / 150 validation, 384 dimensions, nine pinned model file hashes, zero cache-vector hash mismatches, and test downstream counts remain zero. `git` history shows the current graph manifest and I/O manifest were added together in commit `3093c5a`; the older pinned manifest hashes are not available in the tracked history. This explains the provenance gap but does not authorize rewriting either manifest or the M3.0 pin.
- 2026-10-26: Added `src/flycall_data/m32_inputs.py` with fail-closed M1.2/M1.3 pin, raw artifact, graph schema, topology and E5 cache-entry validation. The hash mismatch exits before importing a Parquet reader. Added `scripts/run_m3_2_fly_ab_provisional.py`: it pre-registers the seed/configuration, validates the corrected M2.2b run manifest and cache provenance, applies Windows resource checks, writes train/validation-only checkpoints, metrics, per-class report and reload comparison when all gates pass. Added public source-checked checkpoint loaders and made the evaluator report the registered candidate name. The runner has not been executed against graph rows; the OS and provenance blocks remain, and no test data was used.
- 2026-10-26: Added three graph provenance/runtime gate tests and two runner tests. The selected M2/M3 regression suite passed 82/82. The actual cache input loader resolved the corrected E5 artifact into 700/150 Fly A and Fly B splits (384 dimensions; zero test records in the returned splits). No encoder, graph model, or test input was used by this check.
- 2026-10-26: Executed the registered M3.2 runner preflight as [run `m3-2-fly-ab-provisional-20261026T-gate-check`](../runs/m3-2-fly-ab-provisional-20261026T-gate-check/report.md); it recorded `blocked` at `graph-provenance-preflight`, before dataset/cache loading or Parquet reader import. The report and run manifest show 0 model inputs and test `not_run`. No graph rows or model training were produced.
- 2026-10-26: Added a positive `--seed` option for the M3.4 multi-seed plan. Seed and candidate name are recorded before graph preflight; the graph and Windows runtime gates remain unchanged.
- 2026-10-26: Reconciled the apparent manifest pin mismatch without editing either manifest or pin. Working-tree manifest SHA values differed because Windows checked out CRLF; LF-normalized bytes exactly match both pinned SHA-256 values and Git HEAD. Added normalization regression coverage while retaining raw byte hashes for Parquet. In the subsequent run, the earlier Application Control denial did not reproduce: PyArrow 26.0.0 successfully decoded the graph in the existing isolated environment. No policy workaround, relocation, or trust-rule change was used.
- 2026-10-26: First real-graph seed-42 attempt completed training but was marked failed only when the success message tried to print the Chinese absolute workspace path through the legacy Windows console encoding. Kept that failed run unchanged for audit and fixed runner output to print an ASCII-safe project-relative path.
- 2026-10-26: Completed validated runs for seeds 42, 1337 and 2026. Reports are at `../runs/m3-2-fly-ab-seed-42-crlf-fix-20261026/report.md`, `../runs/m3-2-fly-ab-seed-1337-20261026/report.md`, and `../runs/m3-2-fly-ab-seed-2026-20261026/report.md`. All use 700 train / 150 validation, reload exactly, and preserve test `not_run` / 0 inputs. Each training portion took 6.4–9.0 seconds on this machine.
- 2026-10-26: Spec audit mapped the separate M3.3 requirement to the Fly B implementation and real-graph runs already delivered here. Added explicit M3.3 acceptance coverage above; no additional training or test access was performed.
- 2026-10-26: Replaced POSIX-only peak-RSS reads in M1.3 and M1.2 utilities with a shared Windows/POSIX measurement helper after Windows test discovery exposed `resource` import failures. Installed the already-declared DuckDB 1.5.6 dependency into the isolated E5 environment using a writable `%TEMP%` uv cache. Full `unittest` discovery then passed 131/131 tests. The M1.2 output-boundary check now runs before source-file existence validation, so it is independent of the external, untracked Parquet artifact.

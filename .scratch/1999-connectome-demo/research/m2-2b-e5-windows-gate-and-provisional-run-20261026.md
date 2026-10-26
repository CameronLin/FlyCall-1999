# M2.2b E5 Windows resource gate and provisional run

**Date:** 2026-10-26 (Asia/Taipei)

**Decision:** E5 CPU resource gate passed on this Windows computer for the pinned model, 512-token limit, and batch size 1.
**Data status:** synthetic, `pending_manual_review`; all reported classification values are `smoke_test/provisional`.

The 2026-10-21 macOS snapshot remains valid historical evidence for that computer. It does not describe this Windows machine. The new gate uses the same safety limits: at least 1 GiB available physical RAM and commit, less than 90% memory load, at least 4 GiB free project disk, and no process working set above 3.5 GiB.

## Environment and gate evidence

| Measure | Before E5 load | After full train/validation run | Gate |
|---|---:|---:|---|
| Platform | Windows 11, build 10.0.26200, AMD64 | Same | — |
| Python | CPython 3.14.3 x64 | Same | Direct interpreter; system Python unchanged |
| Physical RAM | 15.71 GiB total; 6.33 GiB available | 5.66 GiB available | Pass; above 1 GiB |
| Windows memory load | 59% | 63% | Pass; below 90% |
| Available commit | 4.80 GiB | 4.10 GiB | Pass; above 1 GiB |
| Project disk free | 774.98 GiB | 774.94 GiB | Pass; above 4 GiB |
| Process peak working set | — | 1,332,563,968 bytes (1.24 GiB) | Pass; below 3.5 GiB |
| Process peak pagefile | — | 2,405,568,512 bytes (2.24 GiB) | Recorded |

The isolated CPython 3.14.3 x64 environment resolved a 43-package, hash-locked CPU dependency set and passed integrated imports. The venv occupied approximately 828.5 MiB. The environment and Hugging Face cache stayed under `%TEMP%\flycall-m22b`; neither the venv nor model weights were added to the repository. See [`requirements-m2-2b-e5-windows.in`](../requirements-m2-2b-e5-windows.in) and [`requirements-m2-2b-e5-windows.lock`](../requirements-m2-2b-e5-windows.lock).

## Pinned model runtime

- Model: `intfloat/multilingual-e5-small`, revision `614241f622f53c4eeff9890bdc4f31cfecc418b3`.
- The local snapshot contains exactly the nine required inference files, totaling `492,795,290` bytes; each file size and SHA-256 is checked by [`e5_runtime.py`](../../../src/flycall_data/e5_runtime.py). The three large files match the hashes recorded from the pinned revision metadata.
- Runtime loaded locally with network access disabled, `trust_remote_code=false`, CPU, one Torch thread, and batch size 1. The model is frozen. Runtime confirmed Transformer → masked mean Pooling → Normalize, output dimension 384, and unit-length vectors.
- Tokenizer class: `XLMRobertaTokenizer`; internal normalizer: `Precompiled`, SHA-256 `c1944f72967dbd5754934af4c2d87d050c6fb4e8a8321b607b0edc4f57ec6c23`; truncation side: right.
- Of the 850 train/validation inputs, zero were truncated; the longest effective input was 334 tokens. Per-record raw/effective token counts are in each run's `tokenization_diagnostics.csv`.

## Train/validation run

Candidate settings, including seed 42 and PCA `k=32`, were written to `pre_registered_candidates.json` before the data loader ran. The frozen manifest supplied 700 train and 150 validation records. The loader audited the full source contract, but the model workflow received only train/validation transcript text. Test transcript count passed downstream was zero; test embeddings, predictions, and metrics remain `not_run`.

The full embedding run is [`m2-2b-e5-provisional-20261025T184820Z`](../runs/m2-2b-e5-provisional-20261025T184820Z/). It generated `6,873,061` cache bytes and spent 132.45 seconds encoding. The first cache-hit rerun, [`m2-2b-e5-provisional-20261025T185218Z`](../runs/m2-2b-e5-provisional-20261025T185218Z/), completed but its per-vector manifest hashes exposed a cache-hit normalization drift; treat that run as superseded for exact cache provenance. The corrected run is [`m2-2b-e5-provisional-20261026T015843Z`](../runs/m2-2b-e5-provisional-20261026T015843Z/): all 850 cached vectors match their manifest SHA-256 values exactly, it added zero cache bytes, and all source checksums remained unchanged. Candidate validation metrics match the first full run. The first run had already written its outputs before PowerShell's legacy console encoding failed to print a Chinese path.

| Candidate | Train accuracy / Macro-F1 | Validation accuracy / Macro-F1 |
|---|---:|---:|
| Embedding → Logistic Regression | 1.000 / 1.000 | 0.873 / 0.868 |
| Embedding → MLP | 0.999 / 0.999 | 0.920 / 0.918 |
| Embedding → PCA(32) → MLP | 0.997 / 0.997 | 0.907 / 0.906 |
| Embedding → LDA(4) → Logistic Regression | 1.000 / 1.000 | 0.900 / 0.900 |

The LDA→Logistic Regression checkpoint reload reproduced validation predictions and fixed-order scores exactly. All source checksums were unchanged. Complete per-class scores, supports, confusion matrices, errors, package versions, settings fingerprint, output checksums, and resource snapshots are in the run artifacts.

These numbers are exploratory results on synthetic data that has not passed manual review. They are not formal performance claims and do not select a final model. No test text entered a tokenizer, encoder, cache, fit, transform, predict, or metrics path.

## Follow-up state

The Windows E5 resource gate is unblocked. M2.2b implementation and provisional scope are complete, including runtime and model-file hash cache-key regression coverage. M2.3 provisional E5/LDA run and checkpoint validation are complete. The M2.4 durable one-use test ledger is implemented and fixture-regression-tested. Formal test evaluation remains gated until the manual review quality gate passes and candidate/configuration approval is recorded.

### Windows regression closeout

On 2026-10-26, the selected M2 regression suite passed **58/58 tests**: E5 runtime (7), evaluation/ledger (17), embedding pipeline (9), embedding Logistic Regression (3), embedding PyTorch baselines (2), LDA baseline (6), text baselines (5), and frozen dataset loader contract (9). The new cache regression proves a hit preserves the exact stored vector and rejects a non-normalized cache payload. An additional **19/19 M3 graph/trainer fixture tests** passed (Fly A/B training 6; graph core 13). Loader tests read frozen sources to validate the data contract; no formal test text entered tokenization, embedding, model fitting/prediction, or formal test metrics. Synthetic test fixtures were used only to verify evaluator authorization and Fly A/B training behavior.

The corrected E5 rerun used only the 700 train and 150 validation cache entries; test input, embeddings, predictions, and metrics remain zero / `not_run`. The fixture trainer tests do not validate the separately blocked M3.2 Parquet/Application Control path or constitute training on the real M1.3 graph.

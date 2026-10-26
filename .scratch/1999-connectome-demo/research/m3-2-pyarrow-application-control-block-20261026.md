# M3.2 Windows Parquet runtime gate

**Date:** 2026-10-26 (Asia/Taipei)

**Result:** blocked before decoding graph data.
**Scope:** isolated-runtime import and raw checksum preflight; no Parquet rows, test split, or model training.

The M3.2 dependency lock resolved PyArrow `26.0.0` for the existing isolated CPython 3.14.3 x64 CPU environment. The wheel was installed under `%TEMP%/flycall-m22b/venv`; this did not modify the system Python installation or repository runtime.

The import preflight for `pyarrow.parquet` failed while loading `pyarrow.lib` with a Windows DLL load error stating that Application Control blocked the file. This is an operating-system application-control denial, not a Parquet schema or data error.

## Raw checksum preflight without Parquet decoding

After the blocked import, SHA-256 was calculated over the raw file bytes only. No Parquet reader was invoked for this check.

| File | Current SHA-256 | Previously recorded SHA-256 | Result |
|---|---|---|---|
| `nodes.parquet` | `a8ad1e6a42c0a386d4bdef517ac628c29a5b7b8f023c51b43cce8e0354087428` | Same | Match |
| `edges.parquet` | `afa69be2078eaf136d00511539145dc82ea54af5aa2f52ffdcb87501488e2175` | Same | Match |
| M1.2 `manifest.json` | `4edcb82d6f5f88c5e8afac62a948368a0d50a87b1c443e0ad91e1e30605b7a88` | `5300c6cefdc6b84a854545e64f4131baa3fc42f0bde97a83f68fcc1c3769cf40` | Mismatch |
| M1.3 `io_manifest.json` | `440f6876822d3f36ce7cd34bb250da2a0a532fbbfdd11bdac182fa4b154cbab8` | `48148a1d64cc5402b17db99dff61ad42a3c29bef8d422ebfa6a25e375e07f585` | Mismatch |

The current I/O manifest's `source_graph.manifest_sha256` still records the old M1.2 manifest hash. Its ordered I/O lists contain 32 unique inputs and 32 unique outputs with no overlap, but the manifest checksum mismatch means that list is not accepted as the pinned M3.0 artifact until provenance is reconciled. The current M1.2 manifest's output hashes agree with the actual Parquet byte hashes; this does not resolve manifest identity or replace schema validation.

Because the native extension did not load:

- `nodes.parquet` and `edges.parquet` were not opened by a Parquet reader. Their bytes were read only for raw SHA-256; no graph rows were parsed.
- Raw Parquet file checksums match the recorded M1.2 output checksums, but manifest identity hashes do not match earlier pinned values.
- No E5 cache rows were combined with graph data.
- No Fly A or Fly B optimizer step, checkpoint, validation metric, or test input was produced.
- No attempt was made to unblock, relocate, rename, or otherwise bypass the denied native extension.

## M3.2 execution path prepared

The train/validation-only trainer, graph/cache input gates and pre-registered runner are now implemented:

- `src/flycall_data/m32_inputs.py` checks the pinned manifest bytes before any Parquet reader import. If pins pass, it verifies raw Parquet SHA-256 values, exact schemas, row counts, endpoints, I/O order and the M3.0 topology contract before returning a graph.
- The E5 loader resolves only the 700 train and 150 validation records against transcript hashes, cache keys, unit-vector values and the corrected embedding manifest. The runner additionally checks the M2.2b run manifest and confirms its recorded test counts remain zero / `not_run`.
- `scripts/run_m3_2_fly_ab_provisional.py` writes the preregistration before reading sources, checks resources, trains CPU-only Fly A then frozen-A Fly B, and saves checkpoints, predictions and metrics for train/validation only. It also records reload comparisons and renders per-class metrics and confusion matrices.

The runner's actual preflight was executed as [run `m3-2-fly-ab-provisional-20261026T-gate-check`](../runs/m3-2-fly-ab-provisional-20261026T-gate-check/report.md). It wrote preregistration and run records, then stopped at `graph-provenance-preflight` because the M1.2/M1.3 manifest hashes differ from their locked values. The run manifest records zero model inputs and test `not_run`; dataset/cache loading and the Parquet reader were not reached. No PyArrow policy bypass or provenance rewrite was made.

Separately, the new E5 cache input loader was run against the frozen dataset and corrected E5 cache. It returned Fly A and Fly B splits with 700 train records, 150 validation records, 384 dimensions and zero test records. This loaded cached vectors only; it did not call the encoder, graph model, or test split. The selected M2/M3 regression suite passed 82/82, including five new synthetic graph-gate and runner tests. These results do not constitute real-graph training or test the runner past the current provenance stop.

M3.2 remains blocked until the graph manifest provenance is authoritatively reconciled and the machine has a Windows-approved Parquet runtime. After both gates pass, the runner performs schema/row checks before constructing graph tensors and follows the locked train/validation-only boundary and resource checks. Example invocation after installing the hash-locked dependencies in an approved environment:

```powershell
python -m pip install --require-hashes -r .scratch/1999-connectome-demo/requirements-m3-2-fly-ab-windows.lock
python scripts/run_m3_2_fly_ab_provisional.py
```

## Follow-up: Windows checkout and current runtime verification

The blocked result above records the first attempt. A read-only comparison later established that both original manifest pins match the Git `HEAD` blobs and the current manifest content when CRLF is normalized to LF:

| Manifest | LF-normalized SHA-256 | Pinned SHA-256 | Git `HEAD` SHA-256 |
|---|---|---|---|
| M1.2 `manifest.json` | `5300c6cefdc6b84a854545e64f4131baa3fc42f0bde97a83f68fcc1c3769cf40` | Same | Same |
| M1.3 `io_manifest.json` | `48148a1d64cc5402b17db99dff61ad42a3c29bef8d422ebfa6a25e375e07f585` | Same | Same |

The working-tree byte hashes differed only because Windows checked out CRLF. The M3.2 gate now normalizes CRLF only for these UTF-8 manifest-content pin checks; it continues to validate Parquet SHA-256 over exact raw bytes. No source manifest, graph artifact, or pinned digest was changed. A regression test covers CRLF checkout behavior and content mismatches still fail before Parquet import.

On a subsequent run in the existing isolated `%TEMP%/flycall-m22b/venv`, PyArrow 26.0.0 successfully loaded the same Parquet native extension and decoded the pinned graph. The earlier Application Control denial did not reproduce; no relocation, rename, policy bypass, or trust-rule change was attempted. The first seed-42 training completed but its run was retained as `failed` because printing the Chinese absolute workspace path raised a Windows console encoding error after all artifacts had been generated. The runner now reports an ASCII-safe project-relative path, and seed 42 was rerun cleanly.

Three completed provisional M3.2 runs are now available:

- [Seed 42](../runs/m3-2-fly-ab-seed-42-crlf-fix-20261026/report.md)
- [Seed 1337](../runs/m3-2-fly-ab-seed-1337-20261026/report.md)
- [Seed 2026](../runs/m3-2-fly-ab-seed-2026-20261026/report.md)

Each run used the 500-node / 2,216-edge graph, 700 train / 150 validation embeddings, and CPU-only Fly A then frozen-A Fly B training. Checkpoint reload passed with zero maximum absolute difference for validation representations and logits; checksummed outputs include graph definition, training history, metrics and train/validation predictions. Each run records test `not_run`, zero test model inputs, synthetic data, and `pending_manual_review`. Training took 6.4–9.0 seconds per seed. These provisional runs do not authorize formal claims or the one-time test gate.

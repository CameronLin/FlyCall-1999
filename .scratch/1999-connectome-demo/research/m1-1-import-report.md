# M1.1 MaleCNS v1.0 edge/node import report

**Date:** 2026-10-13  
**Status:** completed  
**Scope:** M1.1 only. No subgraph, M1.2, model, or case-data work was performed.

## Source and contract

- Source: `data/connectome/malecns_v1.0/connectome-weights-male-cns-v1.0-minconf-0.5.feather`
- GCS generation: `1780494887545976`
- Source size: `1,051,241,946` bytes
- Source SHA-256 before and after import and full output verification: `e35da783d1c686b2b58b3b87cd6a403ae43bfcfba8bff28e08ef752c1a56afc1`
- Mapping: `body_pre -> source_id`, `body_post -> target_id`, `weight -> weight`.
- `nodes.parquet` uses `node_id` for the unique endpoint set and does not imply a neuron, region, or cell-type annotation.
- The exact upstream `minconf-0.5` predicate remains unknown. The importer uses the selected source as published and adds no filter.

## Implementation and reproducibility

- Public functions: `iter_normalized_edges(path, batch_rows)` maps source fields and preserves every input row; `write_standard_tables(source_path, output_dir, batch_rows)` performs global duplicate-pair aggregation and writes the three outputs.
- Global aggregation uses a disk-backed DuckDB table and `GROUP BY`, with a 2 GiB memory cap, 2 threads, and disk spill. Node IDs are produced from both endpoints of the aggregated edge table, externally sorted, then deduplicated as a streaming Parquet write. No 151,856,684-row table is loaded into RAM.
- Read batch size: 65,536 rows. The Feather original was not copied, moved, or written.
- Dependencies: PyArrow `26.0.0`; DuckDB `1.5.6`, pinned in `requirements-connectome.txt`.
- Reproduce import: `uv run --no-project --with-requirements requirements-connectome.txt python3 scripts/import_malecns_v1.py --batch-rows 65536`
- Reproduce full output verification: `uv run --no-project --with-requirements requirements-connectome.txt python3 scripts/verify_malecns_import.py`
- Run tests: `PYTHONPATH=src uv run --no-project --with-requirements requirements-connectome.txt python3 -m unittest discover -s tests -v`

## Full import results

| Output | Rows | Schema | Bytes | SHA-256 |
|---|---:|---|---:|---|
| `data/connectome/derived/malecns_v1.0/edges.parquet` | 151,856,684 | `source_id:int64,target_id:int64,weight:int64` | 582,837,207 | `d32d5be692b127e8b9132e418bbfc4a13fbc36e2f5fabc90293a1f04d5f133aa` |
| `data/connectome/derived/malecns_v1.0/nodes.parquet` | 88,384,522 | `node_id:int64` | 102,750,196 | `71601532b54b5fd8fba108681148a5f791f9c6c69885ed0b124e3750f84fb654` |
| `data/connectome/derived/malecns_v1.0/import_manifest.json` | — | JSON | 2,258 | — |

- Source rows: `151,856,684`; unique output pairs: `151,856,684`; duplicate rows aggregated: `0` after a full-dataset group-by.
- Input and output total weight: `311,833,243` each.
- Self-loop source rows: `123`; output self-loop pairs: `123`; self-loop weight sum: `542`.
- The full verifier streamed every edge and node Parquet row. It checked schemas, nulls, positive weights, row counts, full weight and self-loop sums, strict ordering/uniqueness, manifest fields, output checksums, and source hash. Result: passed.
- Unit tests: 15 passed, including six importer fixture tests for direction mapping, preserved input rows, cross-batch duplicate aggregation, self-loop retention, node deduplication, schema/null/weight errors, exact output schema, and source checksum invariance.

## Resource audit

- Physical RAM from `sysctl -n hw.memsize`: `8,589,934,592` bytes (8 GiB). The command required elevated read-only access because sandboxed `sysctl` returned “Operation not permitted”.
- Source and output are on the same volume. Before the compliant run, `df` showed approximately 23.15 GiB free; the import manifest recorded `24,862,359,552` free bytes.
- Conservative total peak extra-disk estimate: `18,081,690,432` bytes (`16.84 GiB`), based on 112 bytes per source row plus 1 GiB safety allowance. Estimated free space after that budget: `6,780,669,120` bytes (`6.31 GiB`).
- The manifest records `2,732,163,539` bytes of staging files immediately before DuckDB cleanup. This is a measured snapshot, not a guaranteed process-wide peak. Staging was removed after the run; no `.malecns_v1.0.staging-*` directory remains.
- Current output directory size: `685,589,661` bytes. Current free disk at final check: approximately `21.54 GiB`.

## Resource-check rerun record

The first DuckDB full run completed while the requested resource audit was being collected. Its manifest showed 4 threads, above the subsequently specified maximum. No process or staging directory remained when inspected. The output was verified against its manifest and source, then preserved without deletion at `.scratch/1999-connectome-demo/m1-1-resource-audit-unapproved-threads-4/malecns_v1.0/`. The importer was set to 2 threads, the full unit suite passed again, and the compliant import was rerun to the canonical output path. The compliant output passed the independent full verifier. Its edge and node checksums match the quarantined run.

## Remaining issue

- The precise upstream confidence predicate behind the published `minconf-0.5` filename is still undocumented in the source records. No inference or additional filtering was applied; this remains outside M1.1's import contract.

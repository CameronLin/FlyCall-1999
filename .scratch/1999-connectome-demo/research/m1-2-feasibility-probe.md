# M1.2 bounded subgraph feasibility probe

**Initial probe date:** 2026-10-13  
**Plan addendum date:** 2026-10-15  
**Ticket status:** in-progress  
**Result type:** bounded feasibility evidence only; no formal subgraph was published.

## Scope and method

Used only the canonical M1.1 output `data/connectome/derived/malecns_v1.0/edges.parquet`. The quarantined `m1-1-resource-audit-unapproved-threads-4/` output, source Feather, and 1999 case data were not used or changed.

`probe_induced_subgraph(edges_path, seed_node_id, node_limit, max_scan_edges, output_dir)` is an exploratory M1.2 test seam, not a frozen public API. The probe performs one DuckDB Parquet query per seed, with `LIMIT max_scan_edges`, and builds a sparse adjacency map from only the returned rows. BFS treats each edge as undirected for node selection; induced edge rows retain their original direction and weight. It does not rescan the Parquet for each BFS layer and does not build a dense adjacency matrix.

Each call had `node_limit=500` (a provisional probe cap, not an approved final graph size) and `max_scan_edges=50,000`. Four distinct seed calls plus one reproducibility rerun processed at most 250,000 logical edge rows, about 0.165% of the 151,856,684-row table. Each query was capped at 50,000 returned rows. The first Parquet row group contains 65,536 rows and has 201,170 compressed bytes across the three columns; conservatively, five bounded calls could read up to five row groups (327,680 physical row-group rows, about 0.216% of the table and approximately 1,005,850 compressed bytes). This is storage-granularity overhead; the BFS only received the exact 50,000-row cap per call.

If a call returns exactly its cap, the implementation conservatively reports `status=incomplete` and `completeness_reason=budget_exhausted`, even if a particular prefix happens to contain a complete component. It never labels a capped-prefix search as a complete full-graph BFS.

## Fixture tests

Tests were written before the implementation. The first run failed as expected because `flycall_data.subgraph_probe` did not exist. After implementation, all seven M1.2 fixture tests passed, covering undirected BFS over directed rows, direction and weight preservation, the hard node limit, induced-edge filtering, absent seed, budget exhaustion with actual scanned count, deterministic repeat, non-formal artifact labeling, and refusing an official M1.1 output destination.

Commands:

```sh
PYTHONPATH=src uv run --no-project --with-requirements requirements-connectome.txt python3 -m unittest discover -s tests -p test_subgraph_probe.py -v
PYTHONPATH=src uv run --no-project --with-requirements requirements-connectome.txt python3 -m unittest discover -s tests -v
```

Full suite result: **22 tests passed**.

## Resource check and integrity

Immediately before the real-data probe:

- `sysctl -n hw.memsize`: `8,589,934,592` bytes (8 GiB physical RAM).
- `df -k . /private/tmp`: `22,581,540` KiB available on the shared data volume (about 21.54 GiB); the temp path was on the same volume.
- M1.1 output directory allocation: `687,700` KiB.
- DuckDB: `1.5.6`, configured to `memory_limit='2GB'`, `threads=2`; PyArrow: `26.0.0`.
- Query is a limited sequential Parquet scan with no aggregation, sorting, spill, or disk-backed temporary database. Expected persistent probe output was five small JSON summaries, under 50 KiB total.

`/usr/bin/time -l` maximum resident set for the three-strategy process was `133,939,200` bytes (about 127.7 MiB); the reproducibility rerun peaked at `114,835,456` bytes. No whole-table or whole-node collection was loaded into memory.

M1.1 hashes immediately before and after the probes match:

| File | SHA-256 before | SHA-256 after |
|---|---|---|
| `edges.parquet` | `d32d5be692b127e8b9132e418bbfc4a13fbc36e2f5fabc90293a1f04d5f133aa` | same |
| `nodes.parquet` | `71601532b54b5fd8fba108681148a5f791f9c6c69885ed0b124e3750f84fb654` | same |
| `import_manifest.json` | `3633fbfb463e5fc87345cfd76522c884909816c2a028c4aac91c70f18c984d85` | same |

After the probes and final checksum check, `df` showed `21,506,440` KiB available (about 20.51 GiB). The M1.2 probe directory uses 40 KiB allocated for five JSON summaries (34,549 bytes of file contents); no Parquet graph, DuckDB spill, or temporary database was written. Free space fell by `1,075,100` KiB (`~1.03 GiB`) between the pre-probe and final snapshots, far more than the probe artifacts; the change cannot be attributed to the probe output alone. No model was downloaded or loaded.

### Follow-up check of the disk-space decrease (2026-10-15)

Only the relevant M1.2 scratch path, M1.1 derived-data directory, UV cache, and shared-volume free space were inspected. No files were removed.

| Item | Current observation |
|---|---:|
| Free space on the volume containing the project and `/private/tmp` | `18,128,600` KiB (`~17.29 GiB`) |
| M1.2 probe directory | `40` KiB allocated |
| M1.1 derived-data directory | `673,824` KiB allocated |
| `/Users/linyifen/.cache/uv` | `1,207,940` KiB (`~1.15 GiB`) |

The UV cache is a plausible contributor to the earlier `~1.03 GiB` reduction because its present size is of the same order, while the probe artifacts are only 40 KiB. There is no pre-probe UV-cache size snapshot, so this does **not** prove the cache caused the exact decrease. Since the prior post-probe snapshot, free space has also fallen by another `3,377,840` KiB (`~3.22 GiB`); the inspected task paths do not explain that additional change. Its cause remains unknown. The cache and all other files were left untouched.

## Prefix scope correction

All five real-data probe results in the table below came from the **first 50,000 rows of the sorted `edges.parquet` table**, using the same beginning prefix for each call. The “uniform seeded” candidate was drawn only from endpoints observed in that prefix. Every reported weak degree—including the median and maximum—was computed only within that prefix. Thus these are **prefix-local** candidate and degree results. They validate that the probe API handles bounded input, enforces its node/row limits, reports `incomplete / budget_exhausted`, and repeats deterministically. They are **not** evidence for a full-graph seed policy, global weak-degree ranking, full-graph connectivity, or the size/connectivity of a 500-node neighborhood.

## Bounded-prefix seed comparison

All results below are based on the first 50,000 rows returned from the Parquet table, not a global graph scan. The row-group metadata shows this prefix is concentrated in low source IDs (`source_id` range 10001–10009 in row group 0), so its degree and connectivity patterns are strongly biased.

| Candidate policy | Explicit seed | Weak degree (first-50,000-row prefix only) | Nodes selected (limit 500) | Prefix induced edges | Status | Induced edge SHA-256 |
|---|---:|---:|---:|---:|---|---|
| Baseline: first source ID in row group 0 | 10001 | — | 500 | 499 | `incomplete / budget_exhausted` | `265151c4da94baa67d07547475e629f3923f402a0717e2af2bc06bf93ece34b0` |
| Uniform seeded draw from endpoints observed in the prefix only; RNG seed 20261013 | 768937310 | 1 | 500 | 499 | `incomplete / budget_exhausted` | `792a3e63744e20628c2412105f7495c304b2915f470eabc7edba0aded6683f28` |
| Median weak-degree endpoint within the prefix | 278922342 | 1 | 500 | 499 | `incomplete / budget_exhausted` | `812c6ced74b30f47c9d9f04deb8473d22c81f27366b543a272762f1b78b57944` |
| Highest weak-degree endpoint within the prefix; ties by smallest ID | 10003 | 14,983 | 500 | 499 | `incomplete / budget_exhausted` | `4c25d9fa2429fc4ef141b597b3880a47d71849d5c37dca956c5eba1a0c19df3d` |

The high-degree seed rerun selected the identical node IDs and reproduced the same induced-edge checksum. The equal 500-node/499-edge outcomes are properties of this truncated prefix and selection cap only; they are not estimates of full-graph connectivity or evidence for a seed policy. The prefix-local seed comparisons remain API-validation fixtures, not approved or globally evidenced seed policies.

Probe result files (each explicitly marked `is_formal_subgraph: false`):

- `.scratch/1999-connectome-demo/probes/m1-2/prefix-50000-seed-10001/probe_result.json`
- `.scratch/1999-connectome-demo/probes/m1-2/uniform_seeded_from_observed_nodes/probe_result.json`
- `.scratch/1999-connectome-demo/probes/m1-2/median_weak_degree_in_bounded_prefix/probe_result.json`
- `.scratch/1999-connectome-demo/probes/m1-2/highest_weak_degree_in_bounded_prefix/probe_result.json`
- `.scratch/1999-connectome-demo/probes/m1-2/repeat-high-degree-10003/probe_result.json`

## Decisions still open

- No seed policy was selected. Uniform endpoint sampling, degree-stratified selection, and high-degree selection have different coverage and hub-bias tradeoffs; the prefix probe cannot resolve them.
- The spec's 500-node target remains provisional. This bounded-prefix experiment does not validate a 500-node subgraph on the complete graph.
- The current M1.1 node/edge tables do not contain verified brain-region annotations; region-constrained selection remains unavailable without a trustworthy annotation source.
- No full-graph BFS, formal node/edge output, 1,000/2,000-node nested comparison, or M1.3 I/O reachability check was performed.

## Proposed next phase: full-data probe plan (not executed)

This section is a proposal for review only. No new full-table scan, degree computation, or graph output was run for this addendum. The current M1.2 ticket remains `in-progress`.

### 1. Reproducible seed candidates from the complete node table

Use the complete `nodes.parquet` population (`88,384,522` rows) and its Parquet row-group row counts. A proposed reproducible uniform candidate set is 8 node positions sampled without replacement from `[0, N)` with a recorded fixed RNG algorithm and seed (suggested seed: `20261015`). Map each sampled position through cumulative row-group counts, read only the corresponding row groups, and select the exact in-row-group offset. Record the selected positions, IDs, seed, RNG implementation/version, and source checksum. This avoids assuming that node IDs are uniformly distributed and does not draw from the low-ID edge prefix. If multiple positions map to the same row group, read that row group once.

After a full weak-degree index exists, compare separate deterministic candidates: 3 candidates sampled from each of the low, middle, and high degree strata, plus the 3 highest-degree nodes with ties broken by ascending `node_id`. This gives 20 candidates total (8 uniform + 9 stratified + 3 highest-degree) for a comparison only; it does not select or approve a seed policy. All selected IDs must be present in the complete node table. The node table is not loaded wholesale.

### 2. Proposed full-graph weak degree and evidence for high-degree seeds

Define the weak neighbors of node `v` as distinct nodes `u != v` for which at least one directed edge `(v,u)` or `(u,v)` exists. Define `weak_degree(v)` as the count of these distinct neighbors, ignoring weight. Reciprocal directed edges count as one weak neighbor. A self-loop `(v,v)` contributes zero to weak degree, although it remains eligible for retention in the final directed induced-edge output. Include every node from `nodes.parquet` in the degree table; assign degree zero if a node has no non-self neighbor.

Prefix degree counts are not enough to identify a high-degree seed. Obtain global evidence by reading every row of the official `edges.parquet` once in Arrow batches, emitting both endpoint orientations for non-self edges, externally deduplicating `(node_id, neighbor_id)` pairs (to collapse reciprocal input edges), and externally grouping unique neighbors by `node_id`. Use DuckDB `memory_limit='2GB'`, `threads=2`, an explicit scratch `temp_directory`, and a hard temp-space quota. Join the result to the complete node table for zero-degree nodes, then rank by `weak_degree DESC, node_id ASC`. Record source checksums, rows consumed, degree-table checksum, top-degree rows, quantile boundaries, and completion state. Any row, temp-space, or time budget stop before all `151,856,684` source rows are consumed must be reported as `incomplete`; no partial ranking may be called global.

### 3. Bounded exact BFS and complete directed induced edges

Do not rescan all `151,856,684` edges for each BFS layer or each seed. During the full degree pass, materialize a disk-backed weak-adjacency index ordered by `(node_id, neighbor_id)` alongside the degree table. Deduplicate neighbors and use ascending `neighbor_id` as the deterministic traversal order. For each seed, use a queue and visited set in memory; the live set is bounded by the provisional `node_limit=500`. Stop after the deterministic first 500 discovered nodes or after the component is exhausted. A per-seed adjacency-row budget (proposed ceiling: `5,000,000`, with an aggregate ceiling of `50,000,000` across the 20 candidates) is a hard cap. If any needed adjacency rows are unavailable or a cap is reached before that seed's bounded BFS finishes, mark that seed `incomplete / budget_exhausted`; do not describe it as a complete BFS.

After candidate sets are finalized, make one sequential pass over the complete directed `edges.parquet` and route a row to a candidate only when both endpoints belong to that candidate's selected node set. This yields the complete induced directed edges for each completed candidate, preserving original `source_id`, `target_id`, and `weight`, including self-loops. Record consumed source rows; if this pass stops before all `151,856,684` rows, all affected edge outputs are `incomplete` and must remain scratch artifacts. The maximum planned source-table scan is two full passes (`151,856,684` rows for adjacency/degree construction plus `151,856,684` rows for induced-edge extraction); BFS itself reads the disk-backed adjacency index and does not rescan the source table.

### 4. Provisional resource envelope and stop conditions

The source tables currently contain `151,856,684` directed edge rows and `88,384,522` node rows. `edges.parquet` is about 583 MB and `nodes.parquet` about 103 MB. The weak adjacency can require up to `303,713,368` oriented neighbor rows before deduplication, or about 4.86 GB at the uncompressed two-`int64` lower-bound representation. External deduplication/sort spill can exceed that; no full-data spill measurement exists. For planning, cap the M1.2 scratch temporary area at 8 GiB and candidate output at 1 GiB, retain at least 4 GiB free throughout, and refuse to start unless a fresh preflight shows at least 13 GiB available **after** accounting for other known writes. With the latest measured `~17.29 GiB` free, this leaves only about `4.29 GiB` beyond the proposed temp/output caps and reserve, so the estimate is marginal and must be rechecked immediately before any later run. If the external operation reaches its 8 GiB temp cap, stop and report `incomplete`; preserve diagnostic metadata but do not publish graph artifacts.

Use the measured physical RAM of `8,589,934,592` bytes (8 GiB). Keep DuckDB capped at 2 GiB and 2 threads. Plan for no more than about 3 GiB process RSS for the data operation (including Python traversal state and buffers), leaving at least about 5 GiB for macOS and other processes; verify live RSS and system memory pressure before starting. Do not load either full table or an adjacency matrix in RAM.

Two sequential source reads total about 1.17 GB compressed input, but external sorting of up to 303.7 million oriented neighbor rows is the dominant unknown. The bounded 50,000-row probes do not provide a valid throughput benchmark. **Scheduling estimate only:** reserve 30–120 minutes for degree/index construction and induced-edge extraction, explicitly unbenchmarked; stop at a 120-minute wall-clock limit and report `incomplete` if work remains. Before that run, obtain user review of this estimate and perform a fresh resource preflight. Do not download/load models or write under the formal M1.1 directory.

No source pass, index, full-data BFS, or induced-edge output was created for this plan. No M1.1 table or existing probe artifact was modified.

## 2026-10-15 resource preflight and scattered-row-group benchmark

This is a small-sample benchmark only. No full-table scan, formal subgraph, disk-backed adjacency index, or model operation was run. M1.2 remains `in-progress`.

### Resource observations

The host reports `8,589,934,592` bytes physical RAM (8 GiB). The relevant process check found no M1.2/DuckDB probe process running after the benchmark. Both the project and `/private/tmp` are on the same data volume.

| Snapshot | Available KiB | Approx. GiB | Other relevant observations |
|---|---:|---:|---|
| Prior report snapshot | 18,128,600 | 17.29 | Recorded above on 2026-10-15 |
| This preflight, first read | 17,132,352 | 16.34 | `.scratch/1999-connectome-demo`: 673,916 KiB; UV cache: 1,207,940 KiB; `/private/tmp`: 190,044 KiB |
| Immediately before benchmark | 16,110,592 | 15.36 | Same inspected directory sizes; M1.2 probe directory: 40 KiB |
| Immediately after benchmark | 20,292,840 | 19.35 | `.scratch/1999-connectome-demo`: 673,916 KiB; unapproved M1.1 audit output: 673,824 KiB; official M1.1 directory: 673,824 KiB; UV cache: 1,207,940 KiB; `/private/tmp`: 190,044 KiB; M1.2 probe directory: 40 KiB |

The available-space observations moved down by `1,021,760` KiB (`~0.97 GiB`) between the first and pre-benchmark reads, then up by `4,182,248` KiB (`~3.99 GiB`) by the post-benchmark read. The inspected project scratch, formal M1.1, UV cache, `/private/tmp`, and M1.2 probe directory sizes did not change across the relevant snapshots. The evidence does not identify the cause of the prior `~3.22 GiB` reduction or these newer movements; no cause is inferred and no files were deleted.

The extra `.scratch/1999-connectome-demo/m1-1-resource-audit-unapproved-threads-4/` tree is present and occupies `673,824` KiB. It was not opened or used. Its current size is recorded only as disk-usage evidence; no earlier size snapshot establishes when it was created.

### Fixed-seed row-group sample

The benchmark ran offline with PyArrow `26.0.0` and DuckDB `1.5.6`, using DuckDB `memory_limit='2GB'`, `threads=2`, and `max_temp_directory_size='8GB'`. RNG seed: `20261015`. It read only selected row groups from the canonical M1.1 files; it did not use the unapproved audit output.

| Table | Total row groups | Selected row groups | Rows sampled | Compressed row-group bytes | Observed ID range |
|---|---:|---|---:|---:|---|
| `edges.parquet` | 2,318 | 42, 122, 165, 795, 812, 865, 1803, 1970 | 524,288 (8 × 65,536) | 1,847,532 | `source_id`: 10,253–808,545; `target_id`: 10,001–1,571,861,432 |
| `nodes.parquet` | 1,349 | 21, 61, 82, 406, 432, 901, 985, 1249 | 524,288 (8 × 65,536) | 605,574 | `node_id`: 116,235,406–1,364,954,538 |

The edge sample formed an in-memory weak adjacency from those eight groups, excluding self-loops for weak degree; it found zero self-loop rows, 494,416 endpoint nodes and 524,244 distinct weak links. DuckDB's sample-local degree query returned 1,048,488 as the sum of degrees, exactly twice the distinct weak-link count. The sample-local maximum degree was 22,137. These values describe only these sampled row groups.

Three deterministic BFS checks used seeds drawn from the sampled node IDs that also occurred in the sampled edge endpoints. Each selected 500 nodes within the sampled adjacency. A second read of the same eight edge row groups counted sample-local induced directed edges; no edge file or output artifact was written.

| Sample-local candidate | Seed | Degree within sampled adjacency | Selected nodes | Sample-local induced directed edges |
|---|---:|---:|---:|---:|
| Uniform among eligible sampled node IDs | 468,308,629 | 1 | 500 | 580 |
| Median degree among eligible sampled node IDs | 492,196,805 | 1 | 500 | 654 |
| Highest degree among eligible sampled node IDs, tie by smallest ID | 468,073,950 | 2 | 500 | 593 |

These are algorithm and scattered-I/O checks only. Row groups are a sparse sample of the sorted table; they do not establish global node degrees, seed ranking, connectivity, or complete induced edges. The fact that these sample-local searches reached 500 nodes does not imply that a full-graph BFS will do so.

The successful benchmark took `7.052` seconds total in the Python process (`0.0166` s for the first edge read, `0.0100` s for the node read, `0.1094` s for the DuckDB sample-degree aggregation, and `0.4911` s to reread and count sample-local induced edges). The process peak RSS was `357,318,656` bytes (`~340.7 MiB`). The benchmark wrote no data or graph output files; the M1.2 probe directory, UV cache, and `/private/tmp` size readings were unchanged after it. A first attempt stopped after reading the sample because the active offline environment lacked NumPy; the successful offline run used PyArrow-native conversion. Network downloads were disabled and no model was downloaded or loaded.

### Updated full-stage resource estimate and gate

The full-stage estimate remains unbenchmarked: reserve 30–120 minutes, with a 120-minute hard stop; do not present the small sample timings as an extrapolation. For 20 candidate sets of at most 500 nodes, the theoretical induced-edge ceiling is 250,000 directed rows per set, or 5,000,000 rows total. At 24 bytes per `(source_id, target_id, weight)` row this is 120 MB raw; keep a 1 GiB output cap for Parquet and manifests. The weak-adjacency intermediate remains bounded by at most 303,713,368 oriented neighbor rows (`~4.86 GB` raw at 16 bytes each) before deduplication and external-sort spill; retain the proposed 8 GiB scratch-temp cap. DuckDB remains limited to 2 GiB and 2 threads.

At the lowest available-space snapshot in this preflight (`15.36 GiB`), spending both proposed caps (`8 GiB` temp + `1 GiB` output) would leave about `6.36 GiB`, which is `2.36 GiB` above the required 4 GiB buffer **if no other space changes occur**. At the post-benchmark snapshot (`19.35 GiB`), the same capped use would leave about `10.35 GiB`. Because observed free space moved by almost 4 GiB while the inspected relevant directory sizes stayed constant, this does not prove a worst-case 4 GiB reserve. Therefore the full-data phase is **not cleared to start**. Recheck stable available space and establish the reason for the fluctuations before that phase; if the conservative cap plus 4 GiB reserve cannot be guaranteed, stop without starting and report `incomplete` if any later bounded operation has begun.

## 2026-10-15 bounded disk-index and BFS benchmark

This benchmark exercised the planned scratch workflow on sampled row groups only. It did not scan the complete M1.1 tables, create a global index, publish a graph, or touch the unapproved audit output. No files were deleted.

### Fixed-seed input sample and scan volume

Seed: `20261015`. The benchmark read from the official M1.1 files and selected row groups across each complete Parquet row-group range.

| Source table | Total row groups | Selected row groups | Source rows read | Compressed row-group bytes |
|---|---:|---|---:|---:|
| `edges.parquet` | 2,318 | 6, 42, 96, 122, 165, 186, 237, 251, 273, 721, 737, 795, 812, 865, 953, 959, 974, 1106, 1110, 1438, 1600, 1608, 1620, 1730, 1741, 1800, 1803, 1970, 2038, 2151, 2202, 2260 | 2,097,152 | 7,923,173 bytes |
| `nodes.parquet` | 1,349 | 21, 61, 82, 406, 432, 901, 985, 1249 | 524,288 | 605,574 bytes |

The sampled edge IDs ranged from `source_id=10,253–808,545` and `target_id=10,001–1,571,861,432`; sampled node IDs ranged from `116,235,406–1,364,954,538`. The selected rows were serialized to scratch inputs, so subsequent index and induced-edge stages read only those scratch samples. The index query expanded the sampled non-self-loop rows in both orientations, deduplicated `(node_id, neighbor_id)`, and sorted by those fields.

### Disk index, indexed BFS, and induced-edge sample

The benchmark used PyArrow `26.0.0`, DuckDB `1.5.6`, DuckDB `memory_limit='128MB'` (below the 2 GiB ceiling), `threads=2`, and a `512MB` DuckDB temp quota. The weak-adjacency index was a sorted Parquet file. BFS used its `node_id` row-group min/max statistics to locate relevant row groups, with a four-row-group LRU cache; it did not rescan the whole sample index for each BFS layer. Each candidate had a 5,000,000 adjacency-row hard limit.

| Stage | Result | Elapsed |
|---|---|---:|
| Read 32 scattered edge groups and 8 node groups; write sample inputs | 2,097,152 edge rows and 524,288 node rows | 1.2726 s |
| Build sorted weak-adjacency Parquet index | 4,192,610 rows; 64 row groups; 15,436,138 bytes | 1.3649 s |
| Join the sampled node IDs to the index to form candidate pool | 10,051 eligible sampled nodes | 0.2392 s |
| Three row-group-indexed BFS runs | Each reached 500 nodes; each read 131,072 index rows from 2 row groups | 0.0464 s total |
| Read sampled directed edges and write sample-only induced edges | 2,370 rows across candidates; 9,224 bytes | 0.2681 s |

The three deterministic candidates were uniform among sampled eligible nodes (`172613909`, sample weak degree 1), median sample degree (`468799450`, degree 1), and highest sample degree with ties by smallest ID (`172632363`, degree 3). Their sample-only induced directed-edge counts were respectively 546, 1,071, and 753. These outcomes are limited to the selected source row groups; they are not complete full-graph BFS or induced-edge results.

The Python process took `10.2792` seconds total and peaked at `266,846,208` bytes RSS (`~254.5 MiB`). The DuckDB temp watcher observed a `12,550,144` byte (`~12.0 MiB`) peak; the temp directory was `0` bytes after the connection closed. Persistent scratch artifacts total `29,079,632` bytes (`~27.7 MiB`): sampled edge input `12,043,192`, sampled node input `1,591,078`, weak-adjacency index `15,436,138`, and sample-only induced edges `9,224` bytes. They remain under `.scratch/1999-connectome-demo/benchmarks/m1-2-rowgroup-index-bfs-seed-20261015/`; no formal output path was used.

### Before/after disk readings and conservative full-stage calculation

Immediately before the benchmark, `df` reported `21,476,068` KiB (`~20.48 GiB`) available. Immediately after, it reported `21,437,932` KiB (`~20.45 GiB`), a decrease of `38,136` KiB (`~37.2 MiB`). The benchmark directory accounts for `28,504` KiB allocated; the remaining `9,632` KiB (`~9.4 MiB`) is not explained by the recorded directory-size readings. The UV cache remained `1,207,940` KiB, `/private/tmp` remained `190,044` KiB, the official M1.1 directory remained `673,824` KiB, and the unapproved audit directory remained `673,824` KiB. No cause is inferred.

For the requested conservative scenario, start with the **lowest** measured snapshot `15.36 GiB` and subtract the observed near-`4 GiB` downward movement: conservative available space is about `11.36 GiB` (about `11.33 GiB` if reserving this benchmark's persistent `~0.028 GiB` scratch artifacts separately). The proposed full-stage caps require up to `8 GiB` temporary space plus `1 GiB` output, leaving only `2.36 GiB` (or `~2.33 GiB` with the separate benchmark artifact allowance). This is `~1.64–1.67 GiB` short of the required 4 GiB free-space reserve. Thus the current 8 GiB temp and 1 GiB output caps are **not feasible under the conservative scenario**. The theoretical 30–120 minute duration remains an unbenchmarked estimate; the sampled stage timings do not change it.

The benchmark validates the index construction and row-group-addressed BFS mechanics at small scale and gives measured sample temp/output sizes. It does not establish the full-scale external-sort peak or prove the 4 GiB reserve can be maintained. Keep M1.2 blocked from the full-data stage and `in-progress`; wait for review and a resource plan that fits the conservative disk bound.

**Conclusion:** the bounded probe code and fixtures pass, and the scattered-row-group index/BFS benchmark completed. Full-graph selection remains unrun and resource-blocked. M1.2 remains `in-progress`; no formal subgraph is published and no selection assumption is treated as approved.

## 2026-10-15 resource budget reassessment (documentation only)

This reassessment uses the scattered-row-group disk-index/BFS benchmark above. It did not rerun a benchmark, scan the complete tables, build a full index, write a formal subgraph, or load/download a model. M1.2 remains `in-progress` and the full-data resource gate remains **not passed**.

### Measured evidence versus extrapolation

Measured benchmark inputs were 2,097,152 edge rows from 32 of 2,318 edge row groups, which is **1.3810%** of the 151,856,684-row edge table, and 524,288 node rows from 8 of 1,349 node row groups, which is **0.5932%** of the 88,384,522-row node table. The sample index contained 4,192,610 deduplicated oriented adjacency rows, or **1.3804%** of the theoretical 303,713,368 oriented-row upper bound. These scattered groups tested the planned mechanics across the file; they are still small samples and do not establish full-table compression, spill, degree distribution, connectivity, or run time.

Directly measured for this sample: sorted adjacency index 15,436,138 bytes; DuckDB temp peak 12,550,144 bytes with a 128 MiB DuckDB memory limit and two threads; three candidates' induced-edge output 9,224 bytes for 2,370 rows; total persistent sample artifacts 29,079,632 bytes; process peak RSS 266,846,208 bytes; elapsed time 10.2792 seconds. The sample's temp-to-full-row linear scaling would be about 0.846 GiB, and sample-index-to-theoretical-row linear scaling would be about 1.041 GiB. These are **naive extrapolations only**, not upper bounds or reliable full-run estimates: cardinality, row-group skew, compression, sort behavior, memory limit, and external deduplication can change the ratios substantially. The 30–120 minute duration remains an unbenchmarked scheduling allowance, not a benchmark-derived forecast.

### Component-by-component disk budget

All sizes below use GiB (2^30 bytes). Existing M1.1 source tables are read-only inputs already present on disk and are not counted again as newly required space. Compressed full-index sizes and final Parquet sizes have not been measured.

| Component | Measured sample evidence | Full-stage planning amount / bound | Accounting note |
|---|---|---:|---|
| Full weak-adjacency index | 4,192,610 rows, 15,436,138 bytes | **4.526 GiB raw upper bound** for 303,713,368 `(node_id:int64, neighbor_id:int64)` rows | Deduplication may reduce it; compressed size is unknown. The 1.041 GiB linear estimate is not a safe cap. |
| Full weak-degree table | No full table measured | **1.317 GiB raw** for 88,384,522 `(node_id:int64, weak_degree:int64)` rows | Parquet output size is unknown; allow at least this raw capacity in planning. |
| DuckDB external-sort / spill | 12,550,144-byte peak on the sample at 128 MiB memory | Current proposed hard cap: **8 GiB** | The sample's 0.846 GiB linear estimate cannot prove an 8 GiB cap is sufficient. Spill is separate from retained index/degree outputs. |
| Candidate induced-edge outputs | 2,370 sample rows, 9,224 bytes | Up to 20 × 250,000 directed rows = 5,000,000 rows, **0.112 GiB raw**; current output cap **1 GiB** | Compression and manifests are unmeasured. The cap covers scratch candidate outputs. |
| One selected final graph | No final graph produced | At most 500 nodes and 250,000 directed rows: **about 5.72 MiB raw edges**, plus about 4 KiB node IDs and manifest | This is included within the 1 GiB output allowance if promoted/copied within that same output budget; a separate duplicate would need additional space. |
| Staging / checkpoints | Sample artifacts total 29,079,632 bytes | Plan **0.05 GiB** for runtime metadata and batch/checkpoint overhead (planning allowance, not measured) | The source is streamed directly; no full source copy is planned. If a separate full oriented-row staging file is materialized, add up to **4.526 GiB raw** before spill/output overhead. |
| Existing benchmark artifacts | 29,079,632 bytes persistent | **0.027 GiB already occupied** | Included in the conservative available-space calculation below, not added again to peak requirements. |

Under the current caps, the conservative incremental peak budget is approximately `4.526 + 1.317 + 8 + 1 + 0.05 + 4 = 18.893 GiB`, including the required 4 GiB reserve. If a separate full oriented-row staging file is needed, the peak rises to about **23.419 GiB**. These are capacity-planning sums, not predicted compressed output sizes.

### Conservative free-space check

The lowest recorded free-space snapshot is 15.36 GiB. Applying the observed near-4 GiB downward movement gives only **11.36 GiB** conservative availability; allowing separately for the 0.027 GiB benchmark artifacts leaves about **11.33 GiB**. The cause of the observed space movement remains unknown, so this calculation is a conservative scenario, not a guarantee that future fluctuations will stop at 4 GiB.

Against 11.33 GiB, the current full-stage budget of 18.893 GiB is short by about **7.56 GiB**. With separate full oriented-row staging, it is short by about **12.09 GiB**. Therefore the current 8 GiB spill and 1 GiB output caps cannot coexist with the raw index/degree capacity and 4 GiB reserve under the conservative scenario. **Resource gate: not passed. Do not start the full-data phase.**

### Possible lower-cap plan and remaining risk

A future, strictly bounded attempt could be budgeted at no more than 2 GiB DuckDB spill, 2 GiB retained adjacency-index output, 1.5 GiB degree output, 0.25 GiB candidate/final outputs, 0.05 GiB runtime staging, and 4 GiB continuously free: about **9.80 GiB total**, leaving about **1.53 GiB** against the 11.33 GiB conservative availability. This is only a candidate cap configuration for review; it does not prove that the complete index fits in 2 GiB or that the degree Parquet fits in 1.5 GiB. If any spill or output cap is reached, the run must stop and report `incomplete / budget_exhausted`; it must not publish partial artifacts or label them complete. The plan also requires direct streaming without a separate 4.526 GiB oriented staging file. If that staging is necessary, this lower-cap configuration does not fit.

Because the unexplained space changes may recur, the arithmetic alone does not establish an operational guarantee. With current caps, a user-provided destination would need at least **18.893 GiB free throughout execution** (or **23.419 GiB** if separate oriented staging is required); to tolerate another approximately 4 GiB downward swing after preflight, the corresponding preflight readings would need to be at least **22.893 GiB** or **27.419 GiB**. Before any future full-data work, either (a) the user confirms such a sufficiently sized, stable destination and a fresh preflight proves the 4 GiB reserve can be maintained, or (b) the user reviews and accepts a lower-cap, abort-on-cap plan with no separate oriented staging. No file cleanup or relocation is proposed or performed here. No full scan, full index, formal output, or model operation was started; M1.2 remains `in-progress`.

## 2026-10-15 alternative plans (analysis only; not executed)

This comparison adds no new benchmark or source read. Labels below distinguish **measured** observations from **derived bounds** and **unverified planning estimates**. The scattered sample covers only 1.3810% of edge rows and 0.5932% of node rows; its linear size ratios are not used as full-run guarantees. The machine's 8 GiB RAM is a measured host value. Conservative available disk remains about 11.33 GiB after the lowest 15.36 GiB snapshot, the observed near-4 GiB movement, and current benchmark artifacts. The cause and future extent of the disk movement remain unknown.

### Option A: exact weak-view BFS by streaming the edge table once per layer

Do not materialize adjacency or degree tables. For each BFS layer, stream all edge batches and test both endpoints against that layer's frontier. Treat an edge as undirected only for discovery; ignore self-loops for discovery, retain direction/weight for final output. Keep a per-candidate visited set and a bounded set/heap of the lowest-ID new neighbors needed to honor deterministic sorted-neighbor traversal. Finish the entire scan for a layer before deciding the next frontier. A scan that stops early makes that BFS `incomplete`; it cannot be represented as a complete layer.

| Aspect | Assessment |
|---|---|
| Correctness | **Exact bounded BFS**, if every layer consumes all 151,856,684 edge rows and the deterministic seed/tie rule is fixed. It gives the first at most 500 nodes under that rule, not all graph nodes. If the component has fewer than 500 nodes, continue until a complete layer adds none. A separate full edge pass extracts all original directed induced rows; another full pass can independently verify the output count/hash. No global weak-degree ranking is available without computing degrees. |
| Scan count | **Derived bound:** at most 499 complete layer scans to discover/exhaust a component at the 500-node limit, plus one induced-edge extraction scan and one independent verification scan: at most **501 full edge scans**. Uniform reproducible seed selection from the full `nodes.parquet` can use one additional streaming reservoir-sampling pass. For 20 candidates, process all independent BFS frontiers in the same layer scan; the bound stays 501 if that batching is implemented correctly. If candidates are run separately, the conservative bound is about 20 × 501 = **10,020 edge scans**. |
| RAM | **Planning estimate, unmeasured at full scale:** O(batch rows + candidate state), with ≤500 visited/frontier nodes per candidate (≤10,000 node IDs for 20 candidates), bounded neighbor heaps, and a fixed Arrow batch. A PyArrow streaming implementation can avoid DuckDB spill; target RSS ≤1 GiB and abort if measured RSS exceeds 2 GiB. If DuckDB is used, keep its configured cap ≤2 GiB and two threads. The existing ~255 MiB sample RSS does not guarantee this full-pass behavior. |
| Disk | **Planning estimate:** no full adjacency/index or spill file; reserve ≤0.05 GiB for checkpoints/logs and cap all candidate/final output at 0.25 GiB. The raw upper bound for 20 candidate induced-edge outputs is 0.112 GiB; one 500-node result is at most ~5.72 MiB raw edges. With the 4 GiB reserve, planned writes plus reserve are ≤4.30 GiB, below the current conservative 11.33 GiB, assuming no separate row staging and the space check remains live. |
| I/O and risk | **Derived logical work:** 151,856,684 edge rows × 501 passes = **76,080,198,684 row visits** for one seed or correctly batched candidates. If 20 candidates run separately, the bound is about 10,020 passes / 1.522 trillion row visits. The earlier report's ~1.17 GB for “two sequential source reads” does not specify whether those were two edge passes or one edge plus one node read, so it cannot safely be divided into a per-edge-pass byte estimate. No full-pass throughput or runtime is measured; the repeated I/O may dominate. |
| Failure and verification | Enforce full row count per layer and a hard wall-clock / free-space stop. Any interrupted layer, pass, extraction, or verifier is `incomplete / budget_exhausted`, with no formal output. Verify source checksum unchanged, per-layer consumed row counts, deterministic selected IDs, and independently recalculate induced-edge count/hash in a complete pass. The 501 count is for BFS/extraction/independent row scans; pre/post SHA-256 of the source files adds two byte-level reads of each file unless an approved verification mechanism avoids them. |

This is the preferred *algorithmic candidate if the BFS research question must remain unchanged*: it trades disk capacity for repeated read I/O and avoids the 4.526 GiB raw adjacency index plus 1.317 GiB degree table. It is not yet operationally cleared because the scan throughput and worst-case runtime are unmeasured, and a real full-pass benchmark was not authorized or run here.

### Option B: retain the indexed workflow, but put scratch and outputs on user-provided storage

Keep M1.1 inputs read-only on the current volume. Direct the full adjacency index, degree output, DuckDB temp/spill and candidate artifacts to a destination with independently verified usable free space.

| Capacity item | Required free space on destination |
|---|---:|
| Index + degree raw planning bounds + 8 GiB spill cap + 1 GiB output cap + 0.05 GiB staging allowance + 4 GiB reserve | **18.893 GiB throughout execution** |
| Preflight allowance for another ~4 GiB downward movement | **22.893 GiB before starting** |
| If a separate full oriented-row staging file is also materialized | Add up to 4.526 GiB: **23.419 GiB throughout**, or **27.419 GiB preflight** to absorb the same movement |

These are **derived planning requirements**, not measured external-drive performance or guaranteed compressed sizes. A practical user-confirmed target is at least **30 GiB usable free** without the extra staging file, or **35 GiB usable free** if it is needed. A nominal drive capacity is insufficient evidence; measure actual available bytes on the destination and keep at least 4 GiB free there. Also recheck free space on the source volume, which has shown unexplained movements. Verify M1.1 hashes before and after, index/degree row counts and schemas, spill/output quotas, full BFS layer counts, complete induced edges, and manifests. Failure includes a quota hit, unexpected source-volume pressure, unstable/disconnected destination, checksum mismatch, or unfinished scan; partial outputs remain scratch and are marked incomplete. No external volume was inspected or used in this turn.

### Option C: change the selected graph and narrow the research claim

| Variant | Correctness and full-data reads | RAM / disk planning | What it can and cannot claim; failure and verification |
|---|---|---|---|
| **C1 — exact 100-node bounded BFS** | Same layer-streaming method as Option A. **Derived bound:** at most 99 BFS layer scans plus extraction and independent verification = **101 edge scans**. | O(batch + 100 node IDs); no full index/spill; cap scratch and output at 0.10 GiB, plus the 4 GiB reserve. Runtime remains unmeasured. | Exact first 100 nodes for a fixed seed and tie rule, with exact induced directed edges. It changes the scale and cannot support the 500-node or larger-neighborhood comparisons. Any incomplete pass is incomplete; verify as Option A. The 100-node limit is a proposal only. |
| **C2 — deterministic uniform sample of 500 nodes, then exact induced graph** | Reservoir-sample 500 IDs in one streaming pass over the complete nodes table; scan the complete edge table to write all edges whose two endpoints are selected; do a second complete edge pass to independently verify count/hash. **Two edge passes plus one node pass**, excluding pre/post source SHA-256 reads. | O(500 IDs + batch), no index or spill; ≤0.25 GiB output/staging cap plus 4 GiB reserve. | Exact induced graph on the selected random nodes, but **not connected and not a BFS neighborhood**. It supports a random-node induced-sample question only; it cannot support local-neighborhood, connectedness, or BFS claims. Verify reservoir seed/algorithm, node membership, complete edge-row counts, and independent induced-edge count/hash. If any pass is incomplete, no complete sample result. Requires explicit approval to change the selection question. |
| **C3 — BFS on sampled row groups/edges** | Exact BFS only in the sampled graph, not in the full graph. Existing benchmark used 32/2,318 edge groups (1.3810%) and 8/1,349 node groups (0.5932%); it does not provide full-graph connectivity or all induced edges. | **Measured for that sample only:** ~255 MiB peak RSS, ~12.0 MiB DuckDB temp peak, ~27.7 MiB persistent sample artifacts, 10.28 s. Do not scale these values linearly into a guarantee. | Can validate code and explore a clearly labeled sample graph. Missing rows may change paths, reachable nodes and edges; cannot be called full-graph BFS, complete full induced edges, or evidence of a global seed policy. Verify fixed row-group sample IDs/seed and label every output sample-only. |

### Recommendation and resource gate

If the intended claim must remain a connected weak-view BFS neighborhood, evaluate **Option A** first: it is exact by construction, avoids the large persistent index and fits the current disk envelope on paper. Its main cost is up to 501 full edge passes (or substantially more if candidate seeds are not batched); a full-pass throughput measurement and an accepted runtime budget are still missing. If the scientific goal permits a random-node induced sample instead, **C2** is the lowest-I/O exact alternative, but it changes the study question and needs approval. Use Option B only if retaining the index workflow is required and a user-confirmed volume meets the usable-space thresholds above. C3 is for engineering checks only.

No alternative was selected or executed. The overall execution gate therefore remains **not passed**: Option A has bounded memory/disk by design but unmeasured full-pass cost; Option B needs storage not currently provided; C1/C2 change the proposed selection contract; and C3 cannot support full-graph claims. Await review of the research method, then require a fresh per-volume preflight and explicit authorization before any full-data read or write. M1.2 stays `in-progress`; no full scan, index, formal subgraph, deletion, relocation, or model operation occurred.

## 2026-10-15 single full-column streaming scan benchmark

This was the one authorized row-data scan of the official M1.1 `edges.parquet`. No BFS, repeated row scan, index, candidate set, subgraph, model operation, or formal-data write was performed. The pre/post SHA-256 computations were separate byte-integrity reads required by the request; there was exactly one DuckDB row scan.

### Preflight

| Check | Result |
|---|---|
| Physical RAM | `8,589,934,592` bytes (8 GiB), read with `sysctl -n hw.memsize` under the approved preflight. |
| Related processes | No active DuckDB/M1.2/subgraph/connectome process found before or after the scan. |
| Edge file | `data/connectome/derived/malecns_v1.0/edges.parquet`; `582,837,207` bytes. |
| Manifest expectations | `151,856,684` rows; `weight_sum=311,833,243`; edge file SHA-256 recorded as `d32d5be692b127e8b9132e418bbfc4a13fbc36e2f5fabc90293a1f04d5f133aa`. |
| Pre-scan SHA-256 | `d32d5be692b127e8b9132e418bbfc4a13fbc36e2f5fabc90293a1f04d5f133aa`. |
| Disk snapshots | Pre-run observations varied between about `19.46` and `21.46 GiB` free; the immediate scan monitor recorded `21,906,571,264` bytes (`20.402 GiB`) at start. All observed values exceeded the 4 GiB stop line. The unexplained snapshot movement remains a risk. |
| Runtime | DuckDB `1.5.6`, PyArrow `26.0.0`, run through the existing UV cache with `--offline`; no package or model download occurred. |

### Scan result and resource measurements

DuckDB read `source_id`, `target_id`, and `weight` in one `read_parquet` query. The aggregate included `COUNT(*)`, `SUM(weight)`, and diagnostic sums of both endpoint columns so all three data columns were consumed. Settings reported by DuckDB were `memory_limit=122.0 MiB` (configured as `128MB`), `threads=2`, and `max_temp_directory_size=15.2 MiB` (configured as `16MB`).

| Measure | Result |
|---|---:|
| Rows read | `151,856,684` — matches manifest |
| Weight sum | `311,833,243` — matches manifest |
| Diagnostic `SUM(source_id)` | `9,349,088,768,649,082` |
| Diagnostic `SUM(target_id)` | `87,827,155,592,108,081` |
| Timed query | `2.4432` seconds |
| Peak process RSS | `118,603,776` bytes (`~113.1 MiB`) |
| Peak DuckDB temp directory use | `0` bytes; no spill observed |
| Free space at scan start / end | `21,906,571,264` / `21,905,453,056` bytes (`20.402` / `20.401 GiB`); decrease `1,118,208` bytes (`~1.07 MiB`). The monitor's minimum was the end reading. |
| Stop-line margin after scan | `~16.401 GiB` above the 4 GiB minimum |
| Temp path | `/private/tmp/flycall_m1_2_singlepass_20261015`; empty after connection close (`du` reported 0 KiB) |

Post-scan edge file size remained `582,837,207` bytes and SHA-256 remained `d32d5be692b127e8b9132e418bbfc4a13fbc36e2f5fabc90293a1f04d5f133aa`, matching both the pre-scan value and the M1.1 recorded value. The post-scan process check found no related process. The empty temp directory was left in place; it contains no spill file.

A later `df` snapshot during the post-run check reported `20,338,984` KiB (`~19.397 GiB`) free, about `1.004 GiB` below DuckDB's end-of-scan `shutil.disk_usage` reading. This unexplained movement occurred after the scan; it remains above the 4 GiB threshold, and no cause is inferred.

### 501-scan time extrapolation (not a full BFS benchmark)

Multiplying this one measured aggregate-scan time by 501 gives `1,224.0` seconds, or **about 20.4 minutes** if every pass takes the same time. As a sensitivity illustration only, if subsequent passes average twice as long, the total is **about 40.8 minutes**. This is not a measured interval or guaranteed upper bound: this query did not perform frontier membership checks, bounded neighbor selection, or BFS bookkeeping. Warm page cache could make later reads faster; cache eviction, other I/O, frontier processing, or system contention could make them slower. One observation cannot establish a defensible upper runtime. The estimate excludes pre/post SHA-256 byte reads and any setup/serialization time.

The single scan supports the manifest row and weight totals and shows that this simple full-column aggregate completed without spill under the stated settings. It does **not** establish the runtime of up to 501 BFS-layer scans, nor does it authorize or start BFS. The resource gate for M1.2 remains **not passed** pending method review and a separately authorized execution plan. M1.2 remains `in-progress`; no formal subgraph was produced.

## 2026-10-15 controlled no-index streaming BFS probe

This section supersedes the preceding statement that no full-data BFS had run: one user-authorized, fixed-seed engineering probe was completed. It does not supersede the unresolved formal seed policy, and it is not a formal or published connectome subgraph. M1.2 remains `in-progress`.

### Method and safety controls

- Added `src/flycall_data/streaming_bfs.py` and fixture coverage in `tests/test_streaming_bfs.py`. `probe_streaming_bfs(...)` is an exploratory feasibility seam, not a frozen public API.
- The implementation uses PyArrow `26.0.0` to stream 65,536-row batches. For every BFS layer it reads all rows of `edges.parquet`, treats either endpoint as a weak neighbor, and keeps only the 500-node visited set plus a bounded candidate set. If a layer has more candidates than remaining slots, it picks the smallest unseen node IDs for deterministic tie-breaking. It does not build adjacency/degree indexes or a dense matrix and does not use DuckDB.
- Once the node set is selected, a complete source pass writes only directed rows whose two endpoints are selected. A separate complete source pass recomputes the induced row count and digest; the emitted node and edge Parquet files are also read independently and checked for schema, content, and endpoint membership.
- The run enforced at most 501 complete scans, a 60-minute deadline, a 4 GiB free-space floor checked before/after scans and during batch processing, an RSS stop limit of 2 GiB, and a 1 GiB total scratch-output cap. Since the implementation did not use DuckDB, DuckDB spill was 0 bytes / not applicable. No model was downloaded or loaded.
- The existing full test suite passed: 29 tests. The added fixture tests cover weak-direction discovery, layer tie selection/node limit, a component below the target size, induced-edge filtering and direction/weight preservation, self-loop retention, missing seed, scan-budget incompleteness, hard limits, and the disk preflight gate.

### Preflight and integrity

| Check | Before | After |
|---|---:|---:|
| Physical RAM (`sysctl -n hw.memsize`) | 8,589,934,592 bytes | Probe recorded 8,589,934,592 bytes |
| `edges.parquet` size | 582,837,207 bytes | 582,837,207 bytes |
| `edges.parquet` SHA-256 | `d32d5be692b127e8b9132e418bbfc4a13fbc36e2f5fabc90293a1f04d5f133aa` | `d32d5be692b127e8b9132e418bbfc4a13fbc36e2f5fabc90293a1f04d5f133aa` |
| M1.1 expected rows | 151,856,684 | Each of the three complete passes read 151,856,684 rows |
| Related processes | No other M1.2/DuckDB worker found | No worker remained after the run |

Before the run, `df` reported 22,500,962,304 bytes (20.956 GiB) free. The probe's own start/minimum/end observations were 22,574,698,496 / 21,487,845,376 / 21,487,976,448 bytes (21.024 / 20.012 / 20.012 GiB). A post-run `df` snapshot reported 21,486,026,752 bytes (20.010 GiB) free. The observed in-run decline from start to minimum was 1,086,853,120 bytes (1.012 GiB); the lowest reading remained 16.012 GiB above the 4 GiB stop line. The preflight `df` to post-run `df` difference was a decrease of 1,014,935,552 bytes (0.945 GiB), while this run's scratch files totalled 399,404 bytes. The larger movement is unexplained; no cause is inferred, and no files were deleted or moved.

### Probe result

| Measure | Observed result |
|---|---:|
| Diagnostic seed | `10001` (fixed test seed only; not an official seed, not representative, and not evidence for a global seed policy/distribution) |
| Node cap / selected nodes | 500 / 500 |
| BFS layer scans / reached depth | 1 / 1 edge hop from the seed |
| Total full edge scans | 3: one BFS-layer scan, one induced-edge extraction scan, one independent source-validation scan |
| Rows read across all passes | 455,570,052 (= 3 × 151,856,684) |
| Induced directed edges | 32,823; original `source_id -> target_id` direction and `weight` retained |
| Probe elapsed time | 43.983 seconds |
| Peak RSS | 221,626,368 bytes (~211.3 MiB) |
| DuckDB spill / index | 0 bytes / none created; DuckDB was not used |
| Scratch output | 399,404 bytes total; `candidate_edges.parquet` 388,269 bytes; below the 1 GiB cap |
| Independent validation | Pass: complete source-pass count and digest matched the candidate Parquet; candidate schemas, 500 unique sorted node IDs, edge count, and endpoint membership passed |

The selected 500 nodes were reached in one complete layer scan, with the seed plus 499 chosen weak neighbors; therefore this run did not need to estimate the seed component's total size. The logical induced-edge digest is `8c3b3cb192b826491806845734d414af7de1d5584bd5a02362c022e28eb57fea`; the emitted Parquet file SHA-256 is `836ac8b5c2e08f827f006d39774ffd49bcc492e3b64a255e3fe5cc9fdc2140d4`.

Scratch artifact directory: `.scratch/1999-connectome-demo/probes/m1-2/streaming-bfs-seed-10001-20261015-run1/`. It contains `candidate_nodes.parquet`, `candidate_edges.parquet`, and `probe_result.json`. The candidate is explicitly `is_formal_subgraph=false`; it was not written under or promoted into the M1.1 formal directory.

### Interpretation and remaining limits

This is an exact bounded BFS result for the one diagnostic seed and documented layer tie rule, with complete induced directed edges for those selected nodes. It demonstrates that this no-index path completed for this seed under the stated resource limits. It does not establish runtime for a deep component or the 501-scan worst case, and the one seed cannot support representativeness, a global seed policy, or claims about full-graph component-size distributions. The 60-minute ceiling remains enforced for any later run; a scan/deadline/disk/RSS/output cap interruption must remain `incomplete`.

The diagnostic result does not resolve the spec's open seed policy or authorize a formal subgraph. Formal subgraph publication and M1.2 completion remain blocked on review of the seed policy, target-size assumption, and applicable remaining acceptance checks. No M1.1 data, source Feather, 1999 case data, taxonomy, split manifest, or model was changed.

## 2026-10-15 prior row-order audit (smallest-ID rule; superseded)

The findings below document the implementation before the hash-priority change in the following section. The saved seed-10001 probe also used this earlier smallest-ID rule.

No M1.1 Parquet was read, no full-data scan or probe was rerun, and the saved seed-10001 result was only read as JSON. The fixture-only test used two Parquet files containing the same directed edge rows in opposite row order.

### Selection-order finding

Selection does not use the first neighbors encountered in Parquet order. For each complete layer scan, `pc.is_in` checks both `source_id` and `target_id` against the whole frontier. `_SmallestCandidates` keeps at most the number of remaining slots in a max-heap and candidate set: while it is not full it adds unique unseen IDs; once full, a newly seen ID replaces the currently largest retained ID only when it is smaller. Therefore the final candidate set is the smallest required IDs from the whole layer, regardless of row-group order or whether edges are sorted by source or target. `sorted(frontier)` and the sorted returned candidate IDs make the follow-on layer deterministic.

This removes input-row-order dependence for a fixed seed and tie rule. It does **not** remove numeric-ID selection bias: when the cap truncates a wide layer, the current rule favors smaller IDs. Whether numeric ID correlates with source order or another graph property is not established here.

The new fixture `test_selected_nodes_do_not_depend_on_parquet_row_order` starts from the same edge rows, reverses their physical order, and runs seed `20` with two node slots. Although the first observed neighbor differs, both files select `[20, 30]`; the induced directed `(source_id, target_id, weight)` edge sets match. All 8 tests in `tests.test_streaming_bfs` passed. This is a fixture result only, not a full-graph statistical test.

### Two distinct validation claims

- **Induced-edge correctness:** the saved seed-10001 artifact came from one complete source extraction pass and a separate complete source verification pass. The edge row count and ordered-row digest matched the emitted `candidate_edges.parquet`; output schema, node IDs and endpoint membership also passed. This supports completeness of the directed induced edges for that selected node set and source-file order.
- **Selection order-independence:** the new reversed-row fixture supports that the node set for the fixture is unchanged by input row order under the smallest-ID tie rule. It does not establish representativeness or lack of numeric-ID bias.

The result field `induced_edges_sha256` is an **ordered-row digest**: it is stable across Arrow batch boundaries but changes if the same rows are permuted. The internal helper is named `_ordered_edge_digest_state` to make that property explicit. The fixture therefore compares induced edge tuples as a set; the existing digest is for checking extraction against verification over the same source order, not for comparing arbitrary row permutations.

### Formal seed-policy and size choices still open

No formal policy is selected. Options and tradeoffs for review:

| Candidate policy | Reproducibility | Main bias / cost |
|---|---|---|
| Fixed node ID (the current `10001` is diagnostic only) | Exact repeat for the same source version | Arbitrary local neighborhood; no representativeness claim; current smallest-ID layer tie rule adds numeric-ID preference. |
| Uniform node seed by deterministic hash priority over the complete `nodes.parquet` ID set | Can be reproducible and independent of node-table row order with a fixed hash key; requires a complete node pass | Uniform over endpoint IDs does not ensure representative regions, degree classes, or component sizes; may select a small component. |
| Weak-degree-stratified seed candidates from a complete degree calculation | Reproducible with fixed strata and a fixed sampling key | Requires a full weak-degree computation and a defined self-loop counting rule; deliberately over/under-samples degree strata unless weights are applied. |
| Highest weak-degree seed with deterministic ID tie-break | Reproducible after exact full-graph degrees are computed | Strong hub bias; does not describe a typical node or neighborhood. |
| Region-conditioned seed | Reproducible if annotations and candidate set are fixed | Not currently available: M1.1 nodes contain endpoint IDs only and do not establish region/cell-type labels. |

The initial 500-node size is still a provisional feasibility target. The seed-10001 run reached 500 after one layer, but that does not establish that 500 is scientifically suitable, nor does it compare 1,000/2,000-node resource or topology behavior. Final seed policy and target size must be decided before a formal subgraph run. M1.2 remains `in-progress`; no seed policy or node-size policy was frozen.

## 2026-10-15 fixed-salt hash-priority candidate (fixtures/code only)

This work replaces the prior smallest-ID frontier tie rule in the implementation. It only exercised synthetic fixtures; it did not read `nodes.parquet` or `edges.parquet`, rescan M1.1, rerun seed `10001`, or produce a formal subgraph. M1.2 remains `in-progress`.

### Candidate rule

- Hash: `hashlib.blake2b`, 128-bit digest (`digest_size=16`).
- Fixed public salt: ASCII `FlyCallM12-v1` (hex `466c7943616c6c4d31322d7631`). The salt is part of the candidate policy and must be recorded with outputs; it is not a secret.
- Input encoding: each `node_id` as signed int64, exactly 8 bytes, little-endian.
- Rank: digest bytes ascending; `node_id` ascending is used only if two 128-bit digests collide.
- Seed candidate: stream the entire `nodes.parquet` in batches, keep the one ID with minimum rank, and do not materialize the node table. The fixture seam `select_hash_priority_seed(nodes_path)` validates the `node_id:int64` schema and rejects nulls. Its row count is a count of rows, not an independent proof of completeness or uniqueness; before any official use, verify source identity, checksum, manifest row count and the M1.1 unique-node contract.
- BFS frontier: during a complete scan of each layer, consider both endpoints of every edge incident to the frontier as weak neighbors. Keep the `k` lowest-ranked unseen IDs, where `k` is the remaining node capacity. The bounded heap uses the same hash, salt, encoding and tie-break rule. Batch-local de-duplication is only an efficiency step; the total rank order determines the result. Serialized selected IDs remain numerically sorted for stable output formatting, not for selection.
- Limits: the existing `node_limit` hard ceiling remains 500. **500 is a first-release candidate only and remains undecided.** A scan, wall-clock, disk, RSS or output cap still makes the run `incomplete`; hash-priority does not relax any existing safety limit.

### Fixture evidence

`tests/test_streaming_bfs.py` now has 10 passing tests. The new coverage includes:

1. A synthetic complete node table with IDs 1–1,024, written in ascending and descending row order with different row-group sizes, selects seed `49` both ways and scans 1,024 rows in each fixture.
2. A 1,024-leaf star with center `100000` and cap 33 selects the same 32 leaves when Parquet row order is reversed. The expected top-priority leaves include 12 IDs above 512, have maximum ID 1002, and are not the first 32 numeric IDs. A cap of 257 selects leaves across the four ID quartiles in counts `72, 72, 59, 53`. This is a deterministic fixture check that the implemented ordering does not simply retain low IDs; it is not a statistical or full-graph proof.
3. Both row orders produce the same exact induced directed edge tuple set for the selected leaves: 32 edges from `100000` to the selected leaf IDs, with original direction and weights retained. This validates induced-edge filtering separately from selection-order invariance.
4. Existing small fixtures still cover weak-view traversal, node caps, self-loops, absent seeds, incomplete scan budgets and output validation.

Executed the targeted fixture suite with the already cached Python 3.12 / PyArrow 26.0.0 environment; **10 tests passed**. No official data scan was part of this test command. The run emitted sandbox `sysctl` permission warnings from the existing optional RAM-observation helper, but tests completed successfully.

### What this does and does not establish

The total rank order is independent of node numeric order and of Parquet row order for a fixed node/edge set. It removes the previous deterministic preference for small IDs, except that the explicit final tie-break favors a smaller ID in the extraordinarily unlikely event of an identical 128-bit digest. BLAKE2b output is used as a deterministic mixing order; the fixture does not prove an unbiased biological sample, uniform graph properties, or representative components. A hash-ranked endpoint-ID seed can still land in an isolated or small component, and a BFS neighborhood remains conditioned on graph connectivity.

The saved real-data seed-10001 result, including its 500 nodes and 32,823 induced edges, was produced under the superseded smallest-ID rule. It remains evidence for the previously selected set and its extraction checks, but is not evidence for the new hash-priority selection and was not rerun. A future official seed selection would require a complete validated pass over the full node table. The runtime and resource cost of computing 88,384,522 BLAKE2b priorities has not been measured; fixture timing is not a full-table estimate. Any full BFS would still require an approved seed policy, size and resource gate. No M1.1 data was read or changed in this update, and no formal subgraph was published.

Seed policy and target size remain pending human review. M1.2 stays `in-progress`.

## 2026-10-15 adopted first-version candidate and full-node scratch probe

The user adopted the fixed-salt BLAKE2b-128 seed/frontier rule and a 500-node cap **for an engineering demo candidate only**. This is not a claim that 500 is optimal or biologically representative. Diagnostic seed `10001` was not reused; it belongs to the superseded smallest-ID rule. This section supersedes the earlier “pending human review” wording for these first-version candidate choices, but M1.2 remains `in-progress` and no formal subgraph is approved.

### Preflight and source integrity

- Physical RAM from `SC_PHYS_PAGES × SC_PAGE_SIZE`: `8,589,934,592` bytes (8 GiB).
- Preflight free disk: `22,555,914,240` bytes (`21.007 GiB`). After reserving the largest previously observed ~4 GiB space movement and the 1 GiB scratch output cap, the conservative remainder was `17,187,205,120` bytes (`16.007 GiB`), above the required 4 GiB floor by about 12.007 GiB.
- The project scratch tree measured `702,772 KiB`; formal M1.1 directory measured `673,824 KiB`. The process check found no existing M1.2, PyArrow or DuckDB worker. The checksummed source files matched the M1.1 manifest before execution.
- Before execution, the seed selector gained disk-floor and RSS checks during batch processing; the below-floor fixture confirmed it stops before selecting a seed. All 11 `tests.test_streaming_bfs` fixture tests passed.
- DuckDB was not used; no index, spill, model, or non-scratch output was created. The seed scan and BFS each enforced a 4 GiB disk floor and 2 GiB process RSS ceiling. BFS also had the 501 complete-edge-scan and 60-minute limits.

| Source | SHA-256 before | SHA-256 after | Manifest match |
|---|---|---|---|
| `nodes.parquet` | `71601532b54b5fd8fba108681148a5f791f9c6c69885ed0b124e3750f84fb654` | same | yes |
| `edges.parquet` | `d32d5be692b127e8b9132e418bbfc4a13fbc36e2f5fabc90293a1f04d5f133aa` | same | yes |

### Full nodes hash-priority seed selection

The complete `nodes.parquet` was streamed in Arrow batches; no full node table was loaded. All `88,384,522` rows were processed using BLAKE2b-128, salt `FlyCallM12-v1`, signed-int64 little-endian encoding, and `(digest ascending, node ID ascending on digest collision)` ranking. Selected seed: **`274013289`**, priority digest `000000101b2e6230592f8718fc4de3c2`. The scan took `57.612 s`, peak RSS was `90,390,528` bytes (`86.203 MiB`), and minimum observed free disk was `22,544,502,784` bytes (`20.996 GiB`).

### Streaming BFS and candidate validation

The new seed reached the node cap after two complete BFS layer scans: the first found 3 new nodes and the second supplied the remaining 496. The run completed with 500 selected nodes, so this result is cap-limited and does not state the connected component's total size.

| Measure | Result |
|---|---:|
| Complete edge scans | 4 of 501 maximum: 2 BFS layers, induced-edge extraction, independent source validation |
| Rows read | 607,426,736 (= 4 × 151,856,684) |
| BFS time | 21.725 s; full seed-selection + BFS + post-run checksum elapsed `80.056 s` |
| Peak RSS | 446,464,000 bytes (`425.781 MiB`), below 2 GiB |
| Minimum free disk during BFS | 22,543,200,256 bytes (`20.995 GiB`), above the 4 GiB floor |
| DuckDB / spill / index | not used / 0 bytes / none |
| Selected nodes / directed induced edges | 500 / 2,216 |
| Probe scratch output | 106,793 bytes; edge Parquet 102,808 bytes, node Parquet 3,985 bytes |
| Probe status | `complete`, reason `node_limit_reached`; `is_formal_subgraph=false` |

The independent full-source validation passed. A separate artifact check confirmed exact node and edge schemas, 500 unique sorted nodes including the seed, 2,216 edges whose endpoints are all selected, and candidate file SHA-256 values matching the recorded run summary. Original edge direction and weights are retained.

| Scratch artifact | SHA-256 / result |
|---|---|
| `probe/candidate_nodes.parquet` | `a8ad1e6a42c0a386d4bdef517ac628c29a5b7b8f023c51b43cce8e0354087428` |
| `probe/candidate_edges.parquet` | `afa69be2078eaf136d00511539145dc82ea54af5aa2f52ffdcb87501488e2175` |
| Ordered induced-edge digest | `5b33825d0d9ba8f13fc72b2cb4b25556eba43e55255d0743cffc4b705ed53882` |
| Independent validation | `pass` |

Artifacts are confined to `.scratch/1999-connectome-demo/probes/m1-2/streaming-bfs-hash-priority-seed-274013289-20261015-run1/`, including `seed_selection.json`, `run_summary.json`, and the non-formal candidate tables under `probe/`. The minimum observed free space for the whole run was about `20.995 GiB`; final free space was about `20.995 GiB`. No M1.1 file changed. M1.2 remains `in-progress`; the candidate is not a formal or approved subgraph.

## 2026-10-15 deterministic replay and engineering-demo archive

This final section supersedes the preceding run1-only status: run1 remains intact as scratch evidence, run2 is a separate scratch replay, and the verified output was archived only after run1/run2 comparison passed. The archive is an **engineering demo subgraph**, not a biologically representative sample; 500 is the adopted demo cap, not an optimal scale.

### Re-run and resource checks

- Re-ran all 11 `test_streaming_bfs.py` fixture tests with PyArrow `26.0.0`; all passed. Command: `PYTHONPATH=src uv run --offline --python 3.12 --with pyarrow==26.0.0 -- python -m unittest discover -s tests -p 'test_streaming_bfs.py' -v`.
- The project has no Git repository. Core implementation and test source fingerprints used by run2 were `src/flycall_data/streaming_bfs.py` SHA-256 `d31a3c446f74243dc98de1b1aa78dc71cf570ba6056389b4f5928c1ffe5aa458` and `tests/test_streaming_bfs.py` SHA-256 `f3a7f481c3e7bbe2ecffa424b0ab40bdef485354af0bfa8e4a8058667d94d59a`. Their file modification times predate run1's output; run1 and run2 used the same on-disk implementation. PyArrow was run offline from the existing local cache; DuckDB was not used.
- Preflight RAM: `8,589,934,592` bytes (8 GiB). Free disk at run2 start: `20,393,521,152` bytes; minimum during run2: `18,343,780,352` bytes (about 17.08 GiB), above the 4 GiB floor. No matching M1.2/PyArrow/DuckDB process was active at preflight. No model was downloaded or loaded.
- The official M1.1 Parquet source files remained read-only. Run2's pre- and post-run SHA-256 matched the M1.1 import manifest:

| M1.1 file | SHA-256 before | SHA-256 after | Manifest match |
|---|---|---|---|
| `nodes.parquet` | `71601532b54b5fd8fba108681148a5f791f9c6c69885ed0b124e3750f84fb654` | same | yes |
| `edges.parquet` | `d32d5be692b127e8b9132e418bbfc4a13fbc36e2f5fabc90293a1f04d5f133aa` | same | yes |

### Run2 and run1/run2 comparison

The same BLAKE2b-128 policy (`FlyCallM12-v1`, signed-int64 little-endian IDs, digest ascending and node ID tie-break only on digest collision) streamed all `88,384,522` node rows. It selected seed `274013289` with priority `000000101b2e6230592f8718fc4de3c2`. Seed selection took `99.551 s`; streaming BFS took `43.735 s`. BFS reached the 500-node cap in two complete layers and completed four full edge scans (two BFS layers, induced-edge extraction and independent validation), reading `607,426,736` rows. It returned 500 nodes and 2,216 directed induced edges; independent validation passed. Peak RSS was `203,833,344` bytes; minimum free disk during BFS was `18,343,780,352` bytes; scratch output was `106,793` bytes. Full run elapsed `145.240 s`, including source checksums and comparison.

| Comparison | Result |
|---|---|
| Seed ID | run1/run2 both `274013289` |
| Selected node IDs | exact same 500-ID set; canonical set SHA-256 `c21e96f221e7bb301f16cff129cd612fb54dd4232f3aa62f77f1fd444a0e19ae` |
| Sorted induced `(source_id,target_id,weight)` tuples | exact same 2,216 tuples; canonical SHA-256 `df8cccc1e34a101c6c54e61f9bbaf5b8bf8c3983209531a6bd0469b9f26c0471` |
| Source-row-order digest | both `5b33825d0d9ba8f13fc72b2cb4b25556eba43e55255d0743cffc4b705ed53882` |
| Candidate Parquet SHA-256 | nodes both `a8ad1e6a42c0a386d4bdef517ac628c29a5b7b8f023c51b43cce8e0354087428`; edges both `afa69be2078eaf136d00511539145dc82ea54af5aa2f52ffdcb87501488e2175` |

`induced_edges_sha256` is computed in source Parquet row order, so it is order-sensitive and must not be treated as a permutation-invariant set checksum. The sorted-tuple canonical SHA-256 is the order-independent comparison. Both checks matched for the unchanged source.

### Archived engineering demo artifact

The preserved run1 and run2 scratch outputs remain under `.scratch/1999-connectome-demo/probes/m1-2/`. The archive is [engineering-demo-v1.0](../../../data/connectome/derived/malecns_v1.0/subgraphs/engineering-demo-v1.0/) and contains `nodes.parquet`, `edges.parquet`, and `manifest.json`. Archive table checksums match run2 scratch exactly:

| Archived file | SHA-256 |
|---|---|
| `nodes.parquet` | `a8ad1e6a42c0a386d4bdef517ac628c29a5b7b8f023c51b43cce8e0354087428` |
| `edges.parquet` | `afa69be2078eaf136d00511539145dc82ea54af5aa2f52ffdcb87501488e2175` |
| `manifest.json` | `5300c6cefdc6b84a854545e64f4131baa3fc42f0bde97a83f68fcc1c3769cf40` |

The manifest records the MaleCNS v1.0 generation and upstream/M1.1 checksums, hash rule and salt, seed, node cap, node/edge counts, weak-view BFS selection, retained directed edge/weight semantics, run and validation details, output checksums, and the explicit non-representativeness limitation. It records `weight` as the published segment-to-segment connection weight: source documentation describes it as the number of connections/postsynaptic densities, not calibrated synaptic efficacy. The exact upstream `minconf-0.5` comparator remains unspecified; the published artifact was used as-is with no additional filter. M1.1 files were not overwritten or moved. M1.2 acceptance checks passed and the ticket is completed. A dependent M1.3 I/O reachability ticket was created; implementation has not started.

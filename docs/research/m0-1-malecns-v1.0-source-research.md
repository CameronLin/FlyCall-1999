# M0.1 research: MaleCNS v1.0 source and probe

Checked: 2026-10-13  
Scope: official MaleCNS and neuPrint documentation, a 128 KiB read-only range probe, and a full-object download solely to compute SHA-256. No edge rows were parsed, and no graph import, subgraph generation, or case-data access was performed.

## Decision

Use the official **bulk connectivity Feather object** for any eventual whole-graph input:

`gs://flyem-male-cns/v1.0/connectome-data/flat-connectome/connectome-weights-male-cns-v1.0-minconf-0.5.feather`

HTTPS object URL: <https://storage.googleapis.com/flyem-male-cns/v1.0/connectome-data/flat-connectome/connectome-weights-male-cns-v1.0-minconf-0.5.feather>

The MaleCNS download page identifies it as the full segment-to-segment connection graph, excludes segments with no synapses, and lists its size as 1.1 GB. The same page says bulk data is suitable for analysis or ingestion into another database. The neuPrint client FAQ recommends bulk exports for whole-connectome analysis and says the buckets are public; API queries are intended for targeted exploration. The selected route is the public, version-pinned bulk object. The complete file was downloaded only to establish its SHA-256; edge rows were not parsed. [MaleCNS downloads](https://male-cns.janelia.org/download/) · [neuprint-python bulk-download FAQ](https://connectome-neuprint.github.io/neuprint-python/docs/faq.html)

MaleCNS v1.0 was released on 2026-06-08; its release notes describe minor proofreading changes and refined neuron annotations. Pin this release and exact object name rather than following a moving “latest” source. [MaleCNS release notes](https://male-cns.janelia.org/release/)

## Fields, direction, and confidence

| Contract item | Verified from first-party material | Consequence / limit |
|---|---|---|
| Bulk object fields | Parsed from the actual Feather/Pandas metadata in the first 65,536 bytes: `body_pre`, `body_post`, and `weight`, all `int64`; the embedded range index reports 151,856,684 rows. | These are the observed stored column names and types. No data batch or edge row was decoded in this small probe; validate an actual edge before M1. [Probe result](../../data/connectome/malecns_v1.0/probe_result_v1.0.json) |
| neuPrint connection row | The `neuprint-python` query reference documents `bodyId_pre`, `bodyId_post`, and `weight`; with `omit_rois=True`, the adjacency result contains these core fields. | These API names are not the names in the selected bulk object. Do not treat the API and bulk schemas as interchangeable. [Query reference](https://connectome-neuprint.github.io/neuprint-python/docs/queries.html) |
| Direction | The neuPrint query API calls the requested `sources` upstream and `targets` downstream; its examples place identifiers in `bodyId_pre` and `bodyId_post`, respectively. The graph data model describes `ConnectsTo` edges and their associated presynaptic and postsynaptic neurons. | Map pre/source → post/target. If materialized as an adjacency matrix, use `A[target, source]` only as an explicit project convention; do not transpose the stored source table. [Query reference](https://connectome-neuprint.github.io/neuprint-python/docs/queries.html) · [neuPrint property-graph model](https://github.com/connectome-neuprint/neuPrint/blob/master/pgmspecs.md) |
| Weight | The neuPrint property-graph model defines connection `weight` as the number of postsynaptic densities per connection. | Treat it as a count/connection-strength field, not as a calibrated biological synaptic efficacy. Confirm that the selected API probe and bulk schema agree before adopting the common edge contract. [neuPrint property-graph model](https://github.com/connectome-neuprint/neuPrint/blob/master/pgmspecs.md) |
| Confidence | The official MaleCNS connectivity filename is designated `minconf-0.5`; the official page separately documents `conf_pre` and `conf_post` columns for the synaptic-partner table. The connection-weight table is an aggregated edge table, and the page does not list a per-edge confidence column or spell out the exact predicate used to form the `minconf-0.5` product. | Select the published `minconf-0.5` product and apply no additional confidence filter to its edges. Do not infer that edge weight is a confidence score. If the exact upstream per-synapse predicate is needed, obtain its release-method definition from the maintainers; it is not specified on the download page. [MaleCNS downloads](https://male-cns.janelia.org/download/) |

The neuPrint client supports additional relationship properties such as `weightHP` only when available in the dataset; the docs note some such fields are dataset-specific. Do not add `weightHP` to the MaleCNS contract unless the v1.0 API probe confirms it is present. [neuprint-python query reference](https://connectome-neuprint.github.io/neuprint-python/docs/queries.html) · [neuPrint property-graph model](https://github.com/connectome-neuprint/neuPrint/blob/master/pgmspecs.md)

## Reproducible small bulk probe

The object is public and advertises byte-range support. The rerunnable probe script pins the GCS generation, checks the HEAD metadata, fetches the first and last 65,536 bytes, validates HTTP 206 and `Content-Range`, checks Feather magic, parses the embedded schema metadata, and computes SHA-256 for each range:

```sh
python3 -B data/connectome/malecns_v1.0/probe_bulk_range.py \
  --output data/connectome/malecns_v1.0/probe_result_v1.0.json
```

Observed object metadata: 1,051,241,946 bytes; GCS generation `1780494887545976`; server MD5 `8w6dzKJc/QIb8eez2XVZng==`; server CRC32C `dKRPVQ==`. The two retrieved ranges total 131,072 bytes. Their SHA-256 values are `9d011c0b23cd637824184893e42f5d7812391bfa886f790fb6f2294b1df018a4` (bytes 0–65535) and `54d98f0c78c9ca6104acce43a6854a3c0954221cc47ee24c9c40f1d1da22fd48` (bytes 1051176410–1051241945). The raw range result remains in the machine-readable probe result. [Probe script](../../data/connectome/malecns_v1.0/probe_bulk_range.py) · [Probe result](../../data/connectome/malecns_v1.0/probe_result_v1.0.json)

The first and last ranges both contain the expected `ARROW1` marker. Parsing the first range found the three `int64` fields listed above. The checked-in script provides the rerunnable range-probe procedure. Those range checksums remain distinct from the complete object SHA-256 below.

## Complete file acquisition and SHA-256

No matching local Feather file existed under `data/connectome/`, so the exact GCS generation was downloaded. The GET included both the `generation=1780494887545976` query parameter and `x-goog-if-generation-match: 1780494887545976`; the HTTP 200 response returned `x-goog-generation: 1780494887545976`, `Content-Length: 1051241946`, GCS MD5 `8w6dzKJc/QIb8eez2XVZng==`, and CRC32C `dKRPVQ==`. The complete file is at `data/connectome/malecns_v1.0/connectome-weights-male-cns-v1.0-minconf-0.5.feather`.

Commands used:

```sh
curl --fail --location --show-error --retry 3 --retry-delay 2 \
  --header 'x-goog-if-generation-match: 1780494887545976' \
  --dump-header /private/tmp/flycall_malecns_v1_headers.txt \
  --output /Users/linyifen/Desktop/coding/FlyCall-1999/data/connectome/malecns_v1.0/connectome-weights-male-cns-v1.0-minconf-0.5.feather.partial \
  'https://storage.googleapis.com/flyem-male-cns/v1.0/connectome-data/flat-connectome/connectome-weights-male-cns-v1.0-minconf-0.5.feather?generation=1780494887545976'

mv data/connectome/malecns_v1.0/connectome-weights-male-cns-v1.0-minconf-0.5.feather.partial \
  data/connectome/malecns_v1.0/connectome-weights-male-cns-v1.0-minconf-0.5.feather
shasum -a 256 data/connectome/malecns_v1.0/connectome-weights-male-cns-v1.0-minconf-0.5.feather
stat -f 'bytes=%z path=%N' data/connectome/malecns_v1.0/connectome-weights-male-cns-v1.0-minconf-0.5.feather
```

SHA-256 computed on 2026-10-13: `e35da783d1c686b2b58b3b87cd6a403ae43bfcfba8bff28e08ef752c1a56afc1`. `stat` reported exactly 1,051,241,946 bytes. `du -h` reported 1.0G; free space changed from 25 GiB before the download to 24 GiB afterward. The full file was read for hashing and size only; no Feather table or edge rows were decoded.

## License and attribution

The MaleCNS project states that the dataset is CC-BY; its download page links to the Creative Commons Attribution 4.0 deed. CC BY 4.0 requires appropriate credit, a link to the license, and an indication of changes. [MaleCNS release notes](https://male-cns.janelia.org/release/) · [CC BY 4.0 deed](https://creativecommons.org/licenses/by/4.0/)

Suggested attribution for an unmodified source table:

> MaleCNS v1.0 connectome data, produced by the FlyEM Project Team (HHMI Janelia), the University of Cambridge Department of Zoology, the MRC Laboratory of Molecular Biology, and Google Research. Berg S. et al., “Sexual dimorphism in the complete Drosophila male central nervous system connectome,” *Cell* 189(18), 5504–5526.e15 (2026), https://doi.org/10.1016/j.cell.2026.08.015. Source: https://male-cns.janelia.org/download/. Licensed CC BY 4.0: https://creativecommons.org/licenses/by/4.0/. No changes to the source table.

The collaboration partners and release are listed on the official project/release pages; the publication metadata and full author citation are recorded by Janelia. If derived files are later created, replace the final sentence with a clear description of those changes and preserve this source attribution. [MaleCNS project page](https://male-cns.janelia.org/) · [Janelia publication record](https://www.janelia.org/node/70503)

## Unresolved items

1. The official download page does not document the exact confidence comparator or per-synapse predicate used to construct `minconf-0.5`. The selected object is explicitly named for that published threshold; use it as-is and apply no second filter. Ask maintainers for the predicate only if downstream work requires it.
2. M1.1 must decode a small table batch and confirm an actual edge row and intended weight interpretation; this M0.1 task did not parse edge rows.

No case dataset was read or modified. The full source object was downloaded only for its complete SHA-256 and size verification; no edge rows were parsed or transformed.

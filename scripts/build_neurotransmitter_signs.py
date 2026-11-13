#!/usr/bin/env python3
"""Build the per-neuron sign table from the pinned MaleCNS neurotransmitter file.

Ticket 18 (M0.2). Reads only the checksum-pinned official Feather file, writes a
git-ignored Parquet sign table plus a small committed summary JSON that also
reports how the current G0 engineering subgraph (500 nodes) splits by sign.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

import pyarrow.feather as feather  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

from flycall_data.neurotransmitter_signs import (  # noqa: E402
    SIGN_VARIANTS,
    build_sign_table,
    coverage,
    summarize_signs,
)

SOURCE = "data/connectome/malecns_v1.0/body-neurotransmitters-male-cns-v1.0.feather"
SOURCE_SHA256 = "95c9289220663abeb3409f3ad9e5a7f8a53f8093f5139d15502cd08da8879621"
SOURCE_BYTES = 43282834
OUTPUT = "data/connectome/derived/malecns_v1.0/neuron_signs_v1.0.parquet"
SUMMARY = "data/connectome/derived/malecns_v1.0/neuron_signs_v1.0_summary.json"
G0_GRAPH = ".scratch/1999-connectome-demo/runs/m3-2-fly-ab-seed-42-crlf-fix-20261026/graph_definition.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=SOURCE)
    parser.add_argument("--output", default=OUTPUT)
    parser.add_argument("--summary", default=SUMMARY)
    parser.add_argument("--g0-graph", default=G0_GRAPH)
    args = parser.parse_args()

    source = PROJECT_ROOT / args.source
    if source.stat().st_size != SOURCE_BYTES or _sha256(source) != SOURCE_SHA256:
        raise SystemExit("Neurotransmitter source differs from the pinned size/SHA-256; see neurotransmitter_source_manifest.yaml.")
    table = build_sign_table(feather.read_table(source))
    output = PROJECT_ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, output)
    # The Parquet writer may vary bytes across library versions; record the sign
    # content digest too, which is what downstream code depends on.
    content = json.dumps(
        {column: table[column].to_pylist() for column in ("body", *SIGN_VARIANTS)}, separators=(",", ":")
    ).encode("utf-8")

    graph = json.loads((PROJECT_ROOT / args.g0_graph).read_text(encoding="utf-8"))
    bodies = table["body"].to_pylist()
    g0: dict[str, object] = {"graph": args.g0_graph}
    for column in SIGN_VARIANTS:
        signs = dict(zip(bodies, table[column].to_pylist()))
        g0[column] = {
            "all_nodes": coverage((int(node) for node in graph["node_ids"]), signs),
            "input_nodes": coverage((int(node) for node in graph["input_node_ids"]), signs),
            "output_nodes": coverage((int(node) for node in graph["output_node_ids"]), signs),
        }

    summary = {
        "schema_version": 1,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "ticket": "18 M0.2",
        "source": {"path": args.source, "bytes": SOURCE_BYTES, "sha256": SOURCE_SHA256},
        "label_column": "consensus_nt",
        "rules": {
            "acetylcholine": 1, "gaba": -1, "histamine": -1,
            "glutamate": {"sign_glu_inhibitory": -1, "sign_glu_excitatory": 1},
            "dopamine|octopamine|serotonin": "excluded (modulatory)",
            "unclear|missing": "excluded",
            "extra_confidence_threshold": "none; consensus_nt already applies the official 0.5 confidence and presynapse-count rules",
        },
        "output": {
            "path": args.output,
            "parquet_sha256": _sha256(output),
            "sign_content_sha256": hashlib.sha256(content).hexdigest(),
        },
        "summary": summarize_signs(table),
        "g0_engineering_subgraph_coverage": g0,
    }
    summary_path = PROJECT_ROOT / args.summary
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"summary": summary["summary"], "g0": g0}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

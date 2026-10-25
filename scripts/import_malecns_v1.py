#!/usr/bin/env python3
"""Run the bounded-memory M1.1 MaleCNS v1.0 import."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from flycall_data.connectome_importer import write_standard_tables  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source",
        type=Path,
        default=PROJECT_ROOT
        / "data/connectome/malecns_v1.0/connectome-weights-male-cns-v1.0-minconf-0.5.feather",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "data/connectome/derived/malecns_v1.0",
    )
    parser.add_argument("--batch-rows", type=int, default=65_536)
    arguments = parser.parse_args()
    result = write_standard_tables(
        arguments.source, arguments.output, arguments.batch_rows
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

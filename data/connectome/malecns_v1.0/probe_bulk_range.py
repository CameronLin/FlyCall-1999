#!/usr/bin/env python3
"""Read a small, pinned range from the official MaleCNS v1.0 Feather object."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from typing import Any


URL = (
    "https://storage.googleapis.com/flyem-male-cns/v1.0/connectome-data/"
    "flat-connectome/connectome-weights-male-cns-v1.0-minconf-0.5.feather"
)
EXPECTED_GENERATION = "1780494887545976"
RANGE_SIZE = 64 * 1024
TIMEOUT_SECONDS = 45


def fetch_head() -> dict[str, str]:
    request = Request(URL, method="HEAD")
    with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        if response.status != 200:
            raise RuntimeError(f"Expected HTTP 200 for HEAD, got {response.status}.")
        headers = {key.lower(): value for key, value in response.headers.items()}
        hash_values = response.headers.get_all("x-goog-hash") or []
    if hash_values:
        headers["x-goog-hash"] = ",".join(hash_values)
    generation = headers.get("x-goog-generation")
    if generation != EXPECTED_GENERATION:
        raise RuntimeError(
            "The published object generation changed: "
            f"expected {EXPECTED_GENERATION}, got {generation!r}."
        )
    if headers.get("accept-ranges", "").lower() != "bytes":
        raise RuntimeError("The object endpoint does not advertise byte-range reads.")
    return headers


def fetch_range(start: int, end: int, total_size: int) -> tuple[bytes, str]:
    request = Request(URL, headers={"Range": f"bytes={start}-{end}"})
    with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
        if response.status != 206:
            raise RuntimeError(f"Expected HTTP 206 for range read, got {response.status}.")
        content_range = response.headers.get("Content-Range", "")
        expected_range = f"bytes {start}-{end}/{total_size}"
        if content_range != expected_range:
            raise RuntimeError(
                f"Unexpected Content-Range: expected {expected_range!r}, got {content_range!r}."
            )
        data = response.read()
    expected_length = end - start + 1
    if len(data) != expected_length:
        raise RuntimeError(f"Expected {expected_length} bytes, got {len(data)}.")
    return data, content_range


def read_embedded_pandas_metadata(head: bytes) -> dict[str, Any]:
    marker = b'{"index_columns":'
    start = head.find(marker)
    if start < 0:
        raise RuntimeError("Pandas schema metadata was not found in the initial range.")
    tail = head[start:].decode("utf-8", errors="ignore")
    try:
        metadata, _ = json.JSONDecoder().raw_decode(tail)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Could not parse embedded Feather metadata: {exc}.") from exc
    if not isinstance(metadata, dict) or not isinstance(metadata.get("columns"), list):
        raise RuntimeError("Embedded Feather metadata has no column schema.")
    return metadata


def parse_gcs_hashes(header: str | None) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for item in (header or "").split(","):
        name, separator, value = item.strip().partition("=")
        if separator:
            hashes[name] = value
    return hashes


def build_result() -> dict[str, Any]:
    headers = fetch_head()
    try:
        object_size = int(headers["content-length"])
    except (KeyError, ValueError) as exc:
        raise RuntimeError("HEAD response has no valid Content-Length.") from exc
    if object_size < RANGE_SIZE:
        raise RuntimeError(f"Object is unexpectedly small: {object_size} bytes.")

    head_start, head_end = 0, RANGE_SIZE - 1
    tail_start, tail_end = object_size - RANGE_SIZE, object_size - 1
    head, head_content_range = fetch_range(head_start, head_end, object_size)
    tail, tail_content_range = fetch_range(tail_start, tail_end, object_size)
    if not head.startswith(b"ARROW1") or not tail.endswith(b"ARROW1"):
        raise RuntimeError("Byte-range probes do not have the expected Feather/Arrow magic bytes.")

    pandas_metadata = read_embedded_pandas_metadata(head)
    index_columns = pandas_metadata.get("index_columns", [])
    row_count = None
    if index_columns and isinstance(index_columns[0], dict):
        index = index_columns[0]
        if index.get("kind") == "range" and isinstance(index.get("stop"), int):
            row_count = index["stop"] - index.get("start", 0)
    columns = []
    for column in pandas_metadata["columns"]:
        columns.append(
            {
                "name": column.get("name"),
                "numpy_type": column.get("numpy_type"),
                "pandas_type": column.get("pandas_type"),
            }
        )

    return {
        "probe_schema": "flycall.malecns.bulk-range-probe.v1",
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_url": URL,
        "expected_generation": EXPECTED_GENERATION,
        "object": {
            "content_length_bytes": object_size,
            "content_type": headers.get("content-type"),
            "last_modified": headers.get("last-modified"),
            "etag": headers.get("etag"),
            "generation": headers.get("x-goog-generation"),
            "accept_ranges": headers.get("accept-ranges"),
            "server_checksums": parse_gcs_hashes(headers.get("x-goog-hash")),
            "full_object_sha256": None,
            "full_object_sha256_note": "Not computed; the 1,051,241,946-byte object was not downloaded.",
        },
        "feather_probe": {
            "format_magic": "ARROW1",
            "rows_from_embedded_pandas_range_index": row_count,
            "columns_from_embedded_pandas_metadata": columns,
            "probe_scope": "First and last 65,536 bytes only; no table batch decoded.",
            "ranges": [
                {
                    "content_range": head_content_range,
                    "bytes": len(head),
                    "sha256": hashlib.sha256(head).hexdigest(),
                    "magic_at_expected_edge": "ARROW1 at file start",
                },
                {
                    "content_range": tail_content_range,
                    "bytes": len(tail),
                    "sha256": hashlib.sha256(tail).hexdigest(),
                    "magic_at_expected_edge": "ARROW1 at file end",
                },
            ],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path to save the JSON result; otherwise print to stdout.",
    )
    args = parser.parse_args()
    try:
        result = build_result()
    except (HTTPError, URLError, TimeoutError, OSError, RuntimeError) as exc:
        print(f"probe failed: {exc}", file=sys.stderr)
        return 1
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

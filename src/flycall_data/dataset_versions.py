"""Frozen formal dataset versions the pipeline can be pointed at (ticket 25).

v1.0.0 is the template-assembled dataset (review pending); v2.0.0 is the hand-written rewrite whose
`review_status` records that automated QA replaced manual review (D-V2-4). Both share the same labels,
scenario families, split manifest and per-family quotas, so every downstream contract (700/150/150,
family-grouped splits, test sealed) is unchanged.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from flycall_data.loader import DatasetPaths

PROJECT_ROOT = Path(__file__).resolve().parents[2]
_TAXONOMY_DIR = PROJECT_ROOT / "data/1999_synthetic/taxonomy/current"
_MANIFEST = _TAXONOMY_DIR / "formal_split_manifest_frozen_v1.0.yaml"


@dataclass(frozen=True)
class DatasetVersion:
    version: str
    paths: DatasetPaths
    review_status: str
    source_name: str


DATASET_VERSIONS: dict[str, DatasetVersion] = {
    "v1.0.0": DatasetVersion(
        version="v1.0.0",
        paths=DatasetPaths(
            jsonl_path=PROJECT_ROOT / "data/1999_synthetic/formal/v1.0.0/formal_dataset_v1.0.0.jsonl",
            csv_path=PROJECT_ROOT / "data/1999_synthetic/formal/v1.0.0/formal_dataset_v1.0.0.csv",
            taxonomy_path=_TAXONOMY_DIR / "taxonomy_v1.3.yaml",
            frozen_manifest_path=_MANIFEST,
        ),
        review_status="pending_manual_review",
        source_name="formal_dataset_v1.0.0",
    ),
    "v2.0.0": DatasetVersion(
        version="v2.0.0",
        paths=DatasetPaths(
            jsonl_path=PROJECT_ROOT / "data/1999_synthetic/formal/v2.0.0/formal_dataset_v2.0.0.jsonl",
            csv_path=PROJECT_ROOT / "data/1999_synthetic/formal/v2.0.0/formal_dataset_v2.0.0.csv",
            taxonomy_path=_TAXONOMY_DIR / "taxonomy_v1.3_dataset_v2.yaml",
            frozen_manifest_path=_MANIFEST,
        ),
        review_status="automated_qa_passed_no_manual_review",
        source_name="formal_dataset_v2.0.0",
    ),
}
DEFAULT_DATASET_VERSION = "v1.0.0"


def get_dataset_version(version: str) -> DatasetVersion:
    try:
        return DATASET_VERSIONS[version]
    except KeyError as error:
        raise ValueError(f"Unknown dataset version {version!r}; expected one of {sorted(DATASET_VERSIONS)}.") from error

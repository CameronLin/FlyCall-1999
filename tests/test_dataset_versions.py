"""Dataset version switch (ticket 25): v2.0.0 loads through the same frozen contract as v1.0.0."""

from __future__ import annotations

import json
import unittest

from flycall_data.dataset_versions import DATASET_VERSIONS, get_dataset_version
from flycall_data.loader import load_frozen_dataset


class DatasetVersionTests(unittest.TestCase):
    def test_unknown_version_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            get_dataset_version("v9.9.9")

    def test_v1_paths_are_unchanged(self) -> None:
        v1 = get_dataset_version("v1.0.0")
        self.assertTrue(v1.paths.jsonl_path.as_posix().endswith("formal/v1.0.0/formal_dataset_v1.0.0.jsonl"))
        self.assertEqual(v1.review_status, "pending_manual_review")

    def test_versions_share_the_split_manifest(self) -> None:
        manifests = {version.paths.frozen_manifest_path for version in DATASET_VERSIONS.values()}
        self.assertEqual(len(manifests), 1)

    def test_v2_loads_under_the_frozen_contract(self) -> None:
        v2 = get_dataset_version("v2.0.0")
        if not v2.paths.jsonl_path.exists():
            self.skipTest("dataset v2.0.0 not frozen in this checkout")
        bundle = load_frozen_dataset(v2.paths)
        self.assertEqual(bundle.audit_summary["split_counts"], {"train": 700, "validation": 150, "test": 150})
        self.assertTrue(all(row["review_status"] == "automated_qa_passed_no_manual_review" for row in bundle.records))
        self.assertTrue(all(row["id"].startswith("TPE1999-V2-") for row in bundle.records))

    def test_v2_keeps_v1_family_split_assignment(self) -> None:
        v1, v2 = get_dataset_version("v1.0.0"), get_dataset_version("v2.0.0")
        if not v2.paths.jsonl_path.exists():
            self.skipTest("dataset v2.0.0 not frozen in this checkout")

        def family_splits(path):
            out = {}
            for line in path.read_text(encoding="utf-8").splitlines():
                row = json.loads(line)
                out.setdefault(row["scenario_family_id"], set()).add(row["split"])
            return out

        self.assertEqual(family_splits(v1.paths.jsonl_path), family_splits(v2.paths.jsonl_path))


if __name__ == "__main__":
    unittest.main()

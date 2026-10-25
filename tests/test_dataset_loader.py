from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
import csv
import io
from pathlib import Path

from flycall_data.loader import DatasetContractError, DatasetPaths, load_frozen_dataset


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class LoadFrozenDatasetTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.fixture_root = Path(self.temp_dir.name)
        fixture_files = {
            "jsonl_path": (
                "data/1999_synthetic/formal/v1.0.0/formal_dataset_v1.0.0.jsonl",
                "formal_dataset.jsonl",
            ),
            "csv_path": (
                "data/1999_synthetic/formal/v1.0.0/formal_dataset_v1.0.0.csv",
                "formal_dataset.csv",
            ),
            "taxonomy_path": (
                "data/1999_synthetic/taxonomy/current/taxonomy_v1.3.yaml",
                "taxonomy.yaml",
            ),
            "frozen_manifest_path": (
                "data/1999_synthetic/taxonomy/current/formal_split_manifest_frozen_v1.0.yaml",
                "manifest.yaml",
            ),
        }
        copied_paths: dict[str, Path] = {}
        for key, (source_rel, fixture_name) in fixture_files.items():
            destination = self.fixture_root / fixture_name
            shutil.copyfile(PROJECT_ROOT / source_rel, destination)
            copied_paths[key] = destination
        self.paths = DatasetPaths(**copied_paths)

    def source_hashes(self) -> dict[str, str]:
        return {
            "jsonl": sha256(self.paths.jsonl_path),
            "csv": sha256(self.paths.csv_path),
            "taxonomy": sha256(self.paths.taxonomy_path),
            "manifest": sha256(self.paths.frozen_manifest_path),
        }

    def read_jsonl_rows(self) -> list[dict[str, object]]:
        return [
            json.loads(line)
            for line in self.paths.jsonl_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    def write_jsonl_rows(self, rows: list[dict[str, object]]) -> None:
        self.paths.jsonl_path.write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
            encoding="utf-8",
        )

    def write_csv_rows(self, rows: list[dict[str, object]]) -> None:
        output = io.StringIO(newline="")
        with self.paths.csv_path.open(encoding="utf-8", newline="") as source:
            fieldnames = csv.DictReader(source).fieldnames
        assert fieldnames is not None
        writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            rendered = dict(row)
            rendered["speaker_map"] = str(rendered["speaker_map"])
            writer.writerow(rendered)
        self.paths.csv_path.write_text(output.getvalue(), encoding="utf-8")

    def write_consistent_rows(self, rows: list[dict[str, object]]) -> None:
        self.write_jsonl_rows(rows)
        self.write_csv_rows(rows)

    def issue_codes(self, error: DatasetContractError) -> set[str]:
        return {issue.code for issue in error.issues}

    def test_loads_valid_frozen_data_and_returns_audit_summary(self) -> None:
        before = self.source_hashes()

        bundle = load_frozen_dataset(self.paths)

        self.assertEqual(len(bundle.records), 1000)
        self.assertEqual(len(bundle.label_names), 5)
        self.assertEqual(bundle.split_counts, {"train": 700, "validation": 150, "test": 150})
        self.assertEqual(bundle.audit_summary["record_count"], 1000)
        self.assertEqual(bundle.audit_summary["family_count"], 66)
        self.assertEqual(bundle.audit_summary["source_sha256"]["jsonl"], before["jsonl"])
        self.assertEqual(self.source_hashes(), before)

    def test_rejects_missing_required_field_with_structured_issue(self) -> None:
        rows = self.read_jsonl_rows()
        del rows[0]["review_status"]
        self.write_consistent_rows(rows)

        with self.assertRaises(DatasetContractError) as caught:
            load_frozen_dataset(self.paths)

        self.assertIn("record_missing_fields", self.issue_codes(caught.exception))
        self.assertTrue(caught.exception.issues[0].message)

    def test_rejects_duplicate_record_id(self) -> None:
        rows = self.read_jsonl_rows()
        rows[1]["id"] = rows[0]["id"]
        self.write_consistent_rows(rows)

        with self.assertRaises(DatasetContractError) as caught:
            load_frozen_dataset(self.paths)

        self.assertIn("duplicate_record_id", self.issue_codes(caught.exception))

    def test_rejects_unknown_label_and_manifest_family_quota_mismatch(self) -> None:
        rows = self.read_jsonl_rows()
        rows[0]["label_id"] = "unknown_label"
        rows[0]["label_name"] = "未知類別"
        self.write_consistent_rows(rows)
        with self.assertRaises(DatasetContractError) as label_error:
            load_frozen_dataset(self.paths)
        self.assertIn("unknown_record_labels", self.issue_codes(label_error.exception))

        manifest = self.paths.frozen_manifest_path.read_text(encoding="utf-8")
        self.paths.frozen_manifest_path.write_text(
            manifest.replace("planned_records: 20", "planned_records: 19", 1),
            encoding="utf-8",
        )
        with self.assertRaises(DatasetContractError) as quota_error:
            load_frozen_dataset(self.paths)
        self.assertIn("family_quota_mismatch", self.issue_codes(quota_error.exception))

    def test_rejects_label_name_that_disagrees_with_taxonomy(self) -> None:
        rows = self.read_jsonl_rows()
        rows[0]["label_name"] = "錯誤類別名稱"
        self.write_consistent_rows(rows)

        with self.assertRaises(DatasetContractError) as caught:
            load_frozen_dataset(self.paths)

        self.assertIn("record_label_name_mismatch", self.issue_codes(caught.exception))

    def test_rejects_manifest_split_quotas_outside_frozen_contract(self) -> None:
        manifest = self.paths.frozen_manifest_path.read_text(encoding="utf-8")
        self.paths.frozen_manifest_path.write_text(
            manifest.replace("train: 140", "train: 139", 1),
            encoding="utf-8",
        )

        with self.assertRaises(DatasetContractError) as caught:
            load_frozen_dataset(self.paths)

        self.assertIn("manifest_category_split_quota_mismatch", self.issue_codes(caught.exception))

    def test_rejects_jsonl_csv_content_mismatch(self) -> None:
        rows = self.read_jsonl_rows()
        rows[0]["transcript"] = str(rows[0]["transcript"]) + "額外差異"
        self.write_jsonl_rows(rows)

        with self.assertRaises(DatasetContractError) as caught:
            load_frozen_dataset(self.paths)

        self.assertIn("jsonl_csv_content_mismatch", self.issue_codes(caught.exception))

    def test_rejects_family_crossing_splits(self) -> None:
        rows = self.read_jsonl_rows()
        original_family = rows[0]["scenario_family_id"]
        another_row = next(row for row in rows[1:] if row["scenario_family_id"] == original_family)
        rows[0]["split"] = "test" if another_row["split"] != "test" else "train"
        self.write_consistent_rows(rows)

        with self.assertRaises(DatasetContractError) as caught:
            load_frozen_dataset(self.paths)

        self.assertIn("family_cross_split", self.issue_codes(caught.exception))

    def test_failed_load_does_not_change_any_source_checksum(self) -> None:
        rows = self.read_jsonl_rows()
        rows[0]["label_id"] = "unknown_label"
        self.write_consistent_rows(rows)
        before = self.source_hashes()

        with self.assertRaises(DatasetContractError):
            load_frozen_dataset(self.paths)

        self.assertEqual(self.source_hashes(), before)


if __name__ == "__main__":
    unittest.main()

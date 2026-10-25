from __future__ import annotations

import unittest
import csv
import tempfile
from pathlib import Path
from types import SimpleNamespace

from flycall_data.text_baseline import (
    LABEL_ORDER,
    fit_tfidf_matrices,
    run_baselines,
    split_for_smoke,
)
from scripts.run_m2_2a_smoke_test import _write_predictions


def record(record_id: str, label_id: str, split: str, family_id: str, transcript: str) -> dict[str, str]:
    return {
        "id": record_id,
        "label_id": label_id,
        "split": split,
        "scenario_family_id": family_id,
        "transcript": transcript,
    }


def small_records() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for index, label_id in enumerate(LABEL_ORDER):
        rows.extend(
            [
                record(f"train-{index}-a", label_id, "train", f"train-family-{index}", f"R: 案件類別{index} L: 補充內容甲"),
                record(f"train-{index}-b", label_id, "train", f"train-family-{index}", f"L: 案件類別{index} R: 補充內容乙"),
                record(f"val-{index}", label_id, "validation", f"val-family-{index}", f"R: 驗證類別{index} L: 驗證補充{index}"),
            ]
        )
    rows.append(record("test-only", LABEL_ORDER[0], "test", "test-family", "TESTONLYTOKEN 不可進模型"))
    return rows


class TextBaselineTests(unittest.TestCase):
    def test_split_preparation_excludes_test_and_keeps_family_groups_separate(self) -> None:
        train_rows, validation_rows = split_for_smoke(small_records())

        self.assertEqual(len(train_rows), 10)
        self.assertEqual(len(validation_rows), 5)
        self.assertNotIn("test-only", {row["id"] for row in train_rows + validation_rows})
        self.assertTrue(
            {row["scenario_family_id"] for row in train_rows}.isdisjoint(
                row["scenario_family_id"] for row in validation_rows
            )
        )

    def test_tfidf_vocabulary_is_fit_on_train_texts_only(self) -> None:
        train_texts = ["R: common training phrase", "L: common another phrase"]
        validation_texts = ["VALIDATIONONLYTOKEN unseen phrase"]

        vectorizer, train_matrix, validation_matrix = fit_tfidf_matrices(
            train_texts,
            validation_texts,
            feature_kind="char",
        )

        self.assertIn("co", vectorizer.vocabulary_)
        self.assertNotIn("VA", vectorizer.vocabulary_)
        self.assertEqual(train_matrix.shape[1], validation_matrix.shape[1])
        self.assertEqual(train_matrix.shape[0], len(train_texts))
        self.assertEqual(validation_matrix.shape[0], len(validation_texts))

    def test_fixed_candidates_return_train_and_validation_metrics(self) -> None:
        rows = small_records()
        train_rows = [row for row in rows if row["split"] == "train"]
        validation_rows = [row for row in rows if row["split"] == "validation"]

        results = run_baselines(train_rows, validation_rows, random_state=42)

        self.assertEqual(len(results), 4)
        self.assertEqual(
            {(item.feature_kind, item.classifier_name) for item in results},
            {
                ("char", "logistic_regression"),
                ("phrase_char", "logistic_regression"),
                ("char", "linear_svm"),
                ("phrase_char", "linear_svm"),
            },
        )
        for item in results:
            self.assertEqual(len(item.train_metrics["confusion_matrix"]), 5)
            self.assertTrue(all(len(row) == 5 for row in item.train_metrics["confusion_matrix"]))
            self.assertEqual(len(item.validation_metrics["confusion_matrix"]), 5)
            self.assertTrue(all(len(row) == 5 for row in item.validation_metrics["confusion_matrix"]))
            self.assertEqual(set(item.validation_metrics["per_class"]), set(LABEL_ORDER))
            self.assertEqual(item.train_record_ids, tuple(row["id"] for row in train_rows))
            self.assertEqual(item.validation_record_ids, tuple(row["id"] for row in validation_rows))

    def test_test_rows_or_cross_split_families_are_rejected_at_model_boundary(self) -> None:
        rows = small_records()
        train_rows = [row for row in rows if row["split"] == "train"]
        validation_rows = [row for row in rows if row["split"] == "validation"]
        with self.assertRaisesRegex(ValueError, "validation"):
            run_baselines(train_rows, validation_rows + [rows[-1]])

        conflicting = dict(validation_rows[0])
        conflicting["scenario_family_id"] = train_rows[0]["scenario_family_id"]
        with self.assertRaisesRegex(ValueError, "scenario_family_id"):
            run_baselines(train_rows, [conflicting] + validation_rows[1:])

    def test_prediction_artifact_is_marked_provisional_and_contains_only_model_splits(self) -> None:
        result = SimpleNamespace(
            feature_kind="char",
            classifier_name="linear_svm",
            train_record_ids=("train-1",),
            validation_record_ids=("validation-1",),
            train_predictions=(LABEL_ORDER[0],),
            validation_predictions=(LABEL_ORDER[1],),
        )
        with tempfile.TemporaryDirectory() as temporary_dir:
            output_path = Path(temporary_dir) / "predictions.csv"
            count = _write_predictions(
                output_path,
                [result],
                {"train-1": LABEL_ORDER[0], "validation-1": LABEL_ORDER[1]},
            )
            with output_path.open(encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(stream))

        self.assertEqual(count, 2)
        self.assertEqual({row["split"] for row in rows}, {"train", "validation"})
        self.assertTrue(all(row["dataset_status"] == "synthetic" for row in rows))
        self.assertTrue(all(row["review_status"] == "pending_manual_review" for row in rows))
        self.assertTrue(all(row["result_status"] == "smoke_test/provisional" for row in rows))


if __name__ == "__main__":
    unittest.main()

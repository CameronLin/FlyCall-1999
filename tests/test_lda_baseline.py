from __future__ import annotations

import unittest
from dataclasses import replace
from inspect import signature

from flycall_data.embedding_pipeline import SplitEmbeddings
from flycall_data.evaluation import LABEL_ORDER
from flycall_data.lda_baseline import run_lda_logistic_baseline
from flycall_data.model_config import E5_SMALL_CONFIG


def synthetic_batches() -> tuple[SplitEmbeddings, SplitEmbeddings]:
    train_ids: list[str] = []
    train_families: list[str] = []
    train_features: list[tuple[float, ...]] = []
    train_labels: list[str] = []
    validation_ids: list[str] = []
    validation_families: list[str] = []
    validation_features: list[tuple[float, ...]] = []
    validation_labels: list[str] = []

    for class_index, label in enumerate(LABEL_ORDER):
        for replica in range(3):
            vector = [0.0] * 384
            vector[class_index] = 2.0 + replica * 0.05
            vector[5 + class_index] = replica * 0.03
            train_ids.append(f"synthetic-train-{class_index}-{replica}")
            train_families.append(f"synthetic-train-family-{class_index}-{replica}")
            train_features.append(tuple(vector))
            train_labels.append(label)

        validation_vector = [0.0] * 384
        validation_vector[class_index] = 2.1
        validation_vector[5 + class_index] = 0.02
        validation_ids.append(f"synthetic-validation-{class_index}")
        validation_families.append(f"synthetic-validation-family-{class_index}")
        validation_features.append(tuple(validation_vector))
        validation_labels.append(label)

    return (
        SplitEmbeddings(
            "train", tuple(train_ids), tuple(train_families), tuple(train_features), tuple(train_labels)
        ),
        SplitEmbeddings(
            "validation", tuple(validation_ids), tuple(validation_families),
            tuple(validation_features), tuple(validation_labels)
        ),
    )


class LDABaselineTests(unittest.TestCase):
    def test_lda_reduces_to_four_dimensions_then_fits_logistic_regression(self) -> None:
        train, validation = synthetic_batches()

        result = run_lda_logistic_baseline(train, validation, seed=23)

        self.assertEqual(result.candidate, "lda_logistic_regression")
        self.assertEqual(result.input_dimension, 384)
        self.assertEqual(result.lda_dimension, 4)
        self.assertEqual(result.label_order, LABEL_ORDER)
        self.assertEqual(result.parameters["embedding_model"], E5_SMALL_CONFIG.model_id)
        self.assertEqual(result.parameters["embedding_revision"], E5_SMALL_CONFIG.revision)
        self.assertEqual(result.estimator_class_order, tuple(sorted(LABEL_ORDER)))
        self.assertEqual(result.lda_fit_record_ids, train.record_ids)
        self.assertEqual(result.classifier_fit_record_ids, train.record_ids)
        self.assertEqual(len(result.train_reduced[0]), 4)
        self.assertEqual(len(result.validation_reduced[0]), 4)
        self.assertEqual(result.score_label_order, LABEL_ORDER)
        self.assertEqual(result.validation_predictions, LABEL_ORDER)
        self.assertEqual(result.validation_metrics["labels"], list(LABEL_ORDER))
        self.assertEqual(result.validation_metrics["confusion_matrix"], [[1 if i == j else 0 for j in range(5)] for i in range(5)])
        self.assertTrue(all(len(row) == len(LABEL_ORDER) for row in result.train_logits))
        self.assertTrue(all(len(row) == len(LABEL_ORDER) for row in result.validation_logits))
        for scores, prediction in zip(result.validation_logits, result.validation_predictions, strict=True):
            self.assertEqual(LABEL_ORDER[max(range(len(scores)), key=scores.__getitem__)], prediction)
        self.assertEqual(result.test_status, "not_run")
        self.assertEqual(result.evaluation_status, "smoke_test/provisional")

    def test_validation_changes_do_not_change_any_train_fitted_artifact(self) -> None:
        train, validation = synthetic_batches()
        original = run_lda_logistic_baseline(train, validation, seed=23)

        shifted_features = list(validation.features)
        first_row = list(shifted_features[0])
        first_row[0] += 1.25
        shifted_features[0] = tuple(first_row)
        changed_labels = tuple(reversed(validation.labels))
        changed_validation = replace(
            validation, features=tuple(shifted_features), labels=changed_labels
        )
        changed = run_lda_logistic_baseline(train, changed_validation, seed=23)

        self.assertEqual(changed.lda_fit_record_ids, train.record_ids)
        self.assertEqual(changed.classifier_fit_record_ids, train.record_ids)
        self.assertEqual(changed.train_reduced, original.train_reduced)
        self.assertEqual(changed.train_logits, original.train_logits)
        self.assertEqual(changed.train_predictions, original.train_predictions)
        self.assertNotEqual(changed.validation_reduced, original.validation_reduced)

    def test_fixture_run_is_reproducible_and_exposes_no_test_input(self) -> None:
        train, validation = synthetic_batches()
        first = run_lda_logistic_baseline(train, validation, seed=31)
        second = run_lda_logistic_baseline(train, validation, seed=31)

        self.assertEqual(first.train_logits, second.train_logits)
        self.assertEqual(first.validation_logits, second.validation_logits)
        self.assertEqual(first.validation_predictions, second.validation_predictions)
        self.assertNotIn("test", signature(run_lda_logistic_baseline).parameters)
        with self.assertRaises(TypeError):
            run_lda_logistic_baseline(train, validation, seed=31, test=object())  # type: ignore[call-arg]

    def test_train_validation_family_overlap_is_rejected(self) -> None:
        train, validation = synthetic_batches()
        overlapping = replace(
            validation,
            family_ids=(train.family_ids[0],) + validation.family_ids[1:],
        )
        with self.assertRaisesRegex(ValueError, "scenario_family_id"):
            run_lda_logistic_baseline(train, overlapping)

    def test_train_validation_record_id_overlap_is_rejected(self) -> None:
        train, validation = synthetic_batches()
        overlapping = replace(
            validation,
            record_ids=(train.record_ids[0],) + validation.record_ids[1:],
        )
        with self.assertRaisesRegex(ValueError, "record IDs"):
            run_lda_logistic_baseline(train, overlapping)

    def test_non_384_embeddings_and_missing_train_class_are_rejected(self) -> None:
        train, validation = synthetic_batches()
        short_train = replace(
            train,
            features=tuple(tuple(row[:16]) for row in train.features),
        )
        with self.assertRaisesRegex(ValueError, "384-dimensional"):
            run_lda_logistic_baseline(short_train, validation)

        retained = [index for index, label in enumerate(train.labels) if label != LABEL_ORDER[-1]]
        missing_class = replace(
            train,
            record_ids=tuple(train.record_ids[index] for index in retained),
            family_ids=tuple(train.family_ids[index] for index in retained),
            features=tuple(train.features[index] for index in retained),
            labels=tuple(train.labels[index] for index in retained),
        )
        with self.assertRaisesRegex(ValueError, "all five labels"):
            run_lda_logistic_baseline(missing_class, validation)


if __name__ == "__main__":
    unittest.main()

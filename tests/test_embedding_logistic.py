from __future__ import annotations

import unittest

from flycall_data.embedding_pipeline import SplitEmbeddings, run_baseline


LABELS = (
    "sidewalk_maintenance",
    "road_surface_defect",
    "park_general_maintenance",
    "waste_truck_service",
    "street_cleaning",
)


def batches() -> tuple[SplitEmbeddings, SplitEmbeddings]:
    train_ids: list[str] = []
    train_families: list[str] = []
    train_features: list[tuple[float, ...]] = []
    train_labels: list[str] = []
    validation_ids: list[str] = []
    validation_families: list[str] = []
    validation_features: list[tuple[float, ...]] = []
    validation_labels: list[str] = []
    for index, label in enumerate(LABELS):
        vector = tuple(1.0 if axis == index else 0.0 for axis in range(len(LABELS)))
        for replica in range(2):
            train_ids.append(f"train-{index}-{replica}")
            train_families.append(f"train-family-{index}-{replica}")
            train_features.append(vector)
            train_labels.append(label)
        validation_ids.append(f"validation-{index}")
        validation_families.append(f"validation-family-{index}")
        validation_features.append(vector)
        validation_labels.append(label)
    return (
        SplitEmbeddings("train", tuple(train_ids), tuple(train_families), tuple(train_features), tuple(train_labels)),
        SplitEmbeddings("validation", tuple(validation_ids), tuple(validation_families), tuple(validation_features), tuple(validation_labels)),
    )


class EmbeddingLogisticTests(unittest.TestCase):
    def test_logistic_baseline_fits_train_and_reports_in_fixed_label_order(self) -> None:
        train, validation = batches()

        result = run_baseline(
            "logistic_regression",
            train,
            validation,
            label_order=LABELS,
            seed=17,
        )

        self.assertEqual(result.candidate, "logistic_regression")
        self.assertEqual(result.label_order, LABELS)
        self.assertEqual(result.fit_record_ids, train.record_ids)
        self.assertEqual(result.validation_record_ids, validation.record_ids)
        self.assertEqual(result.validation_metrics["labels"], list(LABELS))
        self.assertEqual(result.validation_metrics["confusion_matrix"], [[1 if i == j else 0 for j in range(5)] for i in range(5)])
        self.assertEqual(result.validation_metrics["accuracy"], 1.0)
        self.assertEqual(result.validation_metrics["macro_f1"], 1.0)
        self.assertEqual(tuple(result.validation_metrics["per_class"]), LABELS)
        self.assertTrue(all(result.validation_metrics["per_class"][label]["support"] == 1 for label in LABELS))

    def test_model_interface_has_no_test_argument(self) -> None:
        train, validation = batches()
        with self.assertRaises(TypeError):
            run_baseline("logistic_regression", train, validation, label_order=LABELS, seed=17, test=object())

    def test_family_overlap_between_train_and_validation_is_rejected(self) -> None:
        train, validation = batches()
        overlapping = SplitEmbeddings(
            "validation",
            validation.record_ids,
            (train.family_ids[0],) + validation.family_ids[1:],
            validation.features,
            validation.labels,
        )
        with self.assertRaisesRegex(ValueError, "scenario_family_id"):
            run_baseline("logistic_regression", train, overlapping, label_order=LABELS, seed=17)


if __name__ == "__main__":
    unittest.main()

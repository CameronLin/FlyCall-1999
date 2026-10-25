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


class EmbeddingTorchTests(unittest.TestCase):
    def test_mlp_and_pca_mlp_are_reproducible_with_ordered_metrics(self) -> None:
        train, validation = batches()
        common = {"label_order": LABELS, "seed": 23, "epochs": 50, "hidden_size": 12, "learning_rate": 0.04}

        mlp_first = run_baseline("mlp", train, validation, **common)
        mlp_second = run_baseline("mlp", train, validation, **common)
        pca_first = run_baseline("pca_mlp", train, validation, pca_components=4, **common)
        pca_second = run_baseline("pca_mlp", train, validation, pca_components=4, **common)

        for result in (mlp_first, mlp_second, pca_first, pca_second):
            self.assertEqual(result.label_order, LABELS)
            self.assertEqual(result.fit_record_ids, train.record_ids)
            self.assertEqual(result.validation_record_ids, validation.record_ids)
            self.assertEqual(result.validation_metrics["labels"], list(LABELS))
            self.assertEqual(len(result.validation_metrics["confusion_matrix"]), len(LABELS))
            self.assertEqual(sum(map(sum, result.validation_metrics["confusion_matrix"])), len(validation.labels))
            self.assertEqual(tuple(result.validation_metrics["per_class"]), LABELS)
            self.assertIn(result.validation_metrics["accuracy"], (0.0, 0.2, 0.4, 0.6, 0.8, 1.0))
        self.assertEqual(mlp_first.validation_predictions, mlp_second.validation_predictions)
        self.assertEqual(pca_first.validation_predictions, pca_second.validation_predictions)
        self.assertEqual(pca_first.transform_fit_record_ids, train.record_ids)
        self.assertEqual(pca_first.transform_state, pca_second.transform_state)

    def test_pca_is_fitted_only_on_train_and_rejects_excess_rank(self) -> None:
        train, validation = batches()
        first = run_baseline(
            "pca_mlp", train, validation, label_order=LABELS, seed=3,
            pca_components=4, epochs=20, hidden_size=8, learning_rate=0.04,
        )
        altered_validation = SplitEmbeddings(
            "validation",
            validation.record_ids,
            validation.family_ids,
            tuple(tuple(value * 1000.0 for value in vector) for vector in validation.features),
            validation.labels,
        )
        second = run_baseline(
            "pca_mlp", train, altered_validation, label_order=LABELS, seed=3,
            pca_components=4, epochs=20, hidden_size=8, learning_rate=0.04,
        )

        self.assertEqual(first.transform_state, second.transform_state)
        self.assertEqual(first.transform_fit_record_ids, train.record_ids)
        with self.assertRaisesRegex(ValueError, "rank"):
            run_baseline(
                "pca_mlp", train, validation, label_order=LABELS, seed=3,
                pca_components=5, epochs=1, hidden_size=8, learning_rate=0.04,
            )


if __name__ == "__main__":
    unittest.main()

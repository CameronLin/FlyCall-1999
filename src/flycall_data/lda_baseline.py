"""Train/validation-only E5 → LDA → Logistic Regression baseline.

This module consumes already-produced embedding batches. It does not load a
dataset, tokenize text, create embeddings, or accept a test batch.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any

import numpy as np
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.linear_model import LogisticRegression

from .embedding_pipeline import SplitEmbeddings
from .evaluation import LABEL_ORDER, classification_metrics
from .model_config import E5_SMALL_CONFIG


@dataclass(frozen=True)
class LDABaselineResult:
    """Fixture-run predictions, train-fit provenance and fixed-order metrics."""

    candidate: str
    label_order: tuple[str, ...]
    score_label_order: tuple[str, ...]
    estimator_class_order: tuple[str, ...]
    seed: int
    input_dimension: int
    lda_dimension: int
    lda_fit_record_ids: tuple[str, ...]
    classifier_fit_record_ids: tuple[str, ...]
    validation_record_ids: tuple[str, ...]
    train_reduced: tuple[tuple[float, ...], ...]
    validation_reduced: tuple[tuple[float, ...], ...]
    train_logits: tuple[tuple[float, ...], ...]
    validation_logits: tuple[tuple[float, ...], ...]
    train_predictions: tuple[str, ...]
    validation_predictions: tuple[str, ...]
    train_metrics: dict[str, Any]
    validation_metrics: dict[str, Any]
    parameters: dict[str, Any]
    timings_seconds: dict[str, float]
    lda_model: Any = field(repr=False, compare=False)
    classifier: Any = field(repr=False, compare=False)
    evaluation_status: str = "smoke_test/provisional"
    data_status: str = "synthetic_fixture"
    review_status: str = "pending_manual_review"
    test_status: str = "not_run"


def run_lda_logistic_baseline(
    train: SplitEmbeddings,
    validation: SplitEmbeddings,
    *,
    seed: int = 42,
) -> LDABaselineResult:
    """Fit LDA and Logistic Regression on train only, then evaluate validation.

    Inputs are expected to be 384-dimensional embeddings from the fixed E5
    contract. A test argument intentionally does not exist at this seam.
    """

    if not isinstance(train, SplitEmbeddings) or train.split != "train":
        raise ValueError("run_lda_logistic_baseline requires train embeddings first.")
    if not isinstance(validation, SplitEmbeddings) or validation.split != "validation":
        raise ValueError("run_lda_logistic_baseline requires validation embeddings second.")
    if set(train.labels) != set(LABEL_ORDER):
        raise ValueError("train labels must contain all five labels in the fixed taxonomy.")
    if set((*train.labels, *validation.labels)) - set(LABEL_ORDER):
        raise ValueError("embeddings contain a label outside the fixed taxonomy.")
    if set(train.family_ids).intersection(validation.family_ids):
        raise ValueError("scenario_family_id cannot cross train and validation.")
    if set(train.record_ids).intersection(validation.record_ids):
        raise ValueError("record IDs cannot overlap between train and validation.")
    if not isinstance(seed, int) or isinstance(seed, bool) or seed < 0:
        raise ValueError("seed must be a non-negative integer.")

    expected_dimension = E5_SMALL_CONFIG.output_dimension
    train_dimensions = {len(vector) for vector in train.features}
    validation_dimensions = {len(vector) for vector in validation.features}
    if train_dimensions != {expected_dimension} or validation_dimensions != {expected_dimension}:
        raise ValueError("M2.3 requires 384-dimensional E5 embeddings for both splits.")

    train_matrix = np.asarray(train.features, dtype=np.float64)
    validation_matrix = np.asarray(validation.features, dtype=np.float64)
    if not np.isfinite(train_matrix).all() or not np.isfinite(validation_matrix).all():
        raise ValueError("embedding features must contain only finite values.")

    lda_dimension = min(4, len(LABEL_ORDER) - 1)
    lda = LinearDiscriminantAnalysis(solver="svd", n_components=lda_dimension)
    started = time.perf_counter()
    train_reduced = lda.fit_transform(train_matrix, np.asarray(train.labels))
    lda_fit_transform_seconds = time.perf_counter() - started
    started = time.perf_counter()
    validation_reduced = lda.transform(validation_matrix)
    lda_validation_transform_seconds = time.perf_counter() - started

    classifier = LogisticRegression(
        C=1.0,
        max_iter=1000,
        random_state=seed,
        solver="lbfgs",
    )
    started = time.perf_counter()
    classifier.fit(train_reduced, np.asarray(train.labels))
    classifier_fit_seconds = time.perf_counter() - started

    started = time.perf_counter()
    train_logits = _scores_in_label_order(classifier, train_reduced)
    validation_logits = _scores_in_label_order(classifier, validation_reduced)
    train_predictions = tuple(str(value) for value in classifier.predict(train_reduced))
    validation_predictions = tuple(str(value) for value in classifier.predict(validation_reduced))
    prediction_seconds = time.perf_counter() - started

    return LDABaselineResult(
        candidate="lda_logistic_regression",
        label_order=LABEL_ORDER,
        score_label_order=LABEL_ORDER,
        estimator_class_order=tuple(str(label) for label in classifier.classes_),
        seed=seed,
        input_dimension=expected_dimension,
        lda_dimension=lda_dimension,
        lda_fit_record_ids=train.record_ids,
        classifier_fit_record_ids=train.record_ids,
        validation_record_ids=validation.record_ids,
        train_reduced=_as_tuple_matrix(train_reduced),
        validation_reduced=_as_tuple_matrix(validation_reduced),
        train_logits=_as_tuple_matrix(train_logits),
        validation_logits=_as_tuple_matrix(validation_logits),
        train_predictions=train_predictions,
        validation_predictions=validation_predictions,
        train_metrics=classification_metrics(train.labels, train_predictions, LABEL_ORDER),
        validation_metrics=classification_metrics(
            validation.labels, validation_predictions, LABEL_ORDER
        ),
        parameters={
            "embedding_model": E5_SMALL_CONFIG.model_id,
            "embedding_revision": E5_SMALL_CONFIG.revision,
            "embedding_dimension": E5_SMALL_CONFIG.output_dimension,
            "lda_solver": "svd",
            "lda_components": lda_dimension,
            "classifier": "sklearn.linear_model.LogisticRegression",
            "classifier_solver": "lbfgs",
            "classifier_C": 1.0,
            "classifier_max_iter": 1000,
            "seed": seed,
            "fit_splits": ["train"],
            "evaluation_splits": ["train", "validation"],
            "test": "not_run",
        },
        timings_seconds={
            "lda_fit_and_train_transform": lda_fit_transform_seconds,
            "lda_validation_transform": lda_validation_transform_seconds,
            "classifier_fit": classifier_fit_seconds,
            "prediction_and_scores": prediction_seconds,
        },
        lda_model=lda,
        classifier=classifier,
    )


def _scores_in_label_order(classifier: LogisticRegression, features: np.ndarray) -> np.ndarray:
    raw_scores = np.asarray(classifier.decision_function(features), dtype=np.float64)
    if raw_scores.ndim != 2 or raw_scores.shape[1] != len(classifier.classes_):
        raise ValueError("Logistic Regression did not return multiclass decision scores.")
    class_index = {str(label): index for index, label in enumerate(classifier.classes_)}
    if set(class_index) != set(LABEL_ORDER):
        raise ValueError("Logistic Regression classes differ from the fixed taxonomy.")
    return raw_scores[:, [class_index[label] for label in LABEL_ORDER]]


def _as_tuple_matrix(matrix: np.ndarray) -> tuple[tuple[float, ...], ...]:
    if matrix.ndim != 2 or not np.isfinite(matrix).all():
        raise ValueError("model output must be a finite 2D matrix.")
    return tuple(tuple(float(value) for value in row) for row in matrix)

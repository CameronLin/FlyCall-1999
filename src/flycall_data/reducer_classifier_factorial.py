"""Train/validation-only building blocks for the reducer × classifier factorial.

The factorial separates the dimensionality-reduction stage from the
classification stage: every reducer (raw E5, LDA, Fly A) is paired with every
classifier (SVM, Fly B). This module holds the reducer-agnostic pieces; it never
reads datasets, caches or test rows itself.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import statistics
from typing import Any, Sequence

import numpy as np
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

from .evaluation import LABEL_ORDER, classification_metrics

REDUCERS = ("e5", "lda", "fly_a")
CLASSIFIERS = ("svm", "fly_b")
LDA_COMPONENTS = min(4, len(LABEL_ORDER) - 1)
SVM_PARAMETERS = {"kernel": "rbf", "C": 1.0, "gamma": "scale", "decision_function_shape": "ovr"}
FLY_B_SCHEDULES = (
    {"name": "s1_m3_2_default", "learning_rate": 0.001, "max_epochs": 100, "patience": 10},
    {"name": "s2_long", "learning_rate": 0.003, "max_epochs": 200, "patience": 25},
)
CONSISTENT_DELTA_THRESHOLD = 0.02


class FactorialError(ValueError):
    """Raised when factorial inputs violate the train/validation-only contract."""


@dataclass(frozen=True)
class ReducedFeatures:
    """Train-fit reduction applied to train and validation."""

    reducer: str
    train: np.ndarray
    validation: np.ndarray
    parameters: dict[str, Any]


def _check_matrix(name: str, matrix: np.ndarray, rows: int) -> np.ndarray:
    values = np.asarray(matrix, dtype=np.float64)
    if values.ndim != 2 or values.shape[0] != rows or values.shape[1] < 1:
        raise FactorialError(f"{name} must be a 2D matrix with one row per record.")
    if not np.isfinite(values).all():
        raise FactorialError(f"{name} must contain only finite values.")
    return values


def _check_labels(labels: Sequence[str], *, require_all: bool) -> np.ndarray:
    if any(label not in LABEL_ORDER for label in labels):
        raise FactorialError("labels must come from the fixed taxonomy order.")
    if require_all and set(labels) != set(LABEL_ORDER):
        raise FactorialError("train labels must contain all five classes.")
    return np.asarray(list(labels))


def fit_lda_reducer(
    train_features: np.ndarray,
    train_labels: Sequence[str],
    validation_features: np.ndarray,
) -> ReducedFeatures:
    """Fit LDA(4) on train only, then z-score with train-only statistics."""

    y = _check_labels(train_labels, require_all=True)
    train = _check_matrix("train_features", train_features, len(y))
    validation = np.asarray(validation_features, dtype=np.float64)
    if validation.ndim != 2 or validation.shape[1] != train.shape[1]:
        raise FactorialError("validation features must share the train feature width.")
    _check_matrix("validation_features", validation, validation.shape[0])
    lda = LinearDiscriminantAnalysis(solver="svd", n_components=LDA_COMPONENTS)
    train_reduced = lda.fit_transform(train, y)
    validation_reduced = lda.transform(validation)
    mean = train_reduced.mean(axis=0)
    scale = train_reduced.std(axis=0)
    if np.any(scale <= 0):
        raise FactorialError("an LDA component has zero train variance.")
    return ReducedFeatures(
        reducer="lda",
        train=(train_reduced - mean) / scale,
        validation=(validation_reduced - mean) / scale,
        parameters={
            "lda_solver": "svd",
            "lda_components": LDA_COMPONENTS,
            "post_scaling": "train-only z-score",
            "fit_splits": ["train"],
        },
    )


@dataclass(frozen=True)
class SVMResult:
    train_predictions: tuple[str, ...]
    validation_predictions: tuple[str, ...]
    validation_scores: np.ndarray
    train_metrics: dict[str, Any]
    validation_metrics: dict[str, Any]
    parameters: dict[str, Any]


def run_svm(
    train_features: np.ndarray,
    train_labels: Sequence[str],
    validation_features: np.ndarray,
    validation_labels: Sequence[str],
) -> SVMResult:
    """StandardScaler + RBF SVC fit on train only; fixed preregistered settings."""

    y_train = _check_labels(train_labels, require_all=True)
    y_validation = _check_labels(validation_labels, require_all=False)
    train = _check_matrix("train_features", train_features, len(y_train))
    validation = _check_matrix("validation_features", validation_features, len(y_validation))
    if train.shape[1] != validation.shape[1]:
        raise FactorialError("train and validation feature widths differ.")
    model = make_pipeline(StandardScaler(), SVC(**SVM_PARAMETERS))
    model.fit(train, y_train)
    classes = [str(label) for label in model.classes_]
    if set(classes) != set(LABEL_ORDER):
        raise FactorialError("SVM classes differ from the fixed taxonomy.")
    raw_scores = np.asarray(model.decision_function(validation), dtype=np.float64)
    scores = raw_scores[:, [classes.index(label) for label in LABEL_ORDER]]
    train_predictions = tuple(str(value) for value in model.predict(train))
    validation_predictions = tuple(str(value) for value in model.predict(validation))
    return SVMResult(
        train_predictions=train_predictions,
        validation_predictions=validation_predictions,
        validation_scores=scores,
        train_metrics=classification_metrics(tuple(y_train), train_predictions, LABEL_ORDER),
        validation_metrics=classification_metrics(tuple(y_validation), validation_predictions, LABEL_ORDER),
        parameters={
            "classifier": "sklearn.svm.SVC",
            **SVM_PARAMETERS,
            "scaler": "StandardScaler (train-only)",
            "fit_splits": ["train"],
        },
    )


def summarize(values: Sequence[float]) -> dict[str, float]:
    """Mean and sample SD across seeds (SD is 0 for a single value)."""

    checked = [float(value) for value in values]
    if not checked or not all(math.isfinite(value) for value in checked):
        raise FactorialError("summary values must be finite and non-empty.")
    return {
        "mean": statistics.fmean(checked),
        "sample_std": statistics.stdev(checked) if len(checked) > 1 else 0.0,
    }


def paired_delta(first: Sequence[float], second: Sequence[float]) -> dict[str, Any]:
    """Per-seed first − second with the preregistered consistency verdict."""

    if len(first) != len(second) or not first:
        raise FactorialError("paired deltas need equal, non-empty per-seed lists.")
    deltas = [float(a) - float(b) for a, b in zip(first, second)]
    mean = statistics.fmean(deltas)
    same_sign = all(delta > 0 for delta in deltas) or all(delta < 0 for delta in deltas)
    consistent = same_sign and abs(mean) >= CONSISTENT_DELTA_THRESHOLD
    return {
        "per_seed": deltas,
        "mean": mean,
        "consistent": consistent,
        "verdict": "consistent" if consistent else "unclear",
    }

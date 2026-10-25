"""Small, text-only TF-IDF baselines for the M2.2a provisional smoke test."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC

from .evaluation import LABEL_ORDER, classification_metrics

FEATURE_CONFIGS: dict[str, dict[str, Any]] = {
    "char": {"analyzer": "char", "ngram_range": (2, 5)},
    # Short contiguous character spans serve as phrase-like features for
    # Traditional Chinese without introducing a separately downloaded tokenizer.
    "phrase_char": {"analyzer": "char", "ngram_range": (2, 4)},
}


@dataclass(frozen=True)
class BaselineRun:
    """Metrics and record provenance for one fixed TF-IDF/classifier candidate."""

    feature_kind: str
    classifier_name: str
    feature_parameters: dict[str, Any]
    classifier_parameters: dict[str, Any]
    feature_count: int
    train_record_ids: tuple[str, ...]
    validation_record_ids: tuple[str, ...]
    train_predictions: tuple[str, ...]
    validation_predictions: tuple[str, ...]
    train_metrics: dict[str, Any]
    validation_metrics: dict[str, Any]


def split_for_smoke(
    records: Sequence[Mapping[str, Any]],
) -> tuple[list[Mapping[str, Any]], list[Mapping[str, Any]]]:
    """Select only train and validation rows from a M2.1-validated bundle.

    Test records are intentionally discarded here. The downstream model seam
    accepts only the two returned collections and has no test argument.
    """

    train: list[Mapping[str, Any]] = []
    validation: list[Mapping[str, Any]] = []
    for row in records:
        split = row.get("split")
        if split == "train":
            train.append(row)
        elif split == "validation":
            validation.append(row)
        elif split == "test":
            continue
        else:
            raise ValueError(f"Unexpected split value in frozen dataset: {split!r}")
    _validate_model_rows(train, validation)
    return train, validation


def _validate_model_rows(
    train_records: Sequence[Mapping[str, Any]],
    validation_records: Sequence[Mapping[str, Any]],
) -> None:
    if not train_records or not validation_records:
        raise ValueError("Both train and validation records are required.")

    ids: set[str] = set()
    train_families: set[str] = set()
    validation_families: set[str] = set()
    for expected_split, rows, family_set in (
        ("train", train_records, train_families),
        ("validation", validation_records, validation_families),
    ):
        observed_labels: set[str] = set()
        for row in rows:
            record_id = row.get("id")
            label_id = row.get("label_id")
            family_id = row.get("scenario_family_id")
            transcript = row.get("transcript")
            if row.get("split") != expected_split:
                raise ValueError(
                    f"{expected_split} model input contains a row from split {row.get('split')!r}."
                )
            if not isinstance(record_id, str) or not record_id:
                raise ValueError(f"{expected_split} row is missing a valid record id.")
            if record_id in ids:
                raise ValueError(f"Duplicate record id at model boundary: {record_id}")
            ids.add(record_id)
            if not isinstance(label_id, str) or label_id not in LABEL_ORDER:
                raise ValueError(f"Unknown label at model boundary for {record_id}: {label_id!r}")
            if not isinstance(family_id, str) or not family_id:
                raise ValueError(f"Missing scenario_family_id at model boundary for {record_id}.")
            if not isinstance(transcript, str) or not transcript.strip():
                raise ValueError(f"Missing transcript text at model boundary for {record_id}.")
            observed_labels.add(label_id)
            family_set.add(family_id)
        if observed_labels != set(LABEL_ORDER):
            raise ValueError(
                f"{expected_split} must contain all five frozen labels; "
                f"observed {sorted(observed_labels)}."
            )

    overlap = train_families & validation_families
    if overlap:
        raise ValueError(
            "scenario_family_id crosses train and validation: " + ", ".join(sorted(overlap))
        )


def fit_tfidf_matrices(
    train_texts: Sequence[str],
    validation_texts: Sequence[str],
    *,
    feature_kind: str,
) -> tuple[TfidfVectorizer, Any, Any]:
    """Fit vocabulary/IDF on train text only, then transform validation text."""

    if feature_kind not in FEATURE_CONFIGS:
        raise ValueError(f"Unknown TF-IDF feature kind: {feature_kind!r}")
    if not train_texts or not validation_texts:
        raise ValueError("Train and validation text collections must both be non-empty.")
    feature_parameters = {
        **FEATURE_CONFIGS[feature_kind],
        "min_df": 2,
        "max_features": 50000,
        "sublinear_tf": True,
        "lowercase": False,
    }
    vectorizer = TfidfVectorizer(**feature_parameters)
    train_matrix = vectorizer.fit_transform(train_texts)
    validation_matrix = vectorizer.transform(validation_texts)
    return vectorizer, train_matrix, validation_matrix


def _metrics(y_true: Sequence[str], y_pred: Sequence[str]) -> dict[str, Any]:
    return classification_metrics(y_true, y_pred, LABEL_ORDER)


def run_baselines(
    train_records: Sequence[Mapping[str, Any]],
    validation_records: Sequence[Mapping[str, Any]],
    *,
    random_state: int = 42,
) -> list[BaselineRun]:
    """Fit four fixed CPU candidates using train rows and score train/validation.

    There is deliberately no test parameter. Vectorizer vocabulary and IDF are
    fit on train transcripts; validation is transform-only.
    """

    _validate_model_rows(train_records, validation_records)
    train_texts = [str(row["transcript"]) for row in train_records]
    validation_texts = [str(row["transcript"]) for row in validation_records]
    y_train = [str(row["label_id"]) for row in train_records]
    y_validation = [str(row["label_id"]) for row in validation_records]
    train_ids = tuple(str(row["id"]) for row in train_records)
    validation_ids = tuple(str(row["id"]) for row in validation_records)

    classifier_specs = (
        (
            "logistic_regression",
            lambda: LogisticRegression(
                C=1.0,
                max_iter=1000,
                solver="lbfgs",
                random_state=random_state,
            ),
            {"C": 1.0, "max_iter": 1000, "solver": "lbfgs", "random_state": random_state},
        ),
        (
            "linear_svm",
            lambda: LinearSVC(
                C=1.0,
                dual="auto",
                max_iter=5000,
                random_state=random_state,
            ),
            {"C": 1.0, "dual": "auto", "max_iter": 5000, "random_state": random_state},
        ),
    )

    results: list[BaselineRun] = []
    for feature_kind, config in FEATURE_CONFIGS.items():
        vectorizer, x_train, x_validation = fit_tfidf_matrices(
            train_texts,
            validation_texts,
            feature_kind=feature_kind,
        )
        feature_parameters = {
            **config,
            "min_df": 2,
            "max_features": 50000,
            "sublinear_tf": True,
            "lowercase": False,
            "dtype": "scikit-learn default (float64)",
        }
        for classifier_name, make_classifier, classifier_parameters in classifier_specs:
            classifier = make_classifier()
            classifier.fit(x_train, y_train)
            train_predictions = tuple(str(value) for value in classifier.predict(x_train))
            validation_predictions = tuple(str(value) for value in classifier.predict(x_validation))
            results.append(
                BaselineRun(
                    feature_kind=feature_kind,
                    classifier_name=classifier_name,
                    feature_parameters=feature_parameters,
                    classifier_parameters=classifier_parameters,
                    feature_count=len(vectorizer.vocabulary_),
                    train_record_ids=train_ids,
                    validation_record_ids=validation_ids,
                    train_predictions=train_predictions,
                    validation_predictions=validation_predictions,
                    train_metrics=_metrics(y_train, train_predictions),
                    validation_metrics=_metrics(y_validation, validation_predictions),
                )
            )
    return results

"""Fixture-safe classification metrics, reporting, and test evaluation gate.

This module consumes prediction batches only. It never loads datasets, models,
embeddings, or test rows from disk.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence


LABEL_ORDER = (
    "sidewalk_maintenance",
    "road_surface_defect",
    "park_general_maintenance",
    "waste_truck_service",
    "street_cleaning",
)


class TestEvaluationLockedError(RuntimeError):
    """Raised when test metrics are requested before an explicit valid unlock."""


@dataclass(frozen=True)
class PredictionBatch:
    """Predictions and split provenance without transcript/model input fields."""

    split: str
    record_ids: tuple[str, ...]
    family_ids: tuple[str, ...]
    expected: tuple[str, ...]
    predicted: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.split not in {"train", "validation", "test"}:
            raise ValueError("split must be train, validation, or test.")
        count = len(self.record_ids)
        if count == 0 or any(
            len(values) != count
            for values in (self.family_ids, self.expected, self.predicted)
        ):
            raise ValueError("record IDs, family IDs, expected, and predicted must have the same non-zero length.")
        if any(not isinstance(value, str) or not value for value in self.record_ids):
            raise ValueError("record IDs must be non-empty strings.")
        if len(set(self.record_ids)) != count:
            raise ValueError("record IDs must be unique within a split.")
        if any(not isinstance(value, str) or not value for value in self.family_ids):
            raise ValueError("family IDs must be non-empty strings.")
        if any(not isinstance(value, str) or not value for value in (*self.expected, *self.predicted)):
            raise ValueError("expected and predicted labels must be non-empty strings.")


@dataclass
class TestEvaluationAuthorization:
    """Explicit, process-local one-use unlock for predeclared test candidates.

    This is a fixture seam, not a durable production ledger. A future formal
    test runner must persist authorization consumption across process restarts.
    """

    candidate_names: tuple[str, ...]
    configuration_fingerprint: str
    candidate_list_locked: bool
    configuration_locked: bool
    manual_review_gate_passed: bool
    approval_reference: str
    _consumed_candidates: set[str] = field(default_factory=set, init=False, repr=False)

    def validate(self, candidate_name: str, configuration_fingerprint: str) -> None:
        if not self.candidate_list_locked:
            raise TestEvaluationLockedError("test evaluation requires a locked candidate list.")
        if not self.configuration_locked:
            raise TestEvaluationLockedError("test evaluation requires locked configuration settings.")
        if not self.manual_review_gate_passed:
            raise TestEvaluationLockedError("test evaluation requires the manual review quality gate to pass.")
        if not self.approval_reference:
            raise TestEvaluationLockedError("test evaluation requires an explicit approval reference.")
        if not candidate_name or candidate_name not in self.candidate_names:
            raise TestEvaluationLockedError("candidate is not in the predeclared candidate list.")
        if configuration_fingerprint != self.configuration_fingerprint:
            raise TestEvaluationLockedError("configuration fingerprint differs from the locked settings.")
        if candidate_name in self._consumed_candidates:
            raise TestEvaluationLockedError("test authorization was already consumed for this candidate.")

    def consume(self, candidate_name: str, configuration_fingerprint: str) -> None:
        self.validate(candidate_name, configuration_fingerprint)
        self._consumed_candidates.add(candidate_name)


def classification_metrics(
    expected: Sequence[str], predicted: Sequence[str], label_order: Sequence[str] = LABEL_ORDER
) -> dict[str, Any]:
    """Return deterministic fixed-order classification metrics.

    Confusion-matrix rows are actual labels and columns are predicted labels.
    Undefined per-class precision/recall is reported as 0.0.
    """

    if len(expected) != len(predicted) or not expected:
        raise ValueError("metrics require equally sized, non-empty expected and predicted labels.")
    labels = tuple(label_order)
    if labels != LABEL_ORDER:
        raise ValueError("label_order must match the fixed taxonomy order.")
    index_for = {label: index for index, label in enumerate(labels)}
    if any(label not in index_for for label in (*expected, *predicted)):
        raise ValueError("metrics contain an unknown label outside label_order.")

    matrix = [[0 for _ in labels] for _ in labels]
    for actual, guess in zip(expected, predicted, strict=True):
        matrix[index_for[actual]][index_for[guess]] += 1

    per_class: dict[str, dict[str, float | int]] = {}
    f1_values: list[float] = []
    correct = 0
    for label_index, label in enumerate(labels):
        true_positive = matrix[label_index][label_index]
        support = sum(matrix[label_index])
        predicted_count = sum(row[label_index] for row in matrix)
        precision = true_positive / predicted_count if predicted_count else 0.0
        recall = true_positive / support if support else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        f1_values.append(f1)
        per_class[label] = {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "support": support,
        }
        correct += true_positive

    return {
        "labels": list(labels),
        "accuracy": correct / len(expected),
        "macro_f1": sum(f1_values) / len(labels),
        "per_class": per_class,
        "confusion_matrix": matrix,
    }


def evaluate_predictions(
    train: PredictionBatch,
    validation: PredictionBatch,
    *,
    test: PredictionBatch | None = None,
    test_unlock: TestEvaluationAuthorization | None = None,
    candidate_name: str | None = None,
    configuration_fingerprint: str | None = None,
    label_order: Sequence[str] = LABEL_ORDER,
) -> dict[str, Any]:
    """Evaluate train/validation fixture predictions; test is locked by default."""

    if not isinstance(train, PredictionBatch) or train.split != "train":
        raise ValueError("evaluate_predictions requires a train PredictionBatch first.")
    if not isinstance(validation, PredictionBatch) or validation.split != "validation":
        raise ValueError("evaluate_predictions requires a validation PredictionBatch second.")
    if test is not None and (not isinstance(test, PredictionBatch) or test.split != "test"):
        raise ValueError("test must be a test PredictionBatch when supplied.")
    if test is None and test_unlock is not None:
        raise ValueError("test_unlock cannot be supplied without a test batch.")
    if test is not None:
        if test_unlock is None:
            raise TestEvaluationLockedError("test split is locked until an explicit unlock is supplied.")
        if configuration_fingerprint is None:
            raise TestEvaluationLockedError("test evaluation requires a configuration fingerprint.")
        test_unlock.validate(candidate_name or "", configuration_fingerprint)
    if label_order is None or tuple(label_order) != LABEL_ORDER:
        raise ValueError("label_order must match the fixed taxonomy order.")

    batches = [train, validation] + ([test] if test is not None else [])
    seen_records: set[str] = set()
    seen_families: set[str] = set()
    allowed_labels = set(LABEL_ORDER)
    for batch in batches:
        assert batch is not None
        if set((*batch.expected, *batch.predicted)) - allowed_labels:
            raise ValueError(f"{batch.split} predictions contain an unknown label.")
        overlap_ids = seen_records.intersection(batch.record_ids)
        if overlap_ids:
            raise ValueError("record IDs overlap across evaluation splits.")
        overlap_families = seen_families.intersection(batch.family_ids)
        if overlap_families:
            raise ValueError("scenario_family_id crosses evaluation splits.")
        seen_records.update(batch.record_ids)
        seen_families.update(batch.family_ids)

    if test is not None:
        assert test_unlock is not None and configuration_fingerprint is not None
        test_unlock.consume(candidate_name or "", configuration_fingerprint)

    splits: dict[str, Any] = {
        "train": _evaluate_batch(train),
        "validation": _evaluate_batch(validation),
        "test": {"status": "not_run"},
    }
    if test is not None:
        splits["test"] = {**_evaluate_batch(test), "status": "fixture_only_evaluated"}

    return {
        "evaluation_status": "smoke_test/provisional",
        "data_status": "synthetic_fixture",
        "review_status": "pending_manual_review",
        "candidate_name": candidate_name or "fixture-candidate",
        "label_order": list(LABEL_ORDER),
        "splits": splits,
    }


def _evaluate_batch(batch: PredictionBatch) -> dict[str, Any]:
    errors = [
        {"record_id": record_id, "expected": expected, "predicted": predicted}
        for record_id, expected, predicted in zip(
            batch.record_ids, batch.expected, batch.predicted, strict=True
        )
        if expected != predicted
    ]
    return {
        "status": "evaluated",
        "n_records": len(batch.record_ids),
        "metrics": classification_metrics(batch.expected, batch.predicted),
        "error_cases": errors,
    }


def render_markdown_report(report: dict[str, Any]) -> str:
    """Render a deterministic Markdown summary with fixed label/matrix order."""

    required = {"evaluation_status", "data_status", "review_status", "candidate_name", "label_order", "splits"}
    if not isinstance(report, dict) or not required.issubset(report):
        raise ValueError("report is missing required evaluation metadata.")
    if report["label_order"] != list(LABEL_ORDER):
        raise ValueError("report label order differs from the fixed taxonomy order.")
    lines = [
        "# Classification evaluation report",
        "",
        f"- Status: `{report['evaluation_status']}`",
        f"- Data: `{report['data_status']}`",
        f"- Review status: `{report['review_status']}`",
        f"- Candidate: `{report['candidate_name']}`",
        "- Confusion matrix orientation: rows = actual; columns = predicted.",
    ]
    for split in ("train", "validation", "test"):
        result = report["splits"].get(split, {"status": "not_run"})
        lines.extend(["", f"## {split}", "", f"- Status: `{result['status']}`"])
        if result["status"] == "not_run":
            continue
        metrics = result["metrics"]
        lines.extend([
            f"- Records: {result['n_records']}",
            f"- Accuracy: {metrics['accuracy']:.6f}",
            f"- Macro-F1: {metrics['macro_f1']:.6f}",
            "",
            "### Per-class metrics",
            "",
            "| Label | Precision | Recall | F1 | Support |",
            "|---|---:|---:|---:|---:|",
        ])
        for label in LABEL_ORDER:
            item = metrics["per_class"][label]
            lines.append(
                f"| {label} | {item['precision']:.6f} | {item['recall']:.6f} | "
                f"{item['f1']:.6f} | {item['support']} |"
            )
        lines.extend([
            "",
            "### Confusion matrix",
            "",
            "| Actual \\ Predicted | " + " | ".join(LABEL_ORDER) + " |",
            "|---|" + "---:|" * len(LABEL_ORDER),
        ])
        for label, row in zip(LABEL_ORDER, metrics["confusion_matrix"], strict=True):
            lines.append(f"| {label} | " + " | ".join(str(value) for value in row) + " |")
        errors = result.get("error_cases", [])
        lines.extend(["", "### Error record IDs", ""])
        lines.extend([f"- `{item['record_id']}`: `{item['expected']}` → `{item['predicted']}`" for item in errors])
        if not errors:
            lines.append("- None")
    return "\n".join(lines) + "\n"


def write_markdown_report(report: dict[str, Any], path: Path) -> Path:
    """Write a report at an explicitly supplied path and return that path."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(render_markdown_report(report), encoding="utf-8")
    return destination

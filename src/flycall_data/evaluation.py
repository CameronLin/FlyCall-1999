"""Fixture-safe classification metrics, reporting, and test evaluation gate.

This module consumes prediction batches only. It never loads datasets, models,
embeddings, or test rows from disk.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Sequence


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
        if self.candidate_list_locked is not True:
            raise TestEvaluationLockedError("test evaluation requires a locked candidate list.")
        if self.configuration_locked is not True:
            raise TestEvaluationLockedError("test evaluation requires locked configuration settings.")
        if self.manual_review_gate_passed is not True:
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


@dataclass
class TestRunReservation:
    """Durable one-use reservation that must be written before reading test rows."""

    candidate_name: str
    configuration_fingerprint: str
    reservation_id: str
    record_path: Path
    record_sha256: str


class PersistentTestRunLedger:
    """Cross-process, fail-closed reservation ledger for a future test runner.

    Calling ``reserve`` consumes the candidate/configuration slot before the
    caller opens or tokenizes test inputs. A failed process leaves the slot
    consumed. This class does not read a dataset or run an evaluation.
    """

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def reserve(
        self,
        *,
        candidate_name: str,
        candidate_names: Sequence[str],
        candidate_list_fingerprint: str,
        configuration_fingerprint: str,
        candidate_list_locked: bool,
        configuration_locked: bool,
        manual_review_gate_passed: bool,
        manual_review_summary_sha256: str,
        approval_reference: str,
        source_sha256: dict[str, str],
    ) -> TestRunReservation:
        """Persist an irreversible one-use reservation before any test access."""

        if isinstance(candidate_names, (str, bytes)):
            raise TestEvaluationLockedError("candidate_names must be a sequence of candidate names.")
        candidates = tuple(candidate_names)
        if (
            not isinstance(candidate_name, str)
            or not candidate_name
            or candidate_name != candidate_name.strip()
            or not candidates
            or any(
                not isinstance(name, str) or not name or name != name.strip()
                for name in candidates
            )
        ):
            raise TestEvaluationLockedError("candidate names must be non-empty, trimmed strings.")
        if candidate_list_locked is not True:
            raise TestEvaluationLockedError("test evaluation requires a locked candidate list.")
        if configuration_locked is not True:
            raise TestEvaluationLockedError("test evaluation requires locked configuration settings.")
        if manual_review_gate_passed is not True:
            raise TestEvaluationLockedError("test evaluation requires the manual review quality gate to pass.")
        if not isinstance(approval_reference, str) or not approval_reference.strip():
            raise TestEvaluationLockedError("test evaluation requires an explicit approval reference.")
        if len(set(candidates)) != len(candidates) or candidate_name not in candidates:
            raise TestEvaluationLockedError("candidate must be in a unique, predeclared candidate list.")
        expected_candidate_list_fingerprint = fingerprint_candidate_list(candidates)
        _require_sha256(candidate_list_fingerprint, "candidate_list_fingerprint")
        if candidate_list_fingerprint != expected_candidate_list_fingerprint:
            raise TestEvaluationLockedError("candidate list fingerprint does not match the locked candidate names.")
        _require_sha256(configuration_fingerprint, "configuration_fingerprint")
        _require_sha256(manual_review_summary_sha256, "manual_review_summary_sha256")
        if not isinstance(source_sha256, dict) or not source_sha256:
            raise TestEvaluationLockedError("test reservation requires source file checksums.")
        checked_sources: dict[str, str] = {}
        for name, digest in source_sha256.items():
            if not isinstance(name, str) or not name:
                raise TestEvaluationLockedError("source checksum names must be non-empty strings.")
            _require_sha256(digest, f"source_sha256[{name}]")
            checked_sources[name] = digest

        reservation_id = uuid.uuid4().hex
        payload = {
            "schema_version": 1,
            "status": "reserved",
            "reservation_id": reservation_id,
            "reserved_at_utc": datetime.now(timezone.utc).isoformat(),
            "candidate_name": candidate_name,
            "candidate_names": list(candidates),
            "candidate_list_fingerprint": candidate_list_fingerprint,
            "candidate_list_locked": True,
            "configuration_fingerprint": configuration_fingerprint,
            "configuration_locked": True,
            "manual_review_gate_passed": True,
            "manual_review_summary_sha256": manual_review_summary_sha256,
            "approval_reference": approval_reference.strip(),
            "source_sha256": dict(sorted(checked_sources.items())),
            "test_input_read_at_reservation": False,
        }
        # A candidate may consume the test split only once, even if someone
        # later changes its configuration fingerprint.
        identity = hashlib.sha256(candidate_name.encode("utf-8")).hexdigest()
        record_path = self.root / f"{identity}.json"
        self.root.mkdir(parents=True, exist_ok=True)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
        try:
            descriptor = os.open(record_path, flags, 0o600)
        except FileExistsError as error:
            raise TestEvaluationLockedError(
                "test authorization was already reserved or consumed for this candidate."
            ) from error
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        return TestRunReservation(
            candidate_name=candidate_name,
            configuration_fingerprint=configuration_fingerprint,
            reservation_id=reservation_id,
            record_path=record_path,
            record_sha256=hashlib.sha256(encoded).hexdigest(),
        )

    def validate_reservation(self, reservation: TestRunReservation) -> dict[str, Any]:
        """Re-read a pending reservation before the caller accesses test input."""

        return self._read_reservation(reservation, allowed_statuses={"reserved"})

    def consume_for_evaluation(self, reservation: TestRunReservation) -> dict[str, Any]:
        """Atomically consume a reserved slot before evaluation metrics run.

        If this process exits after the transition, the candidate remains
        consumed. A later attempt fails closed instead of repeating test work.
        """

        if not isinstance(reservation, TestRunReservation):
            raise TypeError("consume_for_evaluation requires a TestRunReservation.")
        record_path = self._checked_record_path(reservation)
        with self._exclusive_record_lock(record_path):
            payload = self._read_reservation(reservation, allowed_statuses={"reserved"})
            payload["status"] = "evaluating"
            payload["evaluation_started_at_utc"] = datetime.now(timezone.utc).isoformat()
            reservation.record_sha256 = self._write_record_payload(record_path, payload)
            return payload

    def _checked_record_path(self, reservation: TestRunReservation) -> Path:
        if not isinstance(reservation, TestRunReservation):
            raise TypeError("reservation must be a TestRunReservation.")
        if (
            not isinstance(reservation.candidate_name, str)
            or not reservation.candidate_name
            or reservation.candidate_name != reservation.candidate_name.strip()
        ):
            raise TestEvaluationLockedError("reservation candidate name is invalid.")
        record_path = reservation.record_path.resolve(strict=True)
        ledger_root = self.root.resolve(strict=True)
        try:
            record_path.relative_to(ledger_root)
        except ValueError as error:
            raise TestEvaluationLockedError("reservation record is outside this ledger root.") from error
        expected_identity = hashlib.sha256(reservation.candidate_name.encode("utf-8")).hexdigest()
        expected_path = (ledger_root / f"{expected_identity}.json").resolve(strict=True)
        if record_path != expected_path:
            raise TestEvaluationLockedError("reservation record path does not match its candidate identity.")
        return record_path

    def _read_reservation(
        self,
        reservation: TestRunReservation,
        *,
        allowed_statuses: set[str],
    ) -> dict[str, Any]:

        if not isinstance(reservation, TestRunReservation):
            raise TypeError("validate_reservation requires a TestRunReservation.")
        _require_sha256(reservation.record_sha256, "reservation_record_sha256")
        record_path = self._checked_record_path(reservation)
        try:
            record_bytes = record_path.read_bytes()
            if hashlib.sha256(record_bytes).hexdigest() != reservation.record_sha256:
                raise TestEvaluationLockedError("reservation record checksum changed after it was created.")
            payload = json.loads(record_bytes.decode("utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise TestEvaluationLockedError("reservation record is unreadable or invalid.") from error
        candidates = payload.get("candidate_names")
        if (
            payload.get("schema_version") != 1
            or payload.get("status") not in allowed_statuses
            or payload.get("reservation_id") != reservation.reservation_id
            or payload.get("candidate_name") != reservation.candidate_name
            or payload.get("configuration_fingerprint") != reservation.configuration_fingerprint
            or not isinstance(candidates, list)
            or reservation.candidate_name not in candidates
            or payload.get("candidate_list_fingerprint") != fingerprint_candidate_list(candidates)
            or payload.get("candidate_list_locked") is not True
            or payload.get("configuration_locked") is not True
            or payload.get("manual_review_gate_passed") is not True
            or not payload.get("approval_reference")
            or payload.get("test_input_read_at_reservation") is not False
        ):
            raise TestEvaluationLockedError("reservation record does not match an active, valid reservation.")
        _require_sha256(payload.get("configuration_fingerprint"), "configuration_fingerprint")
        _require_sha256(payload.get("candidate_list_fingerprint"), "candidate_list_fingerprint")
        _require_sha256(payload.get("manual_review_summary_sha256"), "manual_review_summary_sha256")
        source_sha256 = payload.get("source_sha256")
        if not isinstance(source_sha256, dict) or not source_sha256:
            raise TestEvaluationLockedError("reservation source checksum map is missing or invalid.")
        for name, digest in source_sha256.items():
            if not isinstance(name, str) or not name:
                raise TestEvaluationLockedError("reservation source checksum names are invalid.")
            _require_sha256(digest, f"source_sha256[{name}]")
        return payload

    @contextmanager
    def _exclusive_record_lock(self, record_path: Path) -> Iterator[None]:
        lock_path = record_path.with_name(f"{record_path.name}.lock")
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
        try:
            descriptor = os.open(lock_path, flags, 0o600)
        except FileExistsError as error:
            raise TestEvaluationLockedError("test reservation is being consumed or finalized concurrently.") from error
        try:
            yield
        finally:
            os.close(descriptor)
            try:
                lock_path.unlink()
            except FileNotFoundError:
                pass

    @staticmethod
    def _write_record_payload(record_path: Path, payload: dict[str, Any]) -> str:
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        temporary_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="wb",
                dir=record_path.parent,
                prefix=f".{record_path.stem}.",
                delete=False,
            ) as stream:
                temporary_path = stream.name
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_path, record_path)
            temporary_path = None
        finally:
            if temporary_path and os.path.exists(temporary_path):
                os.unlink(temporary_path)
        return hashlib.sha256(encoded).hexdigest()

    def finalize(
        self,
        reservation: TestRunReservation,
        *,
        status: str,
        test_source_sha256: str | None = None,
        output_sha256: str | None = None,
    ) -> Path:
        """Record completion or failure without releasing the consumed slot."""

        if not isinstance(reservation, TestRunReservation):
            raise TypeError("finalize requires the reservation returned by reserve().")
        if status not in {"completed", "failed_after_reservation"}:
            raise ValueError("status must be completed or failed_after_reservation.")
        if status == "completed" and (test_source_sha256 is None or output_sha256 is None):
            raise TestEvaluationLockedError(
                "completed test runs require both test source and output SHA-256 values."
            )
        for name, digest in (("test_source_sha256", test_source_sha256), ("output_sha256", output_sha256)):
            if digest is not None:
                _require_sha256(digest, name)
        record_path = self._checked_record_path(reservation)
        with self._exclusive_record_lock(record_path):
            payload = self._read_reservation(
                reservation,
                allowed_statuses={"reserved", "evaluating"},
            )
            if status == "completed" and payload["status"] != "evaluating":
                raise TestEvaluationLockedError("a test run can complete only after evaluation was consumed.")
            payload["status"] = status
            payload["finalized_at_utc"] = datetime.now(timezone.utc).isoformat()
            payload["test_source_sha256"] = test_source_sha256
            payload["output_sha256"] = output_sha256
            reservation.record_sha256 = self._write_record_payload(record_path, payload)
        return record_path


def _require_sha256(value: str, name: str) -> None:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(char not in "0123456789abcdef" for char in value)
    ):
        raise TestEvaluationLockedError(f"{name} must be a lowercase SHA-256 digest.")


def fingerprint_candidate_list(candidate_names: Sequence[str]) -> str:
    """Hash the ordered, UTF-8 candidate-name list used by the durable gate."""

    if isinstance(candidate_names, (str, bytes)):
        raise ValueError("candidate_names must be a sequence of names, not a string.")
    names = tuple(candidate_names)
    if not names or any(not isinstance(name, str) or not name or name != name.strip() for name in names):
        raise ValueError("candidate_names must contain non-empty, trimmed strings.")
    if len(set(names)) != len(names):
        raise ValueError("candidate_names must not contain duplicates.")
    encoded = json.dumps(list(names), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


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
    test_reservation: TestRunReservation | None = None,
    test_ledger: PersistentTestRunLedger | None = None,
    candidate_name: str | None = None,
    configuration_fingerprint: str | None = None,
    label_order: Sequence[str] = LABEL_ORDER,
    data_status: str = "synthetic_fixture",
) -> dict[str, Any]:
    """Evaluate predictions; test requires a fixture unlock or prior durable reservation.

    A formal caller must reserve and validate a slot before it opens test input.
    The evaluator only receives prediction batches and never reads a dataset.
    """

    if not isinstance(train, PredictionBatch) or train.split != "train":
        raise ValueError("evaluate_predictions requires a train PredictionBatch first.")
    if not isinstance(validation, PredictionBatch) or validation.split != "validation":
        raise ValueError("evaluate_predictions requires a validation PredictionBatch second.")
    if test is not None and (not isinstance(test, PredictionBatch) or test.split != "test"):
        raise ValueError("test must be a test PredictionBatch when supplied.")
    if label_order is None or tuple(label_order) != LABEL_ORDER:
        raise ValueError("label_order must match the fixed taxonomy order.")
    if data_status not in {"synthetic_fixture", "synthetic"}:
        raise ValueError("data_status must be 'synthetic_fixture' or 'synthetic'.")
    if test is None:
        if any(value is not None for value in (test_unlock, test_reservation, test_ledger)):
            raise ValueError("test authorization cannot be supplied without a test batch.")
    else:
        durable_test_payload: dict[str, Any] | None = None
        if test_unlock is not None and (test_reservation is not None or test_ledger is not None):
            raise ValueError("use either a fixture unlock or a durable reservation, not both.")
        if test_unlock is None and (test_reservation is None or test_ledger is None):
            raise TestEvaluationLockedError("test split is locked until an explicit unlock is supplied.")
        if configuration_fingerprint is None:
            raise TestEvaluationLockedError("test evaluation requires a configuration fingerprint.")
        if not candidate_name:
            raise TestEvaluationLockedError("test evaluation requires a candidate name.")
        if test_unlock is not None:
            if data_status != "synthetic_fixture":
                raise TestEvaluationLockedError(
                    "process-local test unlocks are restricted to synthetic fixtures."
                )
            test_unlock.validate(candidate_name, configuration_fingerprint)
        elif test_reservation is not None and test_ledger is not None:
            if not isinstance(test_ledger, PersistentTestRunLedger):
                raise TypeError("test_ledger must be a PersistentTestRunLedger.")
            if not isinstance(test_reservation, TestRunReservation):
                raise TypeError("test_reservation must be a TestRunReservation.")
            if (
                test_reservation.candidate_name != candidate_name
                or test_reservation.configuration_fingerprint != configuration_fingerprint
            ):
                raise TestEvaluationLockedError(
                    "test reservation differs from the candidate or configuration being evaluated."
                )
            durable_test_payload = test_ledger.consume_for_evaluation(test_reservation)
        else:
            raise TestEvaluationLockedError("test split is locked until an explicit unlock is supplied.")

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
        if test_unlock is not None:
            assert configuration_fingerprint is not None and candidate_name is not None
            test_unlock.consume(candidate_name, configuration_fingerprint)

    splits: dict[str, Any] = {
        "train": _evaluate_batch(train),
        "validation": _evaluate_batch(validation),
        "test": {"status": "not_run"},
    }
    if test is not None:
        test_status = (
            "fixture_only_evaluated"
            if data_status == "synthetic_fixture"
            else "durably_unlocked_evaluated"
        )
        splits["test"] = {**_evaluate_batch(test), "status": test_status}

    report = {
        "evaluation_status": "smoke_test/provisional",
        "data_status": data_status,
        "review_status": "pending_manual_review",
        "candidate_name": candidate_name or "fixture-candidate",
        "label_order": list(LABEL_ORDER),
        "splits": splits,
    }
    if test is not None:
        if durable_test_payload is not None:
            report["test_authorization"] = {
                "mode": "persistent_one_use_ledger",
                "reservation_id": durable_test_payload["reservation_id"],
                "candidate_list_fingerprint": durable_test_payload["candidate_list_fingerprint"],
                "configuration_fingerprint": durable_test_payload["configuration_fingerprint"],
            }
        else:
            report["test_authorization"] = {
                "mode": "process_local_fixture_unlock",
                "candidate_name": candidate_name,
            }
    return report


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

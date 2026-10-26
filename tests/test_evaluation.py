from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from flycall_data.evaluation import (
    LABEL_ORDER,
    PredictionBatch,
    PersistentTestRunLedger,
    TestRunReservation,
    TestEvaluationAuthorization,
    TestEvaluationLockedError,
    classification_metrics,
    evaluate_predictions,
    fingerprint_candidate_list,
    render_markdown_report,
    write_markdown_report,
)


EXPECTED = (
    "sidewalk_maintenance",
    "sidewalk_maintenance",
    "road_surface_defect",
    "road_surface_defect",
    "park_general_maintenance",
    "park_general_maintenance",
    "waste_truck_service",
    "waste_truck_service",
    "street_cleaning",
    "street_cleaning",
)
PREDICTED = (
    "sidewalk_maintenance",
    "road_surface_defect",
    "road_surface_defect",
    "road_surface_defect",
    "park_general_maintenance",
    "park_general_maintenance",
    "waste_truck_service",
    "street_cleaning",
    "street_cleaning",
    "sidewalk_maintenance",
)
EXPECTED_MATRIX = [
    [1, 1, 0, 0, 0],
    [0, 2, 0, 0, 0],
    [0, 0, 2, 0, 0],
    [0, 0, 0, 1, 1],
    [1, 0, 0, 0, 1],
]


def batch(split: str, *, offset: int = 0) -> PredictionBatch:
    size = len(EXPECTED)
    return PredictionBatch(
        split=split,
        record_ids=tuple(f"fixture-{split}-{offset + index}" for index in range(size)),
        family_ids=tuple(f"fixture-{split}-family-{offset + index}" for index in range(size)),
        expected=EXPECTED,
        predicted=PREDICTED,
    )


def valid_unlock() -> TestEvaluationAuthorization:
    return TestEvaluationAuthorization(
        candidate_names=("fixture-candidate",),
        configuration_fingerprint="fixture-config-sha256",
        candidate_list_locked=True,
        configuration_locked=True,
        manual_review_gate_passed=True,
        approval_reference="fixture-approval",
    )


def reserve_fixture(ledger: PersistentTestRunLedger, *, config: str = "b" * 64) -> TestRunReservation:
    candidate_names = ("fixture-candidate", "other-candidate")
    return ledger.reserve(
        candidate_name="fixture-candidate",
        candidate_names=candidate_names,
        candidate_list_fingerprint=fingerprint_candidate_list(candidate_names),
        configuration_fingerprint=config,
        candidate_list_locked=True,
        configuration_locked=True,
        manual_review_gate_passed=True,
        manual_review_summary_sha256="c" * 64,
        approval_reference="fixture-review-approval",
        source_sha256={"fixture-manifest": "d" * 64, "fixture-model": "e" * 64},
    )


class EvaluationTests(unittest.TestCase):
    def test_prediction_batch_requires_aligned_synthetic_provenance(self) -> None:
        with self.assertRaisesRegex(ValueError, "same non-zero length"):
            PredictionBatch(
                split="validation",
                record_ids=("fixture-1",),
                family_ids=("family-1",),
                expected=(LABEL_ORDER[0],),
                predicted=(),
            )

    def test_train_validation_metrics_match_known_fixture_and_fixed_order(self) -> None:
        report = evaluate_predictions(batch("train"), batch("validation"))

        self.assertEqual(report["label_order"], list(LABEL_ORDER))
        self.assertEqual(report["splits"]["validation"]["metrics"]["confusion_matrix"], EXPECTED_MATRIX)
        metrics = report["splits"]["validation"]["metrics"]
        self.assertEqual(metrics["accuracy"], 0.7)
        self.assertAlmostEqual(metrics["macro_f1"], 0.6933333333333334)
        per_class = metrics["per_class"]
        self.assertEqual(per_class[LABEL_ORDER[0]], {
            "precision": 0.5, "recall": 0.5, "f1": 0.5, "support": 2,
        })
        self.assertAlmostEqual(per_class[LABEL_ORDER[1]]["precision"], 2 / 3)
        self.assertEqual(per_class[LABEL_ORDER[1]]["recall"], 1.0)
        self.assertAlmostEqual(per_class[LABEL_ORDER[1]]["f1"], 0.8)
        self.assertEqual(report["splits"]["test"]["status"], "not_run")

    def test_validation_family_or_record_overlap_is_rejected(self) -> None:
        train = batch("train")
        validation = PredictionBatch(
            split="validation",
            record_ids=train.record_ids,
            family_ids=tuple(f"other-val-{index}" for index in range(len(train.record_ids))),
            expected=EXPECTED,
            predicted=PREDICTED,
        )
        with self.assertRaisesRegex(ValueError, "record IDs overlap"):
            evaluate_predictions(train, validation)

        validation = PredictionBatch(
            split="validation",
            record_ids=tuple(f"other-val-{index}" for index in range(len(train.record_ids))),
            family_ids=train.family_ids,
            expected=EXPECTED,
            predicted=PREDICTED,
        )
        with self.assertRaisesRegex(ValueError, "scenario_family_id crosses"):
            evaluate_predictions(train, validation)

    def test_test_fixture_is_rejected_before_metrics_without_unlock(self) -> None:
        with self.assertRaisesRegex(TestEvaluationLockedError, "explicit unlock"):
            evaluate_predictions(batch("train"), batch("validation"), test=batch("test"))

    def test_incomplete_unlock_is_rejected(self) -> None:
        unlock = TestEvaluationAuthorization(
            candidate_names=("fixture-candidate",),
            configuration_fingerprint="fixture-config-sha256",
            candidate_list_locked=True,
            configuration_locked=False,
            manual_review_gate_passed=True,
            approval_reference="fixture-approval",
        )
        with self.assertRaisesRegex(TestEvaluationLockedError, "configuration"):
            evaluate_predictions(
                batch("train"), batch("validation"), test=batch("test"),
                test_unlock=unlock, candidate_name="fixture-candidate",
                configuration_fingerprint="fixture-config-sha256",
            )

    def test_test_unlock_requires_candidate_settings_and_manual_review_gate(self) -> None:
        incomplete_unlocks = (
            TestEvaluationAuthorization(
                candidate_names=("fixture-candidate",),
                configuration_fingerprint="fixture-config-sha256",
                candidate_list_locked=False,
                configuration_locked=True,
                manual_review_gate_passed=True,
                approval_reference="fixture-approval",
            ),
            TestEvaluationAuthorization(
                candidate_names=("fixture-candidate",),
                configuration_fingerprint="fixture-config-sha256",
                candidate_list_locked=True,
                configuration_locked=True,
                manual_review_gate_passed=False,
                approval_reference="fixture-approval",
            ),
            TestEvaluationAuthorization(
                candidate_names=("other-candidate",),
                configuration_fingerprint="fixture-config-sha256",
                candidate_list_locked=True,
                configuration_locked=True,
                manual_review_gate_passed=True,
                approval_reference="fixture-approval",
            ),
            TestEvaluationAuthorization(
                candidate_names=("fixture-candidate",),
                configuration_fingerprint="different-config",
                candidate_list_locked=True,
                configuration_locked=True,
                manual_review_gate_passed=True,
                approval_reference="fixture-approval",
            ),
        )
        for unlock in incomplete_unlocks:
            with self.subTest(unlock=unlock):
                with self.assertRaises(TestEvaluationLockedError):
                    evaluate_predictions(
                        batch("train"), batch("validation"), test=batch("test"),
                        test_unlock=unlock, candidate_name="fixture-candidate",
                        configuration_fingerprint="fixture-config-sha256",
                    )

    def test_explicit_fixture_unlock_is_consumed_once_per_candidate(self) -> None:
        unlock = valid_unlock()
        report = evaluate_predictions(
            batch("train"), batch("validation"), test=batch("test"),
            test_unlock=unlock, candidate_name="fixture-candidate",
            configuration_fingerprint="fixture-config-sha256",
        )
        self.assertEqual(report["splits"]["test"]["status"], "fixture_only_evaluated")
        with self.assertRaisesRegex(TestEvaluationLockedError, "already consumed"):
            evaluate_predictions(
                batch("train"), batch("validation"), test=batch("test"),
                test_unlock=unlock, candidate_name="fixture-candidate",
                configuration_fingerprint="fixture-config-sha256",
            )

    def test_unknown_labels_and_empty_label_order_fail(self) -> None:
        invalid = PredictionBatch(
            split="validation",
            record_ids=("fixture-id",),
            family_ids=("fixture-family",),
            expected=("unknown-label",),
            predicted=(LABEL_ORDER[0],),
        )
        with self.assertRaisesRegex(ValueError, "unknown label"):
            evaluate_predictions(batch("train"), invalid)
        with self.assertRaisesRegex(ValueError, "label_order"):
            evaluate_predictions(batch("train"), batch("validation"), label_order=())

    def test_class_without_predictions_remains_in_fixed_order_with_zero_metrics(self) -> None:
        metrics = classification_metrics(
            (LABEL_ORDER[0], LABEL_ORDER[1]),
            (LABEL_ORDER[0], LABEL_ORDER[0]),
        )

        self.assertEqual(metrics["labels"], list(LABEL_ORDER))
        self.assertEqual(len(metrics["confusion_matrix"]), 5)
        self.assertTrue(all(len(row) == 5 for row in metrics["confusion_matrix"]))
        self.assertEqual(metrics["per_class"][LABEL_ORDER[4]], {
            "precision": 0.0, "recall": 0.0, "f1": 0.0, "support": 0,
        })

    def test_test_is_locked_before_unknown_fixture_label_is_examined(self) -> None:
        unknown_test = PredictionBatch(
            split="test",
            record_ids=("synthetic-test-fixture",),
            family_ids=("synthetic-test-family",),
            expected=("not-a-label",),
            predicted=(LABEL_ORDER[0],),
        )
        with self.assertRaisesRegex(TestEvaluationLockedError, "explicit unlock"):
            evaluate_predictions(batch("train"), batch("validation"), test=unknown_test)

    def test_markdown_report_has_provisional_metrics_and_test_status(self) -> None:
        report = evaluate_predictions(batch("train"), batch("validation"))
        rendered = render_markdown_report(report)

        self.assertIn("smoke_test/provisional", rendered)
        self.assertIn("synthetic_fixture", rendered)
        self.assertIn("pending_manual_review", rendered)
        self.assertIn("Macro-F1", rendered)
        self.assertIn("sidewalk_maintenance", rendered)
        self.assertIn("not_run", rendered)
        with tempfile.TemporaryDirectory() as directory:
            path = write_markdown_report(report, Path(directory) / "fixture-report.md")
            self.assertEqual(path.read_text(encoding="utf-8"), rendered)

    def test_process_local_unlock_is_restricted_to_synthetic_fixture_data(self) -> None:
        with self.assertRaisesRegex(TestEvaluationLockedError, "restricted to synthetic fixtures"):
            evaluate_predictions(
                batch("train"), batch("validation"), test=batch("test"),
                test_unlock=valid_unlock(), candidate_name="fixture-candidate",
                configuration_fingerprint="fixture-config-sha256", data_status="synthetic",
            )

    def test_durable_ledger_rejects_unlocked_or_inconsistent_reservations(self) -> None:
        candidate_names = ("fixture-candidate", "other-candidate")
        valid_kwargs = {
            "candidate_name": "fixture-candidate",
            "candidate_names": candidate_names,
            "candidate_list_fingerprint": fingerprint_candidate_list(candidate_names),
            "configuration_fingerprint": "b" * 64,
            "candidate_list_locked": True,
            "configuration_locked": True,
            "manual_review_gate_passed": True,
            "manual_review_summary_sha256": "c" * 64,
            "approval_reference": "fixture-review-approval",
            "source_sha256": {"fixture-manifest": "d" * 64},
        }
        invalid_variants = (
            ({"candidate_list_locked": False}, "locked candidate list"),
            ({"configuration_locked": False}, "locked configuration"),
            ({"manual_review_gate_passed": False}, "manual review quality gate"),
            ({"approval_reference": "  "}, "approval reference"),
            ({"candidate_list_fingerprint": "f" * 64}, "does not match"),
            ({"candidate_name": "not-predeclared"}, "predeclared candidate list"),
            ({"source_sha256": {"fixture-manifest": "bad"}}, "lowercase SHA-256"),
        )
        with tempfile.TemporaryDirectory() as directory:
            ledger = PersistentTestRunLedger(Path(directory))
            for overrides, message in invalid_variants:
                kwargs = {**valid_kwargs, **overrides}
                with self.subTest(overrides=overrides):
                    with self.assertRaisesRegex(TestEvaluationLockedError, message):
                        ledger.reserve(**kwargs)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_durable_reservation_persists_and_candidate_cannot_be_reserved_twice(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            first_ledger = PersistentTestRunLedger(Path(directory))
            reservation = reserve_fixture(first_ledger)
            second_ledger = PersistentTestRunLedger(Path(directory))
            payload = second_ledger.validate_reservation(reservation)

            self.assertEqual(payload["status"], "reserved")
            self.assertFalse(payload["test_input_read_at_reservation"])
            with self.assertRaisesRegex(TestEvaluationLockedError, "already reserved or consumed"):
                reserve_fixture(second_ledger, config="f" * 64)

            script = r"""
import sys
from pathlib import Path
from flycall_data.evaluation import PersistentTestRunLedger, TestEvaluationLockedError, fingerprint_candidate_list

candidate_names = ("fixture-candidate", "other-candidate")
ledger = PersistentTestRunLedger(Path(sys.argv[1]))
try:
    ledger.reserve(
        candidate_name="fixture-candidate",
        candidate_names=candidate_names,
        candidate_list_fingerprint=fingerprint_candidate_list(candidate_names),
        configuration_fingerprint="b" * 64,
        candidate_list_locked=True,
        configuration_locked=True,
        manual_review_gate_passed=True,
        manual_review_summary_sha256="c" * 64,
        approval_reference="fixture-review-approval",
        source_sha256={"fixture-manifest": "d" * 64},
    )
except TestEvaluationLockedError:
    print("locked")
else:
    raise SystemExit("second process unexpectedly reserved the same candidate")
"""
            environment = os.environ.copy()
            source_root = str(Path(__file__).resolve().parents[1] / "src")
            environment["PYTHONPATH"] = os.pathsep.join(
                [source_root, environment.get("PYTHONPATH", "")]
            ).rstrip(os.pathsep)
            process = subprocess.run(
                [sys.executable, "-c", script, directory],
                check=False,
                capture_output=True,
                text=True,
                timeout=15,
                env=environment,
            )
            self.assertEqual(process.returncode, 0, process.stderr)
            self.assertEqual(process.stdout.strip(), "locked")

    def test_durable_reservation_detects_record_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger = PersistentTestRunLedger(Path(directory))
            reservation = reserve_fixture(ledger)
            with reservation.record_path.open("ab") as stream:
                stream.write(b" ")

            with self.assertRaisesRegex(TestEvaluationLockedError, "checksum changed"):
                PersistentTestRunLedger(Path(directory)).validate_reservation(reservation)

    def test_durable_gate_is_atomically_consumed_once_before_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger = PersistentTestRunLedger(Path(directory))
            reservation = reserve_fixture(ledger)
            configuration = reservation.configuration_fingerprint
            report = evaluate_predictions(
                batch("train"), batch("validation"), test=batch("test"),
                test_reservation=reservation, test_ledger=ledger,
                candidate_name="fixture-candidate", configuration_fingerprint=configuration,
            )

            self.assertEqual(report["evaluation_status"], "smoke_test/provisional")
            self.assertEqual(report["review_status"], "pending_manual_review")
            self.assertEqual(report["splits"]["test"]["status"], "fixture_only_evaluated")
            self.assertEqual(report["test_authorization"]["mode"], "persistent_one_use_ledger")
            self.assertEqual(json.loads(reservation.record_path.read_text(encoding="utf-8"))["status"], "evaluating")

            with self.assertRaises(TestEvaluationLockedError):
                evaluate_predictions(
                    batch("train"), batch("validation"), test=batch("test"),
                    test_reservation=reservation,
                    test_ledger=PersistentTestRunLedger(Path(directory)),
                    candidate_name="fixture-candidate", configuration_fingerprint=configuration,
                )

            ledger.finalize(
                reservation,
                status="completed",
                test_source_sha256="f" * 64,
                output_sha256="a" * 64,
            )
            finalized = json.loads(reservation.record_path.read_text(encoding="utf-8"))
            self.assertEqual(finalized["status"], "completed")
            self.assertEqual(finalized["test_source_sha256"], "f" * 64)
            with self.assertRaises(TestEvaluationLockedError):
                reserve_fixture(PersistentTestRunLedger(Path(directory)), config="9" * 64)

    def test_durable_finalization_requires_output_provenance_and_failure_stays_consumed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            ledger = PersistentTestRunLedger(Path(directory))
            reservation = reserve_fixture(ledger)
            with self.assertRaisesRegex(TestEvaluationLockedError, "require both test source and output"):
                ledger.finalize(reservation, status="completed")
            with self.assertRaisesRegex(TestEvaluationLockedError, "only after evaluation was consumed"):
                ledger.finalize(
                    reservation,
                    status="completed",
                    test_source_sha256="f" * 64,
                    output_sha256="a" * 64,
                )

            ledger.finalize(reservation, status="failed_after_reservation")
            failed = json.loads(reservation.record_path.read_text(encoding="utf-8"))
            self.assertEqual(failed["status"], "failed_after_reservation")
            with self.assertRaisesRegex(TestEvaluationLockedError, "already reserved or consumed"):
                reserve_fixture(PersistentTestRunLedger(Path(directory)), config="9" * 64)


if __name__ == "__main__":
    unittest.main()

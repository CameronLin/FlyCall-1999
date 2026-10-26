from __future__ import annotations

import unittest

from flycall_data.fly_ab_diagnostics import (
    FLY_B_TUNING_SCHEDULES,
    FlyABDiagnosticError,
    fly_a_retains_label_signal,
    validate_embedding_manifest_entries,
)


class FlyABDiagnosticGuardrailTests(unittest.TestCase):
    def test_manifest_accepts_only_frozen_train_and_validation_counts(self) -> None:
        entries = [
            {"record_id": f"train-{index}", "split": "train"}
            for index in range(700)
        ] + [
            {"record_id": f"validation-{index}", "split": "validation"}
            for index in range(150)
        ]
        self.assertEqual(validate_embedding_manifest_entries(entries), {"train": 700, "validation": 150})

    def test_manifest_rejects_test_entries_before_loading_cache(self) -> None:
        entries = [
            {"record_id": f"train-{index}", "split": "train"}
            for index in range(700)
        ] + [
            {"record_id": f"validation-{index}", "split": "validation"}
            for index in range(149)
        ] + [{"record_id": "test-0", "split": "test"}]
        with self.assertRaisesRegex(FlyABDiagnosticError, "train and validation"):
            validate_embedding_manifest_entries(entries)

    def test_manifest_rejects_duplicate_ids(self) -> None:
        entries = [
            {"record_id": f"train-{index}", "split": "train"}
            for index in range(700)
        ] + [
            {"record_id": "train-0" if index == 0 else f"validation-{index}", "split": "validation"}
            for index in range(150)
        ]
        with self.assertRaisesRegex(FlyABDiagnosticError, "duplicate"):
            validate_embedding_manifest_entries(entries)

    def test_probe_gate_selects_the_preregistered_branch(self) -> None:
        self.assertTrue(fly_a_retains_label_signal(raw_mlp_macro_f1=0.90, fly_a_mlp_macro_f1=0.85))
        self.assertFalse(fly_a_retains_label_signal(raw_mlp_macro_f1=0.90, fly_a_mlp_macro_f1=0.79))
        self.assertFalse(fly_a_retains_label_signal(raw_mlp_macro_f1=0.98, fly_a_mlp_macro_f1=0.85))
        self.assertEqual(len({item["name"] for item in FLY_B_TUNING_SCHEDULES}), 3)


if __name__ == "__main__":
    unittest.main()

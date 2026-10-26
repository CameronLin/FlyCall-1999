from __future__ import annotations

import sys
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

import run_m2_2b_e5_provisional as runner  # noqa: E402


class M2SeedRegistrationTests(unittest.TestCase):
    def test_all_baseline_seed_settings_follow_the_preregistered_seed(self) -> None:
        registration = runner._candidate_registration(2026)
        self.assertEqual(registration["seed"], 2026)
        self.assertEqual(registration["candidates"]["logistic_regression"]["random_state"], 2026)
        self.assertEqual(registration["candidates"]["mlp"]["seed"], 2026)
        self.assertEqual(registration["candidates"]["pca_mlp"]["seed"], 2026)
        self.assertEqual(registration["candidates"]["lda_logistic_regression"]["seed"], 2026)

    def test_rejects_non_positive_seed_before_run_setup(self) -> None:
        for invalid in (0, -1, True):
            with self.subTest(seed=invalid), self.assertRaises(ValueError):
                runner._candidate_registration(invalid)


if __name__ == "__main__":
    unittest.main()

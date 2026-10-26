from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

try:
    from streamlit.testing.v1 import AppTest
except ImportError:  # Streamlit is an optional local-demo dependency.
    AppTest = None

from flycall_data.evaluation import LABEL_ORDER
from flycall_data.predictor import FlyCallPredictor


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class FixturePredictor:
    def __init__(self) -> None:
        self.seen_transcripts: list[str] = []

    def predict(self, transcript: str) -> SimpleNamespace:
        self.seen_transcripts.append(transcript)
        return SimpleNamespace(
            predicted_label=LABEL_ORDER[0],
            stages=("E5", "Fly A", "Fly B"),
            label_order=LABEL_ORDER,
            probabilities=(0.8, 0.05, 0.05, 0.05, 0.05),
            logits=(2.0, 0.0, 0.0, 0.0, 0.0),
        )


@unittest.skipIf(AppTest is None, "Streamlit UI dependency is not installed")
class StreamlitAppTests(unittest.TestCase):
    def _run_app(self):
        return AppTest.from_file(str(PROJECT_ROOT / "app.py"), default_timeout=20).run()

    def test_missing_model_paths_show_configuration_error(self) -> None:
        with patch.dict(os.environ, {"FLYCALL_MODEL_MANIFEST": "", "E5_SNAPSHOT": ""}):
            app = self._run_app()

        self.assertFalse(app.exception)
        self.assertEqual(len(app.error), 1)
        self.assertIn("FLYCALL_MODEL_MANIFEST", app.error[0].value)
        self.assertIn("E5_SNAPSHOT", app.error[0].value)

    def test_fixture_prediction_renders_scores_and_confirmation_notice(self) -> None:
        fixture_predictor = FixturePredictor()
        with tempfile.TemporaryDirectory() as temporary:
            manifest = Path(temporary) / "fixture-model-manifest.json"
            manifest.write_text("{}\n", encoding="utf-8")
            environment = {
                "FLYCALL_MODEL_MANIFEST": str(manifest),
                "E5_SNAPSHOT": temporary,
            }
            with patch.dict(os.environ, environment), patch.object(
                FlyCallPredictor,
                "from_locked_manifest",
                return_value=fixture_predictor,
            ):
                app = self._run_app()
                self.assertFalse(app.exception)
                self.assertEqual(len(app.text_area), 1)
                self.assertEqual(len(app.button), 1)

                transcript = "synthetic fixture transcript"
                app.text_area[0].set_value(transcript)
                app.button[0].click()
                app.run()

        self.assertFalse(app.exception)
        self.assertEqual(fixture_predictor.seen_transcripts, [transcript])
        self.assertEqual(len(app.metric), 1)
        self.assertEqual(app.metric[0].value, LABEL_ORDER[0])
        self.assertEqual(len(app.dataframe), 1)
        self.assertTrue(app.info)
        self.assertIn("人工確認", app.info[0].value)


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_ROOT = PROJECT_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

import run_m2_2b_e5_provisional as runner  # noqa: E402
from flycall_data.embedding_pipeline import SplitEmbeddings, run_baseline  # noqa: E402
from flycall_data.evaluation import LABEL_ORDER  # noqa: E402


def _fixture_splits() -> tuple[SplitEmbeddings, SplitEmbeddings]:
    import random

    def build(split: str, per_label: int, offset: int) -> SplitEmbeddings:
        record_ids = []
        family_ids = []
        features = []
        labels = []
        for label_index, label in enumerate(LABEL_ORDER):
            for row_index in range(per_label):
                rng = random.Random(offset + label_index * 1000 + row_index)
                vector = [rng.gauss(0.0, 0.03) for _ in range(384)]
                vector[label_index] += 2.0
                record_ids.append(f"{split}-{label_index}-{row_index}")
                family_ids.append(f"{split}-family-{label_index}-{row_index}")
                features.append(tuple(vector))
                labels.append(label)
        return SplitEmbeddings(
            split=split,
            record_ids=tuple(record_ids),
            family_ids=tuple(family_ids),
            features=tuple(features),
            labels=tuple(labels),
        )

    return build("train", 10, 11), build("validation", 2, 97)


class M2CheckpointTests(unittest.TestCase):
    def test_logistic_mlp_and_pca_mlp_checkpoints_reload_fixed_order_scores(self) -> None:
        train, validation = _fixture_splits()
        source_hashes = {name: hashlib.sha256(name.encode("utf-8")).hexdigest() for name in ("data",)}
        registration = {"configuration_fingerprint": "b" * 64}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch.object(runner, "PROJECT_ROOT", root):
                for candidate in ("logistic_regression", "mlp", "pca_mlp"):
                    with self.subTest(candidate=candidate):
                        kwargs = {"epochs": 3, "hidden_size": 8, "learning_rate": 0.02}
                        if candidate == "pca_mlp":
                            kwargs["pca_components"] = 32
                        result = run_baseline(
                            candidate,
                            train,
                            validation,
                            label_order=LABEL_ORDER,
                            seed=1337,
                            **kwargs,
                        )
                        path = root / f"{candidate}.joblib"
                        manifest = runner._write_baseline_checkpoint(
                            path,
                            result,
                            train,
                            validation,
                            registration,
                            source_hashes,
                        )
                        self.assertTrue(manifest["reload_prediction_match"])
                        self.assertTrue(manifest["reload_score_array_exact_match"])
                        self.assertEqual(manifest["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())


if __name__ == "__main__":
    unittest.main()

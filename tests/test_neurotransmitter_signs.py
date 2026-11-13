from __future__ import annotations

import unittest

import pyarrow as pa

from flycall_data.neurotransmitter_signs import (
    EXCITATORY,
    EXCLUDED,
    INHIBITORY,
    NeurotransmitterSignError,
    build_sign_table,
    coverage,
    sign_for,
    summarize_signs,
)


def source_table(labels: list[str | None], bodies: list[int] | None = None) -> pa.Table:
    count = len(labels)
    return pa.table({
        "body": pa.array(bodies or list(range(10, 10 + count)), type=pa.int64()),
        "cell_type": pa.array([f"T{index}" for index in range(count)]),
        "consensus_nt": pa.array(labels, type=pa.string()),
        "ground_truth": pa.array([None] * count, type=pa.string()),
        "celltype_predicted_nt_confidence": pa.array([0.9] * count, type=pa.float64()),
        "predicted_nt": pa.array(["acetylcholine"] * count),  # ignored: consensus_nt is authoritative
    })


class SignRuleTests(unittest.TestCase):
    def test_decided_rules(self) -> None:
        self.assertEqual(sign_for("acetylcholine", glutamate_sign=INHIBITORY), (EXCITATORY, "acetylcholine"))
        self.assertEqual(sign_for("gaba", glutamate_sign=INHIBITORY)[0], INHIBITORY)
        self.assertEqual(sign_for("histamine", glutamate_sign=EXCITATORY)[0], INHIBITORY)
        self.assertEqual(sign_for("glutamate", glutamate_sign=INHIBITORY)[0], INHIBITORY)
        self.assertEqual(sign_for("glutamate", glutamate_sign=EXCITATORY)[0], EXCITATORY)
        for label in ("dopamine", "octopamine", "serotonin"):
            self.assertEqual(sign_for(label, glutamate_sign=INHIBITORY), (EXCLUDED, "modulatory"))
        self.assertEqual(sign_for("unclear", glutamate_sign=INHIBITORY), (EXCLUDED, "unclear_or_missing"))
        self.assertEqual(sign_for(None, glutamate_sign=INHIBITORY)[0], EXCLUDED)

    def test_unknown_label_and_bad_glutamate_sign_fail(self) -> None:
        with self.assertRaises(NeurotransmitterSignError):
            sign_for("glycine", glutamate_sign=INHIBITORY)
        with self.assertRaises(NeurotransmitterSignError):
            sign_for("gaba", glutamate_sign=0)


class SignTableTests(unittest.TestCase):
    def test_variants_differ_only_on_glutamate(self) -> None:
        labels = ["acetylcholine", "glutamate", "gaba", "histamine", "dopamine", "unclear", None]
        table = build_sign_table(source_table(labels))
        self.assertEqual(table["sign_glu_inhibitory"].to_pylist(), [1, -1, -1, -1, 0, 0, 0])
        self.assertEqual(table["sign_glu_excitatory"].to_pylist(), [1, 1, -1, -1, 0, 0, 0])
        self.assertEqual(table["body"].to_pylist(), list(range(10, 17)))
        summary = summarize_signs(table)
        self.assertEqual(summary["sign_glu_inhibitory"], {"excitatory": 1, "inhibitory": 3, "excluded": 3})
        self.assertEqual(summary["sign_glu_excitatory"], {"excitatory": 2, "inhibitory": 2, "excluded": 3})

    def test_contract_violations_fail(self) -> None:
        with self.assertRaises(NeurotransmitterSignError):
            build_sign_table(source_table(["gaba", "gaba"], bodies=[5, 5]))
        with self.assertRaises(NeurotransmitterSignError):
            build_sign_table(source_table(["gaba"]).drop_columns(["consensus_nt"]))
        with self.assertRaises(NeurotransmitterSignError):
            build_sign_table(source_table(["glycine"]))

    def test_coverage_separates_absent_nodes(self) -> None:
        signs = {1: 1, 2: -1, 3: 0}
        self.assertEqual(
            coverage([1, 2, 3, 4], signs),
            {"nodes": 4, "excitatory": 1, "inhibitory": 1, "excluded": 1, "absent": 1},
        )


if __name__ == "__main__":
    unittest.main()

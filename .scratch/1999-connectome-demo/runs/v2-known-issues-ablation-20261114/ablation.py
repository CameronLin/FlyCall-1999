"""Validation-only ablation for the two known v2 transcript issues (test split is never read).

Usage: python ablation.py <E5 snapshot dir>
"""
import csv
import glob
import json
import re
import sys
from pathlib import Path

ROOT = Path(r"C:\dev\FlyCall-1999")
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "scripts")]
import numpy as np  # noqa: E402
import v2_dataset_tools as t  # noqa: E402
from flycall_data.e5_runtime import load_e5_encoder  # noqa: E402
from flycall_data.evaluation import LABEL_ORDER, classification_metrics  # noqa: E402
from flycall_data.model_config import E5_SMALL_CONFIG  # noqa: E402
from run_v2_test_evaluation import baseline_predict  # noqa: E402

SP = Path(__file__).resolve().parent
E5RUN = ROOT / ".scratch/1999-connectome-demo/runs/m2-2b-e5-dataset-v2-seed-42-20261114"
SNAP = sys.argv[1]  # pinned multilingual-e5-small snapshot directory
MODELS = {"E5 → LR": "m2-logistic_regression-checkpoint.joblib", "E5 → MLP": "m2-mlp-checkpoint.joblib",
          "E5 → LDA → LR": "m2-3-lda-logistic-checkpoint.joblib"}

known = json.loads((SP / "affected_ids.json").read_text(encoding="utf-8"))
opener_ids, after_ids = set(known["opener_ids"]), set(known["after_recap_ids"])
v2 = [json.loads(l) for l in open(ROOT / "data/1999_synthetic/formal/v2.0.0/formal_dataset_v2.0.0.jsonl", encoding="utf-8")]
val = sorted((r for r in v2 if r["split"] == "validation"), key=lambda r: r["id"])
assert len(val) == 150 and all(r["split"] == "validation" for r in val)
raw = {r["id"]: r for p in sorted((t.V2 / "batches_raw").glob("batch_*.txt")) for r in t.parse_file(p)}
ins = json.loads((SP / "inserted_exchanges.json").read_text(encoding="utf-8"))


def without_after_recap_insert(rec):
    lines = rec["transcript"].split("\n")
    pairs = [(blk[j], blk[j + 1]) for blk in ins.get(rec["id"], []) for j in range(0, len(blk), 2)]
    for q, a in pairs:
        if q in lines and lines.index(q) + 1 < len(lines) and lines[lines.index(q) + 1] == a:
            i = lines.index(q)
            del lines[i:i + 2]
    return "\n".join(lines)


def with_original_opener(rec):
    lines = rec["transcript"].split("\n")
    lines[0] = raw[rec["id"]]["lines"][0]
    return "\n".join(lines)


variants = {
    "frozen": [r["transcript"] for r in val],
    "no_after_recap_insert": [without_after_recap_insert(r) if r["id"] in after_ids else r["transcript"] for r in val],
    "original_opener": [with_original_opener(r) if r["id"] in opener_ids else r["transcript"] for r in val],
}
changed = {k: sum(a != b for a, b in zip(v, variants["frozen"])) for k, v in variants.items()}
print("changed texts", changed)
enc = load_e5_encoder(Path(SNAP))
emb = {}
for name, texts in variants.items():
    emb[name] = np.asarray(enc.encode([E5_SMALL_CONFIG.prefix + x for x in texts]), dtype=np.float64)
labels = [r["label_id"] for r in val]
# sanity: frozen-text predictions must equal the saved run's validation predictions
saved = {(r["candidate"], r["record_id"]): r["predicted"] for r in csv.DictReader(open(E5RUN / "predictions.csv", encoding="utf-8")) if r["split"] == "validation"}
cand_key = {"E5 → LR": "logistic_regression", "E5 → MLP": "mlp", "E5 → LDA → LR": "lda_logistic_regression"}
result = {"changed_texts": changed, "models": {}}
for name, file in MODELS.items():
    preds = {v: baseline_predict(E5RUN / file, emb[v]) for v in variants}
    same = sum(p == saved[(cand_key[name], r["id"])] for p, r in zip(preds["frozen"], val))
    row = {"reproduces_saved_predictions": f"{same}/150"}
    for v in variants:
        m = classification_metrics(labels, preds[v], LABEL_ORDER)
        row[v] = {"macro_f1": round(float(m["macro_f1"]), 4), "accuracy": round(float(m["accuracy"]), 4),
                  "flips_vs_frozen": sum(a != b for a, b in zip(preds[v], preds["frozen"]))}
    sw_sc = lambda p: sum(1 for e, q in zip(labels, p) if {e, q} == {"sidewalk_maintenance", "street_cleaning"})
    row["sidewalk_cleaning_confusions"] = {v: sw_sc(preds[v]) for v in variants}
    result["models"][name] = row
    print(name, json.dumps(row, ensure_ascii=False))
(SP / "ablation_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")

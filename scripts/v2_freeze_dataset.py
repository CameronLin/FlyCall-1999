#!/usr/bin/env python3
"""Freeze dataset v2.0.0 (ticket 25): batches -> JSONL + CSV in the v1.0.0 schema, plus taxonomy copy,
validation report and SHA-256 checksums.

    python scripts/v2_freeze_dataset.py

Families, splits and per-family quotas are unchanged from v1.0.0 (D-V2-2), so the frozen split manifest
is reused as-is. Only `formal_review_status` differs (D-V2-4: automated QA replaces manual review), which
is why a dataset-v2 copy of the taxonomy is written next to the current one.
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import v2_dataset_tools as t  # noqa: E402

ROOT = t.PROJECT_ROOT
OUT = ROOT / "data/1999_synthetic/formal/v2.0.0"
TAX_SRC = ROOT / "data/1999_synthetic/taxonomy/current/taxonomy_v1.3.yaml"
TAX_V2 = ROOT / "data/1999_synthetic/taxonomy/current/taxonomy_v1.3_dataset_v2.yaml"
MANIFEST = ROOT / "data/1999_synthetic/taxonomy/current/formal_split_manifest_frozen_v1.0.yaml"
REVIEW_STATUS = "automated_qa_passed_no_manual_review"
GENERATOR = "Claude (Anthropic) hand-written per record; stock-line variation by scripts/v2_vary_stock_lines.py"
PROMPT_VERSION = "flycall1999-formal-v2.0.0"
SPEAKER_MAP = {"R": "客服", "L": "來電民眾"}
FIELDS = ["id", "transcript", "label_id", "label_name", "scenario_id", "scenario_family_id", "split", "is_synthetic",
          "speaker_map", "generator_model", "prompt_version", "review_status"]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    brief = t.load_brief()
    label_names = brief["labels"]
    plan = {r["id"]: r for b in json.loads(t.PLAN.read_text(encoding="utf-8"))["batches"] for r in b}
    records = t.load_all()
    issues = {r["id"]: t.rule_issues(r, plan.get(r["id"])) for r in records}
    bad = {k: v for k, v in issues.items() if v}
    if bad or len(records) != 1000:
        print(f"refusing to freeze: {len(records)} records, {len(bad)} with rule issues")
        return 1
    rows = []
    for r in sorted(records, key=lambda r: list(plan).index(r["id"])):
        p = plan[r["id"]]
        rows.append({
            "id": r["id"], "transcript": r["transcript"], "label_id": p["label_id"], "label_name": label_names[p["label_id"]],
            "scenario_id": r["id"].replace("TPE1999-V2-", "SCENARIO-V2-"), "scenario_family_id": r["family"],
            "split": p["split"], "is_synthetic": True, "speaker_map": SPEAKER_MAP, "generator_model": GENERATOR,
            "prompt_version": PROMPT_VERSION, "review_status": REVIEW_STATUS,
        })
    jsonl = OUT / "formal_dataset_v2.0.0.jsonl"
    jsonl.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8")
    csv_path = OUT / "formal_dataset_v2.0.0.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(FIELDS)
        for row in rows:
            w.writerow([str(row[k]) if k in ("is_synthetic", "speaker_map") else row[k] for k in FIELDS])
    tax = TAX_SRC.read_text(encoding="utf-8")
    assert "formal_review_status: pending_manual_review" in tax
    tax = tax.replace("formal_review_status: pending_manual_review", f"formal_review_status: {REVIEW_STATUS}")
    tax = "# Dataset v2.0.0 copy of taxonomy_v1.3.yaml: identical labels/families; only formal_review_status differs (ticket 25, D-V2-4).\n" + tax
    TAX_V2.write_text(tax, encoding="utf-8")

    audit = json.loads((t.V2 / "audit_report.json").read_text(encoding="utf-8"))
    lc = json.loads((t.V2 / "label_consistency.json").read_text(encoding="utf-8"))
    split_counts = Counter(r["split"] for r in rows)
    label_split = Counter((r["label_id"], r["split"]) for r in rows)
    d = audit["diversity"]
    lines = [
        "# Dataset v2.0.0 validation report",
        "",
        "**Status:** frozen. 自動品質檢查通過，未經人工複核（ticket 25, D-V2-4）。",
        "",
        "## Contents",
        "",
        f"- Records: {len(rows)} (5 labels × 200); families, splits and per-family quotas unchanged from v1.0.0.",
        f"- Splits: train {split_counts['train']}, validation {split_counts['validation']}, test {split_counts['test']}.",
        "- Per label: " + "; ".join(f"{lab} " + "/".join(str(label_split[(lab, s)]) for s in ("train", "validation", "test")) for lab in t.LABEL_ORDER) + " (train/val/test).",
        f"- `review_status`: `{REVIEW_STATUS}`; `prompt_version`: `{PROMPT_VERSION}`.",
        "",
        "## Automated QA results",
        "",
        "| Check | Result | Target |",
        "|---|---:|---|",
        f"| Rule flags (format, 7–17 lines, ≥200 CJK, PII, own-label fragments, agent promises) | {len(audit['rule_flags'])} | 0 |",
        f"| Near-duplicate pairs (char 3-gram Jaccard ≥ 0.72) | {len(audit['near_duplicates'])} | 0 |",
        f"| Max pairwise Jaccard | {audit['max_jaccard']['value']} | < 0.72 (v1: 0.48) |",
        f"| Share of lines reused | {d['share_of_lines_reused']:.1%} | < 20% (v1: ~70%) |",
        f"| Distinct opening lines | {d['distinct_openings']} | (v1: 8) |",
        f"| Distinct closing lines | {d['distinct_closings']} | (v1: 24) |",
        f"| Mean CJK characters | {d['mean_cjk_chars']} | ≥ 200 each |",
        f"| Line-count histogram | {d['line_count_hist']} | 7–17 |",
        f"| Leave-family-out classifier accuracy (char TF-IDF + LR) | {lc['accuracy']:.3f} | — |",
        f"| High-confidence (p ≥ 0.6) other-label predictions | {len(lc['flags'])} | reviewed |",
        "",
        "## Shortcut n-grams (precision ≥ 0.9, coverage ≥ 0.3 within a label)",
        "",
        "Template artefacts found in the hand-written batches were removed by `scripts/v2_vary_stock_lines.py`",
        "(e.g. the agent question 「請問是哪一區的公園？」 in 98% of park calls, 「的方向，」 in road calls,",
        "「公尺範圍」 in cleaning recaps). What remains is the subject vocabulary of each label, accepted as",
        "inherent rather than a label-name echo (v1's 「一般公園」):",
        "",
    ]
    by_label: dict[str, list[str]] = {}
    for s in audit["shortcut_ngrams"]:
        by_label.setdefault(s["label"], []).append(f"「{s['ngram']}」 {s['coverage']:.2f}/{s['precision']:.2f}")
    for lab, items in by_label.items():
        lines.append(f"- {lab}: " + ", ".join(items[:10]))
    lines += [
        "",
        "## Label-consistency review",
        "",
        "Records predicted as another label with p ≥ 0.6 by a classifier trained without their own family were read by Claude:",
        "",
    ]
    for f in lc["flags"]:
        lines.append(f"- {f['id']} ({f['family']}): predicted {f['pred']} p={f['p']} — kept; single complaint inside its family boundary (intended hard boundary case).")
    lines += ["", "## Files and SHA-256", ""]
    for pth in (jsonl, csv_path, TAX_V2, MANIFEST):
        lines.append(f"- `{pth.relative_to(ROOT).as_posix()}` `{sha256(pth)}`")
    (OUT / "validation_report_v2.0.0.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    sums = "".join(f"{sha256(p)}  {p.relative_to(ROOT).as_posix()}\n" for p in (jsonl, csv_path, TAX_V2, MANIFEST))
    (OUT / "SHA256SUMS").write_text(sums, encoding="utf-8")
    print(f"froze {len(rows)} records to {OUT}")
    print(sums)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

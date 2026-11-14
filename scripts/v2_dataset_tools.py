#!/usr/bin/env python3
"""Dataset v2.0.0 tooling (ticket 25): batch plan, batch parsing and automatic QA.

Batch files are authored as plain text blocks:

    ### TPE1999-V2-SW-0001|FAM-SW-TILE-MOVEMENT
    R:...
    L:...

Commands:
    plan            write the 20-batch writing plan from family_brief.json
    check <files>   parse batches and run the rule checks (per-batch feedback)
    audit           run the full QA (rules + shortcuts + diversity) over all batches
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
V2 = PROJECT_ROOT / ".scratch/1999-connectome-demo/data-v2"
BRIEF = V2 / "family_brief.json"
PLAN = V2 / "batch_plan.json"
BATCHES = V2 / "batches"
LABEL_ORDER = ["sidewalk_maintenance", "road_surface_defect", "park_general_maintenance", "waste_truck_service", "street_cleaning"]
PREFIX = {"sidewalk_maintenance": "SW", "road_surface_defect": "RD", "park_general_maintenance": "PK",
          "waste_truck_service": "WT", "street_cleaning": "SC"}
BATCH_SIZE = 50
MIN_LINES, MAX_LINES, MIN_CHARS = 7, 17, 200
# Label-name fragments a caller would not naturally say, checked only against the record's OWN label
# (a fragment of another label's name is not a giveaway; e.g. "有高低差" in a sidewalk call). "一般公園" was the v1 shortcut.
LABEL_FRAGMENTS = {
    "sidewalk_maintenance": ["人行道維護"],
    "road_surface_defect": ["道路凹陷", "有高低差"],
    "park_general_maintenance": ["一般公園", "綠地管理", "設施維護", "車輛違規進入"],
    "waste_truck_service": ["垃圾車清運", "清運及服務", "服務事項"],
    "street_cleaning": ["路面清潔", "行人果皮箱"],
}
ALL_LABEL_NAMES = ["人行道維護", "道路凹陷、不平、有高低差", "一般公園綠地管理及設施維護", "垃圾車清運及服務事項", "路面清潔（含行人果皮箱"]
PROMISE = re.compile(r"(會派人|馬上(派|處理|修)|立刻(派|處理|修)|一定(會|幫您)(修|處理|改善)|保證|[一二三兩幾\d]+(天|個工作天|小時)內(處理|修|完成|派)|已經(派|通知)(人|清潔隊|工程)|我們會(去|派)|今天就會)")
PII = [re.compile(r"09\d{2}[-\s]?\d{3}[-\s]?\d{3}"), re.compile(r"\(?0\d{1,2}\)?[-\s]?\d{3,4}[-\s]?\d{4}"),
       re.compile(r"[A-Z][12]\d{8}"), re.compile(r"\d+\s*號(?!出口|線|公車|車|門)"), re.compile(r"\d+\s*巷\d+\s*弄"),
       re.compile(r"(先生|小姐|太太)貴姓|我姓[^\s，。]{1}[，。]|我叫[^\s，。]{2,3}")]
CJK = re.compile(r"[一-鿿]")


def load_brief() -> dict:
    return json.loads(BRIEF.read_text(encoding="utf-8"))


def make_plan() -> None:
    brief = load_brief()
    counters = collections.Counter()
    records = []
    for fam in brief["families"]:
        for _ in range(fam["n"]):
            counters[fam["label_id"]] += 1
            records.append({"id": f"TPE1999-V2-{PREFIX[fam['label_id']]}-{counters[fam['label_id']]:04d}",
                            "family": fam["family"], "label_id": fam["label_id"], "split": fam["split"]})
    batches = [records[i:i + BATCH_SIZE] for i in range(0, len(records), BATCH_SIZE)]
    PLAN.write_text(json.dumps({"batch_size": BATCH_SIZE, "batches": batches}, ensure_ascii=False, indent=1), encoding="utf-8")
    for n, batch in enumerate(batches, 1):
        fams = collections.Counter(r["family"] for r in batch)
        print(f"batch {n:02d}: {batch[0]['id']}..{batch[-1]['id']}  " + ", ".join(f"{f}×{c}" for f, c in fams.items()))


def parse_file(path: Path) -> list[dict]:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    out = []
    for block in re.split(r"^### ", text, flags=re.M)[1:]:
        head, _, body = block.partition("\n")
        rid, _, fam = head.strip().partition("|")
        lines = [ln.strip() for ln in body.strip().split("\n") if ln.strip()]
        out.append({"id": rid.strip(), "family": fam.strip(), "transcript": "\n".join(lines), "lines": lines, "source": path.name})
    return out


def rule_issues(rec: dict, expected: dict | None) -> list[str]:
    issues = []
    lines = rec["lines"]
    if expected is None:
        issues.append("id not in plan")
    elif expected["family"] != rec["family"]:
        issues.append(f"family mismatch (plan {expected['family']})")
    if not (MIN_LINES <= len(lines) <= MAX_LINES):
        issues.append(f"{len(lines)} lines")
    for i, ln in enumerate(lines):
        want = "R:" if i % 2 == 0 else "L:"
        if not ln.startswith(want):
            issues.append(f"line {i + 1} should start with {want}")
            break
        if len(ln) <= 2:
            issues.append(f"line {i + 1} empty")
    chars = len(CJK.findall(rec["transcript"]))
    if chars < MIN_CHARS:
        issues.append(f"only {chars} CJK chars")
    label = expected["label_id"] if expected else None
    for frag in LABEL_FRAGMENTS.get(label, []):
        if frag in rec["transcript"]:
            issues.append(f"own-label fragment '{frag}'")
    for name in ALL_LABEL_NAMES:
        if name in rec["transcript"]:
            issues.append(f"full label name '{name}'")
    for ln in lines:
        if ln.startswith("R:") and PROMISE.search(ln):
            issues.append(f"service promise: {PROMISE.search(ln).group(0)}")
    for pat in PII:
        m = pat.search(rec["transcript"])
        if m:
            issues.append(f"possible PII: {m.group(0)}")
    return issues


def grams(text: str, n: int = 3) -> set[str]:
    s = "".join(ch for ch in text if not ch.isspace())
    return {s[i:i + n] for i in range(len(s) - n + 1)}


def load_all(files: list[Path] | None = None) -> list[dict]:
    files = files or sorted(BATCHES.glob("batch_*.txt"))
    records = []
    for f in files:
        records.extend(parse_file(f))
    return records


def check(files: list[Path]) -> int:
    plan = {r["id"]: r for b in json.loads(PLAN.read_text(encoding="utf-8"))["batches"] for r in b}
    records = load_all(files)
    bad = 0
    for rec in records:
        issues = rule_issues(rec, plan.get(rec["id"]))
        if issues:
            bad += 1
            print(f"FLAG {rec['id']}: " + "; ".join(issues))
    ids = [r["id"] for r in records]
    dup = [i for i, c in collections.Counter(ids).items() if c > 1]
    if dup:
        print("DUPLICATE IDS:", dup)
    print(f"checked {len(records)} records, flagged {bad}")
    return 1 if bad or dup else 0


def audit() -> int:
    plan = {r["id"]: r for b in json.loads(PLAN.read_text(encoding="utf-8"))["batches"] for r in b}
    records = load_all()
    report: dict = {"records": len(records), "expected": len(plan)}
    report["missing_ids"] = sorted(set(plan) - {r["id"] for r in records})
    report["rule_flags"] = {r["id"]: rule_issues(r, plan.get(r["id"])) for r in records if rule_issues(r, plan.get(r["id"]))}
    # near duplicates
    gs = [grams(r["transcript"]) for r in records]
    near, top = [], (0.0, None)
    for i in range(len(records)):
        for j in range(i + 1, len(records)):
            inter = len(gs[i] & gs[j])
            if not inter:
                continue
            jac = inter / len(gs[i] | gs[j])
            if jac > top[0]:
                top = (jac, (records[i]["id"], records[j]["id"]))
            if jac >= 0.72:
                near.append((records[i]["id"], records[j]["id"], round(jac, 3)))
    report["near_duplicates"] = near
    report["max_jaccard"] = {"value": round(top[0], 4), "pair": top[1]}
    # diversity
    lines = [ln for r in records for ln in r["lines"]]
    counts = collections.Counter(lines)
    report["diversity"] = {
        "total_lines": len(lines), "distinct_lines": len(counts),
        "share_of_lines_reused": round(sum(c for c in counts.values() if c > 1) / len(lines), 4),
        "distinct_openings": len({r["lines"][0] for r in records}), "distinct_closings": len({r["lines"][-1] for r in records}),
        "line_count_hist": dict(sorted(collections.Counter(len(r["lines"]) for r in records).items())),
        "mean_cjk_chars": round(sum(len(CJK.findall(r["transcript"])) for r in records) / max(1, len(records)), 1),
    }
    # shortcut n-grams (2..4 chars): precision >= 0.9 and coverage >= 0.3 within a label
    label_of = {r["id"]: plan[r["id"]]["label_id"] for r in records if r["id"] in plan}
    per_label = collections.Counter(label_of.values())
    shortcuts = []
    for n in (2, 3, 4):
        doc_grams = [(label_of.get(r["id"]), grams(r["transcript"], n)) for r in records]
        df = collections.Counter(g for _, s in doc_grams for g in s)
        for lab in LABEL_ORDER:
            pos = collections.Counter(g for l, s in doc_grams if l == lab for g in s)
            for g, c in pos.items():
                if per_label[lab] and c / per_label[lab] >= 0.3 and c / df[g] >= 0.9 and not re.fullmatch(r"[RL:：\W\d]+", g):
                    shortcuts.append({"label": lab, "ngram": g, "coverage": round(c / per_label[lab], 3), "precision": round(c / df[g], 3)})
    # keep the most informative n-grams (drop ones contained in a longer flagged n-gram of the same label)
    shortcuts.sort(key=lambda s: (-s["coverage"], -len(s["ngram"])))
    report["shortcut_ngrams"] = shortcuts[:60]
    out = V2 / "audit_report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in report.items() if k not in ("rule_flags",)}, ensure_ascii=False, indent=1)[:4000])
    print(f"rule-flagged records: {len(report['rule_flags'])}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("plan")
    c = sub.add_parser("check")
    c.add_argument("files", nargs="+", type=Path)
    sub.add_parser("audit")
    args = parser.parse_args()
    if args.cmd == "plan":
        make_plan()
        return 0
    if args.cmd == "check":
        return check(args.files)
    return audit()


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())

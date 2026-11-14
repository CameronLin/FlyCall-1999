#!/usr/bin/env python3
"""Write the auxiliary files the HTML report reads next to a tuning run.

    python scripts/make_tuning_aux.py timings <tuning-run>
    python scripts/make_tuning_aux.py t-compare <t4-run> <t2-run>

``timings.json`` is derived from ``progress.log`` timestamps (phase A = Fly A CV, B = Fly B CV, final);
``t4_vs_t2.json`` holds the per-seed paired deltas T4 − T2 with the preregistered consistency rule
(three seeds same sign and |mean delta| ≥ 0.02).
"""

from __future__ import annotations

import json
import re
import statistics
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
LINE = re.compile(r"^\[\s*([\d.]+)s\] (\S+) (A|B|final)")
COMBOS = ("lda_to_svm", "fly_a_distance_to_svm", "fly_a_distance_supcon_to_svm", "lda_to_fly_b",
          "fly_a_distance_to_fly_b", "fly_a_distance_supcon_to_fly_b")


def timings(run: Path) -> dict:
    marks: dict[str, dict[str, float]] = {}
    order: list[str] = []
    for raw in (run / "progress.log").read_text(encoding="utf-8").splitlines():
        m = LINE.match(raw)
        if not m:
            continue
        t, graph, phase = float(m.group(1)), m.group(2), m.group(3)
        if graph not in marks:
            marks[graph], _ = {}, order.append(graph)
        marks[graph][phase] = t
    by_graph, start = {}, 0.0
    for graph in order:
        a, b, f = marks[graph]["A"], marks[graph]["B"], marks[graph]["final"]
        by_graph[graph] = {"fly_a_cv_seconds": round(a - start, 1), "fly_b_cv_seconds": round(b - a, 1),
                           "final_training_seconds": round(f - b, 1), "total_seconds": round(f - start, 1)}
        start = f
    return {"source": "progress.log timestamps", "by_graph": by_graph, "run_total_seconds": round(start, 1)}


def f1s(results: dict, graph: str, combo: str) -> list[float]:
    block = results["by_graph"][graph]["final"][combo]
    rows = block.get("by_seed") or [{"validation": v} for v in block["validation_by_seed"]]
    return [float(r["validation"]["macro_f1"]) for r in rows]


def t_compare(t4: Path, t2: Path) -> dict:
    r4 = json.loads((t4 / "results.json").read_text(encoding="utf-8"))
    r2 = json.loads((t2 / "results.json").read_text(encoding="utf-8"))
    deltas = {}
    for graph in r4["by_graph"]:
        deltas[graph] = {}
        for combo in COMBOS:
            a, b = f1s(r2, graph, combo), f1s(r4, graph, combo)
            per_seed = [y - x for x, y in zip(a, b)]
            mean = statistics.fmean(per_seed)
            consistent = (all(d > 0 for d in per_seed) or all(d < 0 for d in per_seed)) and abs(mean) >= 0.02
            deltas[graph][combo] = {"t2_mean": statistics.fmean(a), "t4_mean": statistics.fmean(b), "per_seed": per_seed,
                                    "mean": mean, "consistent": consistent,
                                    "verdict": "consistent" if consistent else "unclear"}
    return {"rule": "three seeds same sign and |mean delta| >= 0.02",
            "t2_run": t2.relative_to(PROJECT_ROOT).as_posix(), "deltas": deltas}


def main() -> int:
    if sys.argv[1] == "timings":
        run = PROJECT_ROOT / sys.argv[2]
        (run / "timings.json").write_text(json.dumps(timings(run), indent=2) + "\n", encoding="utf-8")
    elif sys.argv[1] == "t-compare":
        t4, t2 = PROJECT_ROOT / sys.argv[2], PROJECT_ROOT / sys.argv[3]
        (t4 / "t4_vs_t2.json").write_text(json.dumps(t_compare(t4, t2), indent=2) + "\n", encoding="utf-8")
    else:
        raise SystemExit(__doc__)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

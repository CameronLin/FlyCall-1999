#!/usr/bin/env python3
"""Pre-register and aggregate M3.4 validation-only, multi-seed runs."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from flycall_data.comparison import (  # noqa: E402
    CANDIDATE_NAMES,
    SELECTION_RULE,
    ComparisonError,
    aggregate_validation_runs,
)


DEFAULT_OUTPUT_PARENT = PROJECT_ROOT / ".scratch/1999-connectome-demo/runs"
DEFAULT_SEEDS = (42, 1337, 2026)


def _write_json(path: Path, value: dict) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _display_path(path: Path) -> str:
    try:
        display = Path(path).resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        display = str(path)
    return display.encode("ascii", errors="backslashreplace").decode("ascii")


def _render_report(result: dict) -> str:
    lines = [
        "# M3.4 validation-only candidate comparison",
        "",
        f"- Status: `{result['status']}`",
        f"- Data: `{result['data_status']}`",
        f"- Review: `{result['review_status']}`",
        f"- Seeds: `{', '.join(str(seed) for seed in result['seeds'])}`",
        f"- Selection rule: {result['selection_rule']}",
        f"- Validation winner: `{result['validation_winner']}` (pending manual review)",
        "- Formal test eligible: `false`",
        "- Test: `not_run`",
        "",
        "| Candidate | Validation Macro-F1 mean | Sample SD | Accuracy mean | Sample SD |",
        "|---|---:|---:|---:|---:|",
    ]
    for name in result["candidate_names"]:
        candidate = result["candidates"][name]
        macro_f1 = candidate["validation_macro_f1"]
        accuracy = candidate["validation_accuracy"]
        lines.append(
            f"| `{name}` | {macro_f1['mean']:.4f} | {macro_f1['sample_std']:.4f} "
            f"| {accuracy['mean']:.4f} | {accuracy['sample_std']:.4f} |"
        )
    lines.extend(
        [
            "",
            "## Per-seed validation metrics",
            "",
            "| Candidate | Seed | Validation Macro-F1 | Validation accuracy |",
            "|---|---:|---:|---:|",
        ]
    )
    for name in result["candidate_names"]:
        candidate = result["candidates"][name]
        macro_f1_by_seed = candidate["validation_macro_f1"]["by_seed"]
        accuracy_by_seed = candidate["validation_accuracy"]["by_seed"]
        for seed in result["seeds"]:
            seed_key = str(seed)
            lines.append(
                f"| `{name}` | {seed} | {macro_f1_by_seed[seed_key]:.4f} "
                f"| {accuracy_by_seed[seed_key]:.4f} |"
            )
    lines.extend(
        [
            "",
            "This report reads saved train/validation metrics and provenance only. It does not read test rows, "
            "test predictions, or test metrics. Candidate selection remains provisional until the required "
            "manual review and configuration lock are recorded.",
            "",
        ]
    )
    return "\n".join(lines)


def _render_failure(error: str, *, seeds: Sequence[int], run_dirs: Sequence[Path]) -> dict:
    return {
        "schema_version": 1,
        "status": "incomplete",
        "error": error,
        "candidate_names": list(CANDIDATE_NAMES),
        "seeds": list(seeds),
        "input_run_dirs": [str(path) for path in run_dirs],
        "data_status": "synthetic",
        "review_status": "pending_manual_review",
        "test": {"status": "not_run", "input_count": 0, "prediction_count": 0, "metrics": None},
        "formal_test_eligible": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", action="append", type=Path, required=True, help="completed M2 baseline or M3.2 run; repeat for every seed")
    parser.add_argument("--seed", action="append", type=int, help="declared training seed; repeat at least three times (defaults to 42, 1337, 2026)")
    parser.add_argument("--output-id", help="unique comparison artifact name; defaults to a UTC timestamp")
    parser.add_argument("--output-parent", type=Path, default=DEFAULT_OUTPUT_PARENT)
    args = parser.parse_args(argv)

    seeds = tuple(args.seed) if args.seed is not None else DEFAULT_SEEDS
    if len(seeds) < 3 or len(set(seeds)) != len(seeds) or any(seed < 1 for seed in seeds):
        parser.error("provide at least three unique positive --seed values")
    output_id = args.output_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", output_id):
        parser.error("--output-id may contain only letters, numbers, dot, underscore, and hyphen")

    output_dir = args.output_parent.resolve() / f"m3-4-validation-comparison-{output_id}"
    try:
        output_dir.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        parser.error(f"comparison output already exists: {output_dir}")
    except OSError as error:
        parser.error(f"cannot create comparison output directory: {error}")

    preregistration = {
        "schema_version": 1,
        "status": "pre_registered",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "candidate_names": list(CANDIDATE_NAMES),
        "seeds": list(seeds),
        "selection_rule": SELECTION_RULE,
        "input_run_dirs": [str(path) for path in args.run_dir],
        "data_status": "synthetic",
        "review_status": "pending_manual_review",
        "test": "not_run; no test rows, predictions, or metrics may be opened",
        "formal_test_eligible": False,
    }
    # Persist the candidate and seed plan before opening any run metrics.
    _write_json(output_dir / "pre_registered_comparison.json", preregistration)

    try:
        result = aggregate_validation_runs(
            args.run_dir,
            required_seeds=seeds,
            candidate_names=CANDIDATE_NAMES,
        )
        result["comparison_id"] = output_dir.name
    except (ComparisonError, OSError, ValueError) as error:
        result = _render_failure(str(error), seeds=seeds, run_dirs=args.run_dir)
        result["comparison_id"] = output_dir.name
        _write_json(output_dir / "comparison.json", result)
        (output_dir / "report.md").write_text(
            "# M3.4 validation-only candidate comparison\n\n"
            f"- Status: `incomplete`\n- Test: `not_run`\n- Formal test eligible: `false`\n\n{error}\n",
            encoding="utf-8",
        )
        print(f"M3.4 comparison incomplete: {error}", file=sys.stderr)
        return 2

    _write_json(output_dir / "comparison.json", result)
    _write_json(
        output_dir / "candidate_selection.json",
        {
            "schema_version": 1,
            "status": "provisional_pending_manual_review",
            "candidate_names": list(CANDIDATE_NAMES),
            "seeds": list(seeds),
            "validation_winner": result["validation_winner"],
            "selection_rule": SELECTION_RULE,
            "candidate_list_locked": False,
            "configuration_locked": False,
            "manual_review_gate_passed": False,
            "formal_test_eligible": False,
            "test": "not_run",
            "input_artifacts": result["input_artifacts"],
        },
    )
    (output_dir / "report.md").write_text(_render_report(result), encoding="utf-8")
    print(f"M3.4 validation comparison completed: {_display_path(output_dir)}")
    print(f"Provisional validation winner: {result['validation_winner']}; test remains not_run.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

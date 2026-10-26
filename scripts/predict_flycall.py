#!/usr/bin/env python3
"""Predict one user-supplied transcript with a locked local research model."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from flycall_data.predictor import FlyCallPredictor, PredictorError  # noqa: E402


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-manifest", type=Path, required=True, help="reviewed, configuration-locked model manifest")
    parser.add_argument("--e5-snapshot", type=Path, required=True, help="local, checksum-verified E5 snapshot")
    parser.add_argument("--text", help="one transcript; if omitted, read one transcript from standard input")
    args = parser.parse_args(argv)
    transcript = args.text if args.text is not None else sys.stdin.read()
    try:
        predictor = FlyCallPredictor.from_locked_manifest(
            args.model_manifest,
            e5_snapshot=args.e5_snapshot,
        )
        result = predictor.predict(transcript)
    except (PredictorError, OSError, RuntimeError, ValueError) as error:
        print(f"Prediction unavailable: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result.as_dict(), ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

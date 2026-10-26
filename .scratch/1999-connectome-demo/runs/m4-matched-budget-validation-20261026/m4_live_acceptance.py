from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[4]
TRANSCRIPT = "M4 interface acceptance synthetic transcript: potholes reported."
TOLERANCE = 1e-7
MARKER = "M4RESULT="


def child_result(value: dict[str, Any]) -> None:
    print(MARKER + json.dumps(value, ensure_ascii=True, allow_nan=False))


def run_api(manifest: Path, snapshot: Path, transcript: str) -> None:
    sys.path.insert(0, str(ROOT / "src"))
    from flycall_data.predictor import FlyCallPredictor

    predictor = FlyCallPredictor.from_locked_manifest(manifest, e5_snapshot=snapshot)
    child_result(predictor.predict(transcript).as_dict())


def run_cli(manifest: Path, snapshot: Path, transcript: str) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "predict_flycall.py"),
            "--model-manifest",
            str(manifest),
            "--e5-snapshot",
            str(snapshot),
            "--text",
            transcript,
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
        timeout=90,
    )
    start = result.stdout.find("{")
    if start < 0:
        raise RuntimeError("CLI did not emit JSON: " + repr(result.stdout[-1000:]))
    child_result(json.loads(result.stdout[start:]))


def run_streamlit(manifest: Path, snapshot: Path, transcript: str) -> None:
    os.environ["FLYCALL_MODEL_MANIFEST"] = str(manifest)
    os.environ["E5_SNAPSHOT"] = str(snapshot)
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=90).run()
    if app.exception or app.error:
        raise RuntimeError(
            "Streamlit initial load failed: "
            + repr([str(item.value) for item in (*app.exception, *app.error)])
        )
    if len(app.text_area) != 1 or len(app.button) != 1:
        raise RuntimeError("Streamlit did not render its transcript field and predict button.")
    app.text_area[0].set_value(transcript)
    app.button[0].click()
    app.run()
    if app.exception or app.error:
        raise RuntimeError(
            "Streamlit prediction failed: "
            + repr([str(item.value) for item in (*app.exception, *app.error)])
        )
    if len(app.metric) != 1 or len(app.dataframe) != 1 or len(app.info) != 1:
        raise RuntimeError("Streamlit result label, score table, or manual-confirmation notice is missing.")
    frame = app.dataframe[0].value
    child_result(
        {
            "predicted_label": str(app.metric[0].value),
            "probabilities": [float(frame.iloc[index, 1]) for index in range(5)],
            "logits": [float(frame.iloc[index, 2]) for index in range(5)],
            "score_rows": int(frame.shape[0]),
            "manual_confirmation_notice_rendered": True,
            "exceptions": len(app.exception),
        }
    )


def invoke(mode: str, manifest: Path, snapshot: Path, transcript: str) -> dict[str, Any]:
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "src")
    environment["PYTHONIOENCODING"] = "utf-8"
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--child",
        mode,
        "--manifest",
        str(manifest),
        "--snapshot",
        str(snapshot),
        "--transcript",
        transcript,
    ]
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=120,
    )
    if completed.returncode:
        raise RuntimeError(
            f"{mode} acceptance subprocess failed (exit={completed.returncode}):\n"
            + completed.stdout[-2000:]
            + completed.stderr[-2000:]
        )
    for line in reversed(completed.stdout.splitlines()):
        if line.startswith(MARKER):
            return json.loads(line[len(MARKER) :])
    raise RuntimeError(f"{mode} subprocess emitted no result: {completed.stdout[-2000:]} {completed.stderr[-2000:]}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--transcript", default=TRANSCRIPT)
    parser.add_argument("--child", choices=("api", "cli", "streamlit"))
    parser.add_argument("--output-json", type=Path)
    args = parser.parse_args()
    manifest = args.manifest.resolve(strict=True)
    snapshot = args.snapshot.resolve(strict=True)
    if args.child == "api":
        run_api(manifest, snapshot, args.transcript)
        return 0
    if args.child == "cli":
        run_cli(manifest, snapshot, args.transcript)
        return 0
    if args.child == "streamlit":
        run_streamlit(manifest, snapshot, args.transcript)
        return 0

    api = invoke("api", manifest, snapshot, args.transcript)
    cli = invoke("cli", manifest, snapshot, args.transcript)
    ui = invoke("streamlit", manifest, snapshot, args.transcript)
    api_probabilities = list(api["probabilities"].values())
    api_logits = list(api["logits"].values())
    cli_probability_delta = max(
        abs(float(cli["probabilities"][label]) - float(api["probabilities"][label]))
        for label in api["probabilities"]
    )
    cli_logit_delta = max(
        abs(float(cli["logits"][label]) - float(api["logits"][label]))
        for label in api["logits"]
    )
    ui_probability_delta = max(abs(float(x) - float(y)) for x, y in zip(ui["probabilities"], api_probabilities, strict=True))
    ui_logit_delta = max(abs(float(x) - float(y)) for x, y in zip(ui["logits"], api_logits, strict=True))
    if not (api["predicted_label"] == cli["predicted_label"] == ui["predicted_label"]):
        raise RuntimeError("CLI, API, and Streamlit predicted labels differ.")
    if max(cli_probability_delta, cli_logit_delta, ui_probability_delta, ui_logit_delta) > TOLERANCE:
        raise RuntimeError("CLI, API, and Streamlit score outputs differ beyond the configured tolerance.")
    if not all(
        result["data_status"] == "synthetic"
        and result["review_status"] == "pending_manual_review"
        and result["dispatch_status"] == "simulated_only"
        and result["human_confirmation_required"] is True
        for result in (api, cli)
    ):
        raise RuntimeError("Prediction disclosure fields are missing or inconsistent.")
    report = {
        "status": "passed",
        "candidate": api["candidate_name"],
        "predicted_label": api["predicted_label"],
        "label_order": api["label_order"],
        "probabilities": api_probabilities,
        "logits": api_logits,
        "stages": api["stages"],
        "cli_api_max_abs_probability_delta": cli_probability_delta,
        "cli_api_max_abs_logit_delta": cli_logit_delta,
        "streamlit_api_max_abs_probability_delta": ui_probability_delta,
        "streamlit_api_max_abs_logit_delta": ui_logit_delta,
        "review_status": api["review_status"],
        "data_status": api["data_status"],
        "dispatch_status": api["dispatch_status"],
        "human_confirmation_required": api["human_confirmation_required"],
        "streamlit_score_rows": ui["score_rows"],
        "streamlit_manual_confirmation_notice_rendered": ui["manual_confirmation_notice_rendered"],
        "streamlit_exceptions": ui["exceptions"],
        "test_data_accessed": False,
        "transcript": args.transcript,
        "tolerance": TOLERANCE,
    }
    rendered = json.dumps(report, ensure_ascii=True, indent=2, allow_nan=False) + "\n"
    if args.output_json is not None:
        output_path = args.output_json.resolve()
        output_path.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

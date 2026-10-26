"""Validation-only, multi-seed aggregation for the M3.4 candidate comparison."""

from __future__ import annotations

import hashlib
import json
import math
import statistics
from pathlib import Path
from typing import Any, Sequence

from .evaluation import LABEL_ORDER


CANDIDATE_NAMES = (
    "logistic_regression",
    "mlp",
    "pca_mlp",
    "lda_logistic_regression",
    "fly_a_to_fly_b",
)
SELECTION_RULE = (
    "highest mean validation Macro-F1 across the predeclared seeds; ties use higher mean validation accuracy, "
    "then candidate name in ascending lexical order"
)
DATASET_SOURCE_KEYS = ("jsonl", "csv", "taxonomy", "manifest")
E5_IDENTITY_KEYS = (
    "model_id",
    "revision",
    "prefix",
    "max_seq_length",
    "pooling",
    "normalize_embeddings",
    "model_file_sha256",
)
GRAPH_SOURCE_KEYS = ("graph_manifest", "io_manifest", "nodes_parquet", "edges_parquet")


class ComparisonError(ValueError):
    """Raised when provisional runs cannot form the predeclared comparison."""


def _read_json(path: Path, *, description: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise ComparisonError(f"{description} is unreadable or invalid: {path}") from error
    if not isinstance(value, dict):
        raise ComparisonError(f"{description} must contain a JSON object: {path}")
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def _without_seed_fields(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _without_seed_fields(item)
            for key, item in value.items()
            if key not in {"seed", "random_state", "candidate_name"}
        }
    if isinstance(value, list):
        return [_without_seed_fields(item) for item in value]
    return value


def _fingerprint_registration(registration: dict[str, Any]) -> str:
    unsigned = {key: value for key, value in registration.items() if key != "configuration_fingerprint"}
    return hashlib.sha256(_canonical_bytes(unsigned)).hexdigest()


def _seed_from_registration(registration: dict[str, Any]) -> int:
    raw = registration.get("seed")
    if raw is None and isinstance(registration.get("training"), dict):
        raw = registration["training"].get("seed")
    if isinstance(raw, bool) or not isinstance(raw, int) or raw < 1:
        raise ComparisonError("a run preregistration must include a positive integer training seed.")
    return raw


def _candidate_configuration(registration: dict[str, Any], candidate: str) -> dict[str, Any]:
    if candidate == "fly_a_to_fly_b":
        config = registration.get("training")
        graph = registration.get("graph")
        if not isinstance(config, dict) or not isinstance(graph, dict):
            raise ComparisonError("Fly A/B preregistration is missing its training or graph configuration.")
        return {"training": config, "graph": graph}
    candidates = registration.get("candidates")
    config = candidates.get(candidate) if isinstance(candidates, dict) else None
    if not isinstance(config, dict):
        raise ComparisonError(f"preregistration is missing candidate settings for {candidate}.")
    return config


def _e5_identity(registration: dict[str, Any]) -> dict[str, Any]:
    embedding = registration.get("embedding")
    if not isinstance(embedding, dict):
        raise ComparisonError("run preregistration is missing the embedding settings.")
    identity = {key: embedding.get(key) for key in E5_IDENTITY_KEYS}
    if any(identity[key] is None for key in E5_IDENTITY_KEYS):
        raise ComparisonError("run preregistration is missing pinned E5 identity fields or model file hashes.")
    return identity


def _dataset_sources(run_manifest: dict[str, Any]) -> dict[str, str]:
    source_map = run_manifest.get("source_sha256_after")
    if not isinstance(source_map, dict):
        source_map = run_manifest.get("source_sha256")
    if not isinstance(source_map, dict):
        raise ComparisonError("run manifest is missing source SHA-256 values.")
    sources = {key: source_map.get(key) for key in DATASET_SOURCE_KEYS}
    if any(not isinstance(value, str) or len(value) != 64 for value in sources.values()):
        raise ComparisonError("run manifest is missing one or more frozen dataset source hashes.")
    return sources


def _check_test_not_run(value: dict[str, Any], *, description: str) -> None:
    test = value.get("test")
    if test is None and isinstance(value.get("splits"), dict):
        test = value["splits"].get("test")
    if not isinstance(test, dict) or test.get("status") != "not_run":
        raise ComparisonError(f"{description} must keep test status at not_run.")
    count_keys = (
        "input_count",
        "transcript_count_passed_to_tokenizer",
        "embedding_count",
        "prediction_count",
        "model_inputs",
    )
    for key in count_keys:
        count = test.get(key)
        if count is not None and (isinstance(count, bool) or not isinstance(count, int) or count != 0):
            raise ComparisonError(f"{description} records non-zero test usage for {key}.")
    if test.get("metrics") not in (None, "not_run"):
        raise ComparisonError(f"{description} contains test metrics despite a not_run status.")
    forbidden = {
        "n_records",
        "labels",
        "per_class",
        "confusion_matrix",
        "accuracy",
        "macro_f1",
        "predictions",
        "record_ids",
        "transcripts",
        "transcript_text",
        "embedding_path",
    }
    leaked = forbidden.intersection(test)
    if leaked:
        raise ComparisonError(f"{description} contains test result fields: {sorted(leaked)}.")


def _verify_metrics_checksum(run_dir: Path, run_manifest: dict[str, Any], metrics_path: Path) -> str:
    outputs = run_manifest.get("outputs")
    if not isinstance(outputs, dict):
        raise ComparisonError(f"run manifest has no output checksums: {run_dir}")
    records = [record for name, record in outputs.items() if Path(str(name)).name == metrics_path.name]
    if len(records) != 1 or not isinstance(records[0], dict):
        raise ComparisonError(f"run manifest must contain one checksum for metrics.json: {run_dir}")
    actual = _sha256_file(metrics_path)
    if records[0].get("sha256") != actual:
        raise ComparisonError(f"metrics.json checksum differs from its run manifest: {run_dir}")
    if records[0].get("bytes") != metrics_path.stat().st_size:
        raise ComparisonError(f"metrics.json byte count differs from its run manifest: {run_dir}")
    return actual


def _normalise_candidate_name(raw: str) -> str:
    if raw == "fly_a_to_fly_b" or raw.startswith("fly_a_to_fly_b_m3_2_seed_"):
        return "fly_a_to_fly_b"
    return raw


def _metric_row(
    *,
    report: dict[str, Any],
    candidate: str,
    seed: int,
    run_id: str,
    run_dir: Path,
) -> dict[str, Any]:
    if (
        report.get("evaluation_status") != "smoke_test/provisional"
        or report.get("data_status") != "synthetic"
        or report.get("review_status") != "pending_manual_review"
        or report.get("label_order") != list(LABEL_ORDER)
    ):
        raise ComparisonError(f"{candidate} run {run_id} has incompatible evaluation provenance or label order.")
    _check_test_not_run(report, description=f"{candidate} metrics in {run_id}")
    splits = report.get("splits")
    if not isinstance(splits, dict):
        raise ComparisonError(f"{candidate} metrics in {run_id} are missing train/validation splits.")
    train = splits.get("train")
    validation = splits.get("validation")
    if (
        not isinstance(train, dict)
        or train.get("status") != "evaluated"
        or train.get("n_records") != 700
        or not isinstance(validation, dict)
        or validation.get("status") != "evaluated"
        or validation.get("n_records") != 150
    ):
        raise ComparisonError(f"{candidate} run {run_id} must have evaluated 700/150 train/validation rows.")
    metrics = validation.get("metrics")
    if not isinstance(metrics, dict) or metrics.get("labels") != list(LABEL_ORDER):
        raise ComparisonError(f"{candidate} validation metrics in {run_id} have the wrong label order.")
    accuracy = metrics.get("accuracy")
    macro_f1 = metrics.get("macro_f1")
    for key, number in (("accuracy", accuracy), ("macro_f1", macro_f1)):
        if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number):
            raise ComparisonError(f"{candidate} validation {key} in {run_id} is not finite.")
    per_class = metrics.get("per_class")
    if not isinstance(per_class, dict) or set(per_class) != set(LABEL_ORDER):
        raise ComparisonError(f"{candidate} validation per-class metrics in {run_id} are incomplete.")
    checked_per_class: dict[str, dict[str, float | int]] = {}
    for label in LABEL_ORDER:
        values = per_class[label]
        if not isinstance(values, dict) or values.get("support") != 30:
            raise ComparisonError(f"{candidate} validation support for {label} in {run_id} must be 30.")
        checked: dict[str, float | int] = {"support": 30}
        for key in ("precision", "recall", "f1"):
            number = values.get(key)
            if isinstance(number, bool) or not isinstance(number, (int, float)) or not math.isfinite(number):
                raise ComparisonError(f"{candidate} validation {key} for {label} in {run_id} is not finite.")
            checked[key] = float(number)
        checked_per_class[label] = checked
    matrix = metrics.get("confusion_matrix")
    if (
        not isinstance(matrix, list)
        or len(matrix) != len(LABEL_ORDER)
        or any(not isinstance(row, list) or len(row) != len(LABEL_ORDER) for row in matrix)
        or any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for row in matrix for value in row)
        or sum(sum(row) for row in matrix) != 150
    ):
        raise ComparisonError(f"{candidate} validation confusion matrix in {run_id} is invalid.")
    row_supports = [sum(row) for row in matrix]
    if row_supports != [30] * len(LABEL_ORDER):
        raise ComparisonError(f"{candidate} validation confusion matrix in {run_id} must contain 30 examples per label.")
    column_supports = [sum(matrix[row][column] for row in range(len(LABEL_ORDER))) for column in range(len(LABEL_ORDER))]
    for index, label in enumerate(LABEL_ORDER):
        values = checked_per_class[label]
        true_positive = matrix[index][index]
        predicted_support = column_supports[index]
        expected_recall = true_positive / 30
        expected_precision = true_positive / predicted_support if predicted_support else 0.0
        expected_f1 = (
            2 * expected_precision * expected_recall / (expected_precision + expected_recall)
            if expected_precision + expected_recall
            else 0.0
        )
        if any(
            not math.isclose(float(values[key]), expected, rel_tol=0.0, abs_tol=1e-9)
            for key, expected in (("precision", expected_precision), ("recall", expected_recall), ("f1", expected_f1))
        ):
            raise ComparisonError(f"{candidate} per-class validation metrics in {run_id} disagree with its confusion matrix.")
    expected_accuracy = sum(matrix[index][index] for index in range(len(LABEL_ORDER))) / 150
    expected_macro_f1 = statistics.fmean(checked_per_class[label]["f1"] for label in LABEL_ORDER)
    if not math.isclose(float(accuracy), expected_accuracy, rel_tol=0.0, abs_tol=1e-9):
        raise ComparisonError(f"{candidate} validation accuracy in {run_id} disagrees with its confusion matrix.")
    if not math.isclose(float(macro_f1), expected_macro_f1, rel_tol=0.0, abs_tol=1e-9):
        raise ComparisonError(f"{candidate} validation Macro-F1 in {run_id} disagrees with its per-class metrics.")
    return {
        "candidate": candidate,
        "seed": seed,
        "run_id": run_id,
        "run_dir": str(run_dir),
        "validation": {
            "accuracy": float(accuracy),
            "macro_f1": float(macro_f1),
            "per_class": checked_per_class,
            "confusion_matrix": matrix,
        },
    }


def _extract_run_metrics(
    run_dir: Path,
    *,
    run_manifest: dict[str, Any],
    registration: dict[str, Any],
    metrics: dict[str, Any],
    seed: int,
) -> list[dict[str, Any]]:
    if "candidates" in metrics:
        outputs = metrics["candidates"]
        if not isinstance(outputs, dict):
            raise ComparisonError(f"baseline metrics candidates must be an object: {run_dir}")
        rows: list[dict[str, Any]] = []
        for raw_name, candidate_output in outputs.items():
            candidate = _normalise_candidate_name(str(raw_name))
            if candidate not in CANDIDATE_NAMES or not isinstance(candidate_output, dict):
                raise ComparisonError(f"unexpected M3.4 baseline candidate {raw_name!r} in {run_dir}")
            report = candidate_output.get("report")
            if not isinstance(report, dict):
                raise ComparisonError(f"baseline {candidate} in {run_dir} is missing its evaluator report.")
            declared_name = report.get("candidate_name")
            if declared_name != raw_name:
                raise ComparisonError(f"baseline candidate name does not match its report in {run_dir}.")
            rows.append(_metric_row(report=report, candidate=candidate, seed=seed, run_id=str(run_manifest.get("run_id")), run_dir=run_dir))
        return rows

    report = metrics
    raw_name = report.get("candidate_name")
    if not isinstance(raw_name, str):
        raise ComparisonError(f"Fly A/B metrics in {run_dir} are missing candidate_name.")
    candidate = _normalise_candidate_name(raw_name)
    if candidate != "fly_a_to_fly_b":
        raise ComparisonError(f"unexpected single-model candidate {raw_name!r} in {run_dir}")
    if raw_name != f"fly_a_to_fly_b_m3_2_seed_{seed}":
        raise ComparisonError(f"Fly A/B candidate name in {run_dir} does not match its registered seed.")
    return [
        _metric_row(
            report=report,
            candidate=candidate,
            seed=seed,
            run_id=str(run_manifest.get("run_id")),
            run_dir=run_dir,
        )
    ]


def aggregate_validation_runs(
    run_dirs: Sequence[Path],
    *,
    required_seeds: Sequence[int],
    candidate_names: Sequence[str] = CANDIDATE_NAMES,
) -> dict[str, Any]:
    """Aggregate only saved train/validation metrics; this function never loads test rows."""

    seeds = tuple(required_seeds)
    candidates = tuple(candidate_names)
    if len(seeds) < 3 or len(set(seeds)) != len(seeds) or any(
        isinstance(seed, bool) or not isinstance(seed, int) or seed < 1 for seed in seeds
    ):
        raise ComparisonError("the preregistered comparison requires at least three unique positive seeds.")
    if not candidates or len(set(candidates)) != len(candidates) or set(candidates) - set(CANDIDATE_NAMES):
        raise ComparisonError("candidate_names must be a unique subset of the fixed candidate registry.")
    if not run_dirs:
        raise ComparisonError("at least one completed run directory is required.")

    records: list[dict[str, Any]] = []
    input_artifacts: list[dict[str, Any]] = []
    dataset_identity: dict[str, str] | None = None
    embedding_identity: dict[str, Any] | None = None
    graph_identity: dict[str, str] | None = None
    candidate_config_hashes: dict[str, str] = {}
    seen: set[tuple[str, int]] = set()
    registered_seeds: set[int] = set()

    for supplied_dir in run_dirs:
        run_dir = Path(supplied_dir).resolve(strict=True)
        run_manifest = _read_json(run_dir / "run_manifest.json", description="run manifest")
        registration = _read_json(run_dir / "pre_registered_candidates.json", description="candidate preregistration")
        metrics_path = run_dir / "metrics.json"
        metrics = _read_json(metrics_path, description="candidate metrics")
        seed = _seed_from_registration(registration)
        if seed not in seeds:
            raise ComparisonError(f"run {run_dir.name} has undeclared training seed {seed}.")
        registered_seeds.add(seed)
        data_status = run_manifest.get("data_status")
        review_status = run_manifest.get("review_status")
        if isinstance(run_manifest.get("dataset_audit"), dict):
            data_status = data_status or run_manifest["dataset_audit"].get("data_status")
            review_status = review_status or run_manifest["dataset_audit"].get("review_status")
        if data_status != "synthetic" or review_status != "pending_manual_review":
            raise ComparisonError(f"run {run_dir.name} has incompatible dataset or review status.")
        status = run_manifest.get("status")
        result_status = run_manifest.get("result_status")
        if (
            status not in (None, "completed_provisional")
            or result_status not in (None, "provisional")
            or (status is None and result_status is None)
        ):
            raise ComparisonError(f"run {run_dir.name} is not a completed provisional run.")
        if not isinstance(run_manifest.get("run_id"), str) or not run_manifest["run_id"]:
            raise ComparisonError(f"run {run_dir.name} has no stable run_id.")
        registration_fingerprint = registration.get("configuration_fingerprint")
        if (
            not isinstance(registration_fingerprint, str)
            or registration_fingerprint != _fingerprint_registration(registration)
            or registration_fingerprint
            not in {
                run_manifest.get("configuration_fingerprint"),
                run_manifest.get("candidate_settings_fingerprint"),
            }
        ):
            raise ComparisonError(f"run {run_dir.name} preregistration fingerprint is invalid or differs from its manifest.")
        _check_test_not_run(run_manifest, description=f"run manifest {run_dir.name}")
        _check_test_not_run(metrics, description=f"metrics {run_dir.name}")
        if (
            metrics.get("evaluation_status") != "smoke_test/provisional"
            or metrics.get("data_status") != "synthetic"
            or metrics.get("review_status") != "pending_manual_review"
            or metrics.get("label_order") != list(LABEL_ORDER)
        ):
            raise ComparisonError(f"run {run_dir.name} metrics are not compatible provisional outputs.")

        sources = _dataset_sources(run_manifest)
        if dataset_identity is None:
            dataset_identity = sources
        elif sources != dataset_identity:
            raise ComparisonError("comparison runs use different frozen dataset source checksums.")
        e5 = _e5_identity(registration)
        if embedding_identity is None:
            embedding_identity = e5
        elif e5 != embedding_identity:
            raise ComparisonError("comparison runs use different E5 model or embedding settings.")

        run_graph = run_manifest.get("source_sha256")
        is_fly_run = "candidates" not in metrics
        if is_fly_run and (not isinstance(run_graph, dict) or not all(key in run_graph for key in GRAPH_SOURCE_KEYS)):
            raise ComparisonError(f"Fly A/B run {run_dir.name} is missing pinned graph source checksums.")
        if is_fly_run:
            assert isinstance(run_graph, dict)
            graph_values = {key: run_graph[key] for key in GRAPH_SOURCE_KEYS}
            if graph_identity is None:
                graph_identity = graph_values
            elif graph_values != graph_identity:
                raise ComparisonError("Fly A/B runs do not share the same pinned graph and I/O artifacts.")
            graph_registration = registration.get("graph")
            if not isinstance(graph_registration, dict) or (
                graph_registration.get("pinned_m12_manifest_sha256") != run_graph.get("graph_manifest")
                or graph_registration.get("pinned_m13_io_manifest_sha256") != run_graph.get("io_manifest")
            ):
                raise ComparisonError(f"Fly A/B run {run_dir.name} does not match its preregistered graph manifests.")

        metrics_sha256 = _verify_metrics_checksum(run_dir, run_manifest, metrics_path)
        registration_hash = _sha256_file(run_dir / "pre_registered_candidates.json")
        manifest_hash = _sha256_file(run_dir / "run_manifest.json")
        input_artifacts.append(
            {
                "run_id": run_manifest.get("run_id"),
                "run_dir": str(run_dir),
                "seed": seed,
                "run_manifest_sha256": manifest_hash,
                "registration_sha256": registration_hash,
                "metrics_sha256": metrics_sha256,
            }
        )

        run_rows = _extract_run_metrics(
            run_dir,
            run_manifest=run_manifest,
            registration=registration,
            metrics=metrics,
            seed=seed,
        )
        if not run_rows:
            raise ComparisonError(f"run {run_dir.name} contains no M3.4 candidates.")
        for row in run_rows:
            candidate = row["candidate"]
            key = (candidate, seed)
            if candidate not in candidates:
                raise ComparisonError(f"candidate {candidate} was not included in the predeclared candidate list.")
            if key in seen:
                raise ComparisonError(f"candidate {candidate} has more than one run for seed {seed}.")
            seen.add(key)
            config = _candidate_configuration(registration, candidate)
            fingerprint = hashlib.sha256(_canonical_bytes(_without_seed_fields(config))).hexdigest()
            previous = candidate_config_hashes.setdefault(candidate, fingerprint)
            if previous != fingerprint:
                raise ComparisonError(f"candidate {candidate} settings changed across the preregistered seeds.")
            records.append(row)

    if registered_seeds != set(seeds):
        missing = sorted(set(seeds) - registered_seeds)
        raise ComparisonError(f"comparison is missing preregistered seed runs: {missing}.")
    missing_cells = [
        (candidate, seed)
        for candidate in candidates
        for seed in seeds
        if (candidate, seed) not in seen
    ]
    if missing_cells:
        raise ComparisonError(f"comparison does not contain every candidate for every seed: {missing_cells}.")
    extra_candidates = {candidate for candidate, _seed in seen} - set(candidates)
    if extra_candidates:
        raise ComparisonError(f"comparison contains undeclared candidates: {sorted(extra_candidates)}.")

    summaries: dict[str, Any] = {}
    for candidate in candidates:
        candidate_rows = sorted(
            (row for row in records if row["candidate"] == candidate),
            key=lambda row: row["seed"],
        )
        macro_f1_values = [row["validation"]["macro_f1"] for row in candidate_rows]
        accuracy_values = [row["validation"]["accuracy"] for row in candidate_rows]
        class_summary: dict[str, Any] = {}
        confusion_sum = [[0 for _ in LABEL_ORDER] for _ in LABEL_ORDER]
        for index, label in enumerate(LABEL_ORDER):
            class_summary[label] = {}
            for metric_name in ("precision", "recall", "f1"):
                values = [row["validation"]["per_class"][label][metric_name] for row in candidate_rows]
                class_summary[label][metric_name] = {
                    "mean": statistics.fmean(values),
                    "sample_std": statistics.stdev(values),
                }
            class_summary[label]["support_per_seed"] = [row["validation"]["per_class"][label]["support"] for row in candidate_rows]
            for row in candidate_rows:
                for column, value in enumerate(row["validation"]["confusion_matrix"][index]):
                    confusion_sum[index][column] += value
        summaries[candidate] = {
            "seed_count": len(seeds),
            "seeds": list(seeds),
            "validation_macro_f1": {
                "mean": statistics.fmean(macro_f1_values),
                "sample_std": statistics.stdev(macro_f1_values),
                "by_seed": {str(row["seed"]): row["validation"]["macro_f1"] for row in candidate_rows},
            },
            "validation_accuracy": {
                "mean": statistics.fmean(accuracy_values),
                "sample_std": statistics.stdev(accuracy_values),
                "by_seed": {str(row["seed"]): row["validation"]["accuracy"] for row in candidate_rows},
            },
            "per_class": class_summary,
            "aggregate_confusion_matrix": confusion_sum,
            "run_ids": [row["run_id"] for row in candidate_rows],
        }

    winner = min(
        candidates,
        key=lambda candidate: (
            -summaries[candidate]["validation_macro_f1"]["mean"],
            -summaries[candidate]["validation_accuracy"]["mean"],
            candidate,
        ),
    )
    return {
        "schema_version": 1,
        "status": "validation_complete_pending_manual_review",
        "candidate_names": list(candidates),
        "seeds": list(seeds),
        "label_order": list(LABEL_ORDER),
        "data_status": "synthetic",
        "review_status": "pending_manual_review",
        "candidates": summaries,
        "validation_winner": winner,
        "selection_rule": SELECTION_RULE,
        "input_artifacts": input_artifacts,
        "dataset_source_sha256": dataset_identity,
        "e5_identity": embedding_identity,
        "graph_source_sha256": graph_identity,
        "test": {"status": "not_run", "input_count": 0, "prediction_count": 0, "metrics": None},
        "formal_test_eligible": False,
    }

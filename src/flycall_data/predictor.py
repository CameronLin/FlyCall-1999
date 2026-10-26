"""Checksum-checked, train-time-model inference for the local research demo."""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from .e5_runtime import E5_MODEL_FILE_SHA256, load_e5_encoder
from .evaluation import LABEL_ORDER
from .fly_ab_training import GraphDefinition, load_fly_a_checkpoint, load_fly_b_checkpoint
from .model_config import E5_SMALL_CONFIG


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class PredictorError(ValueError):
    """Raised when a locked model bundle or inference input is incompatible."""


@dataclass(frozen=True)
class DemoPrediction:
    candidate_name: str
    predicted_label: str
    logits: tuple[float, ...]
    probabilities: tuple[float, ...]
    label_order: tuple[str, ...]
    stages: tuple[str, ...]
    data_status: str = "synthetic"
    review_status: str = "pending_manual_review"
    dispatch_status: str = "simulated_only"
    human_confirmation_required: bool = True

    def as_dict(self) -> dict[str, Any]:
        return {
            "candidate_name": self.candidate_name,
            "predicted_label": self.predicted_label,
            "logits": {label: score for label, score in zip(self.label_order, self.logits, strict=True)},
            "probabilities": {
                label: score for label, score in zip(self.label_order, self.probabilities, strict=True)
            },
            "label_order": list(self.label_order),
            "stages": list(self.stages),
            "data_status": self.data_status,
            "review_status": self.review_status,
            "dispatch_status": self.dispatch_status,
            "human_confirmation_required": self.human_confirmation_required,
        }


def _read_json(path: Path, *, description: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise PredictorError(f"{description} is unreadable or invalid: {path}") from error
    if not isinstance(value, dict):
        raise PredictorError(f"{description} must contain a JSON object: {path}")
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha256_json(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _resolve_project_artifact(root: Path, relative_path: Any, *, description: str) -> Path:
    if not isinstance(relative_path, str) or not relative_path or Path(relative_path).is_absolute():
        raise PredictorError(f"{description} must be a non-empty project-relative path.")
    resolved = (root / relative_path).resolve(strict=True)
    project_root = Path(PROJECT_ROOT).resolve()
    try:
        resolved.relative_to(project_root)
    except ValueError as error:
        raise PredictorError(f"{description} resolves outside the project workspace.") from error
    if not resolved.is_file():
        raise PredictorError(f"{description} must resolve to a file.")
    return resolved


def _verify_output_record(run_manifest: dict[str, Any], artifact_path: Path) -> None:
    outputs = run_manifest.get("outputs")
    if not isinstance(outputs, dict):
        raise PredictorError("model run manifest has no output checksums.")
    matching = [record for name, record in outputs.items() if Path(str(name)).name == artifact_path.name]
    if len(matching) != 1 or not isinstance(matching[0], dict):
        raise PredictorError(f"model run manifest must contain one checksum for {artifact_path.name}.")
    if matching[0].get("sha256") != _sha256_file(artifact_path):
        raise PredictorError(f"model artifact checksum does not match the run manifest: {artifact_path.name}.")
    if matching[0].get("bytes") != artifact_path.stat().st_size:
        raise PredictorError(f"model artifact byte count does not match the run manifest: {artifact_path.name}.")


def _checked_logits(values: Sequence[float]) -> tuple[float, ...]:
    logits = tuple(float(value) for value in values)
    if len(logits) != len(LABEL_ORDER) or any(not math.isfinite(value) for value in logits):
        raise PredictorError("model output must contain five finite logits in the fixed taxonomy order.")
    return logits


def _softmax(logits: Sequence[float]) -> tuple[float, ...]:
    maximum = max(logits)
    exponentials = [math.exp(value - maximum) for value in logits]
    total = sum(exponentials)
    if not math.isfinite(total) or total <= 0:
        raise PredictorError("model output cannot be converted to finite class probabilities.")
    return tuple(value / total for value in exponentials)


class FlyCallPredictor:
    """One E5 plus locked baseline or Fly A→B model behind a common API."""

    def __init__(self, *, candidate_name: str, backend: str, encoder: Any, model: Any, stages: tuple[str, ...]) -> None:
        self.candidate_name = candidate_name
        self.backend = backend
        self.encoder = encoder
        self.model = model
        self.stages = stages

    @classmethod
    def from_locked_manifest(
        cls,
        manifest_path: Path,
        *,
        e5_snapshot: Path,
        encoder: Any | None = None,
    ) -> FlyCallPredictor:
        manifest_file = Path(manifest_path).resolve(strict=True)
        root = manifest_file.parent
        try:
            manifest_file.relative_to(Path(PROJECT_ROOT).resolve())
        except ValueError as error:
            raise PredictorError("model manifest must stay inside the project workspace.") from error
        approval = _read_json(manifest_file, description="locked model manifest")
        if (
            approval.get("schema_version") != 1
            or approval.get("status") != "model_locked_for_demo"
            or approval.get("candidate_list_locked") is not True
            or approval.get("configuration_locked") is not True
            or not isinstance(approval.get("approval_reference"), str)
            or not approval["approval_reference"].strip()
            or approval.get("data_status") != "synthetic"
            or approval.get("review_status") != "pending_manual_review"
        ):
            raise PredictorError(
                "demo requires a locked model manifest; it must disclose synthetic data and pending manual review."
            )
        if approval.get("label_order") != list(LABEL_ORDER):
            raise PredictorError("locked model label order differs from the fixed taxonomy order.")
        embedding = approval.get("embedding")
        expected_e5_files = [list(item) for item in E5_MODEL_FILE_SHA256]
        if (
            not isinstance(embedding, dict)
            or embedding.get("model_id") != E5_SMALL_CONFIG.model_id
            or embedding.get("revision") != E5_SMALL_CONFIG.revision
            or embedding.get("model_file_sha256") != expected_e5_files
        ):
            raise PredictorError("locked model manifest does not match the pinned E5 model files and revision.")

        model_spec = approval.get("model")
        if not isinstance(model_spec, dict) or not isinstance(model_spec.get("kind"), str):
            raise PredictorError("locked model manifest is missing the selected model artifact.")
        run_manifest_path = _resolve_project_artifact(
            root, model_spec.get("run_manifest_path"), description="model run manifest path"
        )
        if _sha256_file(run_manifest_path) != model_spec.get("run_manifest_sha256"):
            raise PredictorError("model run manifest checksum differs from the locked model manifest.")
        run_manifest = _read_json(run_manifest_path, description="model run manifest")
        dataset_audit = run_manifest.get("dataset_audit")
        data_status = run_manifest.get("data_status") or (
            dataset_audit.get("data_status") if isinstance(dataset_audit, dict) else None
        )
        review_status = run_manifest.get("review_status") or (
            dataset_audit.get("review_status") if isinstance(dataset_audit, dict) else None
        )
        if data_status != "synthetic" or review_status != "pending_manual_review":
            raise PredictorError("selected model run is not marked synthetic with manual review pending.")
        result_status = run_manifest.get("result_status")
        completed_status = run_manifest.get("status")
        if result_status != "provisional" and completed_status != "completed_provisional":
            raise PredictorError("selected model run is not a completed provisional artifact.")
        if result_status == "provisional" and run_manifest.get("checkpoint_reload_verified") is not True:
            raise PredictorError("selected baseline run has not verified its checkpoint reloads.")
        if completed_status == "completed_provisional":
            summary = run_manifest.get("summary")
            reload_record = summary.get("checkpoint_reload") if isinstance(summary, dict) else None
            reload_status = reload_record.get("status") if isinstance(reload_record, dict) else None
            if reload_status != "passed":
                raise PredictorError("selected Fly A/B run has not verified its checkpoint reloads.")
        config_fingerprint = run_manifest.get("candidate_settings_fingerprint") or run_manifest.get("configuration_fingerprint")
        if config_fingerprint != model_spec.get("configuration_fingerprint"):
            raise PredictorError("locked model configuration fingerprint differs from its run manifest.")
        registration_path = run_manifest_path.parent / "pre_registered_candidates.json"
        _verify_output_record(run_manifest, registration_path)
        registration = _read_json(registration_path, description="candidate preregistration")
        unsigned_registration = {
            key: value for key, value in registration.items() if key != "configuration_fingerprint"
        }
        if (
            registration.get("configuration_fingerprint") != config_fingerprint
            or _sha256_json(unsigned_registration) != config_fingerprint
        ):
            raise PredictorError("candidate preregistration fingerprint differs from its run manifest.")
        test = run_manifest.get("test")
        if not isinstance(test, dict) or test.get("status") != "not_run":
            raise PredictorError("selected model run must retain test status not_run.")

        artifact_kind = model_spec.get("kind")
        if artifact_kind == "e5_baseline":
            checkpoint_path = _resolve_project_artifact(
                root, model_spec.get("checkpoint_path"), description="baseline checkpoint path"
            )
            if _sha256_file(checkpoint_path) != model_spec.get("checkpoint_sha256"):
                raise PredictorError("baseline checkpoint checksum differs from the locked model manifest.")
            _verify_output_record(run_manifest, checkpoint_path)
            import joblib

            try:
                checkpoint = joblib.load(checkpoint_path)
            except Exception as error:
                raise PredictorError(f"baseline checkpoint could not be loaded: {error}") from error
            candidate_name = approval.get("candidate_name")
            if not isinstance(checkpoint, dict) or not isinstance(candidate_name, str):
                raise PredictorError("baseline checkpoint or selected candidate has an invalid structure.")
            if (
                checkpoint.get("schema_version") != 1
                or checkpoint.get("artifact_type") != "flycall_e5_baseline"
                or checkpoint.get("candidate") != candidate_name
                or checkpoint.get("label_order") != list(LABEL_ORDER)
                or checkpoint.get("embedding_dimension") != E5_SMALL_CONFIG.output_dimension
                or checkpoint.get("embedding_model") != E5_SMALL_CONFIG.model_id
                or checkpoint.get("embedding_revision") != E5_SMALL_CONFIG.revision
                or checkpoint.get("embedding_model_files_sha256") != expected_e5_files
                or checkpoint.get("configuration_fingerprint") != config_fingerprint
            ):
                raise PredictorError("baseline checkpoint metadata is incompatible with the locked selection.")
            source_sha256 = run_manifest.get("source_sha256_after")
            if (
                not isinstance(source_sha256, dict)
                or run_manifest.get("source_sha256_before") != source_sha256
                or checkpoint.get("source_sha256") != source_sha256
            ):
                raise PredictorError("baseline checkpoint and run manifest do not share frozen source hashes.")
            if checkpoint.get("seed") != model_spec.get("seed"):
                raise PredictorError("baseline checkpoint seed differs from the locked model manifest.")
            registered_candidates = registration.get("candidates")
            registered_config = registered_candidates.get(candidate_name) if isinstance(registered_candidates, dict) else None
            if (
                not isinstance(registered_config, dict)
                or not isinstance(checkpoint.get("configuration"), dict)
            ):
                raise PredictorError("selected baseline is missing its registered configuration.")
            config = checkpoint["configuration"]
            compared_keys = {
                "logistic_regression": ("C", "max_iter", "solver", "random_state"),
                "mlp": ("hidden_size", "epochs", "learning_rate", "seed"),
                "pca_mlp": ("pca_components", "hidden_size", "epochs", "learning_rate", "seed"),
                "lda_logistic_regression": (
                    "lda_solver",
                    "lda_components",
                    "classifier_C",
                    "classifier_max_iter",
                    "classifier_solver",
                    "seed",
                ),
            }
            if candidate_name not in compared_keys or any(
                config.get(key) != registered_config.get(key) for key in compared_keys[candidate_name]
            ):
                raise PredictorError("selected baseline settings differ from the preregistered configuration.")
            model_object = checkpoint.get("model")
            preprocessor = checkpoint.get("preprocessor")
            if candidate_name == "logistic_regression":
                classes = getattr(model_object, "classes_", ())
                if (
                    getattr(model_object, "n_features_in_", None) != E5_SMALL_CONFIG.output_dimension
                    or len(classes) == 0
                    or set(str(label) for label in classes) != set(LABEL_ORDER)
                    or getattr(model_object, "C", None) is None
                    or float(model_object.C) != float(registered_config.get("C"))
                ):
                    raise PredictorError("Logistic Regression checkpoint has incompatible d, C, or label settings.")
            elif candidate_name in {"mlp", "pca_mlp"}:
                expected_input = E5_SMALL_CONFIG.output_dimension
                if candidate_name == "pca_mlp":
                    components = registered_config.get("pca_components")
                    if (
                        preprocessor is None
                        or len(getattr(preprocessor, "mean", ())) != E5_SMALL_CONFIG.output_dimension
                        or len(getattr(preprocessor, "components", ())) != components
                        or any(
                            len(row) != E5_SMALL_CONFIG.output_dimension
                            for row in getattr(preprocessor, "components", ())
                        )
                    ):
                        raise PredictorError("PCA checkpoint does not match its registered d/k dimensions.")
                    expected_input = components
                try:
                    model_layers = tuple(model_object)
                except TypeError:
                    model_layers = ()
                if (
                    not model_layers
                    or getattr(model_layers[0], "in_features", None) != expected_input
                    or getattr(model_layers[-1], "out_features", None) != len(LABEL_ORDER)
                ):
                    raise PredictorError("MLP checkpoint input/output dimensions do not match its configuration.")
            elif candidate_name == "lda_logistic_regression":
                lda = checkpoint.get("lda")
                classifier = checkpoint.get("classifier")
                expected_components = registered_config.get("lda_components")
                classes = getattr(classifier, "classes_", ())
                if (
                    getattr(lda, "n_features_in_", None) != E5_SMALL_CONFIG.output_dimension
                    or getattr(classifier, "n_features_in_", None) != expected_components
                    or getattr(classifier, "C", None) is None
                    or float(classifier.C) != float(registered_config.get("classifier_C"))
                    or len(classes) == 0
                    or set(str(label) for label in classes) != set(LABEL_ORDER)
                ):
                    raise PredictorError("LDA checkpoint does not match its registered d/k/C/class contract.")
            backend_model = {"checkpoint": checkpoint}
            stages = ("Pinned E5 384-dimensional embedding", f"{candidate_name} classifier")
        elif artifact_kind == "fly_a_to_fly_b":
            candidate_name = approval.get("candidate_name")
            if candidate_name != "fly_a_to_fly_b":
                raise PredictorError("Fly A/B model selection must use the registered candidate name.")
            source_sha256 = run_manifest.get("source_sha256")
            if not isinstance(source_sha256, dict):
                raise PredictorError("Fly A/B run manifest is missing source hashes.")
            registered_training = registration.get("training")
            if (
                not isinstance(registered_training, dict)
                or registered_training.get("seed") != model_spec.get("seed")
                or registered_training.get("candidate_name") != f"fly_a_to_fly_b_m3_2_seed_{model_spec.get('seed')}"
            ):
                raise PredictorError("Fly A/B seed or candidate differs from its preregistered configuration.")
            expected_e5_files_hash = _sha256_json(expected_e5_files)
            if source_sha256.get("e5_model_files") != expected_e5_files_hash:
                raise PredictorError("Fly A/B run used E5 model files different from the locked E5 identity.")
            graph_path = _resolve_project_artifact(
                root, model_spec.get("graph_definition_path"), description="graph definition path"
            )
            if _sha256_file(graph_path) != model_spec.get("graph_definition_sha256"):
                raise PredictorError("graph definition checksum differs from the locked model manifest.")
            _verify_output_record(run_manifest, graph_path)
            graph_data = _read_json(graph_path, description="saved graph definition")
            if graph_data.get("source_sha256") != source_sha256:
                raise PredictorError("saved graph definition has different source hashes from its run manifest.")
            try:
                graph = GraphDefinition(
                    node_ids=tuple(graph_data["node_ids"]),
                    input_node_ids=tuple(graph_data["input_node_ids"]),
                    output_node_ids=tuple(graph_data["output_node_ids"]),
                    edges=tuple(tuple(edge) for edge in graph_data["edges"]),
                    steps=graph_data["steps"],
                )
            except (KeyError, TypeError, ValueError) as error:
                raise PredictorError(f"saved graph definition is invalid: {error}") from error
            fly_a_path = _resolve_project_artifact(
                root, model_spec.get("fly_a_checkpoint_path"), description="Fly A checkpoint path"
            )
            fly_b_path = _resolve_project_artifact(
                root, model_spec.get("fly_b_checkpoint_path"), description="Fly B checkpoint path"
            )
            if _sha256_file(fly_a_path) != model_spec.get("fly_a_checkpoint_sha256"):
                raise PredictorError("Fly A checkpoint checksum differs from the locked model manifest.")
            if _sha256_file(fly_b_path) != model_spec.get("fly_b_checkpoint_sha256"):
                raise PredictorError("Fly B checkpoint checksum differs from the locked model manifest.")
            _verify_output_record(run_manifest, fly_a_path)
            _verify_output_record(run_manifest, fly_b_path)
            expected_b_sources = dict(source_sha256)
            expected_b_sources["fly_a_checkpoint"] = model_spec["fly_a_checkpoint_sha256"]
            try:
                fly_a = load_fly_a_checkpoint(
                    graph,
                    E5_SMALL_CONFIG.output_dimension,
                    fly_a_path,
                    expected_source_sha256=source_sha256,
                )
                fly_b = load_fly_b_checkpoint(
                    graph,
                    fly_b_path,
                    expected_source_sha256=expected_b_sources,
                )
            except (ValueError, RuntimeError) as error:
                raise PredictorError(f"Fly A/B checkpoint contract failed: {error}") from error
            backend_model = {"fly_a": fly_a, "fly_b": fly_b}
            stages = ("Pinned E5 384-dimensional embedding", "Fly A 384→32", "Fly B 32→5 logits")
        else:
            raise PredictorError(f"unsupported locked model kind: {artifact_kind!r}.")

        loaded_encoder = encoder if encoder is not None else load_e5_encoder(e5_snapshot)
        model = {"kind": artifact_kind, **backend_model}
        return cls(
            candidate_name=str(candidate_name),
            backend=artifact_kind,
            encoder=loaded_encoder,
            model=model,
            stages=stages,
        )

    def predict(self, transcript: str) -> DemoPrediction:
        if not isinstance(transcript, str) or not transcript.strip():
            raise PredictorError("enter a non-empty transcript before predicting.")
        try:
            transcript.encode("utf-8", errors="strict")
        except UnicodeEncodeError as error:
            raise PredictorError("transcript must be valid UTF-8 text.") from error
        prefixed = E5_SMALL_CONFIG.prefix + transcript
        vectors = self.encoder.encode([prefixed])
        if len(vectors) != 1 or len(vectors[0]) != E5_SMALL_CONFIG.output_dimension:
            raise PredictorError("E5 did not return exactly one 384-dimensional embedding.")
        embedding = tuple(float(value) for value in vectors[0])
        if any(not math.isfinite(value) for value in embedding):
            raise PredictorError("E5 returned a non-finite embedding.")
        norm = math.sqrt(sum(value * value for value in embedding))
        if not math.isclose(norm, 1.0, rel_tol=1e-4, abs_tol=1e-4):
            raise PredictorError("E5 returned a vector that is not L2-normalized.")
        logits = self._predict_embedding(embedding)
        probabilities = _softmax(logits)
        predicted_index = max(range(len(LABEL_ORDER)), key=probabilities.__getitem__)
        return DemoPrediction(
            candidate_name=self.candidate_name,
            predicted_label=LABEL_ORDER[predicted_index],
            logits=logits,
            probabilities=probabilities,
            label_order=LABEL_ORDER,
            stages=self.stages,
        )

    def _predict_embedding(self, embedding: Sequence[float]) -> tuple[float, ...]:
        if self.backend == "e5_baseline":
            import numpy as np

            checkpoint = self.model["checkpoint"]
            model = checkpoint["model"] if "model" in checkpoint else checkpoint["classifier"]
            features: Any = (tuple(embedding),)
            candidate_name = checkpoint["candidate"]
            if candidate_name == "logistic_regression":
                raw = np.asarray(model.decision_function(np.asarray(features, dtype=np.float64)), dtype=np.float64)
                class_index = {str(label): index for index, label in enumerate(model.classes_)}
                return _checked_logits(raw[0, [class_index[label] for label in LABEL_ORDER]])
            if candidate_name == "lda_logistic_regression":
                reduced = checkpoint["lda"].transform(np.asarray(features, dtype=np.float64))
                raw = np.asarray(checkpoint["classifier"].decision_function(reduced), dtype=np.float64)
                classifier = checkpoint["classifier"]
                class_index = {str(label): index for index, label in enumerate(classifier.classes_)}
                return _checked_logits(raw[0, [class_index[label] for label in LABEL_ORDER]])
            if candidate_name == "pca_mlp":
                features = checkpoint["preprocessor"].transform(features)
            import torch

            with torch.no_grad():
                raw = model(torch.tensor(features, dtype=torch.float32, device="cpu")).cpu().numpy()
            return _checked_logits(raw[0])
        if self.backend == "fly_a_to_fly_b":
            import torch

            values = torch.tensor((tuple(embedding),), dtype=torch.float32, device="cpu")
            with torch.no_grad():
                logits = self.model["fly_b"](self.model["fly_a"](values))[0].tolist()
            return _checked_logits(logits)
        raise PredictorError(f"unsupported predictor backend {self.backend!r}.")

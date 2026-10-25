"""Fixture-friendly frozen-embedding and train/validation baseline seams.

The module deliberately keeps encoder injection and feature batches independent
of optional ML backends. No encoder, model weights, dataset loader, or split
reader is created here.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Protocol, Sequence

from .evaluation import classification_metrics


class Encoder(Protocol):
    """Small adapter interface implemented by a real or fixture encoder."""

    def encode(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        """Return one numeric vector per supplied, already-prefixed text."""


@dataclass(frozen=True)
class EmbeddingSettings:
    """All settings that affect one cached embedding value."""

    model_id: str
    revision: str
    tokenizer_revision: str
    prefix: str
    preprocessing_version: str
    max_seq_length: int
    truncation_policy: str
    pooling: str
    normalize_embeddings: bool
    dtype: str
    output_dimension: int
    device: str
    batch_size: int

    def __post_init__(self) -> None:
        for name in (
            "model_id", "revision", "tokenizer_revision", "preprocessing_version",
            "truncation_policy", "pooling", "device",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be a non-empty string.")
        if not isinstance(self.prefix, str):
            raise ValueError("prefix must be a string.")
        if not isinstance(self.max_seq_length, int) or self.max_seq_length < 1:
            raise ValueError("max_seq_length must be a positive integer.")
        if not isinstance(self.normalize_embeddings, bool):
            raise ValueError("normalize_embeddings must be a boolean.")
        if self.dtype not in {"float32", "float64"}:
            raise ValueError("dtype must be 'float32' or 'float64'.")
        if not isinstance(self.output_dimension, int) or self.output_dimension < 1:
            raise ValueError("output_dimension must be a positive integer.")
        if not isinstance(self.batch_size, int) or self.batch_size < 1:
            raise ValueError("batch_size must be a positive integer.")


class EmbeddingCache:
    """Small content-addressed JSON cache; callers choose an isolated path."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    @staticmethod
    def key_for(text: str, settings: EmbeddingSettings) -> str:
        try:
            text_bytes = text.encode("utf-8", errors="strict")
        except UnicodeEncodeError as error:
            raise ValueError("transcript text is not valid strict UTF-8.") from error
        payload = {
            "text_sha256": hashlib.sha256(text_bytes).hexdigest(),
            **asdict(settings),
        }
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    def get(self, key: str) -> tuple[float, ...] | None:
        path = self.root / f"{key}.json"
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError(f"invalid embedding cache entry: {path.name}") from error
        if payload.get("key") != key or not isinstance(payload.get("vector"), list):
            raise ValueError(f"embedding cache entry metadata mismatch: {path.name}")
        return tuple(_finite_float(value, context="cached embedding") for value in payload["vector"])

    def put(self, key: str, vector: Sequence[float]) -> None:
        values = [_finite_float(value, context="embedding") for value in vector]
        self.root.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            {"key": key, "vector": values},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        temporary_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.root, prefix=f".{key}.", delete=False
            ) as stream:
                temporary_path = stream.name
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_path, self.root / f"{key}.json")
        finally:
            if temporary_path and os.path.exists(temporary_path):
                os.unlink(temporary_path)


@dataclass(frozen=True)
class SplitTexts:
    """Raw transcript inputs from one permitted model split."""

    split: str
    record_ids: tuple[str, ...]
    family_ids: tuple[str, ...]
    texts: tuple[str, ...]
    labels: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.split not in {"train", "validation"}:
            raise ValueError("model input split must be train or validation.")
        count = len(self.record_ids)
        if count == 0 or len(self.family_ids) != count or len(self.texts) != count or len(self.labels) != count:
            raise ValueError("record ids, family ids, texts, and labels must have the same non-zero length.")
        if any(not isinstance(value, str) or not value for value in self.record_ids):
            raise ValueError("record_ids must be non-empty strings.")
        if len(set(self.record_ids)) != count:
            raise ValueError("record ids must be unique within a split.")
        if any(not isinstance(value, str) or not value for value in self.family_ids):
            raise ValueError("family_ids must be non-empty strings.")
        if any(not isinstance(value, str) or not value for value in self.labels):
            raise ValueError("labels must be non-empty strings.")
        for text in self.texts:
            if not isinstance(text, str):
                raise ValueError("transcript text must be a string.")
            try:
                text.encode("utf-8", errors="strict")
            except UnicodeEncodeError as error:
                raise ValueError("transcript text is not valid strict UTF-8.") from error


def embed_texts(
    records: SplitTexts,
    encoder: Encoder,
    settings: EmbeddingSettings,
    cache: EmbeddingCache,
) -> SplitEmbeddings:
    """Encode only permitted train/validation transcripts and retain provenance."""

    if not isinstance(records, SplitTexts):
        raise TypeError("embed_texts requires a SplitTexts batch with an explicit allowed split.")
    texts = records.texts
    keys: list[str] = []
    result_by_key: dict[str, tuple[float, ...]] = {}
    missing_text_by_key: dict[str, str] = {}
    for text in texts:
        if not isinstance(text, str):
            raise ValueError("transcript text must be a string.")
        key = cache.key_for(text, settings)
        keys.append(key)
        if key in result_by_key or key in missing_text_by_key:
            continue
        cached = cache.get(key)
        if cached is not None:
            result_by_key[key] = _validate_vector(cached, settings)
        else:
            missing_text_by_key[key] = text

    if missing_text_by_key:
        ordered_keys = list(missing_text_by_key)
        prefixed_texts = [settings.prefix + missing_text_by_key[key] for key in ordered_keys]
        try:
            encoded = encoder.encode(prefixed_texts)
        except Exception as error:
            raise ValueError("encoder failed to produce embeddings.") from error
        if len(encoded) != len(ordered_keys):
            raise ValueError(
                f"encoder returned {len(encoded)} vectors for {len(ordered_keys)} texts."
            )
        for key, raw_vector in zip(ordered_keys, encoded, strict=True):
            vector = _validate_vector(raw_vector, settings)
            result_by_key[key] = vector
            cache.put(key, vector)

    return SplitEmbeddings(
        split=records.split,
        record_ids=records.record_ids,
        family_ids=records.family_ids,
        features=tuple(result_by_key[key] for key in keys),
        labels=records.labels,
    )


@dataclass(frozen=True)
class SplitEmbeddings:
    """Validated feature rows from exactly one permitted model split."""

    split: str
    record_ids: tuple[str, ...]
    family_ids: tuple[str, ...]
    features: tuple[tuple[float, ...], ...]
    labels: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.split not in {"train", "validation"}:
            raise ValueError("model input split must be train or validation.")
        count = len(self.record_ids)
        if count == 0 or len(self.family_ids) != count or len(self.features) != count or len(self.labels) != count:
            raise ValueError("record ids, family ids, features, and labels must have the same non-zero length.")
        if any(not isinstance(value, str) or not value for value in self.record_ids):
            raise ValueError("record_ids must be non-empty strings.")
        if len(set(self.record_ids)) != count:
            raise ValueError("record ids must be unique within a split.")
        if any(not isinstance(value, str) or not value for value in self.family_ids):
            raise ValueError("family_ids must be non-empty strings.")
        if any(not isinstance(value, str) or not value for value in self.labels):
            raise ValueError("labels must be non-empty strings.")
        dimensions = {len(vector) for vector in self.features}
        if len(dimensions) != 1 or 0 in dimensions:
            raise ValueError("feature vectors must have one consistent non-zero dimension.")
        for vector in self.features:
            for value in vector:
                _finite_float(value, context="feature")


@dataclass(frozen=True)
class BaselineResult:
    """Predictions, fixed-order metrics, and the fitted fixture/model objects."""

    candidate: str
    label_order: tuple[str, ...]
    seed: int
    fit_record_ids: tuple[str, ...]
    train_record_ids: tuple[str, ...]
    validation_record_ids: tuple[str, ...]
    train_predictions: tuple[str, ...]
    validation_predictions: tuple[str, ...]
    train_metrics: dict[str, Any]
    validation_metrics: dict[str, Any]
    parameters: dict[str, Any]
    transform_fit_record_ids: tuple[str, ...]
    transform_state: dict[str, Any] | None
    model: Any = field(repr=False, compare=False)
    preprocessor: Any = field(default=None, repr=False, compare=False)


@dataclass(frozen=True)
class PCAState:
    """Train-fitted PCA basis that can only transform subsequent feature rows."""

    mean: tuple[float, ...]
    components: tuple[tuple[float, ...], ...]
    fit_record_ids: tuple[str, ...]

    def transform(self, features: Sequence[Sequence[float]]) -> tuple[tuple[float, ...], ...]:
        torch = _require_torch()
        if not features:
            raise ValueError("PCA transform requires non-empty features.")
        input_dimension = len(self.mean)
        if any(len(vector) != input_dimension for vector in features):
            raise ValueError("PCA transform feature dimension differs from fitted dimension.")
        matrix = torch.tensor(features, dtype=torch.float64, device="cpu")
        mean = torch.tensor(self.mean, dtype=torch.float64, device="cpu")
        components = torch.tensor(self.components, dtype=torch.float64, device="cpu")
        projected = (matrix - mean) @ components.T
        return tuple(tuple(float(value) for value in row) for row in projected.tolist())


def run_baseline(
    candidate: str,
    train: SplitEmbeddings,
    validation: SplitEmbeddings,
    *,
    label_order: Sequence[str],
    seed: int,
    pca_components: int | None = None,
    epochs: int = 80,
    hidden_size: int = 16,
    learning_rate: float = 0.02,
) -> BaselineResult:
    """Fit one fixed candidate on train and evaluate train/validation only."""

    labels = _validate_model_splits(train, validation, label_order)
    if candidate == "logistic_regression":
        if pca_components is not None:
            raise ValueError("pca_components is only valid for the pca_mlp candidate.")
        try:
            from sklearn.linear_model import LogisticRegression
        except ImportError as error:
            raise RuntimeError("Logistic Regression requires the existing scikit-learn environment.") from error
        model = LogisticRegression(C=1.0, max_iter=1000, solver="lbfgs", random_state=seed)
        model.fit(train.features, train.labels)
        train_predictions = tuple(str(value) for value in model.predict(train.features))
        validation_predictions = tuple(str(value) for value in model.predict(validation.features))
        parameters = {"C": 1.0, "max_iter": 1000, "solver": "lbfgs", "random_state": seed}
        transform_fit_record_ids: tuple[str, ...] = ()
        transform_state = None
        preprocessor = None
    elif candidate in {"mlp", "pca_mlp"}:
        if candidate == "pca_mlp" and pca_components is None:
            raise ValueError("pca_mlp requires pca_components.")
        if candidate == "mlp" and pca_components is not None:
            raise ValueError("pca_components is only valid for the pca_mlp candidate.")
        if epochs < 1 or hidden_size < 1 or not math.isfinite(learning_rate) or learning_rate <= 0.0:
            raise ValueError("epochs, hidden_size, and learning_rate must be positive.")
        preprocessor = None
        train_features: Sequence[Sequence[float]] = train.features
        validation_features: Sequence[Sequence[float]] = validation.features
        transform_fit_record_ids = ()
        transform_state = None
        if candidate == "pca_mlp":
            assert pca_components is not None
            preprocessor = _fit_pca(train, pca_components)
            train_features = preprocessor.transform(train.features)
            validation_features = preprocessor.transform(validation.features)
            transform_fit_record_ids = preprocessor.fit_record_ids
            transform_state = {
                "mean": list(preprocessor.mean),
                "components": [list(row) for row in preprocessor.components],
                "fit_record_ids": list(preprocessor.fit_record_ids),
            }
        model, train_predictions, validation_predictions = _fit_torch_mlp(
            train_features,
            train.labels,
            validation_features,
            label_order=labels,
            seed=seed,
            hidden_size=hidden_size,
            epochs=epochs,
            learning_rate=learning_rate,
        )
        parameters = {
            "seed": seed,
            "hidden_size": hidden_size,
            "epochs": epochs,
            "learning_rate": learning_rate,
            "pca_components": pca_components if candidate == "pca_mlp" else None,
        }
    else:
        raise ValueError(f"unsupported baseline candidate: {candidate!r}")

    return BaselineResult(
        candidate=candidate,
        label_order=labels,
        seed=seed,
        fit_record_ids=train.record_ids,
        train_record_ids=train.record_ids,
        validation_record_ids=validation.record_ids,
        train_predictions=train_predictions,
        validation_predictions=validation_predictions,
        train_metrics=classification_metrics(train.labels, train_predictions, labels),
        validation_metrics=classification_metrics(validation.labels, validation_predictions, labels),
        parameters=parameters,
        transform_fit_record_ids=transform_fit_record_ids,
        transform_state=transform_state,
        model=model,
        preprocessor=preprocessor,
    )


def _fit_pca(train: SplitEmbeddings, components: int) -> PCAState:
    torch = _require_torch()
    features = torch.tensor(train.features, dtype=torch.float64, device="cpu")
    if components < 1:
        raise ValueError("PCA component count must be positive.")
    centered = features - features.mean(dim=0)
    rank = int(torch.linalg.matrix_rank(centered).item())
    if components > rank:
        raise ValueError(f"PCA component count {components} exceeds train feature rank {rank}.")
    covariance = centered.T @ centered / max(1, features.shape[0] - 1)
    _, eigenvectors = torch.linalg.eigh(covariance)
    basis = eigenvectors[:, -components:].flip(dims=(1,)).T.contiguous()
    # Eigenvector signs are arbitrary; make each component's largest-magnitude
    # entry positive so fixture transforms are stable across repeated fits.
    for row_index in range(basis.shape[0]):
        pivot_index = int(torch.argmax(torch.abs(basis[row_index])).item())
        if basis[row_index, pivot_index] < 0:
            basis[row_index] *= -1
    mean = tuple(float(value) for value in features.mean(dim=0).tolist())
    component_rows = tuple(tuple(float(value) for value in row) for row in basis.tolist())
    return PCAState(mean=mean, components=component_rows, fit_record_ids=train.record_ids)


def _fit_torch_mlp(
    train_features: Sequence[Sequence[float]],
    train_labels: Sequence[str],
    validation_features: Sequence[Sequence[float]],
    *,
    label_order: Sequence[str],
    seed: int,
    hidden_size: int,
    epochs: int,
    learning_rate: float,
) -> tuple[Any, tuple[str, ...], tuple[str, ...]]:
    torch = _require_torch()
    nn = torch.nn
    x_train = torch.tensor(train_features, dtype=torch.float32, device="cpu")
    x_validation = torch.tensor(validation_features, dtype=torch.float32, device="cpu")
    class_index = {label: index for index, label in enumerate(label_order)}
    y_train = torch.tensor([class_index[label] for label in train_labels], dtype=torch.long, device="cpu")
    with torch.random.fork_rng(devices=[]):
        torch.manual_seed(seed)
        model = nn.Sequential(
            nn.Linear(x_train.shape[1], hidden_size),
            nn.ReLU(),
            nn.Linear(hidden_size, len(label_order)),
        )
        optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
        model.train()
        for _ in range(epochs):
            optimizer.zero_grad(set_to_none=True)
            loss = nn.functional.cross_entropy(model(x_train), y_train)
            loss.backward()
            optimizer.step()
        model.eval()
        with torch.no_grad():
            train_indices = model(x_train).argmax(dim=1).tolist()
            validation_indices = model(x_validation).argmax(dim=1).tolist()
    return (
        model,
        tuple(label_order[index] for index in train_indices),
        tuple(label_order[index] for index in validation_indices),
    )


def _require_torch() -> Any:
    try:
        import torch
    except ImportError as error:
        raise RuntimeError("MLP baselines require the existing PyTorch fixture environment.") from error
    return torch


def _validate_model_splits(
    train: SplitEmbeddings,
    validation: SplitEmbeddings,
    label_order: Sequence[str],
) -> tuple[str, ...]:
    if train.split != "train" or validation.split != "validation":
        raise ValueError("run_baseline requires train and validation splits in that order.")
    if len(train.features[0]) != len(validation.features[0]):
        raise ValueError("train and validation feature dimensions differ.")
    if set(train.record_ids) & set(validation.record_ids):
        raise ValueError("record ids overlap between train and validation.")
    if set(train.family_ids) & set(validation.family_ids):
        raise ValueError("scenario_family_id crosses train and validation.")
    labels = tuple(label_order)
    if not labels or any(not isinstance(label, str) or not label for label in labels):
        raise ValueError("label_order must contain non-empty label strings.")
    if len(set(labels)) != len(labels):
        raise ValueError("label_order must not contain duplicates.")
    unknown = (set(train.labels) | set(validation.labels)) - set(labels)
    if unknown:
        raise ValueError("observed labels are missing from label_order: " + ", ".join(sorted(unknown)))
    if set(train.labels) != set(labels):
        raise ValueError("train must contain every label in label_order.")
    return labels


def _finite_float(value: object, *, context: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{context} values must be finite numbers.")
    try:
        result = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as error:
        raise ValueError(f"{context} values must be finite numbers.") from error
    if not math.isfinite(result):
        raise ValueError(f"{context} values must be finite numbers.")
    return result


def _validate_vector(vector: Sequence[float], settings: EmbeddingSettings) -> tuple[float, ...]:
    if isinstance(vector, (str, bytes)):
        raise ValueError("encoder output must be a numeric vector.")
    values = tuple(_finite_float(value, context="embedding") for value in vector)
    if len(values) != settings.output_dimension:
        raise ValueError(
            f"embedding dimension mismatch: expected {settings.output_dimension}, got {len(values)}."
        )
    if settings.normalize_embeddings:
        norm = math.sqrt(sum(value * value for value in values))
        if norm == 0.0:
            raise ValueError("cannot L2-normalize a zero norm embedding.")
        values = tuple(value / norm for value in values)
    return values

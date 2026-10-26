"""Train-validation-only Fly A/B trainers for the M3.2 engineering run.

All samples and graph rows enter through in-memory value objects. This module
does not read datasets, Parquet, embedding caches, or test rows from disk.
"""

from __future__ import annotations

import hashlib
import math
import os
import tempfile
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterator

import torch
from torch.nn import functional as F

from .evaluation import LABEL_ORDER, PredictionBatch, classification_metrics, evaluate_predictions
from .graph_core import CLASS_ORDER, FlyA, FlyB, GraphCoreError, SparseGraphCore, distance_preserving_loss


@dataclass(frozen=True)
class GraphDefinition:
    """In-memory, ordered graph contract used to construct an A or B core."""

    node_ids: tuple[int, ...]
    input_node_ids: tuple[int, ...]
    output_node_ids: tuple[int, ...]
    edges: tuple[tuple[int, int, int], ...]
    steps: int = 2

    def build_core(self) -> SparseGraphCore:
        return SparseGraphCore(
            node_ids=self.node_ids,
            input_node_ids=self.input_node_ids,
            output_node_ids=self.output_node_ids,
            edges=self.edges,
            steps=self.steps,
        )


@dataclass(frozen=True)
class EmbeddingSplit:
    """One in-memory train or validation slice; no transcript field exists."""

    split: str
    record_ids: tuple[str, ...]
    family_ids: tuple[str, ...]
    embeddings: torch.Tensor
    labels: tuple[str, ...] | None = None

    def __post_init__(self) -> None:
        if self.split not in {"train", "validation", "test"}:
            raise ValueError("split must be train, validation, or test.")
        count = len(self.record_ids)
        if count == 0 or len(self.family_ids) != count:
            raise ValueError("record_ids and family_ids must have the same non-zero length.")
        if self.labels is not None and len(self.labels) != count:
            raise ValueError("labels must match the split row count.")
        if any(not isinstance(value, str) or not value for value in self.record_ids + self.family_ids):
            raise ValueError("record and family IDs must be non-empty strings.")
        if len(set(self.record_ids)) != count:
            raise ValueError("record IDs must be unique within a split.")
        if not isinstance(self.embeddings, torch.Tensor):
            raise ValueError("embeddings must be an in-memory torch.Tensor.")


@dataclass(frozen=True)
class TrainingConfig:
    seed: int = 42
    batch_size: int = 32
    max_epochs: int = 100
    patience: int = 10
    learning_rate: float = 1e-3
    gradient_clip_norm: float = 1.0
    torch_threads: int = 1

    def __post_init__(self) -> None:
        for name in ("seed", "batch_size", "max_epochs", "patience", "torch_threads"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise ValueError(f"{name} must be a positive integer.")
        if self.batch_size < 2:
            raise ValueError("batch_size must be at least 2 for pairwise distance loss.")
        for name in ("learning_rate", "gradient_clip_norm"):
            value = getattr(self, name)
            if not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive.")


@dataclass(frozen=True)
class TrainingResult:
    task: str
    model: torch.nn.Module
    selected_epoch: int
    best_validation_metric: float
    history: tuple[dict[str, float], ...]
    checkpoint_path: Path
    checkpoint_sha256: str
    evaluation: dict[str, Any] | None = None


def validate_engineering_graph(graph: GraphDefinition) -> None:
    """Enforce the graph size and recurrent setting frozen for the first run."""

    core = graph.build_core()
    if len(core.node_ids) != 500 or len(core.edges) != 2216:
        raise GraphCoreError("the M3.2 engineering graph must contain exactly 500 nodes and 2,216 edges.")
    if len(core.input_node_ids) != 32 or len(core.output_node_ids) != 32:
        raise GraphCoreError("the M3.2 engineering graph requires the ordered 32+32 I/O coordinates.")
    if core.steps != 2:
        raise GraphCoreError("the locked M3.2 first run requires T=2.")


def _validate_sha256_map(values: dict[str, str], name: str) -> dict[str, str]:
    if not isinstance(values, dict) or not values:
        raise ValueError(f"{name} must be a non-empty mapping of source names to SHA-256 values.")
    checked: dict[str, str] = {}
    for key, digest in values.items():
        if not isinstance(key, str) or not key or not isinstance(digest, str):
            raise ValueError(f"{name} contains an invalid source name or checksum.")
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise ValueError(f"{name}[{key}] must be a lowercase SHA-256 digest.")
        checked[key] = digest
    return dict(sorted(checked.items()))


def _validate_splits(
    train: EmbeddingSplit,
    validation: EmbeddingSplit,
    *,
    require_labels: bool,
) -> int:
    if train.split != "train" or validation.split != "validation":
        raise ValueError("only train and validation splits are accepted; test is never a model input.")
    if require_labels:
        if train.labels is None or validation.labels is None:
            raise ValueError("Fly B requires train and validation labels.")
        allowed = set(LABEL_ORDER)
        if any(label not in allowed for label in train.labels + validation.labels):
            raise ValueError("labels must match the fixed taxonomy order.")
    elif train.labels is not None or validation.labels is not None:
        raise ValueError("Fly A is label-free and does not accept labels.")
    if set(train.record_ids) & set(validation.record_ids):
        raise ValueError("train and validation record IDs must be disjoint.")
    if set(train.family_ids) & set(validation.family_ids):
        raise ValueError("scenario families must not cross train and validation.")
    for batch in (train, validation):
        values = batch.embeddings
        if values.ndim != 2 or values.shape[0] != len(batch.record_ids) or values.shape[1] < 1:
            raise ValueError("embedding matrix shape must match the split records and have positive dimension.")
        if values.device.type != "cpu" or values.dtype != torch.float32:
            raise ValueError("M3.2 uses CPU float32 embeddings only.")
        if not torch.all(torch.isfinite(values)):
            raise ValueError("embeddings must contain only finite values.")
        norms = torch.linalg.vector_norm(values, ord=2, dim=1)
        if torch.any(norms <= 0) or not torch.allclose(norms, torch.ones_like(norms), rtol=1e-4, atol=1e-4):
            raise ValueError("E5 embeddings must be non-zero and L2-normalized.")
    if train.embeddings.shape[1] != validation.embeddings.shape[1]:
        raise ValueError("train and validation embedding dimensions must match.")
    return int(train.embeddings.shape[1])


@contextmanager
def _seeded_cpu(seed: int, threads: int) -> Iterator[None]:
    previous_state = torch.random.get_rng_state()
    previous_threads = torch.get_num_threads()
    try:
        torch.set_num_threads(threads)
        torch.manual_seed(seed)
        yield
    finally:
        torch.random.set_rng_state(previous_state)
        torch.set_num_threads(previous_threads)


def _training_batches(count: int, batch_size: int, generator: torch.Generator) -> list[torch.Tensor]:
    order = torch.randperm(count, generator=generator)
    batches = list(order.split(batch_size))
    if len(batches) > 1 and len(batches[-1]) == 1:
        batches[-2] = torch.cat((batches[-2], batches[-1]))
        batches.pop()
    if any(len(batch) < 2 for batch in batches):
        raise ValueError("training requires at least two records in every distance-loss batch.")
    return batches


def _check_finite_gradients(model: torch.nn.Module, clip_norm: float) -> None:
    for parameter in model.parameters():
        if parameter.grad is not None and not torch.all(torch.isfinite(parameter.grad)):
            raise FloatingPointError("non-finite gradient; the latest valid checkpoint is preserved.")
    norm = torch.nn.utils.clip_grad_norm_(model.parameters(), clip_norm, error_if_nonfinite=True)
    if not torch.isfinite(norm):
        raise FloatingPointError("non-finite gradient norm; the latest valid checkpoint is preserved.")


def _checkpoint_payload(
    model: torch.nn.Module,
    *,
    task: str,
    config: TrainingConfig,
    epoch: int,
    source_sha256: dict[str, str],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "task": task,
        "model_metadata": model.checkpoint_metadata(),
        "training_metadata": {
            "seed": config.seed,
            "batch_size": config.batch_size,
            "max_epochs": config.max_epochs,
            "patience": config.patience,
            "learning_rate": config.learning_rate,
            "gradient_clip_norm": config.gradient_clip_norm,
            "torch_threads": config.torch_threads,
            "selected_epoch": epoch,
            "selection_metric": "validation_distance_stress" if task == "fly_a" else "validation_macro_f1_then_loss",
            "data_status": "synthetic",
            "review_status": "pending_manual_review",
            "evaluation_status": "smoke_test/provisional",
            "source_sha256": source_sha256,
        },
        "state_dict": model.state_dict(),
    }


def _write_checkpoint(payload: dict[str, Any], path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", dir=path.parent, prefix=f".{path.name}.", delete=False) as stream:
            temp_path = stream.name
            torch.save(payload, stream)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, path)
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)
    return _file_sha256(path)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_checkpoint(
    model: torch.nn.Module,
    path: Path,
    *,
    task: str,
    expected_source_sha256: dict[str, str],
) -> dict[str, Any]:
    try:
        payload = torch.load(path, map_location="cpu", weights_only=True)
    except Exception as error:
        raise GraphCoreError(f"could not load {task} checkpoint: {error}") from error
    if not isinstance(payload, dict) or payload.get("schema_version") != 1 or payload.get("task") != task:
        raise GraphCoreError("checkpoint is missing its training schema or task identity.")
    if payload.get("model_metadata") != model.checkpoint_metadata():
        raise GraphCoreError("checkpoint topology, I/O order, dimension, or class contract does not match.")
    training = payload.get("training_metadata")
    if not isinstance(training, dict) or training.get("source_sha256") != expected_source_sha256:
        raise GraphCoreError("checkpoint source provenance does not match the expected sources.")
    try:
        model.load_state_dict(payload["state_dict"], strict=True)
    except Exception as error:
        raise GraphCoreError(f"checkpoint parameters are incompatible: {error}") from error
    return training


def load_fly_a_checkpoint(
    graph: GraphDefinition,
    embedding_dim: int,
    checkpoint_path: Path,
    *,
    expected_source_sha256: dict[str, str],
) -> FlyA:
    """Load a source-checked Fly A checkpoint for CPU inference or chaining."""

    source_hashes = _validate_sha256_map(expected_source_sha256, "expected_source_sha256")
    model = FlyA(embedding_dim, graph.build_core())
    _load_checkpoint(
        model,
        Path(checkpoint_path),
        task="fly_a",
        expected_source_sha256=source_hashes,
    )
    model.eval()
    return model


def load_fly_b_checkpoint(
    graph: GraphDefinition,
    checkpoint_path: Path,
    *,
    expected_source_sha256: dict[str, str],
) -> FlyB:
    """Load a source-checked Fly B checkpoint with the fixed five-label order."""

    source_hashes = _validate_sha256_map(expected_source_sha256, "expected_source_sha256")
    model = FlyB(graph.build_core(), label_order=LABEL_ORDER)
    _load_checkpoint(
        model,
        Path(checkpoint_path),
        task="fly_b",
        expected_source_sha256=source_hashes,
    )
    model.eval()
    return model


def train_fly_a(
    graph: GraphDefinition,
    train: EmbeddingSplit,
    validation: EmbeddingSplit,
    *,
    checkpoint_path: Path,
    source_sha256: dict[str, str],
    config: TrainingConfig = TrainingConfig(),
) -> TrainingResult:
    """Train label-free Fly A and select its earliest minimum-stress epoch."""

    dimension = _validate_splits(train, validation, require_labels=False)
    source_hashes = _validate_sha256_map(source_sha256, "source_sha256")
    path = Path(checkpoint_path)
    with _seeded_cpu(config.seed, config.torch_threads):
        model = FlyA(dimension, graph.build_core())
        optimizer = torch.optim.Adam(model.parameters(), lr=config.learning_rate)
        generator = torch.Generator(device="cpu").manual_seed(config.seed)
        history: list[dict[str, float]] = []
        best_score = math.inf
        best_epoch = 0
        best_state: dict[str, torch.Tensor] | None = None
        stale_epochs = 0

        for epoch in range(1, config.max_epochs + 1):
            model.train()
            weighted_loss = 0.0
            pair_count = 0
            for indices in _training_batches(len(train.record_ids), config.batch_size, generator):
                batch = train.embeddings.index_select(0, indices)
                optimizer.zero_grad(set_to_none=True)
                loss = distance_preserving_loss(batch, model(batch))
                if not torch.isfinite(loss):
                    raise FloatingPointError("non-finite Fly A loss; the latest valid checkpoint is preserved.")
                loss.backward()
                _check_finite_gradients(model, config.gradient_clip_norm)
                optimizer.step()
                pairs = len(indices) * (len(indices) - 1) // 2
                weighted_loss += float(loss.detach()) * pairs
                pair_count += pairs

            model.eval()
            with torch.no_grad():
                stress = distance_preserving_loss(validation.embeddings, model(validation.embeddings))
            if not torch.isfinite(stress):
                raise FloatingPointError("non-finite Fly A validation stress; the latest valid checkpoint is preserved.")
            train_loss = weighted_loss / pair_count
            validation_stress = float(stress)
            history.append({"epoch": float(epoch), "train_loss": train_loss, "validation_stress": validation_stress})
            if validation_stress < best_score:
                best_score = validation_stress
                best_epoch = epoch
                best_state = {name: value.detach().cpu().clone() for name, value in model.state_dict().items()}
                _write_checkpoint(
                    _checkpoint_payload(model, task="fly_a", config=config, epoch=epoch, source_sha256=source_hashes),
                    path,
                )
                stale_epochs = 0
            else:
                stale_epochs += 1
                if stale_epochs >= config.patience:
                    break

        if best_state is None:
            raise FloatingPointError("Fly A did not produce a finite validation checkpoint.")
        model.load_state_dict(best_state, strict=True)

    return TrainingResult(
        task="fly_a",
        model=model,
        selected_epoch=best_epoch,
        best_validation_metric=best_score,
        history=tuple(history),
        checkpoint_path=path,
        checkpoint_sha256=_file_sha256(path),
    )


def train_fly_b(
    graph: GraphDefinition,
    train: EmbeddingSplit,
    validation: EmbeddingSplit,
    *,
    fly_a_checkpoint_path: Path,
    fly_a_source_sha256: dict[str, str],
    source_sha256: dict[str, str],
    checkpoint_path: Path,
    config: TrainingConfig = TrainingConfig(),
    candidate_name: str = "fly_a_to_fly_b_m3_2_seed_42",
) -> TrainingResult:
    """Freeze selected Fly A, fit Fly B on train labels, and select on validation."""

    dimension = _validate_splits(train, validation, require_labels=True)
    source_hashes = _validate_sha256_map(source_sha256, "source_sha256")
    fly_a_sources = _validate_sha256_map(fly_a_source_sha256, "fly_a_source_sha256")
    fly_a_path = Path(fly_a_checkpoint_path)
    fly_a_digest = _file_sha256(fly_a_path)
    if source_hashes.get("fly_a_checkpoint") != fly_a_digest:
        raise ValueError("source_sha256 must include the matching fly_a_checkpoint SHA-256.")
    if set(train.labels or ()) != set(LABEL_ORDER):
        raise ValueError("Fly B training data must contain every class in the fixed taxonomy order.")

    with _seeded_cpu(config.seed, config.torch_threads):
        model_a = load_fly_a_checkpoint(
            graph,
            dimension,
            fly_a_path,
            expected_source_sha256=fly_a_sources,
        )
        for parameter in model_a.parameters():
            parameter.requires_grad_(False)
        with torch.no_grad():
            train_representations = model_a(train.embeddings).detach()
            validation_representations = model_a(validation.embeddings).detach()

        labels = torch.tensor([LABEL_ORDER.index(label) for label in train.labels or ()], dtype=torch.long)
        validation_labels = torch.tensor(
            [LABEL_ORDER.index(label) for label in validation.labels or ()], dtype=torch.long
        )
        model = FlyB(graph.build_core(), label_order=LABEL_ORDER)
        optimizer = torch.optim.Adam(model.parameters(), lr=config.learning_rate)
        generator = torch.Generator(device="cpu").manual_seed(config.seed)
        history: list[dict[str, float]] = []
        best_macro_f1 = -math.inf
        best_validation_loss = math.inf
        best_epoch = 0
        best_state: dict[str, torch.Tensor] | None = None
        stale_epochs = 0

        for epoch in range(1, config.max_epochs + 1):
            model.train()
            weighted_loss = 0.0
            seen_rows = 0
            for indices in _training_batches(len(train.record_ids), config.batch_size, generator):
                reps = train_representations.index_select(0, indices)
                targets = labels.index_select(0, indices)
                optimizer.zero_grad(set_to_none=True)
                logits = model(reps)
                loss = F.cross_entropy(logits, targets)
                if not torch.isfinite(loss):
                    raise FloatingPointError("non-finite Fly B loss; the latest valid checkpoint is preserved.")
                loss.backward()
                _check_finite_gradients(model, config.gradient_clip_norm)
                optimizer.step()
                weighted_loss += float(loss.detach()) * len(indices)
                seen_rows += len(indices)

            model.eval()
            with torch.no_grad():
                validation_logits = model(validation_representations)
                validation_loss_tensor = F.cross_entropy(validation_logits, validation_labels)
            if not torch.isfinite(validation_loss_tensor) or not torch.all(torch.isfinite(validation_logits)):
                raise FloatingPointError("non-finite Fly B validation output; the latest valid checkpoint is preserved.")
            validation_predictions = tuple(LABEL_ORDER[index] for index in validation_logits.argmax(dim=1).tolist())
            validation_metrics = classification_metrics(validation.labels or (), validation_predictions, LABEL_ORDER)
            macro_f1 = float(validation_metrics["macro_f1"])
            validation_loss = float(validation_loss_tensor)
            history.append({
                "epoch": float(epoch),
                "train_loss": weighted_loss / seen_rows,
                "validation_loss": validation_loss,
                "validation_macro_f1": macro_f1,
            })
            improved = macro_f1 > best_macro_f1 or (macro_f1 == best_macro_f1 and validation_loss < best_validation_loss)
            if improved:
                best_macro_f1 = macro_f1
                best_validation_loss = validation_loss
                best_epoch = epoch
                best_state = {name: value.detach().cpu().clone() for name, value in model.state_dict().items()}
                _write_checkpoint(
                    _checkpoint_payload(model, task="fly_b", config=config, epoch=epoch, source_sha256=source_hashes),
                    Path(checkpoint_path),
                )
                stale_epochs = 0
            else:
                stale_epochs += 1
                if stale_epochs >= config.patience:
                    break

        if best_state is None:
            raise FloatingPointError("Fly B did not produce a valid validation checkpoint.")
        model.load_state_dict(best_state, strict=True)
        model.eval()
        with torch.no_grad():
            train_logits = model(train_representations)
            validation_logits = model(validation_representations)
        train_predictions = tuple(LABEL_ORDER[index] for index in train_logits.argmax(dim=1).tolist())
        validation_predictions = tuple(LABEL_ORDER[index] for index in validation_logits.argmax(dim=1).tolist())
        train_batch = PredictionBatch("train", train.record_ids, train.family_ids, train.labels or (), train_predictions)
        validation_batch = PredictionBatch(
            "validation", validation.record_ids, validation.family_ids, validation.labels or (), validation_predictions
        )
        report = evaluate_predictions(
            train_batch,
            validation_batch,
            candidate_name=candidate_name,
            data_status="synthetic",
        )
        checkpoint_path = Path(checkpoint_path)

    return TrainingResult(
        task="fly_b",
        model=model,
        selected_epoch=best_epoch,
        best_validation_metric=best_macro_f1,
        history=tuple(history),
        checkpoint_path=checkpoint_path,
        checkpoint_sha256=_file_sha256(checkpoint_path),
        evaluation=report,
    )

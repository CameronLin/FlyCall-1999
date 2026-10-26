"""Small, explicit guardrails for exploratory Fly A/B diagnostics."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import torch
from torch.nn import functional as F

from .evaluation import LABEL_ORDER, PredictionBatch, classification_metrics, evaluate_predictions
from .fly_ab_training import (
    EmbeddingSplit,
    GraphDefinition,
    TrainingConfig,
    TrainingResult,
    _check_finite_gradients,
    _checkpoint_payload,
    _file_sha256,
    _load_checkpoint,
    _seeded_cpu,
    _training_batches,
    _validate_sha256_map,
    _validate_splits,
    _write_checkpoint,
    load_fly_a_checkpoint,
)
from .graph_core import FlyBWithE5Residual

TRAIN_VALIDATION_COUNTS = {"train": 700, "validation": 150}
FLY_B_TUNING_SCHEDULES = (
    {"name": "lr_0_001_ep200_pat25", "learning_rate": 0.001, "max_epochs": 200, "patience": 25},
    {"name": "lr_0_003_ep200_pat25", "learning_rate": 0.003, "max_epochs": 200, "patience": 25},
    {"name": "lr_0_01_ep200_pat25", "learning_rate": 0.01, "max_epochs": 200, "patience": 25},
)


class FlyABDiagnosticError(ValueError):
    """Raised when diagnostic inputs violate the train/validation-only contract."""


def validate_embedding_manifest_entries(entries: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    """Require exactly the frozen train/validation embeddings, with no test entry."""

    if len(entries) != sum(TRAIN_VALIDATION_COUNTS.values()):
        raise FlyABDiagnosticError("embedding manifest must contain exactly 850 train/validation entries.")
    counts = {"train": 0, "validation": 0}
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise FlyABDiagnosticError("embedding manifest contains an invalid entry.")
        record_id = entry.get("record_id")
        split = entry.get("split")
        if not isinstance(record_id, str) or not record_id or record_id in seen:
            raise FlyABDiagnosticError("embedding manifest contains a missing or duplicate record ID.")
        seen.add(record_id)
        if split not in counts:
            raise FlyABDiagnosticError("embedding manifest may contain train and validation entries only.")
        counts[split] += 1
    if counts != TRAIN_VALIDATION_COUNTS:
        raise FlyABDiagnosticError(f"embedding manifest split counts differ from the frozen 700/150 contract: {counts}.")
    return counts


def fly_a_retains_label_signal(*, raw_mlp_macro_f1: float, fly_a_mlp_macro_f1: float) -> bool:
    """Choose the next diagnostic branch using the preregistered validation rule."""

    for name, value in (("raw_mlp_macro_f1", raw_mlp_macro_f1), ("fly_a_mlp_macro_f1", fly_a_mlp_macro_f1)):
        if not isinstance(value, (int, float)) or not math.isfinite(value) or not 0.0 <= value <= 1.0:
            raise FlyABDiagnosticError(f"{name} must be a finite value between zero and one.")
    return fly_a_mlp_macro_f1 >= 0.85 and raw_mlp_macro_f1 - fly_a_mlp_macro_f1 <= 0.10


def load_fly_b_e5_residual_checkpoint(
    graph: GraphDefinition,
    embedding_dim: int,
    checkpoint_path: Path,
    *,
    expected_source_sha256: dict[str, str],
    gate_logit_init: float = -2.0,
) -> FlyBWithE5Residual:
    """Load the separately versioned residual candidate with provenance checks."""

    source_hashes = _validate_sha256_map(expected_source_sha256, "expected_source_sha256")
    model = FlyBWithE5Residual(
        graph.build_core(),
        embedding_dim=embedding_dim,
        label_order=LABEL_ORDER,
        gate_logit_init=gate_logit_init,
    )
    _load_checkpoint(
        model,
        Path(checkpoint_path),
        task="fly_b_e5_residual",
        expected_source_sha256=source_hashes,
    )
    model.eval()
    return model


def train_fly_b_with_e5_residual(
    graph: GraphDefinition,
    train: EmbeddingSplit,
    validation: EmbeddingSplit,
    *,
    fly_a_checkpoint_path: Path,
    fly_a_source_sha256: dict[str, str],
    source_sha256: dict[str, str],
    checkpoint_path: Path,
    config: TrainingConfig = TrainingConfig(),
    candidate_name: str = "fly_a_to_fly_b_gated_e5_residual",
    gate_logit_init: float = -2.0,
) -> TrainingResult:
    """Train a gated raw-E5 residual into Fly B while keeping Fly A frozen.

    The E5 residual joins the normal Fly B adapter drives before its graph core.
    It cannot reach class logits except through that graph core and readout.
    """

    dimension = _validate_splits(train, validation, require_labels=True)
    if dimension != 384:
        raise ValueError("the preregistered E5 residual candidate requires 384-dimensional E5 inputs.")
    source_hashes = _validate_sha256_map(source_sha256, "source_sha256")
    fly_a_sources = _validate_sha256_map(fly_a_source_sha256, "fly_a_source_sha256")
    fly_a_path = Path(fly_a_checkpoint_path)
    fly_a_digest = _file_sha256(fly_a_path)
    if source_hashes.get("fly_a_checkpoint") != fly_a_digest:
        raise ValueError("source_sha256 must include the matching fly_a_checkpoint SHA-256.")
    if set(train.labels or ()) != set(LABEL_ORDER):
        raise ValueError("Fly B training data must contain every class in the fixed taxonomy order.")

    path = Path(checkpoint_path)
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
            train_a = model_a(train.embeddings).detach()
            validation_a = model_a(validation.embeddings).detach()

        labels = torch.tensor([LABEL_ORDER.index(label) for label in train.labels or ()], dtype=torch.long)
        validation_labels = torch.tensor(
            [LABEL_ORDER.index(label) for label in validation.labels or ()], dtype=torch.long
        )
        model = FlyBWithE5Residual(
            graph.build_core(),
            embedding_dim=dimension,
            label_order=LABEL_ORDER,
            gate_logit_init=gate_logit_init,
        )
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
                e5_values = train.embeddings.index_select(0, indices)
                a_values = train_a.index_select(0, indices)
                targets = labels.index_select(0, indices)
                optimizer.zero_grad(set_to_none=True)
                logits = model(a_values, e5_values)
                loss = F.cross_entropy(logits, targets)
                if not torch.isfinite(loss):
                    raise FloatingPointError("non-finite residual Fly B loss; the latest valid checkpoint is preserved.")
                loss.backward()
                _check_finite_gradients(model, config.gradient_clip_norm)
                optimizer.step()
                weighted_loss += float(loss.detach()) * len(indices)
                seen_rows += len(indices)

            model.eval()
            with torch.no_grad():
                validation_logits = model(validation_a, validation.embeddings)
                validation_loss_tensor = F.cross_entropy(validation_logits, validation_labels)
            if not torch.isfinite(validation_loss_tensor) or not torch.all(torch.isfinite(validation_logits)):
                raise FloatingPointError("non-finite residual Fly B validation output; latest checkpoint is preserved.")
            validation_predictions = tuple(LABEL_ORDER[index] for index in validation_logits.argmax(dim=1).tolist())
            metrics = classification_metrics(validation.labels or (), validation_predictions, LABEL_ORDER)
            macro_f1 = float(metrics["macro_f1"])
            validation_loss = float(validation_loss_tensor)
            history.append({
                "epoch": float(epoch),
                "train_loss": weighted_loss / seen_rows,
                "validation_loss": validation_loss,
                "validation_macro_f1": macro_f1,
                "residual_gate": float(model.residual_gate.detach()),
            })
            improved = macro_f1 > best_macro_f1 or (
                macro_f1 == best_macro_f1 and validation_loss < best_validation_loss
            )
            if improved:
                best_macro_f1 = macro_f1
                best_validation_loss = validation_loss
                best_epoch = epoch
                best_state = {name: value.detach().cpu().clone() for name, value in model.state_dict().items()}
                _write_checkpoint(
                    _checkpoint_payload(
                        model,
                        task="fly_b_e5_residual",
                        config=config,
                        epoch=epoch,
                        source_sha256=source_hashes,
                    ),
                    path,
                )
                stale_epochs = 0
            else:
                stale_epochs += 1
                if stale_epochs >= config.patience:
                    break

        if best_state is None:
            raise FloatingPointError("Residual Fly B did not produce a valid validation checkpoint.")
        model.load_state_dict(best_state, strict=True)
        model.eval()
        with torch.no_grad():
            train_logits = model(train_a, train.embeddings)
            validation_logits = model(validation_a, validation.embeddings)
        train_predictions = tuple(LABEL_ORDER[index] for index in train_logits.argmax(dim=1).tolist())
        validation_predictions = tuple(LABEL_ORDER[index] for index in validation_logits.argmax(dim=1).tolist())
        train_batch = PredictionBatch("train", train.record_ids, train.family_ids, train.labels or (), train_predictions)
        validation_batch = PredictionBatch(
            "validation", validation.record_ids, validation.family_ids, validation.labels or (), validation_predictions
        )
        report = evaluate_predictions(train_batch, validation_batch, candidate_name=candidate_name, data_status="synthetic")

    return TrainingResult(
        task="fly_b_e5_residual",
        model=model,
        selected_epoch=best_epoch,
        best_validation_metric=best_macro_f1,
        history=tuple(history),
        checkpoint_path=path,
        checkpoint_sha256=_file_sha256(path),
        evaluation=report,
    )

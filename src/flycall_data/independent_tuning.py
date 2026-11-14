"""Separate Fly A / Fly B tuning on train-only grouped cross-validation (ticket 20).

Preregistration: .scratch/1999-connectome-demo/research/
independent-fly-a-fly-b-tuning-preregistration-20261113.md

Everything here works on in-memory tensors; nothing reads datasets or test rows.
Two Fly A objectives (decision D4): label-free ``distance`` and
``distance_supcon`` (distance + supervised contrastive). Training either stops
early on a held-out train fold, or runs a fixed number of epochs (final models),
so the real validation split is never used for model selection.
"""

from __future__ import annotations

import hashlib
import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Sequence

import torch
from torch.nn import functional as F

from .evaluation import LABEL_ORDER, classification_metrics
from .fly_ab_training import GraphDefinition, _check_finite_gradients, _seeded_cpu, _training_batches
from .graph_core import FlyA, FlyB, distance_preserving_loss

OBJECTIVES = ("distance", "distance_supcon")
SUPCON_LAMBDA = 1.0
SUPCON_TEMPERATURE = 0.1
LEARNING_RATES = (0.001, 0.003, 0.01)
MAX_EPOCHS = 200
PATIENCE = 25
FOLDS = 5
SEEDS = (42, 1337, 2026)
CV_KEY = b"FlyCallM37-CV-v1"
BATCH_SIZE = 32
CLIP_NORM = 1.0


class TuningError(ValueError):
    """Raised when tuning inputs violate the train-only contract."""


def grouped_stratified_folds(family_ids: Sequence[str], labels: Sequence[str], folds: int = FOLDS) -> list[int]:
    """Assign each row a fold so that families never split, stratified by class."""

    if len(family_ids) != len(labels) or not family_ids:
        raise TuningError("family_ids and labels must be non-empty and aligned.")
    family_label: dict[str, str] = {}
    for family, label in zip(family_ids, labels):
        if family_label.setdefault(family, label) != label:
            raise TuningError(f"family {family} spans more than one label.")
    by_label: dict[str, list[str]] = defaultdict(list)
    for family, label in family_label.items():
        by_label[label].append(family)
    order = {
        family: hashlib.blake2b(family.encode("utf-8"), digest_size=16, key=CV_KEY).digest()
        for family in family_label
    }
    assignment: dict[str, int] = {}
    counter = 0
    for label in LABEL_ORDER:
        for family in sorted(by_label.get(label, []), key=lambda name: (order[name], name)):
            assignment[family] = counter % folds
            counter += 1
    fold_of_row = [assignment[family] for family in family_ids]
    for fold in range(folds):
        training_labels = {label for label, row_fold in zip(labels, fold_of_row) if row_fold != fold}
        if training_labels != set(labels):
            raise TuningError(f"fold {fold} training part lacks a class.")
    return fold_of_row


def supcon_loss(z: torch.Tensor, y: torch.Tensor, temperature: float = SUPCON_TEMPERATURE) -> torch.Tensor:
    """Supervised contrastive loss on L2-normalized rows (Khosla et al., 2020)."""

    if z.shape[0] != y.shape[0] or z.ndim != 2:
        raise TuningError("z must be (batch, dim) aligned with y.")
    count = z.shape[0]
    logits = (z @ z.T) / temperature
    self_mask = torch.eye(count, dtype=torch.bool, device=z.device)
    logits = logits.masked_fill(self_mask, float("-inf"))
    log_prob = logits - torch.logsumexp(logits, dim=1, keepdim=True)
    positives = (y.unsqueeze(0) == y.unsqueeze(1)) & ~self_mask
    has_positive = positives.any(dim=1)
    if not bool(has_positive.any()):
        return z.sum() * 0.0
    masked = log_prob.masked_fill(~positives, 0.0)
    per_anchor = masked.sum(dim=1)[has_positive] / positives.sum(dim=1)[has_positive]
    return -per_anchor.mean()


def fly_a_objective(objective: str, x: torch.Tensor, z: torch.Tensor, y: torch.Tensor | None) -> torch.Tensor:
    if objective == "distance":
        return distance_preserving_loss(x, z)
    if objective == "distance_supcon":
        if y is None:
            raise TuningError("distance_supcon needs labels.")
        return distance_preserving_loss(x, z) + SUPCON_LAMBDA * supcon_loss(z, y)
    raise TuningError(f"unknown Fly A objective {objective!r}.")


@dataclass
class FitResult:
    model: torch.nn.Module
    selected_epoch: int
    epochs_run: int
    best_selection_value: float | None


def _check_mode(max_epochs: int, patience: int, select: tuple | None) -> None:
    if max_epochs < 1 or patience < 1:
        raise TuningError("max_epochs and patience must be positive.")
    if select is not None and len(select) != 2:
        raise TuningError("select must be (inputs, labels).")


def fit_fly_a(
    graph: GraphDefinition,
    x: torch.Tensor,
    y: torch.Tensor | None,
    *,
    objective: str,
    learning_rate: float,
    seed: int,
    max_epochs: int = MAX_EPOCHS,
    patience: int = PATIENCE,
    select: tuple[torch.Tensor, torch.Tensor | None] | None = None,
) -> FitResult:
    """Train Fly A; early-stop on ``select`` (held-out train fold) or run fixed epochs."""

    _check_mode(max_epochs, patience, select)
    if objective not in OBJECTIVES:
        raise TuningError(f"unknown Fly A objective {objective!r}.")
    with _seeded_cpu(seed, 1):
        model = FlyA(int(x.shape[1]), graph.build_core())
        optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
        generator = torch.Generator(device="cpu").manual_seed(seed)
        best_value, best_epoch, best_state, stale = math.inf, 0, None, 0
        epoch = 0
        for epoch in range(1, max_epochs + 1):
            model.train()
            for indices in _training_batches(int(x.shape[0]), BATCH_SIZE, generator):
                batch_y = None if y is None else y.index_select(0, indices)
                batch_x = x.index_select(0, indices)
                optimizer.zero_grad(set_to_none=True)
                loss = fly_a_objective(objective, batch_x, model(batch_x), batch_y)
                if not torch.isfinite(loss):
                    raise FloatingPointError("non-finite Fly A loss.")
                loss.backward()
                _check_finite_gradients(model, CLIP_NORM)
                optimizer.step()
            if select is None:
                continue
            model.eval()
            with torch.no_grad():
                value = float(fly_a_objective(objective, select[0], model(select[0]), select[1]))
            if not math.isfinite(value):
                raise FloatingPointError("non-finite Fly A selection loss.")
            if value < best_value:
                best_value, best_epoch, stale = value, epoch, 0
                best_state = {name: tensor.detach().clone() for name, tensor in model.state_dict().items()}
            else:
                stale += 1
                if stale >= patience:
                    break
        if select is None:
            model.eval()
            return FitResult(model, epoch, epoch, None)
        assert best_state is not None
        model.load_state_dict(best_state, strict=True)
        model.eval()
        return FitResult(model, best_epoch, epoch, best_value)


def fit_fly_b(
    graph: GraphDefinition,
    r: torch.Tensor,
    y: torch.Tensor,
    *,
    learning_rate: float,
    seed: int,
    max_epochs: int = MAX_EPOCHS,
    patience: int = PATIENCE,
    select: tuple[torch.Tensor, torch.Tensor] | None = None,
) -> FitResult:
    """Train Fly B on fixed representations; select by Macro-F1 then loss (M3.3 rule)."""

    _check_mode(max_epochs, patience, select)
    with _seeded_cpu(seed, 1):
        model = FlyB(graph.build_core(), label_order=LABEL_ORDER, input_width=int(r.shape[1]))
        optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
        generator = torch.Generator(device="cpu").manual_seed(seed)
        best_key, best_epoch, best_state, stale = (-math.inf, -math.inf), 0, None, 0
        epoch = 0
        for epoch in range(1, max_epochs + 1):
            model.train()
            for indices in _training_batches(int(r.shape[0]), BATCH_SIZE, generator):
                optimizer.zero_grad(set_to_none=True)
                loss = F.cross_entropy(model(r.index_select(0, indices)), y.index_select(0, indices))
                if not torch.isfinite(loss):
                    raise FloatingPointError("non-finite Fly B loss.")
                loss.backward()
                _check_finite_gradients(model, CLIP_NORM)
                optimizer.step()
            if select is None:
                continue
            model.eval()
            with torch.no_grad():
                logits = model(select[0])
                value_loss = float(F.cross_entropy(logits, select[1]))
            f1 = macro_f1(select[1], logits.argmax(dim=1))
            key = (f1, -value_loss)
            if key > best_key:
                best_key, best_epoch, stale = key, epoch, 0
                best_state = {name: tensor.detach().clone() for name, tensor in model.state_dict().items()}
            else:
                stale += 1
                if stale >= patience:
                    break
        if select is None:
            model.eval()
            return FitResult(model, epoch, epoch, None)
        assert best_state is not None
        model.load_state_dict(best_state, strict=True)
        model.eval()
        return FitResult(model, best_epoch, epoch, best_key[0])


def label_tensor(labels: Sequence[str]) -> torch.Tensor:
    if any(label not in LABEL_ORDER for label in labels):
        raise TuningError("labels must use the fixed taxonomy.")
    return torch.tensor([LABEL_ORDER.index(label) for label in labels], dtype=torch.long)


def macro_f1(y_true: torch.Tensor | Sequence[int], y_pred: torch.Tensor | Sequence[int]) -> float:
    true = [LABEL_ORDER[int(index)] for index in (y_true.tolist() if isinstance(y_true, torch.Tensor) else y_true)]
    pred = [LABEL_ORDER[int(index)] for index in (y_pred.tolist() if isinstance(y_pred, torch.Tensor) else y_pred)]
    return float(classification_metrics(true, pred, LABEL_ORDER)["macro_f1"])


def choose_learning_rate(scores: dict[float, float]) -> float:
    """Highest score; ties go to the smaller learning rate (preregistered)."""

    if not scores:
        raise TuningError("no learning-rate scores to choose from.")
    return min(scores, key=lambda rate: (-scores[rate], rate))


def median_epoch(epochs: Sequence[int]) -> int:
    ordered = sorted(int(value) for value in epochs)
    if not ordered:
        raise TuningError("no epochs recorded.")
    middle = len(ordered) // 2
    value = ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2
    return max(1, int(math.floor(value + 0.5)))

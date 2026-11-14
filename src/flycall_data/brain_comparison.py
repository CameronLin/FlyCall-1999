"""Post-hoc comparison of trained Fly A and Fly B "brains" on the same graph.

Three views (no model selection happens here):
1. Edge-by-edge: how each model changed every connection's strength.
2. Neuron activity: per-neuron activation and class selectivity (eta squared).
3. Lesions: silence one neuron (or a whole edge class) and measure the drop.

``node_states`` reproduces ``SparseGraphCore.forward`` exactly but returns all
node states and accepts lesion options; tests check equality with forward().
"""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import numpy as np
import torch
from scipy.stats import spearmanr

from .evaluation import LABEL_ORDER
from .fly_ab_training import GraphDefinition
from .graph_core import FlyA, FlyB, SparseGraphCore


class BrainComparisonError(ValueError):
    """Raised when a checkpoint or analysis input is inconsistent."""


def load_trained(kind: str, graph: GraphDefinition, path: Path, *, input_width: int = 32, embedding_dim: int = 384):
    """Load a final checkpoint written by run_independent_tuning.py."""

    payload = torch.load(Path(path), map_location="cpu", weights_only=True)
    if kind == "fly_a":
        model = FlyA(embedding_dim, graph.build_core())
    elif kind == "fly_b":
        model = FlyB(graph.build_core(), label_order=LABEL_ORDER, input_width=input_width)
    else:
        raise BrainComparisonError(f"unknown model kind {kind!r}")
    if payload.get("model_metadata") != model.checkpoint_metadata():
        raise BrainComparisonError(f"{path} does not match the graph/model contract.")
    model.load_state_dict(payload["state_dict"], strict=True)
    model.eval()
    return model, payload.get("metadata", {})


def node_states(
    core: SparseGraphCore,
    drives: torch.Tensor,
    *,
    silenced: torch.Tensor | None = None,
    edge_scale: torch.Tensor | None = None,
) -> torch.Tensor:
    """Final states of all nodes; optionally silence nodes or rescale edges.

    ``silenced`` is a boolean (num_nodes,) mask: those nodes are clamped to 0
    after every step, so they send nothing and read out as 0. ``edge_scale``
    multiplies each effective (signed) edge weight.
    """

    count = len(core.node_ids)
    hidden = torch.zeros((drives.shape[0], count), dtype=drives.dtype)
    driven = torch.zeros_like(hidden).index_copy(1, core.input_index, drives)
    degree = core.in_degrees.clamp_min(1).to(dtype=drives.dtype).unsqueeze(0)
    weights = core.signed_edge_weights
    if edge_scale is not None:
        if edge_scale.shape != weights.shape:
            raise BrainComparisonError("edge_scale must have one value per edge.")
        weights = weights * edge_scale
    keep = None
    if silenced is not None:
        if silenced.shape != (count,) or silenced.dtype != torch.bool:
            raise BrainComparisonError("silenced must be a boolean mask over nodes.")
        keep = (~silenced).to(drives.dtype).unsqueeze(0)
    if getattr(core, "input_at_step_zero", False):
        hidden = torch.tanh(driven)
        if keep is not None:
            hidden = hidden * keep
    for _ in range(core.steps):
        messages = hidden.index_select(1, core.source_index) * weights.unsqueeze(0)
        hidden = torch.tanh(torch.zeros_like(hidden).index_add(1, core.target_index, messages) / degree + driven)
        if keep is not None:
            hidden = hidden * keep
    return hidden


def fly_a_drives(model: FlyA, embeddings: torch.Tensor) -> torch.Tensor:
    normalized = embeddings / torch.linalg.vector_norm(embeddings, ord=2, dim=1, keepdim=True)
    return torch.tanh(model.input_projection(normalized))


def fly_a_output(model: FlyA, embeddings: torch.Tensor, **lesion) -> torch.Tensor:
    states = node_states(model.graph_core, fly_a_drives(model, embeddings), **lesion)
    out = states.index_select(1, model.graph_core.output_index)
    norm = torch.linalg.vector_norm(out, ord=2, dim=1, keepdim=True)
    return out / norm.clamp_min(1e-12)  # a fully silenced output would otherwise divide by zero


def fly_b_logits(model: FlyB, inputs: torch.Tensor, **lesion) -> torch.Tensor:
    states = node_states(model.graph_core, model.input_adapter(inputs), **lesion)
    return model.readout(states.index_select(1, model.graph_core.output_index))


def edge_log_change(core: SparseGraphCore, graph: GraphDefinition) -> np.ndarray:
    """log(trained magnitude / initial magnitude) per edge (sign excluded)."""

    initial = graph.build_core().edge_gains.detach()
    return torch.log(core.edge_gains.detach() / initial).numpy()


def eta_squared(activations: np.ndarray, labels: Sequence[int]) -> np.ndarray:
    """Between-class share of variance per neuron (0 = no class signal, 1 = pure)."""

    values = np.asarray(activations, dtype=np.float64)
    groups = np.asarray(labels)
    total = ((values - values.mean(axis=0)) ** 2).sum(axis=0)
    between = np.zeros(values.shape[1])
    for label in np.unique(groups):
        part = values[groups == label]
        between += len(part) * (part.mean(axis=0) - values.mean(axis=0)) ** 2
    with np.errstate(invalid="ignore", divide="ignore"):
        result = np.where(total > 1e-12, between / total, 0.0)
    return result


def spearman(first: np.ndarray, second: np.ndarray) -> float:
    value = spearmanr(first, second).statistic
    return float(value) if np.isfinite(value) else 0.0


def top_set(values: np.ndarray, fraction: float | None = None, count: int | None = None) -> set[int]:
    order = np.argsort(-np.asarray(values), kind="stable")
    size = count if count is not None else max(1, int(round(len(order) * float(fraction))))
    return set(order[:size].tolist())


def jaccard(first: set[int], second: set[int]) -> float:
    union = first | second
    return len(first & second) / len(union) if union else 1.0

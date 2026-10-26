"""Small-fixture sparse recurrent graph core for M3.1.

The implementation consumes in-memory node IDs, ordered synthetic I/O IDs,
edge tuples and tensors only. It does not load datasets or connectome files.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Sequence

import torch
from torch import nn
from torch.nn import functional as F


EPSILON = 1e-6
CLASS_ORDER = (
    "sidewalk_maintenance",
    "road_surface_defect",
    "park_general_maintenance",
    "waste_truck_service",
    "street_cleaning",
)


class GraphCoreError(ValueError):
    """Raised when a graph fixture or model input violates the M3.0 contract."""


def _checked_ids(name: str, values: Sequence[int]) -> tuple[int, ...]:
    try:
        result = tuple(values)
    except TypeError as exc:
        raise GraphCoreError(f"{name} must be a sequence of integer IDs") from exc
    if not result:
        raise GraphCoreError(f"{name} must not be empty")
    if any(isinstance(value, bool) or not isinstance(value, int) for value in result):
        raise GraphCoreError(f"{name} must contain only integer IDs")
    if len(set(result)) != len(result):
        raise GraphCoreError(f"{name} must contain unique IDs")
    return result


def _inverse_softplus(value: float) -> float:
    if not math.isfinite(value) or value <= 0.0:
        raise GraphCoreError("normalized edge prior must be finite and greater than epsilon")
    # Stable inverse of log(1 + exp(x)) for positive value.
    result = value + math.log(-math.expm1(-value))
    if not math.isfinite(result):
        raise GraphCoreError("edge prior cannot be represented by a finite raw parameter")
    return result


def _initial_raw_edge_parameters(
    edges: tuple[tuple[int, int, int], ...], in_degrees: dict[int, int]
) -> list[float]:
    log_priors = [math.log1p(weight) for _, _, weight in edges]
    incoming: dict[int, list[int]] = {}
    for edge_index, (_, target_id, _) in enumerate(edges):
        incoming.setdefault(target_id, []).append(edge_index)

    raw_parameters = [0.0] * len(edges)
    for target_id, edge_indices in incoming.items():
        degree = in_degrees[target_id]
        if degree != len(edge_indices) or degree <= 0:
            raise GraphCoreError("incoming edge count does not match fixed indegree")
        mean_prior = math.fsum(log_priors[index] for index in edge_indices) / degree
        if not math.isfinite(mean_prior) or mean_prior <= 0.0:
            raise GraphCoreError(
                f"target {target_id} has zero or invalid incoming log1p prior mean"
            )
        for edge_index in edge_indices:
            normalized_prior = log_priors[edge_index] / mean_prior
            raw_parameters[edge_index] = _inverse_softplus(normalized_prior - EPSILON)
    return raw_parameters


class SparseGraphCore(nn.Module):
    """Fixed directed edge support with trainable positive gains.

    `node_ids`, `input_node_ids`, `output_node_ids`, and edge tuples are all
    supplied by the caller. Input/output order is preserved exactly. Each
    edge tuple is `(source_id, target_id, source_weight)`.
    """

    def __init__(
        self,
        node_ids: Sequence[int],
        input_node_ids: Sequence[int],
        output_node_ids: Sequence[int],
        edges: Sequence[tuple[int, int, int]],
        steps: int = 2,
    ) -> None:
        super().__init__()
        self.node_ids = _checked_ids("node_ids", node_ids)
        self.input_node_ids = _checked_ids("input_node_ids", input_node_ids)
        self.output_node_ids = _checked_ids("output_node_ids", output_node_ids)
        if isinstance(steps, bool) or not isinstance(steps, int) or steps < 1:
            raise GraphCoreError("steps must be a positive integer")
        self.steps = steps
        self.epsilon = EPSILON

        node_set = set(self.node_ids)
        if not set(self.input_node_ids).issubset(node_set):
            raise GraphCoreError("input_node_ids must belong to node_ids")
        if not set(self.output_node_ids).issubset(node_set):
            raise GraphCoreError("output_node_ids must belong to node_ids")
        if not set(self.input_node_ids).isdisjoint(self.output_node_ids):
            raise GraphCoreError("input_node_ids and output_node_ids must be disjoint")

        checked_edges: list[tuple[int, int, int]] = []
        seen_pairs: set[tuple[int, int]] = set()
        for row in edges:
            if not isinstance(row, (tuple, list)) or len(row) != 3:
                raise GraphCoreError("each edge must be (source_id, target_id, weight)")
            source_id, target_id, weight = row
            if any(isinstance(value, bool) or not isinstance(value, int) for value in row[:2]):
                raise GraphCoreError("edge endpoints must be integer node IDs")
            if source_id not in node_set or target_id not in node_set:
                raise GraphCoreError("edge endpoints must belong to node_ids")
            if isinstance(weight, bool) or not isinstance(weight, int) or weight < 0:
                raise GraphCoreError("source weights must be non-negative integers")
            pair = (source_id, target_id)
            if pair in seen_pairs:
                raise GraphCoreError("duplicate directed edge pair in fixture")
            seen_pairs.add(pair)
            checked_edges.append((source_id, target_id, weight))
        if not checked_edges:
            raise GraphCoreError("edges must not be empty")
        self.edges = tuple(checked_edges)
        self.node_index = {node_id: index for index, node_id in enumerate(self.node_ids)}

        in_degrees_by_id = {node_id: 0 for node_id in self.node_ids}
        for _, target_id, _ in self.edges:
            in_degrees_by_id[target_id] += 1
        raw_init = _initial_raw_edge_parameters(self.edges, in_degrees_by_id)
        if not all(math.isfinite(value) for value in raw_init):
            raise GraphCoreError("edge initialization produced a non-finite parameter")

        source_index = torch.tensor(
            [self.node_index[source] for source, _, _ in self.edges], dtype=torch.long
        )
        target_index = torch.tensor(
            [self.node_index[target] for _, target, _ in self.edges], dtype=torch.long
        )
        input_index = torch.tensor(
            [self.node_index[node_id] for node_id in self.input_node_ids], dtype=torch.long
        )
        output_index = torch.tensor(
            [self.node_index[node_id] for node_id in self.output_node_ids], dtype=torch.long
        )
        in_degrees = torch.tensor(
            [in_degrees_by_id[node_id] for node_id in self.node_ids], dtype=torch.long
        )
        self.register_buffer("source_index", source_index)
        self.register_buffer("target_index", target_index)
        self.register_buffer("input_index", input_index)
        self.register_buffer("output_index", output_index)
        self.register_buffer("in_degrees", in_degrees)
        self.raw_edge_parameters = nn.Parameter(torch.tensor(raw_init, dtype=torch.float32))

    @property
    def edge_gains(self) -> torch.Tensor:
        return F.softplus(self.raw_edge_parameters) + self.epsilon

    @property
    def topology_sha256(self) -> str:
        payload = {
            "node_ids": self.node_ids,
            "input_node_ids": self.input_node_ids,
            "output_node_ids": self.output_node_ids,
            "edges": self.edges,
        }
        encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def forward(self, input_drives: torch.Tensor) -> torch.Tensor:
        if not isinstance(input_drives, torch.Tensor):
            raise GraphCoreError("input_drives must be an in-memory torch.Tensor")
        if input_drives.ndim != 2 or input_drives.shape[1] != len(self.input_node_ids):
            raise GraphCoreError(
                f"input_drives must have shape (batch, {len(self.input_node_ids)})"
            )
        if not input_drives.is_floating_point() or input_drives.dtype != self.raw_edge_parameters.dtype:
            raise GraphCoreError("input_drives must use the model floating-point dtype")
        if input_drives.device != self.raw_edge_parameters.device:
            raise GraphCoreError("input_drives and graph parameters must be on the same device")
        if not torch.all(torch.isfinite(input_drives)):
            raise GraphCoreError("input_drives must contain only finite values")

        batch_size = input_drives.shape[0]
        hidden = torch.zeros(
            (batch_size, len(self.node_ids)),
            dtype=input_drives.dtype,
            device=input_drives.device,
        )
        input_drive_by_node = torch.zeros_like(hidden).index_copy(
            1, self.input_index, input_drives
        )
        degree = self.in_degrees.clamp_min(1).to(dtype=input_drives.dtype).unsqueeze(0)
        gains = self.edge_gains

        for _ in range(self.steps):
            messages = hidden.index_select(1, self.source_index) * gains.unsqueeze(0)
            aggregated = torch.zeros_like(hidden).index_add(
                1, self.target_index, messages
            )
            hidden = torch.tanh(aggregated / degree + input_drive_by_node)

        return hidden.index_select(1, self.output_index)

    def checkpoint_metadata(self) -> dict[str, object]:
        return {
            "node_ids": list(self.node_ids),
            "input_node_ids": list(self.input_node_ids),
            "output_node_ids": list(self.output_node_ids),
            "edges": [list(edge) for edge in self.edges],
            "topology_sha256": self.topology_sha256,
            "steps": self.steps,
            "epsilon": self.epsilon,
            "edge_init": "per-target-mean-one-log1p-inverse-softplus",
            "aggregation": "fixed-indegree-including-self-loops",
            "edge_parameter_count": len(self.edges),
        }


class FlyA(nn.Module):
    """Fixture Fly A: d-dimensional embeddings to ordered normalized 32-vector."""

    def __init__(self, embedding_dim: int, graph_core: SparseGraphCore) -> None:
        super().__init__()
        if isinstance(embedding_dim, bool) or not isinstance(embedding_dim, int) or embedding_dim < 1:
            raise GraphCoreError("embedding_dim must be a positive integer")
        if len(graph_core.input_node_ids) != 32 or len(graph_core.output_node_ids) != 32:
            raise GraphCoreError("Fly A graph must have 32 ordered input and output nodes")
        self.embedding_dim = embedding_dim
        self.input_projection = nn.Linear(embedding_dim, 32)
        self.graph_core = graph_core

    @property
    def parameter_counts(self) -> dict[str, int]:
        adapter = sum(parameter.numel() for parameter in self.input_projection.parameters())
        core = self.graph_core.raw_edge_parameters.numel()
        return {"adapter": adapter, "graph_core": core, "readout": 0, "total": adapter + core}

    def forward(self, embeddings: torch.Tensor) -> torch.Tensor:
        if not isinstance(embeddings, torch.Tensor):
            raise GraphCoreError("embeddings must be an in-memory torch.Tensor")
        if embeddings.ndim != 2 or embeddings.shape[1] != self.embedding_dim:
            raise GraphCoreError(f"embeddings must have shape (batch, {self.embedding_dim})")
        if not embeddings.is_floating_point() or embeddings.dtype != self.input_projection.weight.dtype:
            raise GraphCoreError("embeddings must use the model floating-point dtype")
        if not torch.all(torch.isfinite(embeddings)):
            raise GraphCoreError("embeddings must contain only finite values")
        norm = torch.linalg.vector_norm(embeddings, ord=2, dim=1, keepdim=True)
        if torch.any(norm <= 0):
            raise GraphCoreError("embeddings must have non-zero L2 norm")
        normalized = embeddings / norm
        drives = torch.tanh(self.input_projection(normalized))
        output = self.graph_core(drives)
        output_norm = torch.linalg.vector_norm(output, ord=2, dim=1, keepdim=True)
        if torch.any(output_norm <= 0):
            raise GraphCoreError("Fly A output has zero L2 norm")
        return output / output_norm

    def checkpoint_metadata(self) -> dict[str, object]:
        return {
            "model_kind": "FlyA",
            "embedding_dim": self.embedding_dim,
            "input_projection_width": 32,
            "projection_parameter_count": self.parameter_counts["adapter"],
            "parameter_counts": self.parameter_counts,
            "graph_core": self.graph_core.checkpoint_metadata(),
        }


class FlyB(nn.Module):
    """Fixture Fly B: ordered 32-vector to fixed-taxonomy 5-class logits."""

    def __init__(
        self,
        graph_core: SparseGraphCore,
        label_order: Sequence[str] = CLASS_ORDER,
    ) -> None:
        super().__init__()
        self.label_order = tuple(label_order)
        if self.label_order != CLASS_ORDER:
            raise GraphCoreError("label_order must match the fixed taxonomy order")
        if len(graph_core.input_node_ids) != 32 or len(graph_core.output_node_ids) != 32:
            raise GraphCoreError("Fly B graph must have 32 ordered input and output nodes")
        self.input_adapter = nn.Linear(32, 32)
        self.graph_core = graph_core
        self.readout = nn.Linear(32, len(self.label_order))

    @property
    def parameter_counts(self) -> dict[str, int]:
        adapter = sum(parameter.numel() for parameter in self.input_adapter.parameters())
        core = self.graph_core.raw_edge_parameters.numel()
        readout = sum(parameter.numel() for parameter in self.readout.parameters())
        return {
            "adapter": adapter,
            "graph_core": core,
            "readout": readout,
            "total": adapter + core + readout,
        }

    def forward(self, fly_a_output: torch.Tensor) -> torch.Tensor:
        if not isinstance(fly_a_output, torch.Tensor):
            raise GraphCoreError("fly_a_output must be an in-memory torch.Tensor")
        if fly_a_output.ndim != 2 or fly_a_output.shape[1] != 32:
            raise GraphCoreError("fly_a_output must have shape (batch, 32)")
        if not fly_a_output.is_floating_point() or fly_a_output.dtype != self.input_adapter.weight.dtype:
            raise GraphCoreError("fly_a_output must use the model floating-point dtype")
        if not torch.all(torch.isfinite(fly_a_output)):
            raise GraphCoreError("fly_a_output must contain only finite values")
        drives = self.input_adapter(fly_a_output)
        graph_output = self.graph_core(drives)
        return self.readout(graph_output)

    def checkpoint_metadata(self) -> dict[str, object]:
        return {
            "model_kind": "FlyB",
            "input_width": 32,
            "output_width": 5,
            "label_order": list(self.label_order),
            "parameter_counts": self.parameter_counts,
            "graph_core": self.graph_core.checkpoint_metadata(),
        }


class FlyBWithE5Residual(nn.Module):
    """Exploratory Fly B that adds a gated E5 residual before its graph core.

    Both the Fly A adapter output and the projected E5 residual become drives
    for Fly B's ordered input nodes. Classification still passes through the
    Fly B graph core and readout; there is no encoder-to-readout shortcut.
    """

    def __init__(
        self,
        graph_core: SparseGraphCore,
        embedding_dim: int = 384,
        label_order: Sequence[str] = CLASS_ORDER,
        gate_logit_init: float = -2.0,
    ) -> None:
        super().__init__()
        if isinstance(embedding_dim, bool) or not isinstance(embedding_dim, int) or embedding_dim < 1:
            raise GraphCoreError("embedding_dim must be a positive integer")
        if not isinstance(gate_logit_init, (int, float)) or not torch.isfinite(torch.tensor(float(gate_logit_init))):
            raise GraphCoreError("gate_logit_init must be finite")
        self.fly_b = FlyB(graph_core, label_order=label_order)
        self.embedding_dim = embedding_dim
        self.gate_logit_init = float(gate_logit_init)
        self.e5_residual_projection = nn.Linear(embedding_dim, 32, bias=False)
        self.residual_gate_logit = nn.Parameter(torch.tensor(self.gate_logit_init))

    @property
    def parameter_counts(self) -> dict[str, int]:
        residual = sum(parameter.numel() for parameter in self.e5_residual_projection.parameters())
        return {
            **self.fly_b.parameter_counts,
            "e5_residual_projection": residual,
            "residual_gate": self.residual_gate_logit.numel(),
            "total": self.fly_b.parameter_counts["total"] + residual + self.residual_gate_logit.numel(),
        }

    @property
    def residual_gate(self) -> torch.Tensor:
        """Current blend weight in [0, 1], exposed for diagnostics and reporting."""

        return torch.sigmoid(self.residual_gate_logit)

    def forward(self, fly_a_output: torch.Tensor, e5_embedding: torch.Tensor) -> torch.Tensor:
        if not isinstance(fly_a_output, torch.Tensor) or not isinstance(e5_embedding, torch.Tensor):
            raise GraphCoreError("Fly A output and E5 embedding must be in-memory tensors")
        if fly_a_output.ndim != 2 or fly_a_output.shape[1] != 32:
            raise GraphCoreError("fly_a_output must have shape (batch, 32)")
        if e5_embedding.ndim != 2 or e5_embedding.shape != (fly_a_output.shape[0], self.embedding_dim):
            raise GraphCoreError(f"e5_embedding must have shape (batch, {self.embedding_dim})")
        if (
            not fly_a_output.is_floating_point()
            or not e5_embedding.is_floating_point()
            or fly_a_output.dtype != self.fly_b.input_adapter.weight.dtype
            or e5_embedding.dtype != self.e5_residual_projection.weight.dtype
            or fly_a_output.device != e5_embedding.device
        ):
            raise GraphCoreError("Fly A output and E5 embedding must share the model dtype and device")
        if not torch.all(torch.isfinite(fly_a_output)) or not torch.all(torch.isfinite(e5_embedding)):
            raise GraphCoreError("Fly A output and E5 embedding must contain only finite values")
        fly_a_drives = self.fly_b.input_adapter(fly_a_output)
        e5_residual = self.e5_residual_projection(e5_embedding)
        drives = fly_a_drives + self.residual_gate * e5_residual
        graph_output = self.fly_b.graph_core(drives)
        return self.fly_b.readout(graph_output)

    def checkpoint_metadata(self) -> dict[str, object]:
        return {
            "model_kind": "FlyBWithE5Residual",
            "input_width": 32,
            "e5_embedding_dim": self.embedding_dim,
            "output_width": 5,
            "label_order": list(self.fly_b.label_order),
            "parameter_counts": self.parameter_counts,
            "fusion": "fly_b_adapter(fly_a_output)+sigmoid(gate)*bias_free_e5_projection(e5_embedding)",
            "gate_logit_init": self.gate_logit_init,
            "classifier_shortcut": False,
            "graph_core": self.fly_b.graph_core.checkpoint_metadata(),
        }


def distance_preserving_loss(
    embeddings: torch.Tensor, representations: torch.Tensor
) -> torch.Tensor:
    """Mean squared pair-distance error over distinct pairs in a batch."""
    if not isinstance(embeddings, torch.Tensor) or not isinstance(representations, torch.Tensor):
        raise GraphCoreError("distance loss accepts only in-memory tensors")
    if embeddings.ndim != 2 or representations.ndim != 2:
        raise GraphCoreError("distance loss inputs must be rank-2 tensors")
    if embeddings.shape[0] != representations.shape[0] or embeddings.shape[0] < 2:
        raise GraphCoreError("distance loss requires matching batches with at least two rows")
    if embeddings.device != representations.device or embeddings.dtype != representations.dtype:
        raise GraphCoreError("distance loss inputs must share dtype and device")
    if not torch.all(torch.isfinite(embeddings)) or not torch.all(torch.isfinite(representations)):
        raise GraphCoreError("distance loss inputs must be finite")
    embedding_norms = torch.linalg.vector_norm(embeddings, ord=2, dim=1, keepdim=True)
    representation_norms = torch.linalg.vector_norm(
        representations, ord=2, dim=1, keepdim=True
    )
    if torch.any(embedding_norms <= 0) or torch.any(representation_norms <= 0):
        raise GraphCoreError("distance loss inputs must have non-zero L2 norms")
    normalized_embeddings = embeddings / embedding_norms
    normalized_representations = representations / representation_norms
    embedding_distances = torch.pdist(normalized_embeddings, p=2)
    representation_distances = torch.pdist(normalized_representations, p=2)
    return torch.mean((embedding_distances - representation_distances) ** 2)


def save_model_checkpoint(model: nn.Module, path: str | Path) -> None:
    """Save a fixture model state with strict M3.0 contract metadata."""
    metadata_method = getattr(model, "checkpoint_metadata", None)
    if not callable(metadata_method):
        raise GraphCoreError("model must provide checkpoint_metadata()")
    destination = Path(path)
    payload = {"metadata": metadata_method(), "state_dict": model.state_dict()}
    torch.save(payload, destination)


def load_model_checkpoint(model: nn.Module, path: str | Path) -> None:
    """Load a CPU checkpoint only when its contract metadata matches the model."""
    metadata_method = getattr(model, "checkpoint_metadata", None)
    if not callable(metadata_method):
        raise GraphCoreError("model must provide checkpoint_metadata()")
    try:
        payload = torch.load(Path(path), map_location="cpu", weights_only=True)
    except Exception as exc:
        raise GraphCoreError(f"could not load fixture checkpoint: {exc}") from exc
    if not isinstance(payload, dict) or "metadata" not in payload or "state_dict" not in payload:
        raise GraphCoreError("checkpoint is missing metadata or state_dict")
    if payload["metadata"] != metadata_method():
        raise GraphCoreError("checkpoint contract metadata does not match model")
    try:
        model.load_state_dict(payload["state_dict"], strict=True)
    except Exception as exc:
        raise GraphCoreError(f"checkpoint state_dict is incompatible: {exc}") from exc

"""Central, non-loading model target configuration for embedding workflows.

The selected E5 values describe a target for a future restricted CPU trial.
This module never resolves, downloads, or instantiates model dependencies.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .embedding_pipeline import EmbeddingSettings


@dataclass(frozen=True)
class EmbeddingModelConfig:
    """Immutable model identity and trial settings, separate from runtime IO."""

    model_id: str
    revision: str
    prefix: str
    max_seq_length: int
    output_dimension: int
    pooling: str
    normalize_embeddings: bool
    trial_device: str
    trial_batch_size: int
    status: str

    def __post_init__(self) -> None:
        for name in ("model_id", "revision", "pooling", "trial_device", "status"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{name} must be a non-empty string.")
        if not isinstance(self.prefix, str):
            raise ValueError("prefix must be a string.")
        if not isinstance(self.max_seq_length, int) or self.max_seq_length < 1:
            raise ValueError("max_seq_length must be a positive integer.")
        if not isinstance(self.output_dimension, int) or self.output_dimension < 1:
            raise ValueError("output_dimension must be a positive integer.")
        if not isinstance(self.normalize_embeddings, bool):
            raise ValueError("normalize_embeddings must be a boolean.")
        if not isinstance(self.trial_batch_size, int) or self.trial_batch_size < 1:
            raise ValueError("trial_batch_size must be a positive integer.")

    def embedding_settings(
        self,
        *,
        preprocessing_version: str,
        truncation_policy: str,
        dtype: str = "float32",
    ) -> EmbeddingSettings:
        """Build a cache-key settings value without loading the model."""

        from .embedding_pipeline import EmbeddingSettings

        return EmbeddingSettings(
            model_id=self.model_id,
            revision=self.revision,
            tokenizer_revision=self.revision,
            prefix=self.prefix,
            preprocessing_version=preprocessing_version,
            max_seq_length=self.max_seq_length,
            truncation_policy=truncation_policy,
            pooling=self.pooling,
            normalize_embeddings=self.normalize_embeddings,
            dtype=dtype,
            output_dimension=self.output_dimension,
            device=self.trial_device,
            batch_size=self.trial_batch_size,
        )


E5_SMALL_CONFIG = EmbeddingModelConfig(
    model_id="intfloat/multilingual-e5-small",
    revision="614241f622f53c4eeff9890bdc4f31cfecc418b3",
    prefix="query: ",
    max_seq_length=512,
    output_dimension=384,
    pooling="masked_mean",
    normalize_embeddings=True,
    trial_device="cpu",
    trial_batch_size=1,
    status="selected_not_downloaded_or_loaded",
)

"""Pinned, local-only runtime for the multilingual-e5-small trial.

Optional model dependencies are imported only when :func:`load_e5_encoder` is
called. Loading requires an already downloaded snapshot at the pinned revision;
this module never downloads a model or executes repository code.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from .model_config import E5_SMALL_CONFIG


E5_MODEL_FILES: tuple[tuple[str, int, str], ...] = (
    (
        "1_Pooling/config.json",
        200,
        "987f7a67a38fa564c849bb5d277c52ab9088a84368fc0be31a354125aebb12a0",
    ),
    (
        "config.json",
        655,
        "69137736cab8b8903a07fe8afaafdda25aac55415a12a55d1bffa9f581abf959",
    ),
    (
        "model.safetensors",
        470_641_600,
        "1a55775f53449dac10a2bcbc312469fac40b96d53198c407081a831f81c98477",
    ),
    (
        "modules.json",
        387,
        "c6e29747481e8b5dd2b58401966aeac910de39092f90cda9a704b1545f902b04",
    ),
    (
        "sentence_bert_config.json",
        57,
        "948201d8329907aae938fa62f9ceeed53f5694dacc2b87b9f3b78b37ee986529",
    ),
    (
        "sentencepiece.bpe.model",
        5_069_051,
        "cfc8146abe2a0488e9e2a0c56de7952f7c11ab059eca145a0a727afce0db2865",
    ),
    (
        "special_tokens_map.json",
        167,
        "d05497f1da52c5e09554c0cd874037a083e1dc1b9cfd48034d1c717f1afc07a7",
    ),
    (
        "tokenizer.json",
        17_082_730,
        "0b44a9d7b51c3c62626640cda0e2c2f70fdacdc25bbbd68038369d14ebdf4c39",
    ),
    (
        "tokenizer_config.json",
        443,
        "a1d6bc8734a6f635dc158508bef000f8e2e5a759c7d92f984b2c86e5ff53425b",
    ),
)
E5_MODEL_FILE_SHA256 = tuple(sorted((name, digest) for name, _size, digest in E5_MODEL_FILES))
EXPECTED_TOKENIZER_CLASS = "XLMRobertaTokenizer"
EXPECTED_TOKENIZER_NORMALIZER = "Precompiled"
EXPECTED_TOKENIZER_NORMALIZER_SHA256 = "c1944f72967dbd5754934af4c2d87d050c6fb4e8a8321b607b0edc4f57ec6c23"


@dataclass(frozen=True)
class TokenizationDiagnostic:
    """Per-input token counts before and after the configured right truncation."""

    input_index: int
    raw_token_count: int
    effective_token_count: int
    truncated: bool
    truncated_token_count: int

    def as_dict(self) -> dict[str, int | bool]:
        return {
            "input_index": self.input_index,
            "raw_token_count": self.raw_token_count,
            "effective_token_count": self.effective_token_count,
            "truncated": self.truncated,
            "truncated_token_count": self.truncated_token_count,
        }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_e5_snapshot(snapshot_dir: Path) -> dict[str, Any]:
    """Verify the exact pinned local snapshot and return its file hashes."""

    snapshot = Path(snapshot_dir).resolve(strict=True)
    if snapshot.name != E5_SMALL_CONFIG.revision:
        raise ValueError(
            f"E5 snapshot directory must end in pinned revision {E5_SMALL_CONFIG.revision}."
        )
    verified: dict[str, str] = {}
    for relative_name, expected_size, expected_digest in E5_MODEL_FILES:
        path = snapshot / relative_name
        if not path.is_file():
            raise FileNotFoundError(f"required E5 model file is missing: {relative_name}")
        actual_size = path.stat().st_size
        if actual_size != expected_size:
            raise ValueError(
                f"E5 model file size mismatch for {relative_name}: "
                f"expected {expected_size}, got {actual_size}."
            )
        actual_digest = _sha256_file(path)
        if actual_digest != expected_digest:
            raise ValueError(f"E5 model SHA-256 mismatch for {relative_name}.")
        verified[relative_name] = actual_digest
    return {
        "model_id": E5_SMALL_CONFIG.model_id,
        "revision": E5_SMALL_CONFIG.revision,
        "snapshot_path": str(snapshot),
        "total_bytes": sum(size for _name, size, _digest in E5_MODEL_FILES),
        "files": [
            {"path": name, "bytes": size, "sha256": verified[name]}
            for name, size, _digest in E5_MODEL_FILES
        ],
    }


def _read_model_contract(snapshot: Path) -> dict[str, Any]:
    modules = json.loads((snapshot / "modules.json").read_text(encoding="utf-8"))
    if not isinstance(modules, list):
        raise ValueError("E5 modules.json must contain a list.")
    pooling_entries = [item for item in modules if str(item.get("type", "")).endswith(".Pooling")]
    normalize_entries = [item for item in modules if str(item.get("type", "")).endswith(".Normalize")]
    transformer_entries = [item for item in modules if str(item.get("type", "")).endswith(".Transformer")]
    if (
        len(modules) != 3
        or len(pooling_entries) != 1
        or len(normalize_entries) != 1
        or len(transformer_entries) != 1
    ):
        raise ValueError("Pinned E5 modules.json must contain one Transformer, Pooling, and Normalize module.")
    ordered_types = [str(item.get("type", "")) for item in modules]
    if not (
        ordered_types[0].endswith(".Transformer")
        and ordered_types[1].endswith(".Pooling")
        and ordered_types[2].endswith(".Normalize")
    ):
        raise ValueError("Pinned E5 modules must run Transformer, mean pooling, then normalization in order.")

    pooling_path = snapshot / str(pooling_entries[0].get("path", "")) / "config.json"
    pooling = json.loads(pooling_path.read_text(encoding="utf-8"))
    if pooling.get("pooling_mode_mean_tokens") is not True:
        raise ValueError("Pinned E5 model does not enable masked mean-token pooling.")
    for key in ("pooling_mode_cls_token", "pooling_mode_max_tokens", "pooling_mode_mean_sqrt_len_tokens", "pooling_mode_weightedmean_tokens", "pooling_mode_lasttoken"):
        if pooling.get(key, False) is not False:
            raise ValueError(f"Pinned E5 pooling config unexpectedly enables {key}.")
    config = json.loads((snapshot / "config.json").read_text(encoding="utf-8"))
    if config.get("hidden_size") != E5_SMALL_CONFIG.output_dimension:
        raise ValueError("Pinned E5 transformer hidden size differs from the 384-dimensional contract.")
    return {
        "modules": [item["type"] for item in modules],
        "pooling_config": pooling,
        "normalization_module": normalize_entries[0]["type"],
        "transformer_module": transformer_entries[0]["type"],
        "hidden_size": config["hidden_size"],
    }


def _normalizer_digest(tokenizer: Any) -> tuple[str, str]:
    backend = getattr(tokenizer, "backend_tokenizer", None)
    normalizer = getattr(backend, "normalizer", None)
    if normalizer is None:
        raise ValueError("E5 tokenizer does not expose the expected backend normalizer.")
    state = normalizer.__getstate__()
    if isinstance(state, str):
        state_bytes = state.encode("utf-8")
    elif isinstance(state, bytes):
        state_bytes = state
    else:
        state_bytes = json.dumps(state, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return type(normalizer).__name__, hashlib.sha256(state_bytes).hexdigest()


def _sequence_length(values: Any) -> int:
    if hasattr(values, "sum") and hasattr(values, "item"):
        return int(values.sum().item())
    if isinstance(values, (list, tuple)):
        return len(values)
    raise TypeError("tokenizer returned an unsupported input_ids or attention_mask value.")


def inspect_tokenization(
    tokenizer: Any,
    transformer_module: Any,
    texts: Sequence[str],
    *,
    max_seq_length: int,
) -> tuple[TokenizationDiagnostic, ...]:
    """Measure untruncated and effective token counts without sending text to a model."""

    if not isinstance(max_seq_length, int) or max_seq_length < 1:
        raise ValueError("max_seq_length must be a positive integer.")
    if not texts:
        return ()
    diagnostics: list[TokenizationDiagnostic] = []
    batch_size = 32
    for batch_start in range(0, len(texts), batch_size):
        batch_texts = list(texts[batch_start : batch_start + batch_size])
        for text in batch_texts:
            if not isinstance(text, str):
                raise ValueError("tokenization inputs must be strings.")
            text.encode("utf-8", errors="strict")
        raw = tokenizer(
            batch_texts,
            add_special_tokens=True,
            truncation=False,
            padding=False,
            return_attention_mask=False,
        )
        raw_counts = [_sequence_length(token_ids) for token_ids in raw["input_ids"]]

        # Sentence Transformers 6 preprocess is the same public path used by
        # encode(), and keeps this audit aligned with the configured truncation.
        effective = transformer_module.preprocess(batch_texts)
        if "attention_mask" in effective:
            effective_counts = [
                int(value)
                for value in effective["attention_mask"].sum(dim=1).tolist()
            ]
        else:
            effective_counts = [
                _sequence_length(token_ids) for token_ids in effective["input_ids"]
            ]
        if len(raw_counts) != len(batch_texts) or len(effective_counts) != len(batch_texts):
            raise ValueError("tokenizer diagnostic batch did not preserve input order and count.")

        for offset, (raw_count, effective_count) in enumerate(zip(raw_counts, effective_counts, strict=True)):
            index = batch_start + offset
            if effective_count > max_seq_length:
                raise ValueError(
                    f"effective tokenizer length {effective_count} exceeds max_seq_length {max_seq_length}."
                )
            if effective_count > raw_count:
                raise ValueError("effective token count cannot exceed the untruncated count.")
            diagnostics.append(
                TokenizationDiagnostic(
                    input_index=index,
                    raw_token_count=raw_count,
                    effective_token_count=effective_count,
                    truncated=effective_count < raw_count,
                    truncated_token_count=max(0, raw_count - effective_count),
                )
            )
    return tuple(diagnostics)


class E5SmallEncoder:
    """Frozen CPU encoder bound to the pinned, checksum-verified snapshot."""

    def __init__(self, model: Any, tokenizer: Any, model_manifest: dict[str, Any]) -> None:
        self.model = model
        self.tokenizer = tokenizer
        self.model_manifest = model_manifest
        self.transformer_module = model[0]
        self.max_seq_length = E5_SMALL_CONFIG.max_seq_length
        self.prefix = E5_SMALL_CONFIG.prefix
        self.last_tokenization_diagnostics: tuple[TokenizationDiagnostic, ...] = ()

    def inspect(self, texts: Sequence[str]) -> tuple[TokenizationDiagnostic, ...]:
        diagnostics = inspect_tokenization(
            self.tokenizer,
            self.transformer_module,
            texts,
            max_seq_length=self.max_seq_length,
        )
        self.last_tokenization_diagnostics = diagnostics
        return diagnostics

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        values = list(texts)
        if not values:
            return []
        if any(not isinstance(text, str) or not text.startswith(self.prefix) for text in values):
            raise ValueError(f"every E5 input must already start with {self.prefix!r}.")
        diagnostics = self.inspect(values)
        encoded = self.model.encode(
            values,
            batch_size=E5_SMALL_CONFIG.trial_batch_size,
            show_progress_bar=False,
            convert_to_numpy=True,
            normalize_embeddings=False,
        )
        if getattr(encoded, "ndim", None) != 2 or encoded.shape != (len(values), E5_SMALL_CONFIG.output_dimension):
            raise ValueError(
                f"E5 returned shape {getattr(encoded, 'shape', None)}; expected "
                f"({len(values)}, {E5_SMALL_CONFIG.output_dimension})."
            )
        vectors: list[list[float]] = []
        for row_index, row in enumerate(encoded):
            vector = [float(value) for value in row]
            if not all(math.isfinite(value) for value in vector):
                raise ValueError("E5 returned a non-finite embedding value.")
            norm = math.sqrt(sum(value * value for value in vector))
            if not math.isclose(norm, 1.0, rel_tol=1e-4, abs_tol=1e-4):
                raise ValueError(f"E5 normalization module returned vector norm {norm:.8f}, expected 1.")
            vectors.append(vector)
        self.last_tokenization_diagnostics = diagnostics
        return vectors


def load_e5_encoder(snapshot_dir: Path, *, num_threads: int = 1) -> E5SmallEncoder:
    """Load the pinned E5 snapshot locally on CPU after verifying every file."""

    if not isinstance(num_threads, int) or num_threads < 1:
        raise ValueError("num_threads must be a positive integer.")
    snapshot = Path(snapshot_dir).resolve(strict=True)
    model_manifest = verify_e5_snapshot(snapshot)
    contract = _read_model_contract(snapshot)
    try:
        import torch
        from sentence_transformers import SentenceTransformer
    except ImportError as error:
        raise RuntimeError("E5 runtime requires the pinned Sentence Transformers CPU environment.") from error

    torch.set_num_threads(num_threads)
    torch.set_num_interop_threads(1)
    model = SentenceTransformer(
        str(snapshot),
        device=E5_SMALL_CONFIG.trial_device,
        trust_remote_code=False,
        local_files_only=True,
    )
    model.max_seq_length = E5_SMALL_CONFIG.max_seq_length
    model.eval()
    for parameter in model.parameters():
        parameter.requires_grad_(False)
        if parameter.device.type != "cpu":
            raise ValueError("E5 trial model must remain on CPU.")
    if model.get_embedding_dimension() != E5_SMALL_CONFIG.output_dimension:
        raise ValueError("E5 runtime output dimension differs from the pinned 384-dimensional contract.")
    if model.max_seq_length != E5_SMALL_CONFIG.max_seq_length:
        raise ValueError("E5 runtime sequence length differs from the pinned 512-token contract.")

    tokenizer = model.tokenizer
    if type(tokenizer).__name__ != EXPECTED_TOKENIZER_CLASS:
        raise ValueError(f"unexpected E5 tokenizer class: {type(tokenizer).__name__}.")
    if getattr(tokenizer, "truncation_side", None) != "right":
        raise ValueError("E5 tokenizer must use explicit right-side truncation.")
    normalizer_name, normalizer_digest = _normalizer_digest(tokenizer)
    if normalizer_name != EXPECTED_TOKENIZER_NORMALIZER:
        raise ValueError(f"unexpected E5 tokenizer normalizer: {normalizer_name}.")
    if normalizer_digest != EXPECTED_TOKENIZER_NORMALIZER_SHA256:
        raise ValueError("E5 tokenizer normalizer digest differs from the verified pinned runtime.")
    if contract["hidden_size"] != E5_SMALL_CONFIG.output_dimension:
        raise ValueError("verified model config and runtime output dimensions differ.")

    model_manifest.update(
        {
            "modules": contract["modules"],
            "pooling": "masked_mean",
            "normalization": "model Normalize module; output norm checked at runtime",
            "output_dimension": model.get_embedding_dimension(),
            "max_seq_length": model.max_seq_length,
            "device": E5_SMALL_CONFIG.trial_device,
            "batch_size": E5_SMALL_CONFIG.trial_batch_size,
            "tokenizer_class": type(tokenizer).__name__,
            "tokenizer_normalizer": normalizer_name,
            "tokenizer_normalizer_sha256": normalizer_digest,
            "truncation_side": tokenizer.truncation_side,
            "trust_remote_code": False,
            "local_files_only": True,
            "model_frozen": all(not parameter.requires_grad for parameter in model.parameters()),
        }
    )
    return E5SmallEncoder(model, tokenizer, model_manifest)

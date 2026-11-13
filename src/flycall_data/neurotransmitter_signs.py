"""Map MaleCNS v1.0 neurotransmitter labels to fixed neuron signs (ticket 18).

Input is the official ``body-neurotransmitters-male-cns-v1.0.feather`` table.
The recommended ``consensus_nt`` column is used as-is: MaleCNS already marks a
neuron ``unclear`` when it has < 50 presynapses / low confidence and its cell
type has < 100 presynapses or celltype confidence < 0.5, and overrides with
experimental ground truth where available (Berg et al. 2026, Cell, Methods).
No second confidence threshold is applied here.

Sign rules (decided 2026-11-13):
- acetylcholine → +1
- gaba → −1
- glutamate → −1 (primary) / +1 (sensitivity variant)
- histamine → −1
- dopamine, octopamine, serotonin → excluded (modulatory)
- unclear / missing → excluded
"""

from __future__ import annotations

from collections import Counter
from typing import Iterable, Mapping

import pyarrow as pa

EXCITATORY, INHIBITORY, EXCLUDED = 1, -1, 0
REQUIRED_COLUMNS = ("body", "cell_type", "consensus_nt", "ground_truth", "celltype_predicted_nt_confidence")
FAST_SIGNS = {"acetylcholine": EXCITATORY, "gaba": INHIBITORY, "histamine": INHIBITORY}
GLUTAMATE = "glutamate"
MODULATORY = frozenset({"dopamine", "octopamine", "serotonin"})
UNCLEAR = "unclear"
KNOWN_LABELS = frozenset(FAST_SIGNS) | {GLUTAMATE, UNCLEAR} | MODULATORY
SIGN_VARIANTS = {"sign_glu_inhibitory": INHIBITORY, "sign_glu_excitatory": EXCITATORY}


class NeurotransmitterSignError(ValueError):
    """Raised when the source table violates the expected contract."""


def sign_for(label: str | None, *, glutamate_sign: int) -> tuple[int, str]:
    """Return (sign, reason) for one consensus label; unknown labels fail."""

    if glutamate_sign not in (EXCITATORY, INHIBITORY):
        raise NeurotransmitterSignError("glutamate_sign must be +1 or -1.")
    if label is None or label == UNCLEAR:
        return EXCLUDED, "unclear_or_missing"
    if label not in KNOWN_LABELS:
        raise NeurotransmitterSignError(f"unexpected consensus_nt label {label!r}; extend the mapping explicitly.")
    if label in MODULATORY:
        return EXCLUDED, "modulatory"
    if label == GLUTAMATE:
        return glutamate_sign, "glutamate"
    return FAST_SIGNS[label], label


def build_sign_table(source: pa.Table) -> pa.Table:
    """Derive the per-neuron sign table; the source table is not modified."""

    missing = [name for name in REQUIRED_COLUMNS if name not in source.schema.names]
    if missing:
        raise NeurotransmitterSignError(f"source table lacks columns: {missing}")
    bodies = source["body"].to_pylist()
    if any(body is None for body in bodies) or len(set(bodies)) != len(bodies):
        raise NeurotransmitterSignError("body IDs must be present and unique.")
    if not pa.types.is_int64(source.schema.field("body").type):
        raise NeurotransmitterSignError("body IDs must be int64 (no float round-trip).")
    labels = source["consensus_nt"].to_pylist()
    primary, sensitivity, reasons = [], [], []
    for label in labels:
        sign, reason = sign_for(label, glutamate_sign=INHIBITORY)
        primary.append(sign)
        reasons.append(reason)
        sensitivity.append(sign_for(label, glutamate_sign=EXCITATORY)[0])
    return pa.table({
        "body": source["body"],
        "cell_type": source["cell_type"],
        "consensus_nt": source["consensus_nt"],
        "ground_truth": source["ground_truth"],
        "celltype_predicted_nt_confidence": source["celltype_predicted_nt_confidence"],
        "sign_glu_inhibitory": pa.array(primary, type=pa.int8()),
        "sign_glu_excitatory": pa.array(sensitivity, type=pa.int8()),
        "sign_reason": pa.array(reasons, type=pa.string()),
    })


def summarize_signs(table: pa.Table) -> dict[str, object]:
    """Counts by consensus label and by sign for both variants."""

    labels = Counter("<missing>" if value is None else value for value in table["consensus_nt"].to_pylist())
    summary: dict[str, object] = {
        "row_count": table.num_rows,
        "consensus_nt_counts": dict(sorted(labels.items(), key=lambda item: -item[1])),
        "reason_counts": dict(Counter(table["sign_reason"].to_pylist())),
    }
    for column in SIGN_VARIANTS:
        counts = Counter(table[column].to_pylist())
        summary[column] = {
            "excitatory": counts.get(EXCITATORY, 0),
            "inhibitory": counts.get(INHIBITORY, 0),
            "excluded": counts.get(EXCLUDED, 0),
        }
    return summary


def coverage(node_ids: Iterable[int], signs: Mapping[int, int]) -> dict[str, int]:
    """How a node set splits into +1 / −1 / excluded / absent-from-table."""

    result = {"nodes": 0, "excitatory": 0, "inhibitory": 0, "excluded": 0, "absent": 0}
    for node_id in node_ids:
        result["nodes"] += 1
        if node_id not in signs:
            result["absent"] += 1
        elif signs[node_id] == EXCITATORY:
            result["excitatory"] += 1
        elif signs[node_id] == INHIBITORY:
            result["inhibitory"] += 1
        else:
            result["excluded"] += 1
    return result

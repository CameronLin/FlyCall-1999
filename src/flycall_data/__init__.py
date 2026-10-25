"""Read-only access to frozen FlyCall datasets."""

from .loader import (
    ContractIssue,
    DatasetBundle,
    DatasetContractError,
    DatasetPaths,
    load_frozen_dataset,
)

__all__ = [
    "ContractIssue",
    "DatasetBundle",
    "DatasetContractError",
    "DatasetPaths",
    "load_frozen_dataset",
]

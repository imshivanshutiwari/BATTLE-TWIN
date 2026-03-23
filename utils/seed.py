"""
Deterministic seeding for reproducible battlefield simulations.

Sets seeds across all frameworks used in BATTLE-TWIN:
Python stdlib, NumPy, PyTorch, and hash-based randomness.
"""

import os
import random
import hashlib
from typing import Optional

import numpy as np
import torch


_GLOBAL_SEED: Optional[int] = None


def set_global_seed(seed: int = 42) -> None:
    """
    Set deterministic seeds across all frameworks.

    Args:
        seed: Integer seed value. Default 42.
    """
    global _GLOBAL_SEED
    _GLOBAL_SEED = seed

    # Python stdlib
    random.seed(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)

    # NumPy
    np.random.seed(seed)

    # PyTorch
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False

    # For any subprocess reproducibility
    os.environ["CUBLAS_WORKSPACE_CONFIG"] = ":4096:8"


def get_global_seed() -> Optional[int]:
    """Return the currently set global seed, or None if unset."""
    return _GLOBAL_SEED


def deterministic_hash(value: str, modulus: int = 2**31) -> int:
    """
    Produce a deterministic integer hash from a string.

    Uses SHA-256 for uniform distribution. Useful for
    generating reproducible unit IDs, positions, etc.

    Args:
        value: String to hash.
        modulus: Upper bound for the returned integer.

    Returns:
        Deterministic integer in [0, modulus).
    """
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return int(digest, 16) % modulus


def seeded_rng(seed: int) -> np.random.Generator:
    """
    Create an independent NumPy random generator with a specific seed.

    Args:
        seed: Seed for this generator instance.

    Returns:
        np.random.Generator with PCG64 bit generator.
    """
    return np.random.default_rng(seed)


if __name__ == "__main__":
    set_global_seed(42)
    print(f"Global seed set to: {get_global_seed()}")
    print(f"Deterministic hash('unit_alpha'): {deterministic_hash('unit_alpha')}")
    rng = seeded_rng(123)
    print(f"Seeded RNG sample: {rng.random():.6f}")
    print("seed.py OK")

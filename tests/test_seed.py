"""Tests for utils/seed.py — deterministic seeding."""

import numpy as np
from utils.seed import set_global_seed, get_global_seed, deterministic_hash, create_seeded_rng


def test_set_global_seed():
    set_global_seed(42)
    assert get_global_seed() == 42


def test_deterministic_hash():
    h1 = deterministic_hash("test_input")
    h2 = deterministic_hash("test_input")
    assert h1 == h2
    assert isinstance(h1, int)


def test_create_seeded_rng():
    rng = create_seeded_rng(42)
    val1 = rng.random()
    rng2 = create_seeded_rng(42)
    val2 = rng2.random()
    assert val1 == val2


def test_numpy_reproducibility():
    set_global_seed(123)
    a = np.random.rand(5)
    set_global_seed(123)
    b = np.random.rand(5)
    np.testing.assert_array_equal(a, b)

"""Tests for utils/config_loader.py."""

from utils.config_loader import load_config


def test_load_battlefield_config():
    config = load_config("battlefield_config")
    assert config is not None
    assert "friendly_units" in config or "ao_name" in config


def test_load_nats_config():
    config = load_config("nats_config")
    assert config is not None


def test_load_agents_config():
    config = load_config("agents_config")
    assert config is not None


def test_load_sensor_config():
    config = load_config("sensor_config")
    assert config is not None


def test_load_ue5_config():
    config = load_config("ue5_config")
    assert config is not None


def test_invalid_config_raises():
    import pytest

    with pytest.raises(FileNotFoundError):
        load_config("nonexistent_config_xyz")

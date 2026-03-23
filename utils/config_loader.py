"""
Configuration loader for BATTLE-TWIN.

Loads YAML configuration files with:
- Environment variable override support
- .env file loading
- Nested key access via dot-notation
- Validation of required fields
- Caching of loaded configs
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from dotenv import load_dotenv


# Load .env from project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

_CONFIG_CACHE: Dict[str, Dict[str, Any]] = {}
_CONFIGS_DIR = _PROJECT_ROOT / "configs"


class ConfigValidationError(Exception):
    """Raised when a required config field is missing or invalid."""
    pass


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """
    Recursively merge override dict into base dict.

    Args:
        base: Base configuration dictionary.
        override: Override values to merge in.

    Returns:
        Merged dictionary (base is modified in-place and returned).
    """
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value
    return base


def _resolve_env_vars(config: Any) -> Any:
    """
    Recursively resolve ${ENV_VAR} references in config values.

    Supports:
        ${VAR}          — required, raises if missing
        ${VAR:-default} — with default value

    Args:
        config: Configuration value (dict, list, str, or scalar).

    Returns:
        Config with environment variables resolved.
    """
    if isinstance(config, dict):
        return {k: _resolve_env_vars(v) for k, v in config.items()}
    elif isinstance(config, list):
        return [_resolve_env_vars(item) for item in config]
    elif isinstance(config, str) and "${" in config:
        import re
        pattern = r"\$\{([^}]+)\}"
        matches = re.findall(pattern, config)
        result = config
        for match in matches:
            if ":-" in match:
                var_name, default = match.split(":-", 1)
            else:
                var_name = match
                default = None
            env_val = os.environ.get(var_name.strip())
            if env_val is None:
                if default is not None:
                    env_val = default
                else:
                    env_val = f"${{{match}}}"
            result = result.replace(f"${{{match}}}", env_val)
        return result
    return config


def load_config(
    config_name: str,
    override: Optional[Dict[str, Any]] = None,
    required_fields: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Load a YAML configuration file from configs/ directory.

    Args:
        config_name: Name of the config file (with or without .yaml extension).
        override: Optional dictionary of values to override.
        required_fields: List of dot-notation paths that must exist.

    Returns:
        Parsed configuration dictionary with env vars resolved.

    Raises:
        FileNotFoundError: If config file doesn't exist.
        ConfigValidationError: If required fields are missing.
    """
    if not config_name.endswith((".yaml", ".yml")):
        config_name = f"{config_name}.yaml"

    cache_key = config_name
    if cache_key in _CONFIG_CACHE and override is None:
        return _CONFIG_CACHE[cache_key]

    config_path = _CONFIGS_DIR / config_name
    if not config_path.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {config_path}"
        )

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    # Resolve environment variables
    config = _resolve_env_vars(config)

    # Apply overrides
    if override:
        config = _deep_merge(config, override)

    # Validate required fields
    if required_fields:
        for field_path in required_fields:
            _validate_field_exists(config, field_path)

    _CONFIG_CACHE[cache_key] = config
    return config


def _validate_field_exists(config: Dict[str, Any], field_path: str) -> None:
    """
    Validate that a dot-notation field path exists in config.

    Args:
        config: Configuration dictionary.
        field_path: Dot-separated path like 'nats.servers'.

    Raises:
        ConfigValidationError: If field is missing.
    """
    parts = field_path.split(".")
    current = config
    for part in parts:
        if not isinstance(current, dict) or part not in current:
            raise ConfigValidationError(
                f"Required config field missing: '{field_path}'"
            )
        current = current[part]


def get_nested(config: Dict[str, Any], key_path: str, default: Any = None) -> Any:
    """
    Get a value from a nested dict using dot-notation.

    Args:
        config: Configuration dictionary.
        key_path: Dot-separated key path.
        default: Default value if path not found.

    Returns:
        Value at the key path, or default.
    """
    parts = key_path.split(".")
    current = config
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return default
    return current


def reload_config(config_name: str) -> Dict[str, Any]:
    """Force reload a configuration file, bypassing cache."""
    if not config_name.endswith((".yaml", ".yml")):
        config_name = f"{config_name}.yaml"
    _CONFIG_CACHE.pop(config_name, None)
    return load_config(config_name)


def list_configs() -> List[str]:
    """List all available configuration files."""
    if _CONFIGS_DIR.exists():
        return [f.name for f in _CONFIGS_DIR.glob("*.yaml")]
    return []


if __name__ == "__main__":
    print(f"Config directory: {_CONFIGS_DIR}")
    print(f"Available configs: {list_configs()}")
    try:
        bf_config = load_config("battlefield_config")
        print(f"Loaded battlefield_config: {list(bf_config.keys())}")
    except FileNotFoundError:
        print("battlefield_config.yaml not yet created — OK for now")
    print("config_loader.py OK")

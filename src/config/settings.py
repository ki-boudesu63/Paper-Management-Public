"""Configuration module for Paper Management.

Reads and writes config.yaml. No hardcoded paths allowed.
All path settings come from the YAML configuration file.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

CONFIG_FILENAME = "config.yaml"
DEFAULT_LANGUAGE = "ja"
VALID_LANGUAGES = frozenset({"ja", "en", "zh"})

# Required keys under 'paths' section
REQUIRED_PATH_KEYS = frozenset(
    {"library_root", "vault_path", "style_folder", "watch_folder"}
)


def _find_config_path(override: str | Path | None = None) -> Path:
    """Locate the config file.

    Resolution order:
    1. Explicit override path
    2. PAPER_MGMT_CONFIG environment variable
    3. config.yaml in the project root (two levels up from this file)

    Raises:
        FileNotFoundError: If the resolved path does not exist.
    """
    if override is not None:
        path = Path(override)
    elif env_path := os.environ.get("PAPER_MGMT_CONFIG"):
        path = Path(env_path)
    else:
        # Default: project root / config.yaml
        project_root = Path(__file__).resolve().parent.parent.parent
        path = project_root / CONFIG_FILENAME

    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    return path


def load_settings(config_path: str | Path | None = None) -> dict[str, Any]:
    """Load settings from config.yaml.

    Args:
        config_path: Optional explicit path to config file.

    Returns:
        Parsed configuration dictionary.

    Raises:
        FileNotFoundError: If config file does not exist.
        ValueError: If YAML content is not a dictionary.
    """
    path = _find_config_path(config_path)

    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Config file must contain a YAML mapping, got: {type(data)}")

    return data


def save_settings(
    settings: dict[str, Any],
    config_path: str | Path | None = None,
) -> None:
    """Save settings to config.yaml.

    Args:
        settings: Configuration dictionary to persist.
        config_path: Optional explicit path to config file.

    Raises:
        ValueError: If settings is not a dictionary.
    """
    if not isinstance(settings, dict):
        raise ValueError("Settings must be a dictionary")

    path = _find_config_path(config_path)

    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(settings, f, default_flow_style=False, allow_unicode=True)


def get_language(config_path: str | Path | None = None) -> str:
    """Return the configured UI language.

    Defaults to Japanese when the key is missing or invalid.
    """
    settings = load_settings(config_path)
    language = settings.get("language", DEFAULT_LANGUAGE)

    if language not in VALID_LANGUAGES:
        return DEFAULT_LANGUAGE

    return str(language)


def set_language(lang: str, config_path: str | Path | None = None) -> None:
    """Persist the configured UI language.

    Args:
        lang: Language code. Must be one of ja, en, or zh.
        config_path: Optional explicit path to config file.

    Raises:
        ValueError: If lang is not supported.
    """
    if lang not in VALID_LANGUAGES:
        raise ValueError(f"Unsupported language: {lang}")

    settings = load_settings(config_path)
    settings["language"] = lang
    save_settings(settings, config_path)


def get_path_settings(
    config_path: str | Path | None = None,
) -> dict[str, str]:
    """Extract and return path settings from config.

    Returns:
        Dictionary with keys: library_root, vault_path, style_folder, watch_folder.
    """
    settings = load_settings(config_path)
    paths = settings.get("paths", {})

    if not isinstance(paths, dict):
        raise ValueError("'paths' section must be a mapping")

    return {key: str(paths.get(key, "")) for key in REQUIRED_PATH_KEYS}


def get_import_settings(
    config_path: str | Path | None = None,
) -> dict[str, Any]:
    """Extract and return import settings from config.

    Returns:
        Dictionary with import-related settings including:
        - unsorted_folder_name: str
        - watch_interval_sec: int
        - contact_email: str
        - extract_full_text: bool
    """
    settings = load_settings(config_path)
    import_settings = settings.get("import_settings", {})

    if not isinstance(import_settings, dict):
        raise ValueError("'import_settings' section must be a mapping")

    return import_settings


def is_full_text_extraction_enabled(
    config_path: str | Path | None = None,
) -> bool:
    """Check if full-text extraction via Docling is enabled.

    Reads the extract_full_text flag from import_settings.
    Defaults to False if the flag is missing.

    Args:
        config_path: Optional explicit path to config file.

    Returns:
        True if full-text extraction is enabled, False otherwise.
    """
    import_settings = get_import_settings(config_path)
    return bool(import_settings.get("extract_full_text", False))


def get_vault_name(config_path: str | Path | None = None) -> str:
    """Get the Obsidian vault name.

    If vault_name is empty, derives it from vault_path's folder name.

    Returns:
        Vault name string.
    """
    settings = load_settings(config_path)
    vault_name = settings.get("vault_name", "")

    if vault_name:
        return str(vault_name)

    # Derive from vault_path folder name
    paths = settings.get("paths", {})
    vault_path = paths.get("vault_path", "")

    if not vault_path:
        return ""

    return Path(vault_path).name

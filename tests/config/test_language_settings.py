"""Tests for language settings helpers."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from src.config.settings import get_language, set_language


def _write_config(path: Path, data: dict) -> Path:
    """Write a config.yaml file and return its path."""
    config_file = path / "config.yaml"
    config_file.write_text(
        yaml.dump(data, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )
    return config_file


def test_get_language_returns_configured_language(tmp_path: Path) -> None:
    """get_language returns a supported configured language."""
    config = _write_config(tmp_path, {"language": "zh"})

    assert get_language(config) == "zh"


def test_get_language_defaults_to_ja_when_missing(tmp_path: Path) -> None:
    """get_language defaults to Japanese when language is missing."""
    config = _write_config(tmp_path, {})

    assert get_language(config) == "ja"


def test_get_language_defaults_to_ja_when_invalid(tmp_path: Path) -> None:
    """get_language defaults to Japanese when language is invalid."""
    config = _write_config(tmp_path, {"language": "fr"})

    assert get_language(config) == "ja"


def test_set_language_persists_supported_language(tmp_path: Path) -> None:
    """set_language writes a supported language to config."""
    config = _write_config(tmp_path, {"language": "ja", "server": {"port": 12000}})

    set_language("en", config)

    saved = yaml.safe_load(config.read_text(encoding="utf-8"))
    assert saved["language"] == "en"
    assert saved["server"]["port"] == 12000


def test_set_language_rejects_unsupported_language(tmp_path: Path) -> None:
    """set_language rejects unsupported language codes."""
    config = _write_config(tmp_path, {"language": "ja"})

    with pytest.raises(ValueError):
        set_language("fr", config)

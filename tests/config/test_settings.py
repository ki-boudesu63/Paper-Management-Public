"""Tests for settings module, focusing on new import_settings features."""

from __future__ import annotations

from pathlib import Path

import yaml

from src.config.settings import (
    get_import_settings,
    is_full_text_extraction_enabled,
)


def _write_config(path: Path, data: dict) -> Path:
    """Write a config.yaml file and return its path."""
    config_file = path / "config.yaml"
    config_file.write_text(
        yaml.dump(data, default_flow_style=False, allow_unicode=True),
        encoding="utf-8",
    )
    return config_file


# ============================================================
# Tests: get_import_settings
# ============================================================


class TestGetImportSettings:
    """Tests for extracting import settings from config."""

    def test_returns_import_settings_dict(self, tmp_path: Path) -> None:
        config = _write_config(
            tmp_path,
            {
                "paths": {"library_root": "/lib"},
                "import_settings": {
                    "unsorted_folder_name": "unsorted",
                    "extract_full_text": True,
                },
            },
        )
        result = get_import_settings(config)
        assert isinstance(result, dict)
        assert result["unsorted_folder_name"] == "unsorted"
        assert result["extract_full_text"] is True

    def test_returns_empty_dict_when_section_missing(self, tmp_path: Path) -> None:
        config = _write_config(tmp_path, {"paths": {"library_root": "/lib"}})
        result = get_import_settings(config)
        assert result == {}


# ============================================================
# Tests: is_full_text_extraction_enabled
# ============================================================


class TestIsFullTextExtractionEnabled:
    """Tests for the extract_full_text flag."""

    def test_returns_true_when_enabled(self, tmp_path: Path) -> None:
        config = _write_config(
            tmp_path,
            {"import_settings": {"extract_full_text": True}},
        )
        assert is_full_text_extraction_enabled(config) is True

    def test_returns_false_when_disabled(self, tmp_path: Path) -> None:
        config = _write_config(
            tmp_path,
            {"import_settings": {"extract_full_text": False}},
        )
        assert is_full_text_extraction_enabled(config) is False

    def test_defaults_to_false_when_missing(self, tmp_path: Path) -> None:
        config = _write_config(
            tmp_path,
            {"import_settings": {"unsorted_folder_name": "unsorted"}},
        )
        assert is_full_text_extraction_enabled(config) is False

    def test_defaults_to_false_when_section_missing(self, tmp_path: Path) -> None:
        config = _write_config(
            tmp_path,
            {"paths": {"library_root": "/lib"}},
        )
        assert is_full_text_extraction_enabled(config) is False

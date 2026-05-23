"""Tests for web-layer i18n helpers."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import yaml
from jinja2 import Environment

from src.config.settings import set_language
from src.web import i18n
from src.web.i18n import configure_templates_globals


def _write_config(path: Path, language: str) -> Path:
    """Write a minimal config file for i18n tests."""
    config_file = path / "config.yaml"
    config_file.write_text(
        yaml.dump({"language": language}, default_flow_style=False),
        encoding="utf-8",
    )
    return config_file


def _request(config_path: Path) -> SimpleNamespace:
    """Create a minimal request-like object with app.state.config_path."""
    state = SimpleNamespace(config_path=str(config_path))
    app = SimpleNamespace(state=state)
    return SimpleNamespace(app=app)


def _render(template: str, config_path: Path) -> str:
    """Render a tiny template with the production i18n globals."""
    env = Environment(autoescape=True)
    configure_templates_globals(env.globals)
    return env.from_string(template).render(request=_request(config_path))


def test_t_returns_key_in_configured_language(tmp_path: Path) -> None:
    """t() returns values from the current language dictionary."""
    config_path = _write_config(tmp_path, "en")

    rendered = _render("{{ t('settings.save_button') }}", config_path)

    assert rendered == "Save Settings"


def test_t_interpolates_placeholders(tmp_path: Path) -> None:
    """t() interpolates named placeholders."""
    config_path = _write_config(tmp_path, "en")

    rendered = _render("{{ t('library.rescan_done', count=5) }}", config_path)

    assert rendered == "Rescan completed (5 papers)"


def test_t_falls_back_to_japanese_when_key_missing_in_language(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Missing translated keys fall back to Japanese values."""
    config_path = _write_config(tmp_path, "en")
    monkeypatch.setattr(
        i18n,
        "_TRANSLATIONS",
        {
            "ja": {"fallback": {"only": "\u65e5\u672c\u8a9e\u306e\u307f"}},
            "en": {},
        },
    )

    rendered = _render("{{ t('fallback.only') }}", config_path)

    assert rendered == "\u65e5\u672c\u8a9e\u306e\u307f"


def test_t_returns_key_when_missing_in_all_languages(
    monkeypatch,
    tmp_path: Path,
) -> None:
    """Completely unknown keys render as the key string."""
    config_path = _write_config(tmp_path, "en")
    monkeypatch.setattr(i18n, "_TRANSLATIONS", {"ja": {}, "en": {}})

    rendered = _render("{{ t('missing.key') }}", config_path)

    assert rendered == "missing.key"


def test_language_switching_rereads_config_per_request(tmp_path: Path) -> None:
    """Changing the config language affects subsequent renders."""
    config_path = _write_config(tmp_path, "ja")

    first = _render("{{ t('settings.save_button') }}", config_path)
    set_language("en", config_path)
    second = _render("{{ t('settings.save_button') }}", config_path)

    assert first == "\u8a2d\u5b9a\u3092\u4fdd\u5b58"
    assert second == "Save Settings"

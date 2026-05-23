"""Request-scoped translation helpers for the web UI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jinja2 import pass_context
from jinja2.runtime import Context

from src.config.settings import DEFAULT_LANGUAGE, get_language

LOCALE_DIR = Path(__file__).resolve().parent / "locale"
SUPPORTED_LOCALES = ("ja", "en", "zh")

_TRANSLATIONS: dict[str, dict[str, Any]] = {}


def _load_locale(language: str) -> dict[str, Any]:
    """Load and cache a locale dictionary."""
    if language not in _TRANSLATIONS:
        locale_path = LOCALE_DIR / f"{language}.json"
        with open(locale_path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            raise ValueError(f"Locale file must contain an object: {locale_path}")
        _TRANSLATIONS[language] = data
    return _TRANSLATIONS[language]


def _lookup(locale: dict[str, Any], key: str) -> str | None:
    """Find a dotted translation key in a nested locale dictionary."""
    current: Any = locale
    for part in key.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]

    if not isinstance(current, str):
        return None

    return current


def _get_config_path(context: Context) -> str | None:
    """Read the active config path from the request app state."""
    request = context.get("request")
    if request is None:
        return None

    path = getattr(request.app.state, "config_path", "")
    return str(path) if path else None


def _get_config_path_from_request(request: Any) -> str | None:
    """Read the active config path from a FastAPI request."""
    path = getattr(request.app.state, "config_path", "")
    return str(path) if path else None


def _translate(language: str, key: str, **kwargs: Any) -> str:
    """Translate a key in the requested language."""
    text = _lookup(_load_locale(language), key)
    if text is None and language != DEFAULT_LANGUAGE:
        text = _lookup(_load_locale(DEFAULT_LANGUAGE), key)
    if text is None:
        text = key

    if not kwargs:
        return text

    return text.format(**kwargs)


@pass_context
def current_language(context: Context) -> str:
    """Return the language configured for the current request."""
    return get_language(_get_config_path(context))


@pass_context
def t(context: Context, key: str, **kwargs: Any) -> str:
    """Translate a key for the current request language.

    Missing keys fall back to Japanese and then to the key itself.
    """
    return _translate(current_language(context), key, **kwargs)


def translate_for_request(request: Any, key: str, **kwargs: Any) -> str:
    """Translate a key using the language configured for a request."""
    language = get_language(_get_config_path_from_request(request))
    return _translate(language, key, **kwargs)


def configure_templates_globals(globals_dict: dict[str, Any]) -> None:
    """Register i18n helpers on a Jinja globals mapping."""
    globals_dict["t"] = t
    globals_dict["current_language"] = current_language

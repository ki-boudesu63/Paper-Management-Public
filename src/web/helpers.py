"""Web layer helper utilities.

Provides path conversion and other shared helpers for web routes.
"""

from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def to_vault_relative(
    abs_path: str | None,
    vault_path: str,
) -> str | None:
    """Convert an absolute file path to a vault-relative POSIX path.

    Obsidian's ``file=`` parameter in ``obsidian://open`` URIs expects a
    path relative to the vault root, using forward slashes.

    Args:
        abs_path: Absolute path to the file (e.g. note or PDF).
                  May be None or empty.
        vault_path: Absolute path to the Obsidian vault root.
                    May be empty if not configured.

    Returns:
        Vault-relative path with forward slashes, or filename-only
        fallback when the path is outside the vault or vault_path is
        empty.  Returns None when abs_path is None.
    """
    if abs_path is None:
        return None

    if not abs_path:
        return ""

    # Normalize to Path objects for reliable comparison
    try:
        file_path = Path(abs_path)
    except (ValueError, OSError):
        logger.warning("Invalid file path, returning filename: %s", abs_path)
        return _extract_filename(abs_path)

    # Fallback when vault_path is not configured
    if not vault_path or not vault_path.strip():
        logger.warning(
            "vault_path is empty; falling back to filename for: %s",
            abs_path,
        )
        return _extract_filename(abs_path)

    try:
        vault = Path(vault_path)
        # Use resolve() to normalize .. and trailing slashes, but only
        # if the paths exist.  For non-existent paths (common in tests),
        # fall back to manual normalization.
        try:
            relative = file_path.resolve().relative_to(vault.resolve())
        except (ValueError, OSError):
            # resolve() may fail or paths may not match after resolution;
            # try without resolve as a secondary attempt.
            relative = file_path.relative_to(vault)

        # Convert to forward-slash (POSIX) format for Obsidian URI
        return relative.as_posix()

    except ValueError:
        # file_path is not under vault_path
        logger.warning(
            "Path is not under vault; falling back to filename. path=%s vault=%s",
            abs_path,
            vault_path,
        )
        return _extract_filename(abs_path)


def _extract_filename(path_str: str) -> str:
    """Extract the filename from a path string.

    Handles both forward and back slashes.

    Args:
        path_str: A file path string.

    Returns:
        The filename component.
    """
    try:
        return Path(path_str).name
    except (ValueError, OSError):
        # Last resort: split on common separators
        return path_str.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]

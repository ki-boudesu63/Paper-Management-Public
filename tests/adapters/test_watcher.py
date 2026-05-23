"""Tests for FolderWatcher.

Tests verify event dispatching, debounce logic, and ignored extensions.
Uses tmp_path for isolated filesystem operations.
Uses PollingObserver (use_polling=True) to avoid Windows native observer flakiness.
Uses poll-until-called helper instead of fixed sleep to handle CI/load variance.
"""

from __future__ import annotations

import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.adapters.watcher import (
    DEBOUNCE_SECONDS,
    IGNORED_EXTENSIONS,
    FolderWatcher,
)

# ============================================================
# Test-level constants
# ============================================================

# Short intervals for fast tests, but generous timeout for CI load
_POLL_INTERVAL = 0.5
_DEBOUNCE = 0.5
_WAIT_TICK = 0.25  # polling granularity inside helper
_POSITIVE_TIMEOUT = 15.0  # max wait for callback (poll + debounce + stability)
_NEGATIVE_WAIT = 5.0  # fixed wait for assert_not_called (must exceed full pipeline)


# ============================================================
# Helpers
# ============================================================


def _wait_until_called(
    mock: MagicMock,
    timeout: float = _POSITIVE_TIMEOUT,
    tick: float = _WAIT_TICK,
) -> None:
    """Poll until mock has been called, or raise after timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if mock.called:
            return
        time.sleep(tick)
    raise AssertionError(f"Callback was not called within {timeout}s")


# ============================================================
# Fixtures
# ============================================================


@pytest.fixture
def watch_dir(tmp_path: Path) -> Path:
    """Create a watch directory."""
    d = tmp_path / "watch"
    d.mkdir()
    return d


@pytest.fixture
def callback() -> MagicMock:
    """Create a mock callback function."""
    return MagicMock()


# ============================================================
# Construction
# ============================================================


class TestFolderWatcherInit:
    """Tests for watcher initialization."""

    def test_init_creates_instance(self, watch_dir: Path, callback: MagicMock) -> None:
        watcher = FolderWatcher(
            watch_folder=watch_dir,
            on_new_pdf=callback,
        )
        assert watcher is not None

    def test_init_with_nonexistent_dir_raises(
        self, tmp_path: Path, callback: MagicMock
    ) -> None:
        with pytest.raises(FileNotFoundError):
            FolderWatcher(
                watch_folder=tmp_path / "nonexistent",
                on_new_pdf=callback,
            )


# ============================================================
# File Detection
# ============================================================


class TestFileDetection:
    """Tests for PDF file detection.

    All tests use use_polling=True to force PollingObserver,
    eliminating Windows native ReadDirectoryChangesW instability.
    """

    def test_detects_new_pdf(self, watch_dir: Path, callback: MagicMock) -> None:
        watcher = FolderWatcher(
            watch_folder=watch_dir,
            on_new_pdf=callback,
            poll_interval=_POLL_INTERVAL,
            debounce_seconds=_DEBOUNCE,
            use_polling=True,
        )
        watcher.start()

        try:
            pdf_path = watch_dir / "test_paper.pdf"
            pdf_path.write_bytes(b"%PDF-1.4 test content")

            _wait_until_called(callback, timeout=_POSITIVE_TIMEOUT)

            call_args = callback.call_args[0]
            assert Path(call_args[0]).name == "test_paper.pdf"
        finally:
            watcher.stop()

    def test_ignores_crdownload_extension(
        self, watch_dir: Path, callback: MagicMock
    ) -> None:
        watcher = FolderWatcher(
            watch_folder=watch_dir,
            on_new_pdf=callback,
            poll_interval=_POLL_INTERVAL,
            debounce_seconds=_DEBOUNCE,
            use_polling=True,
        )
        watcher.start()

        try:
            (watch_dir / "test.crdownload").write_bytes(b"partial")
            time.sleep(_NEGATIVE_WAIT)
            callback.assert_not_called()
        finally:
            watcher.stop()

    def test_ignores_part_extension(self, watch_dir: Path, callback: MagicMock) -> None:
        watcher = FolderWatcher(
            watch_folder=watch_dir,
            on_new_pdf=callback,
            poll_interval=_POLL_INTERVAL,
            debounce_seconds=_DEBOUNCE,
            use_polling=True,
        )
        watcher.start()

        try:
            (watch_dir / "test.part").write_bytes(b"partial")
            time.sleep(_NEGATIVE_WAIT)
            callback.assert_not_called()
        finally:
            watcher.stop()

    def test_ignores_tmp_extension(self, watch_dir: Path, callback: MagicMock) -> None:
        watcher = FolderWatcher(
            watch_folder=watch_dir,
            on_new_pdf=callback,
            poll_interval=_POLL_INTERVAL,
            debounce_seconds=_DEBOUNCE,
            use_polling=True,
        )
        watcher.start()

        try:
            (watch_dir / "test.tmp").write_bytes(b"temp data")
            time.sleep(_NEGATIVE_WAIT)
            callback.assert_not_called()
        finally:
            watcher.stop()

    def test_ignores_non_pdf_files(self, watch_dir: Path, callback: MagicMock) -> None:
        watcher = FolderWatcher(
            watch_folder=watch_dir,
            on_new_pdf=callback,
            poll_interval=_POLL_INTERVAL,
            debounce_seconds=_DEBOUNCE,
            use_polling=True,
        )
        watcher.start()

        try:
            (watch_dir / "readme.txt").write_text("hello")
            (watch_dir / "image.png").write_bytes(b"PNG data")
            time.sleep(_NEGATIVE_WAIT)
            callback.assert_not_called()
        finally:
            watcher.stop()


# ============================================================
# Start / Stop
# ============================================================


class TestStartStop:
    """Tests for watcher lifecycle."""

    def test_start_and_stop(self, watch_dir: Path, callback: MagicMock) -> None:
        watcher = FolderWatcher(
            watch_folder=watch_dir,
            on_new_pdf=callback,
            poll_interval=_POLL_INTERVAL,
        )
        watcher.start()
        assert watcher.is_running

        watcher.stop()
        assert not watcher.is_running

    def test_stop_idempotent(self, watch_dir: Path, callback: MagicMock) -> None:
        watcher = FolderWatcher(
            watch_folder=watch_dir,
            on_new_pdf=callback,
            poll_interval=_POLL_INTERVAL,
        )
        watcher.start()
        watcher.stop()
        watcher.stop()  # Should not raise
        assert not watcher.is_running


# ============================================================
# Constants
# ============================================================


class TestConstants:
    """Tests for module-level constants."""

    def test_ignored_extensions_contains_expected(self) -> None:
        assert ".crdownload" in IGNORED_EXTENSIONS
        assert ".part" in IGNORED_EXTENSIONS
        assert ".tmp" in IGNORED_EXTENSIONS

    def test_debounce_seconds_is_positive(self) -> None:
        assert DEBOUNCE_SECONDS > 0

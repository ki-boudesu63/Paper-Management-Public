"""Folder watcher for detecting new PDF files.

Uses watchdog library with PollingObserver fallback.
Implements debounce logic and ignores partial download files.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from collections.abc import Callable
from pathlib import Path

from watchdog.events import FileCreatedEvent, FileMovedEvent, FileSystemEventHandler
from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver

logger = logging.getLogger(__name__)

# ============================================================
# Constants
# ============================================================

DEBOUNCE_SECONDS = 2.0
IGNORED_EXTENSIONS = frozenset({".crdownload", ".part", ".tmp"})
PDF_EXTENSION = ".pdf"
DEFAULT_POLL_INTERVAL = 2.0
SIZE_STABILITY_CHECKS = 3
SIZE_STABILITY_INTERVAL = 0.5


class _PdfEventHandler(FileSystemEventHandler):
    """Watchdog event handler that filters for stable PDF files.

    Ignores partial downloads and non-PDF files.
    Implements debounce to avoid duplicate events.
    """

    def __init__(
        self,
        on_new_pdf: Callable[[str], None],
        debounce_seconds: float = DEBOUNCE_SECONDS,
    ) -> None:
        super().__init__()
        self._on_new_pdf = on_new_pdf
        self._debounce_seconds = debounce_seconds
        self._seen: dict[str, float] = {}
        self._lock = threading.Lock()

    def on_created(self, event: FileCreatedEvent) -> None:
        """Handle file creation events."""
        if event.is_directory:
            return
        self._process(event.src_path)

    def on_moved(self, event: FileMovedEvent) -> None:
        """Handle file move/rename events (e.g., .crdownload -> .pdf)."""
        if event.is_directory:
            return
        self._process(event.dest_path)

    def _process(self, file_path: str) -> None:
        """Process a file event with filtering and debounce."""
        path = Path(file_path)

        # Ignore non-PDF and partial download files
        if path.suffix.lower() != PDF_EXTENSION:
            return
        if self._is_ignored_extension(path):
            return

        # Debounce: skip if seen recently
        now = time.time()
        with self._lock:
            last_seen = self._seen.get(file_path, 0.0)
            if now - last_seen < self._debounce_seconds:
                return
            self._seen[file_path] = now

        # Wait for size stability in a background thread
        thread = threading.Thread(
            target=self._wait_and_notify,
            args=(file_path,),
            daemon=True,
        )
        thread.start()

    def _wait_and_notify(self, file_path: str) -> None:
        """Wait for file size to stabilize, then notify callback."""
        if not self._wait_for_stable_size(file_path):
            logger.warning("File size not stable, skipping: %s", file_path)
            return

        try:
            self._on_new_pdf(file_path)
        except Exception:
            logger.exception("Callback error for: %s", file_path)

    @staticmethod
    def _wait_for_stable_size(file_path: str) -> bool:
        """Wait until the file size stops changing.

        Returns True if the file is stable, False if it disappeared
        or never stabilized.
        """
        prev_size = -1
        stable_count = 0

        for _ in range(SIZE_STABILITY_CHECKS * 4):
            try:
                current_size = os.path.getsize(file_path)
            except OSError:
                return False

            if current_size == prev_size and current_size > 0:
                stable_count += 1
                if stable_count >= SIZE_STABILITY_CHECKS:
                    return True
            else:
                stable_count = 0

            prev_size = current_size
            time.sleep(SIZE_STABILITY_INTERVAL)

        return stable_count >= SIZE_STABILITY_CHECKS

    @staticmethod
    def _is_ignored_extension(path: Path) -> bool:
        """Check if a file has an ignored extension."""
        return path.suffix.lower() in IGNORED_EXTENSIONS


class FolderWatcher:
    """Watches a folder for new PDF files and triggers callbacks.

    Uses watchdog Observer with PollingObserver fallback.
    """

    def __init__(
        self,
        watch_folder: Path,
        on_new_pdf: Callable[[str], None],
        poll_interval: float = DEFAULT_POLL_INTERVAL,
        debounce_seconds: float = DEBOUNCE_SECONDS,
        use_polling: bool = False,
    ) -> None:
        if not watch_folder.exists():
            raise FileNotFoundError(f"Watch folder does not exist: {watch_folder}")

        self._watch_folder = watch_folder
        self._on_new_pdf = on_new_pdf
        self._poll_interval = poll_interval
        self._debounce_seconds = debounce_seconds
        self._use_polling = use_polling
        self._observer: Observer | PollingObserver | None = None
        self._is_running = False

    @property
    def is_running(self) -> bool:
        """Return whether the watcher is currently running."""
        return self._is_running

    def start(self) -> None:
        """Start watching the folder."""
        if self._is_running:
            return

        handler = _PdfEventHandler(
            on_new_pdf=self._on_new_pdf,
            debounce_seconds=self._debounce_seconds,
        )

        try:
            if self._use_polling:
                raise OSError("Force polling mode")
            self._observer = Observer()
            self._observer.schedule(handler, str(self._watch_folder), recursive=False)
            self._observer.start()
        except OSError:
            logger.info("Native observer failed, falling back to PollingObserver")
            self._observer = PollingObserver(timeout=self._poll_interval)
            self._observer.schedule(handler, str(self._watch_folder), recursive=False)
            self._observer.start()

        self._is_running = True
        logger.info("Watching folder: %s", self._watch_folder)

    def stop(self) -> None:
        """Stop watching the folder."""
        if not self._is_running:
            return

        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=5.0)
            self._observer = None

        self._is_running = False
        logger.info("Stopped watching folder: %s", self._watch_folder)

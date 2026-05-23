"""ImportAppService: orchestrates the paper import pipeline.

Sequence (from domain model design doc 5-2):
1. Watcher detects new PDF -> callback fires
2. Check metadata buffer (Chrome extension pre-fetched data)
3. If no buffer hit, extract DOI from PDF -> resolve via CrossRef
4. If metadata resolved: create Paper -> rename -> initial-letter sort -> MD gen -> save
5. If metadata fails: move PDF to unsorted folder
6. Update in-memory cache via repository

This module also handles duplicate detection via PaperRepository.find_by_id().
"""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from src.application.doi_extractor import extract_doi_from_pdf
from src.application.metadata_buffer import MetadataBuffer
from src.application.pdf_content_extractor import (
    IMAGE_PLACEHOLDER,
    ExtractedFigure,
    build_assets_dir_name,
    extract_pdf_content,
    save_figures,
)
from src.domain.paper import Metadata, Paper, PaperId
from src.domain.ports import MetadataResolver, PaperRepository

logger = logging.getLogger(__name__)

# ============================================================
# Constants
# ============================================================

PDF_HEAD_SIZE = 65536  # 64KB for SHA-256 hashing

# Separator between metadata section and extracted body in MD
BODY_SEPARATOR = "\n---\n\n"

# Fallback text when an image placeholder has no matching figure.
# Empty string: silently remove unmatched placeholders.  These arise
# when decorative images (logos, icons) are filtered out by the size
# threshold in pdf_content_extractor, or when extraction genuinely
# fails.  In both cases the placeholder carries no useful information
# and should disappear quietly.
_MISSING_FIGURE_TEXT = ""


# ============================================================
# Figure embedding helper
# ============================================================


def embed_figures_in_markdown(
    body_markdown: str,
    figures: list[ExtractedFigure],
    assets_dir_name: str,
) -> str:
    """Replace ``<!-- image -->`` placeholders with figure references.

    Each placeholder in *body_markdown* corresponds to the k-th picture
    in the source document (1-based ``source_index``).  For every
    placeholder we look up a figure whose ``source_index`` matches.

    Handling of mismatches:
    * **More placeholders than figures** — unmatched placeholders are
      replaced with a short fallback text so the reader knows an image
      was expected.
    * **More figures than placeholders** — surplus figures (i.e. those
      whose ``source_index`` exceeds the placeholder count) are appended
      at the end of the body, preserving the old behaviour as a safety
      net.
    * **No placeholders at all** — all figures are appended at the end.

    Args:
        body_markdown: Markdown text exported by Docling.
        figures: Successfully extracted figures with ``source_index``.
        assets_dir_name: Name of the assets directory (for image paths).

    Returns:
        Markdown string with placeholders replaced by ``![alt](path)``
        references.
    """

    placeholder_count = body_markdown.count(IMAGE_PLACEHOLDER)

    if placeholder_count == 0 and not figures:
        # Nothing to embed
        return body_markdown

    # Build a lookup: source_index -> figure reference string.
    # URL-encode the path so spaces and special characters (common in
    # Paperpile-style filenames like "S et al. 2022 - ...") are
    # percent-encoded, ensuring Obsidian can resolve the image link.
    from urllib.parse import quote as url_quote

    fig_ref_by_index: dict[int, str] = {}
    for fig in figures:
        encoded_path = url_quote(f"{assets_dir_name}/{fig.filename}", safe="/")
        fig_ref_by_index[fig.source_index] = f"![{fig.alt_text}]({encoded_path})"

    if placeholder_count == 0:
        # No placeholders — append all figures at end (legacy fallback)
        parts = [body_markdown]
        for fig in figures:
            parts.append(fig_ref_by_index[fig.source_index])
        return "\n\n".join(parts)

    # Replace placeholders one-by-one, in order
    result_parts: list[str] = []
    remainder = body_markdown
    current_source_index = 0

    while IMAGE_PLACEHOLDER in remainder:
        current_source_index += 1
        before, _, remainder = remainder.partition(IMAGE_PLACEHOLDER)
        result_parts.append(before)

        ref = fig_ref_by_index.get(current_source_index)
        if ref is not None:
            result_parts.append(ref)
        else:
            result_parts.append(_MISSING_FIGURE_TEXT)

    result_parts.append(remainder)
    embedded_md = "".join(result_parts)

    # Append surplus figures whose source_index exceeds placeholder count
    surplus_refs: list[str] = []
    for fig in figures:
        if fig.source_index > placeholder_count:
            surplus_refs.append(fig_ref_by_index[fig.source_index])

    if surplus_refs:
        embedded_md = embedded_md + "\n\n" + "\n\n".join(surplus_refs)

    return embedded_md


# ============================================================
# Import Result
# ============================================================


@dataclass(frozen=True)
class ImportResult:
    """Result of an import attempt for a single PDF."""

    pdf_path: str
    status: Literal["success", "duplicate", "unsorted", "error"]
    paper: Paper | None = None
    message: str = ""


# ============================================================
# ImportAppService
# ============================================================


class ImportAppService:
    """Application service for the paper import pipeline.

    Coordinates watcher callbacks, metadata resolution, and repository persistence.
    """

    def __init__(
        self,
        paper_repo: PaperRepository,
        metadata_resolver: MetadataResolver,
        metadata_buffer: MetadataBuffer,
        library_root: Path,
        unsorted_folder_name: str = "未整理",
        extract_full_text: bool = False,
    ) -> None:
        self._paper_repo = paper_repo
        self._metadata_resolver = metadata_resolver
        self._metadata_buffer = metadata_buffer
        self._library_root = library_root
        self._unsorted_folder_name = unsorted_folder_name
        self._extract_full_text = extract_full_text
        self._import_history: list[ImportResult] = []

    @property
    def import_history(self) -> list[ImportResult]:
        """Return the list of import results (most recent last)."""
        return list(self._import_history)

    # ============================================================
    # Public API
    # ============================================================

    def initialize(self) -> None:
        """Initialize the service: scan repository to build cache."""
        self._paper_repo.scan()

    def handle_new_pdf(self, pdf_path: str) -> ImportResult:
        """Main entry point: process a newly detected PDF.

        This is the callback wired to the FolderWatcher.

        Args:
            pdf_path: Absolute path to the detected PDF file.

        Returns:
            ImportResult describing the outcome.
        """
        logger.info("Processing new PDF: %s", pdf_path)

        try:
            result = self._process_pdf(pdf_path)
        except Exception as exc:
            logger.exception("Unexpected error importing %s", pdf_path)
            result = ImportResult(
                pdf_path=pdf_path,
                status="error",
                message=str(exc),
            )

        self._import_history.append(result)
        return result

    def receive_extension_metadata(self, metadata: Metadata) -> None:
        """Receive metadata from the Chrome extension and buffer it.

        Called by the API endpoint POST /api/import/metadata.

        Args:
            metadata: Pre-fetched metadata from the Chrome extension.
        """
        self._metadata_buffer.put(metadata)
        logger.info(
            "Buffered extension metadata: %s (DOI: %s)",
            metadata.title[:50],
            metadata.doi.value if metadata.doi else "N/A",
        )

    def register_metadata_only(
        self,
        metadata: Metadata,
        *,
        require_resolved: bool = False,
    ) -> ImportResult:
        """Register a DOI-backed paper without an attached PDF.

        CrossRef is used to complete metadata when possible. If the DOI already
        exists in the repository, no duplicate paper is created.
        """
        if metadata.doi is None:
            return ImportResult(
                pdf_path="",
                status="unsorted",
                message="DOI is required for metadata-only registration",
            )

        resolved = self._metadata_resolver.resolve(metadata.doi)
        if require_resolved and resolved is None:
            result = ImportResult(
                pdf_path="",
                status="unsorted",
                message=f"Metadata resolution failed for DOI: {metadata.doi.value}",
            )
            self._import_history.append(result)
            return result

        completed_metadata = resolved if resolved is not None else metadata
        paper = Paper.create(metadata=completed_metadata)

        existing = self._paper_repo.find_by_id(paper.id)
        if existing is not None:
            result = ImportResult(
                pdf_path="",
                status="duplicate",
                paper=existing,
                message=f"Paper already exists: {paper.id.value}",
            )
            self._import_history.append(result)
            return result

        self._paper_repo.save(paper)
        result = ImportResult(pdf_path="", status="success", paper=paper)
        self._import_history.append(result)
        return result

    def attach_pdf_to_paper(self, paper_id: PaperId, pdf_path: str) -> Paper:
        """Attach a PDF to an existing paper and optionally extract its body."""
        paper = self._paper_repo.attach_pdf(paper_id, pdf_path)
        if self._extract_full_text:
            self._extract_and_append_content(pdf_path, paper)
        logger.info("Attached PDF to paper: %s", paper_id.value)
        return paper

    # ============================================================
    # Private pipeline
    # ============================================================

    def _process_pdf(self, pdf_path: str) -> ImportResult:
        """Core pipeline: resolve metadata -> create paper -> persist."""
        path = Path(pdf_path)
        if not path.exists():
            return ImportResult(
                pdf_path=pdf_path,
                status="error",
                message="PDF file does not exist",
            )

        # Step 1: Try to resolve metadata
        metadata = self._resolve_metadata(pdf_path)

        if metadata is None:
            # Metadata resolution failed -> move to unsorted
            return self._move_to_unsorted(pdf_path)

        # Step 2: Read PDF head bytes for potential hash-based ID
        pdf_head_bytes = self._read_pdf_head(pdf_path)

        # Step 3: Create Paper entity
        paper = Paper.create(
            metadata=metadata,
            pdf_path=pdf_path,
            pdf_head_bytes=pdf_head_bytes,
        )

        # Step 4: Check for duplicates
        existing = self._paper_repo.find_by_id(paper.id)
        if existing is not None:
            if not existing.has_pdf:
                attached = self.attach_pdf_to_paper(existing.id, pdf_path)
                self._cleanup_buffer(metadata)
                return ImportResult(
                    pdf_path=pdf_path,
                    status="success",
                    paper=attached,
                    message=f"PDF attached to existing paper: {attached.id.value}",
                )
            logger.info("Duplicate paper detected: %s", paper.id.value)
            return ImportResult(
                pdf_path=pdf_path,
                status="duplicate",
                paper=existing,
                message=f"Paper already exists: {paper.id.value}",
            )

        # Step 5: Save (handles rename, initial-letter sort, MD generation)
        self._paper_repo.save(paper)

        # Step 6: Extract full text and figures (graceful degradation)
        if self._extract_full_text:
            self._extract_and_append_content(pdf_path, paper)

        # Step 7: Clean up buffer entry
        self._cleanup_buffer(metadata)

        logger.info(
            "Successfully imported: %s -> %s",
            pdf_path,
            paper.pdf_path,
        )

        return ImportResult(
            pdf_path=pdf_path,
            status="success",
            paper=paper,
        )

    def _extract_and_append_content(self, original_pdf_path: str, paper: Paper) -> None:
        """Extract full text and figures from PDF, append to the MD note.

        Figures are embedded at their original positions in the body
        Markdown by replacing ``<!-- image -->`` placeholders that
        Docling inserts during ``export_to_markdown()``.

        This step runs after the paper has been saved. On failure,
        the import still succeeds with metadata-only MD (graceful degradation).

        Args:
            original_pdf_path: Path to the original PDF (before rename).
            paper: The saved Paper entity (with updated pdf_path/note_path).
        """
        # Use the saved PDF path if available, fall back to original
        pdf_to_extract = paper.pdf_path or original_pdf_path

        try:
            extraction = extract_pdf_content(pdf_to_extract)
        except Exception:
            logger.warning(
                "Content extraction failed for %s, continuing without body",
                pdf_to_extract,
                exc_info=True,
            )
            return

        if not extraction.is_successful:
            logger.info(
                "Content extraction returned no content for %s: %s",
                pdf_to_extract,
                extraction.error_message,
            )
            return

        # Determine target paths
        if paper.note_path is None:
            logger.warning("Paper has no note_path, skipping content append")
            return

        note_path = Path(paper.note_path)
        file_name = paper.build_file_name()
        assets_dir_name = build_assets_dir_name(file_name.value)
        assets_dir = note_path.parent / assets_dir_name

        # Save figures if any
        if extraction.figures:
            save_figures(extraction.figures, assets_dir)

        if not extraction.body_markdown:
            return

        # Embed figure references at their original positions
        body_content = embed_figures_in_markdown(
            extraction.body_markdown,
            extraction.figures,
            assets_dir_name,
        )

        # Append to existing MD file
        try:
            existing_md = note_path.read_text(encoding="utf-8")
            updated_md = existing_md + BODY_SEPARATOR + body_content + "\n"
            note_path.write_text(updated_md, encoding="utf-8")
            logger.info("Appended extracted content to %s", note_path)
        except OSError:
            logger.warning(
                "Failed to append content to %s",
                note_path,
                exc_info=True,
            )

    def _resolve_metadata(self, pdf_path: str) -> Metadata | None:
        """Attempt to resolve metadata through multiple strategies.

        Priority:
        1. Buffer lookup by DOI (from PDF)
        2. Buffer lookup by author/year (fuzzy, from PDF filename)
        3. DOI extraction from PDF text -> CrossRef resolution
        """
        # Strategy 1 & 3: Extract DOI from PDF
        doi = extract_doi_from_pdf(pdf_path)

        if doi is not None:
            # Check buffer first (Chrome extension may have sent it)
            buffered = self._metadata_buffer.lookup_by_doi(doi.value)
            if buffered is not None:
                logger.info("Metadata found in buffer by DOI: %s", doi.value)
                return buffered

            # Resolve via CrossRef
            resolved = self._metadata_resolver.resolve(doi)
            if resolved is not None:
                logger.info("Metadata resolved via CrossRef for DOI: %s", doi.value)
                return resolved

        # Strategy 2: Try filename-based fuzzy match from buffer
        filename_meta = self._try_filename_buffer_match(pdf_path)
        if filename_meta is not None:
            return filename_meta

        logger.warning("Could not resolve metadata for: %s", pdf_path)
        return None

    def _try_filename_buffer_match(self, pdf_path: str) -> Metadata | None:
        """Try to match a PDF filename against buffered metadata.

        Paperpile-style filenames: "Family YYYY - Title.pdf"
        or "Family et al. YYYY - Title.pdf"
        """
        stem = Path(pdf_path).stem
        parts = stem.split(" ")

        if len(parts) < 2:
            return None

        # Extract potential author and year from filename
        family_name = parts[0]
        year = None
        for part in parts[1:]:
            try:
                candidate = int(part)
                if 1900 <= candidate <= 2100:
                    year = candidate
                    break
            except ValueError:
                continue

        if year is None:
            return None

        result = self._metadata_buffer.lookup_by_author_year(family_name, year)
        if result is not None:
            logger.info(
                "Metadata found in buffer by author/year: %s %d",
                family_name,
                year,
            )
        return result

    def _move_to_unsorted(self, pdf_path: str) -> ImportResult:
        """Move a PDF to the unsorted folder when metadata resolution fails."""
        unsorted_dir = self._library_root / self._unsorted_folder_name
        unsorted_dir.mkdir(exist_ok=True)

        source = Path(pdf_path)
        target = unsorted_dir / source.name

        # Handle name collision in unsorted folder
        if target.exists():
            stem = source.stem
            suffix = source.suffix
            counter = 1
            while target.exists():
                target = unsorted_dir / f"{stem}_{counter}{suffix}"
                counter += 1

        try:
            shutil.move(str(source), str(target))
        except OSError as exc:
            logger.error("Failed to move to unsorted: %s", exc)
            return ImportResult(
                pdf_path=pdf_path,
                status="error",
                message=f"Failed to move to unsorted folder: {exc}",
            )

        logger.info("Moved to unsorted: %s -> %s", pdf_path, target)
        return ImportResult(
            pdf_path=pdf_path,
            status="unsorted",
            message=f"Metadata resolution failed. Moved to: {target}",
        )

    @staticmethod
    def _read_pdf_head(pdf_path: str) -> bytes:
        """Read the first 64KB of a PDF file for hashing."""
        with open(pdf_path, "rb") as f:
            return f.read(PDF_HEAD_SIZE)

    @staticmethod
    def _cleanup_buffer(metadata: Metadata) -> None:
        """Clean up is handled by TTL expiration.

        No explicit removal needed as the buffer self-purges.
        This method is a hook for future explicit cleanup if needed.
        """
        pass

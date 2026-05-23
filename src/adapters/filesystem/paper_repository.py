"""Filesystem-based PaperRepository implementation.

Scans initial-letter folders (A-Z, #) at startup, caching papers in memory.
Each paper is stored as a PDF + MD (YAML frontmatter) pair.
Uses python-frontmatter for MD reading/writing.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import frontmatter

from src.domain.paper import (
    DOI,
    Author,
    InitialLetter,
    Metadata,
    Paper,
    PaperId,
    PublicationYear,
)
from src.domain.ports import PaperRepository

logger = logging.getLogger(__name__)

# Valid initial-letter folder names
INITIAL_LETTERS = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ") + ["#"]
FRONTMATTER_DELIMITER = "---"
FRONTMATTER_KEY_PATTERN = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$")


class FilesystemPaperRepository(PaperRepository):
    """Concrete PaperRepository backed by the filesystem.

    Papers are stored in initial-letter folders (A-Z, #) as PDF/MD pairs.
    An in-memory cache maps PaperId -> Paper for fast lookups.
    """

    def __init__(self, library_root: Path) -> None:
        if not library_root.exists():
            raise FileNotFoundError(f"Library root does not exist: {library_root}")
        self._library_root = library_root
        self._cache: dict[PaperId, Paper] = {}

    # ============================================================
    # Public API (Port implementation)
    # ============================================================

    def find_by_id(self, paper_id: PaperId) -> Paper | None:
        """Find a paper by its ID from the in-memory cache."""
        return self._cache.get(paper_id)

    def find_all(self) -> list[Paper]:
        """Return all papers from the in-memory cache."""
        return list(self._cache.values())

    def save(self, paper: Paper) -> None:
        """Persist a paper to the filesystem and update the cache.

        If the paper already exists, updates the MD file in place.
        If new, copies the PDF from its current path when present and creates the MD.
        """
        existing = self._cache.get(paper.id)

        folder = self._library_root / paper.initial_letter.letter
        folder.mkdir(exist_ok=True)

        file_name = paper.build_file_name()
        pdf_target = folder / f"{file_name.value}.pdf"
        md_target = folder / f"{file_name.value}.md"

        if existing is not None:
            # Remove old files if the name changed
            self._remove_old_files(existing)

        # Copy PDF if the paper has one and it is not already in target location.
        if paper.has_pdf and paper.pdf_path is not None:
            source_pdf = Path(paper.pdf_path)
            if source_pdf.exists() and source_pdf.resolve() != pdf_target.resolve():
                shutil.copy2(str(source_pdf), str(pdf_target))
            paper.pdf_path = str(pdf_target)
        else:
            paper.pdf_path = None

        # Write the MD note
        md_content = paper.to_markdown_note()
        md_target.write_text(md_content, encoding="utf-8")

        # Update paper paths
        paper.note_path = str(md_target)

        # Update cache
        self._cache[paper.id] = paper

    def attach_pdf(self, paper_id: PaperId, pdf_path: str) -> Paper:
        """Attach a PDF to an existing paper and refresh its MD note.

        The selected PDF is copied into the paper's initial-letter folder using
        the Paperpile-style basename derived from the paper metadata.
        """
        paper = self._cache.get(paper_id)
        if paper is None:
            raise KeyError(f"Paper not found: {paper_id.value}")

        source_pdf = Path(pdf_path)
        if not source_pdf.exists():
            raise FileNotFoundError(f"PDF file does not exist: {pdf_path}")

        folder = self._library_root / paper.initial_letter.letter
        folder.mkdir(exist_ok=True)
        file_name = paper.build_file_name()
        target_pdf = folder / f"{file_name.value}.pdf"

        if source_pdf.resolve() != target_pdf.resolve():
            shutil.copy2(str(source_pdf), str(target_pdf))

        paper.pdf_path = str(target_pdf)
        if paper.note_path is None:
            paper.note_path = str(folder / f"{file_name.value}.md")

        note_path = Path(paper.note_path)
        note_path.write_text(paper.to_markdown_note(), encoding="utf-8")
        self._cache[paper.id] = paper
        return paper

    def delete(self, paper_id: PaperId) -> None:
        """Remove a paper, its files, and its assets folder from the filesystem.

        Removes PDF, MD, and the <stem>.assets/ directory if present.
        Safe to call even when files have already been manually deleted —
        missing files are silently skipped while the cache entry is always removed.

        Raises:
            KeyError: If paper_id is not found in the cache.
        """
        paper = self._cache.get(paper_id)
        if paper is None:
            raise KeyError(f"Paper not found: {paper_id.value}")

        self._remove_old_files(paper)
        self._remove_assets_folder(paper)
        del self._cache[paper_id]

    # ============================================================
    # Scanning
    # ============================================================

    def scan(self) -> None:
        """Scan all initial-letter folders and populate the cache.

        Creates missing initial-letter folders.
        Loads papers from existing PDF/MD pairs.
        """
        self._ensure_initial_folders()
        self._cache.clear()

        for letter in INITIAL_LETTERS:
            folder = self._library_root / letter
            if not folder.is_dir():
                continue
            self._scan_folder(folder, letter)

        logger.info("Scanned library: %d papers found", len(self._cache))

    # ============================================================
    # Private helpers
    # ============================================================

    def _ensure_initial_folders(self) -> None:
        """Create A-Z and # folders if they do not exist."""
        for letter in INITIAL_LETTERS:
            folder = self._library_root / letter
            folder.mkdir(exist_ok=True)

    def _scan_folder(self, folder: Path, letter: str) -> None:
        """Scan a single initial-letter folder for PDF/MD pairs."""
        for md_path in folder.glob("*.md"):
            try:
                pdf_path = _resolve_pdf_for_note(md_path)
                paper = self._load_paper_from_md(md_path, pdf_path, letter)
                self._cache[paper.id] = paper
            except Exception:
                logger.warning(
                    "Failed to load paper from %s, skipping",
                    md_path,
                    exc_info=True,
                )

    def _load_paper_from_md(
        self,
        md_path: Path,
        pdf_path: Path | None,
        letter: str,
    ) -> Paper:
        """Parse an MD file with YAML frontmatter and reconstruct a Paper."""
        fm = _load_frontmatter_metadata(md_path)

        paper_id_str = _frontmatter_text(fm.get("paper_id", ""))
        title = _frontmatter_text(fm.get("title", ""))
        year_val = _frontmatter_year(fm.get("year", 2000))
        doi_str = _frontmatter_text(fm.get("doi", ""))
        journal = _frontmatter_text(fm.get("journal", ""))
        journal_abbrev = _frontmatter_text(fm.get("journal_abbrev", ""))
        volume = _frontmatter_text(fm.get("volume", ""))
        issue = _frontmatter_text(fm.get("issue", ""))
        pages = _frontmatter_text(fm.get("pages", ""))
        abstract = _frontmatter_text(fm.get("abstract", ""))
        memo = _frontmatter_text(fm.get("memo", ""))
        initial = _frontmatter_text(fm.get("initial_letter", letter), fallback=letter)
        tags = fm.get("tags", [])
        imported_str = fm.get("imported_at", "")

        # Reconstruct authors
        authors_raw = _normalize_authors_frontmatter(fm.get("authors", []))
        authors = tuple(
            Author(
                family_name=a.get("family", "Unknown"),
                given_name=a.get("given", ""),
            )
            for a in authors_raw
        )
        if not authors:
            authors = (Author(family_name="Unknown"),)

        # Build domain objects
        doi = _safe_doi(doi_str)
        metadata = Metadata(
            title=title,
            authors=authors,
            year=PublicationYear(year_val),
            doi=doi,
            journal=journal,
            journal_abbrev=journal_abbrev,
            volume=volume,
            issue=issue,
            pages=pages,
            abstract=abstract,
            memo=memo,
        )

        paper_id = _safe_paper_id(paper_id_str, doi, pdf_path)

        # Parse imported_at
        imported_at = None
        if imported_str:
            try:
                imported_at = datetime_parse(imported_str)
            except (ValueError, TypeError):
                imported_at = None

        paper = Paper(
            id=paper_id,
            metadata=metadata,
            pdf_path=str(pdf_path) if pdf_path is not None else None,
            note_path=str(md_path),
            initial_letter=_safe_initial_letter(initial, letter),
            tags=tags if isinstance(tags, list) else [],
            **({"imported_at": imported_at} if imported_at else {}),
        )

        return paper

    def _remove_old_files(self, paper: Paper) -> None:
        """Remove old PDF and MD files for a paper.

        Silently skips files that do not exist (already deleted externally).
        """
        if paper.pdf_path:
            pdf = Path(paper.pdf_path)
            if pdf.exists():
                pdf.unlink()

        if paper.note_path:
            md = Path(paper.note_path)
            if md.exists():
                md.unlink()

    def _remove_assets_folder(self, paper: Paper) -> None:
        """Remove the <stem>.assets/ directory associated with a paper.

        The assets folder (containing extracted figures) is named after the
        PDF stem using the same convention as pdf_content_extractor.
        Silently skips if the folder does not exist.
        """
        if not paper.pdf_path:
            return
        pdf = Path(paper.pdf_path)
        assets_dir = pdf.parent / f"{pdf.stem}.assets"
        if assets_dir.is_dir():
            shutil.rmtree(str(assets_dir))
            logger.info("Removed assets folder: %s", assets_dir)


def datetime_parse(s: str | datetime) -> datetime:
    """Parse an ISO-like datetime string."""
    if isinstance(s, datetime):
        return s if s.tzinfo is not None else s.replace(tzinfo=UTC)

    # Handle both with and without timezone
    s = s.strip().strip('"')
    try:
        return datetime.fromisoformat(s).replace(tzinfo=UTC)
    except ValueError:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=UTC)


def _load_frontmatter_metadata(md_path: Path) -> dict[str, Any]:
    """Load frontmatter, falling back to a lenient parser on YAML errors."""
    try:
        post = frontmatter.load(str(md_path))
        return dict(post.metadata)
    except Exception:
        logger.warning(
            "Strict frontmatter parse failed for %s; using lenient parser",
            md_path,
            exc_info=True,
        )
        return _parse_frontmatter_lenient(md_path.read_text(encoding="utf-8"))


def _parse_frontmatter_lenient(text: str) -> dict[str, Any]:
    """Extract common frontmatter keys without requiring valid YAML."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != FRONTMATTER_DELIMITER:
        return {}

    block: list[str] = []
    for line in lines[1:]:
        if line.strip() == FRONTMATTER_DELIMITER:
            break
        block.append(line)

    data: dict[str, Any] = {}
    index = 0
    while index < len(block):
        line = block[index]
        match = FRONTMATTER_KEY_PATTERN.match(line)
        if match is None:
            index += 1
            continue

        key = match.group(1)
        value = match.group(2).strip().strip('"').strip("'")
        if value in {"|-", "|", ">-", ">"}:
            value_lines: list[str] = []
            index += 1
            while index < len(block):
                next_line = block[index]
                if FRONTMATTER_KEY_PATTERN.match(next_line):
                    index -= 1
                    break
                value_lines.append(next_line.strip())
                index += 1
            data[key] = "\n".join(part for part in value_lines if part)
        else:
            data[key] = value
        index += 1

    return data


def _frontmatter_text(raw: object, fallback: str = "") -> str:
    """Return a safe string from Obsidian-edited frontmatter values."""
    if raw is None:
        return fallback
    if isinstance(raw, str):
        return raw
    if isinstance(raw, (int, float, bool)):
        return str(raw)
    if isinstance(raw, list):
        return "\n".join(_frontmatter_text(item) for item in raw).strip()
    return fallback


def _frontmatter_year(raw: object) -> int:
    """Return a safe publication year from frontmatter."""
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str):
        try:
            return int(raw.strip())
        except ValueError:
            return 2000
    return 2000


def _normalize_authors_frontmatter(raw: object) -> list[dict[str, str]]:
    """Normalize authors frontmatter into a list of mappings.

    Obsidian properties can rewrite complex YAML values as JSON strings.
    Treat those as valid input so editing another property does not make the
    paper disappear from the scanned library.
    """
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return [{"family": raw, "given": ""}] if raw.strip() else []
        return _normalize_authors_frontmatter(parsed)

    if not isinstance(raw, list):
        return []

    authors: list[dict[str, str]] = []
    for item in raw:
        if isinstance(item, dict):
            authors.append(
                {
                    "family": str(item.get("family", "Unknown")),
                    "given": str(item.get("given", "")),
                }
            )
        elif isinstance(item, str) and item.strip():
            try:
                parsed = json.loads(item)
            except json.JSONDecodeError:
                authors.append({"family": item.strip(), "given": ""})
            else:
                authors.extend(_normalize_authors_frontmatter(parsed))
    return authors


def _safe_doi(raw: str) -> DOI | None:
    """Build DOI if valid; otherwise ignore the field."""
    if not raw.strip():
        return None
    try:
        return DOI(raw)
    except ValueError:
        logger.warning("Ignoring invalid DOI in frontmatter: %s", raw)
        return None


def _resolve_pdf_for_note(md_path: Path) -> Path | None:
    """Resolve the optional PDF path associated with an MD note."""
    fm = _load_frontmatter_metadata(md_path)
    pdf_filename = _frontmatter_text(fm.get("pdf_filename", "")).strip()
    if pdf_filename:
        candidate = md_path.parent / pdf_filename
        return candidate if candidate.exists() else None

    candidate = md_path.with_suffix(".pdf")
    return candidate if candidate.exists() else None


def _safe_paper_id(raw: str, doi: DOI | None, pdf_path: Path | None) -> PaperId:
    """Build a PaperId, deriving a fallback when frontmatter is damaged."""
    if raw.strip():
        return PaperId(raw.strip())
    if doi is not None:
        return PaperId.from_doi(doi)
    if pdf_path is None:
        raise ValueError("Cannot derive paper_id without DOI or PDF")
    return PaperId.from_pdf_bytes(pdf_path.read_bytes()[:65536])


def _safe_initial_letter(raw: str, fallback: str) -> InitialLetter:
    """Build InitialLetter, falling back to the folder letter."""
    try:
        return InitialLetter(raw)
    except ValueError:
        return InitialLetter(fallback)

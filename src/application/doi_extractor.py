"""Extract DOI from PDF files using pypdf.

Reads the first pages of a PDF and applies regex to find DOI patterns.
Falls back to checking the first few pages if the first page has no DOI.
"""

from __future__ import annotations

import logging
import re

from pypdf import PdfReader

from src.domain.paper import DOI

logger = logging.getLogger(__name__)

# ============================================================
# Constants
# ============================================================

MAX_PAGES_TO_SCAN = 3
DOI_REGEX = re.compile(
    r"(?:doi[:\s]*|https?://(?:dx\.)?doi\.org/)"
    r"(10\.\d{4,9}/[^\s,;\"'<>\]})]+)",
    re.IGNORECASE,
)
DOI_BARE_REGEX = re.compile(
    r"\b(10\.\d{4,9}/[^\s,;\"'<>\]})]+)",
)


# ============================================================
# Public API
# ============================================================


def extract_doi_from_pdf(pdf_path: str) -> DOI | None:
    """Extract a DOI from the first pages of a PDF file.

    Scans up to MAX_PAGES_TO_SCAN pages for DOI patterns.
    Returns the first valid DOI found, or None.

    Args:
        pdf_path: Absolute path to the PDF file.

    Returns:
        A DOI value object if found, None otherwise.
    """
    try:
        reader = PdfReader(pdf_path)
    except Exception:
        logger.warning("Failed to open PDF: %s", pdf_path, exc_info=True)
        return None

    pages_to_scan = min(len(reader.pages), MAX_PAGES_TO_SCAN)
    for page_idx in range(pages_to_scan):
        page = reader.pages[page_idx]
        text = page.extract_text() or ""
        doi = _find_doi_in_text(text)
        if doi is not None:
            return doi

    return None


# ============================================================
# Private helpers
# ============================================================


def _find_doi_in_text(text: str) -> DOI | None:
    """Find the first valid DOI in a text string.

    Tries the prefixed pattern first (doi:, https://doi.org/),
    then falls back to bare 10.xxxx/ pattern.
    """
    # Try prefixed DOI patterns first (more reliable)
    match = DOI_REGEX.search(text)
    if match:
        return _try_create_doi(match.group(1))

    # Fall back to bare DOI pattern
    match = DOI_BARE_REGEX.search(text)
    if match:
        return _try_create_doi(match.group(1))

    return None


def _try_create_doi(raw: str) -> DOI | None:
    """Attempt to create a DOI value object, returning None on failure.

    Strips trailing punctuation that may have been captured by regex.
    """
    # Clean up trailing punctuation commonly captured
    cleaned = raw.rstrip(".,;:")
    try:
        return DOI(cleaned)
    except ValueError:
        logger.debug("Invalid DOI candidate: %s", cleaned)
        return None

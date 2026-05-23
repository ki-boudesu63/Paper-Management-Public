"""Tests for DOI extraction from PDF files."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from src.application.doi_extractor import (
    MAX_PAGES_TO_SCAN,
    _find_doi_in_text,
    extract_doi_from_pdf,
)

# ============================================================
# Tests: _find_doi_in_text (unit tests for regex matching)
# ============================================================


class TestFindDoiInText:
    """Tests for the internal DOI text extraction function."""

    def test_doi_with_prefix(self) -> None:
        text = "Some text doi:10.1234/test.paper more text"
        doi = _find_doi_in_text(text)
        assert doi is not None
        assert doi.value == "10.1234/test.paper"

    def test_doi_with_url_prefix(self) -> None:
        text = "Available at https://doi.org/10.1038/nature12373"
        doi = _find_doi_in_text(text)
        assert doi is not None
        assert doi.value == "10.1038/nature12373"

    def test_doi_with_dx_url_prefix(self) -> None:
        text = "http://dx.doi.org/10.1016/j.cell.2021.01.001"
        doi = _find_doi_in_text(text)
        assert doi is not None
        assert doi.value == "10.1016/j.cell.2021.01.001"

    def test_bare_doi_pattern(self) -> None:
        text = "Reference: 10.1234/abcdef"
        doi = _find_doi_in_text(text)
        assert doi is not None
        assert doi.value == "10.1234/abcdef"

    def test_doi_with_trailing_period_stripped(self) -> None:
        text = "See 10.1234/test.paper."
        doi = _find_doi_in_text(text)
        assert doi is not None
        # Trailing period should be stripped
        assert not doi.value.endswith(".")

    def test_no_doi_in_text(self) -> None:
        text = "This text has no DOI whatsoever."
        doi = _find_doi_in_text(text)
        assert doi is None

    def test_empty_text(self) -> None:
        doi = _find_doi_in_text("")
        assert doi is None

    def test_doi_case_insensitive_prefix(self) -> None:
        text = "DOI: 10.1234/CaseSensitive"
        doi = _find_doi_in_text(text)
        assert doi is not None
        # DOI values are normalized to lowercase
        assert doi.value == "10.1234/casesensitive"

    def test_doi_with_complex_suffix(self) -> None:
        text = "doi:10.1002/(SICI)1097-0142(19990801)86:3<399::AID-CNCR7>3.0.CO;2-E"
        doi = _find_doi_in_text(text)
        assert doi is not None


# ============================================================
# Tests: extract_doi_from_pdf (integration with pypdf mock)
# ============================================================


class TestExtractDoiFromPdf:
    """Tests for PDF-level DOI extraction using mocked pypdf."""

    def test_extracts_doi_from_first_page(self, tmp_path: Path) -> None:
        pdf_path = str(tmp_path / "test.pdf")

        mock_page = MagicMock()
        mock_page.extract_text.return_value = (
            "Research Article\ndoi:10.1234/extracted.doi\nAbstract..."
        )

        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]

        with patch("src.application.doi_extractor.PdfReader") as mock_cls:
            mock_cls.return_value = mock_reader
            doi = extract_doi_from_pdf(pdf_path)

        assert doi is not None
        assert doi.value == "10.1234/extracted.doi"

    def test_scans_multiple_pages(self, tmp_path: Path) -> None:
        pdf_path = str(tmp_path / "test.pdf")

        page_no_doi = MagicMock()
        page_no_doi.extract_text.return_value = "No DOI on this page"

        page_with_doi = MagicMock()
        page_with_doi.extract_text.return_value = "doi:10.5678/page2.doi"

        mock_reader = MagicMock()
        mock_reader.pages = [
            page_no_doi,
            page_with_doi,
            MagicMock(),
            MagicMock(),
            MagicMock(),
        ]

        with patch("src.application.doi_extractor.PdfReader") as mock_cls:
            mock_cls.return_value = mock_reader
            doi = extract_doi_from_pdf(pdf_path)

        assert doi is not None
        assert doi.value == "10.5678/page2.doi"

    def test_returns_none_when_no_doi_found(self, tmp_path: Path) -> None:
        pdf_path = str(tmp_path / "test.pdf")

        mock_page = MagicMock()
        mock_page.extract_text.return_value = "No DOI anywhere"

        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]

        with patch("src.application.doi_extractor.PdfReader") as mock_cls:
            mock_cls.return_value = mock_reader
            doi = extract_doi_from_pdf(pdf_path)

        assert doi is None

    def test_returns_none_on_open_failure(self, tmp_path: Path) -> None:
        pdf_path = str(tmp_path / "nonexistent.pdf")

        with patch("src.application.doi_extractor.PdfReader") as mock_cls:
            mock_cls.side_effect = RuntimeError("Cannot open")
            doi = extract_doi_from_pdf(pdf_path)

        assert doi is None

    def test_limits_pages_scanned(self, tmp_path: Path) -> None:
        pdf_path = str(tmp_path / "test.pdf")

        # Create a list of 100 mock pages, none with DOI
        mock_pages = []
        for _ in range(100):
            page = MagicMock()
            page.extract_text.return_value = "No DOI"
            mock_pages.append(page)

        mock_reader = MagicMock()
        mock_reader.pages = mock_pages

        with patch("src.application.doi_extractor.PdfReader") as mock_cls:
            mock_cls.return_value = mock_reader
            extract_doi_from_pdf(pdf_path)

        # Should only call extract_text on MAX_PAGES_TO_SCAN pages
        called_count = sum(1 for p in mock_pages if p.extract_text.called)
        assert called_count == MAX_PAGES_TO_SCAN

    def test_handles_none_extract_text(self, tmp_path: Path) -> None:
        """Test graceful handling when extract_text returns None."""
        pdf_path = str(tmp_path / "test.pdf")

        mock_page = MagicMock()
        mock_page.extract_text.return_value = None

        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]

        with patch("src.application.doi_extractor.PdfReader") as mock_cls:
            mock_cls.return_value = mock_reader
            doi = extract_doi_from_pdf(pdf_path)

        assert doi is None

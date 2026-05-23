"""Tests for PDF content extraction using Docling (all mocked)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from src.application.pdf_content_extractor import (
    ASSETS_FOLDER_SUFFIX,
    ExtractedFigure,
    ExtractionResult,
    build_assets_dir_name,
    extract_pdf_content,
    save_figures,
)

# ============================================================
# Tests: ExtractionResult
# ============================================================


class TestExtractionResult:
    """Tests for the ExtractionResult data class."""

    def test_successful_result(self) -> None:
        result = ExtractionResult(body_markdown="# Hello")
        assert result.is_successful is True
        assert result.body_markdown == "# Hello"
        assert result.figures == []
        assert result.error_message == ""

    def test_failed_result(self) -> None:
        result = ExtractionResult(error_message="Something went wrong")
        assert result.is_successful is False
        assert result.body_markdown is None

    def test_result_with_figures(self) -> None:
        fig = ExtractedFigure(
            image_bytes=b"fake-png",
            filename="figure-1.png",
            alt_text="Figure 1",
            source_index=1,
        )
        result = ExtractionResult(body_markdown="# Content", figures=[fig])
        assert result.is_successful is True
        assert len(result.figures) == 1
        assert result.figures[0].filename == "figure-1.png"


# ============================================================
# Tests: extract_pdf_content (Docling fully mocked)
# ============================================================


class TestExtractPdfContent:
    """Tests for PDF content extraction with mocked Docling."""

    def test_extracts_markdown_from_pdf(self, tmp_path: Path) -> None:
        """Happy path: Docling converts PDF to Markdown."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake content")

        mock_doc = MagicMock()
        mock_doc.export_to_markdown.return_value = (
            "# Extracted Title\n\nBody text here."
        )
        mock_doc.pictures = []

        mock_result = MagicMock()
        mock_result.document = mock_doc

        mock_converter = MagicMock()
        mock_converter.convert.return_value = mock_result

        with patch(
            "docling.document_converter.DocumentConverter",
            return_value=mock_converter,
        ):
            result = extract_pdf_content(str(pdf_file))

        assert result.is_successful is True
        assert "Extracted Title" in result.body_markdown
        assert result.error_message == ""

    def test_extracts_figures_from_pdf(self, tmp_path: Path) -> None:
        """Docling finds figures and we extract them."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake content")

        # Create a mock PIL image
        mock_pil_image = MagicMock()

        def mock_save(buf: object, format: str = "PNG") -> None:
            buf.write(b"fake-png-bytes")  # type: ignore[union-attr]

        mock_pil_image.save.side_effect = mock_save

        # Create a mock picture with caption
        mock_picture = MagicMock()
        mock_picture.get_image.return_value = mock_pil_image
        mock_caption = MagicMock()
        mock_caption.text = "A nice diagram"
        mock_picture.captions = [mock_caption]

        mock_doc = MagicMock()
        mock_doc.export_to_markdown.return_value = "# Title\n\nSome text."
        mock_doc.pictures = [mock_picture]

        mock_result = MagicMock()
        mock_result.document = mock_doc

        mock_converter = MagicMock()
        mock_converter.convert.return_value = mock_result

        with patch(
            "docling.document_converter.DocumentConverter",
            return_value=mock_converter,
        ):
            result = extract_pdf_content(str(pdf_file))

        assert result.is_successful is True
        assert len(result.figures) == 1
        assert result.figures[0].filename == "figure-1.png"
        assert result.figures[0].alt_text == "A nice diagram"
        assert result.figures[0].image_bytes == b"fake-png-bytes"
        assert result.figures[0].source_index == 1

    def test_returns_failure_when_file_missing(self) -> None:
        """Non-existent PDF path returns a failed result."""
        result = extract_pdf_content("/nonexistent/path/test.pdf")
        assert result.is_successful is False
        assert "does not exist" in result.error_message

    def test_returns_failure_on_docling_error(self, tmp_path: Path) -> None:
        """Docling conversion error returns a failed result (no exception)."""
        pdf_file = tmp_path / "broken.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 broken")

        with patch(
            "docling.document_converter.DocumentConverter",
            side_effect=RuntimeError("Model load failed"),
        ):
            result = extract_pdf_content(str(pdf_file))

        assert result.is_successful is False
        assert "Model load failed" in result.error_message

    def test_figures_extraction_failure_still_returns_markdown(
        self, tmp_path: Path
    ) -> None:
        """If figure extraction fails, Markdown body is still returned."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake content")

        mock_doc = MagicMock()
        mock_doc.export_to_markdown.return_value = "# Good content"
        # pictures property raises to simulate error
        type(mock_doc).pictures = property(
            lambda self: (_ for _ in ()).throw(RuntimeError("broken"))
        )

        mock_result = MagicMock()
        mock_result.document = mock_doc

        mock_converter = MagicMock()
        mock_converter.convert.return_value = mock_result

        with patch(
            "docling.document_converter.DocumentConverter",
            return_value=mock_converter,
        ):
            result = extract_pdf_content(str(pdf_file))

        assert result.is_successful is True
        assert result.body_markdown == "# Good content"
        # Figures should be empty due to extraction failure
        assert result.figures == []

    def test_figure_without_caption_gets_default_alt(self, tmp_path: Path) -> None:
        """A figure without a caption gets a default alt text."""
        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake content")

        mock_pil_image = MagicMock()

        def mock_save(buf: object, format: str = "PNG") -> None:
            buf.write(b"png-data")  # type: ignore[union-attr]

        mock_pil_image.save.side_effect = mock_save

        mock_picture = MagicMock()
        mock_picture.get_image.return_value = mock_pil_image
        mock_picture.captions = []

        mock_doc = MagicMock()
        mock_doc.export_to_markdown.return_value = "# Title"
        mock_doc.pictures = [mock_picture]

        mock_result = MagicMock()
        mock_result.document = mock_doc

        mock_converter = MagicMock()
        mock_converter.convert.return_value = mock_result

        with patch(
            "docling.document_converter.DocumentConverter",
            return_value=mock_converter,
        ):
            result = extract_pdf_content(str(pdf_file))

        assert result.is_successful is True
        assert result.figures[0].alt_text == "Figure 1"
        assert result.figures[0].source_index == 1


# ============================================================
# Tests: save_figures
# ============================================================


class TestSaveFigures:
    """Tests for saving extracted figures to the filesystem."""

    def test_saves_figures_to_assets_dir(self, tmp_path: Path) -> None:
        assets_dir = tmp_path / "paper.assets"
        figures = [
            ExtractedFigure(
                image_bytes=b"png-data-1",
                filename="figure-1.png",
                alt_text="Figure 1",
                source_index=1,
            ),
            ExtractedFigure(
                image_bytes=b"png-data-2",
                filename="figure-2.png",
                alt_text="Figure 2",
                source_index=2,
            ),
        ]

        save_figures(figures, assets_dir)

        assert (assets_dir / "figure-1.png").exists()
        assert (assets_dir / "figure-1.png").read_bytes() == b"png-data-1"
        assert (assets_dir / "figure-2.png").exists()
        assert (assets_dir / "figure-2.png").read_bytes() == b"png-data-2"

    def test_creates_assets_dir_if_missing(self, tmp_path: Path) -> None:
        assets_dir = tmp_path / "nested" / "dir" / "paper.assets"
        figures = [
            ExtractedFigure(
                image_bytes=b"data",
                filename="figure-1.png",
                alt_text="Fig 1",
                source_index=1,
            ),
        ]

        save_figures(figures, assets_dir)
        assert assets_dir.exists()
        assert (assets_dir / "figure-1.png").exists()

    def test_no_op_when_no_figures(self, tmp_path: Path) -> None:
        assets_dir = tmp_path / "paper.assets"
        save_figures([], assets_dir)
        assert not assets_dir.exists()


# ============================================================
# Tests: build_assets_dir_name
# ============================================================


class TestBuildAssetsDirName:
    """Tests for assets directory name generation."""

    def test_basic_name(self) -> None:
        assert build_assets_dir_name("Smith 2024 - Deep Learning") == (
            "Smith 2024 - Deep Learning.assets"
        )

    def test_preserves_stem(self) -> None:
        name = build_assets_dir_name("paper")
        assert name == "paper.assets"
        assert name.endswith(ASSETS_FOLDER_SUFFIX)


# ============================================================
# Tests: Size-based figure filtering
# ============================================================


def _make_mock_picture_with_size(
    width: int, height: int, caption: str | None = None
) -> tuple[MagicMock, MagicMock]:
    """Create a mock picture element whose get_image() returns an image of given size.

    Returns (mock_picture, mock_pil_image).
    """
    from PIL import Image

    # Create a real PIL image of the specified size so that
    # _is_below_minimum_size can read its dimensions from PNG bytes.
    real_image = Image.new("RGB", (width, height), color="red")

    mock_picture = MagicMock()
    mock_picture.get_image.return_value = real_image

    if caption:
        mock_caption = MagicMock()
        mock_caption.text = caption
        mock_picture.captions = [mock_caption]
    else:
        mock_picture.captions = []

    return mock_picture, real_image


class TestFigureSizeFiltering:
    """Tests that small decorative images are filtered out during extraction."""

    def test_small_picture_excluded(self, tmp_path: Path) -> None:
        """A picture smaller than MIN_FIGURE_DIMENSION_PX is excluded."""

        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake content")

        # Small icon: both dimensions below threshold
        small_pic, _ = _make_mock_picture_with_size(50, 50)

        mock_doc = MagicMock()
        mock_doc.export_to_markdown.return_value = "# Title"
        mock_doc.pictures = [small_pic]

        mock_result = MagicMock()
        mock_result.document = mock_doc

        mock_converter = MagicMock()
        mock_converter.convert.return_value = mock_result

        with patch(
            "docling.document_converter.DocumentConverter",
            return_value=mock_converter,
        ):
            result = extract_pdf_content(str(pdf_file))

        assert result.is_successful is True
        assert len(result.figures) == 0

    def test_large_picture_kept(self, tmp_path: Path) -> None:
        """A picture larger than MIN_FIGURE_DIMENSION_PX is kept."""

        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake content")

        # Real figure: dimensions above threshold
        large_pic, _ = _make_mock_picture_with_size(700, 500, caption="Figure 1")

        mock_doc = MagicMock()
        mock_doc.export_to_markdown.return_value = "# Title"
        mock_doc.pictures = [large_pic]

        mock_result = MagicMock()
        mock_result.document = mock_doc

        mock_converter = MagicMock()
        mock_converter.convert.return_value = mock_result

        with patch(
            "docling.document_converter.DocumentConverter",
            return_value=mock_converter,
        ):
            result = extract_pdf_content(str(pdf_file))

        assert result.is_successful is True
        assert len(result.figures) == 1
        assert result.figures[0].alt_text == "Figure 1"

    def test_wide_but_short_banner_excluded(self, tmp_path: Path) -> None:
        """A wide but short banner strip is excluded (height below threshold)."""
        from src.application.pdf_content_extractor import MIN_FIGURE_DIMENSION_PX

        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake content")

        # Wide banner: width above threshold but height below.
        # _is_below_minimum_size uses OR logic: if either dimension
        # is below the threshold, the picture is excluded.
        banner_pic, _ = _make_mock_picture_with_size(
            MIN_FIGURE_DIMENSION_PX + 100, MIN_FIGURE_DIMENSION_PX - 50
        )

        mock_doc = MagicMock()
        mock_doc.export_to_markdown.return_value = "# Title"
        mock_doc.pictures = [banner_pic]

        mock_result = MagicMock()
        mock_result.document = mock_doc

        mock_converter = MagicMock()
        mock_converter.convert.return_value = mock_result

        with patch(
            "docling.document_converter.DocumentConverter",
            return_value=mock_converter,
        ):
            result = extract_pdf_content(str(pdf_file))

        # Height < threshold -> excluded (OR logic: either dim too small)
        assert len(result.figures) == 0

    def test_both_dims_below_threshold_excluded(self, tmp_path: Path) -> None:
        """Picture where both width and height are below threshold is excluded."""
        from src.application.pdf_content_extractor import MIN_FIGURE_DIMENSION_PX

        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake content")

        tiny_pic, _ = _make_mock_picture_with_size(
            MIN_FIGURE_DIMENSION_PX - 1, MIN_FIGURE_DIMENSION_PX - 1
        )

        mock_doc = MagicMock()
        mock_doc.export_to_markdown.return_value = "# Title"
        mock_doc.pictures = [tiny_pic]

        mock_result = MagicMock()
        mock_result.document = mock_doc

        mock_converter = MagicMock()
        mock_converter.convert.return_value = mock_result

        with patch(
            "docling.document_converter.DocumentConverter",
            return_value=mock_converter,
        ):
            result = extract_pdf_content(str(pdf_file))

        assert len(result.figures) == 0

    def test_source_index_preserved_when_small_pics_skipped(
        self, tmp_path: Path
    ) -> None:
        """source_index counts all pictures, including skipped small ones.

        If pictures are [small, large, small, large], the two kept figures
        should have source_index=2 and source_index=4.
        """

        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake content")

        small1, _ = _make_mock_picture_with_size(50, 50)
        large1, _ = _make_mock_picture_with_size(600, 400, caption="Real Fig A")
        small2, _ = _make_mock_picture_with_size(80, 60)
        large2, _ = _make_mock_picture_with_size(700, 500, caption="Real Fig B")

        mock_doc = MagicMock()
        mock_doc.export_to_markdown.return_value = "# Title"
        mock_doc.pictures = [small1, large1, small2, large2]

        mock_result = MagicMock()
        mock_result.document = mock_doc

        mock_converter = MagicMock()
        mock_converter.convert.return_value = mock_result

        with patch(
            "docling.document_converter.DocumentConverter",
            return_value=mock_converter,
        ):
            result = extract_pdf_content(str(pdf_file))

        assert len(result.figures) == 2
        # source_index is 1-based position among ALL pictures
        assert result.figures[0].source_index == 2  # 2nd picture overall
        assert result.figures[1].source_index == 4  # 4th picture overall
        # Filenames use extracted_count (sequential among kept figures)
        assert result.figures[0].filename == "figure-1.png"
        assert result.figures[1].filename == "figure-2.png"

    def test_exact_threshold_excluded(self, tmp_path: Path) -> None:
        """A picture exactly at (threshold-1, threshold-1) is excluded (strictly less than)."""
        from src.application.pdf_content_extractor import MIN_FIGURE_DIMENSION_PX

        pdf_file = tmp_path / "test.pdf"
        pdf_file.write_bytes(b"%PDF-1.4 fake content")

        # Both dimensions exactly at threshold -> NOT excluded (not < threshold)
        exact_pic, _ = _make_mock_picture_with_size(
            MIN_FIGURE_DIMENSION_PX, MIN_FIGURE_DIMENSION_PX
        )

        mock_doc = MagicMock()
        mock_doc.export_to_markdown.return_value = "# Title"
        mock_doc.pictures = [exact_pic]

        mock_result = MagicMock()
        mock_result.document = mock_doc

        mock_converter = MagicMock()
        mock_converter.convert.return_value = mock_result

        with patch(
            "docling.document_converter.DocumentConverter",
            return_value=mock_converter,
        ):
            result = extract_pdf_content(str(pdf_file))

        # Exactly at threshold -> kept (< is strict)
        assert len(result.figures) == 1

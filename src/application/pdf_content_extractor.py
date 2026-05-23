"""Extract full text and figures from PDF files using Docling.

Provides a high-level interface for converting PDF documents into
Markdown text with embedded figure references. Designed for graceful
degradation: extraction failures return a result with None fields
instead of raising exceptions.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

# ============================================================
# Constants
# ============================================================

ASSETS_FOLDER_SUFFIX = ".assets"
FIGURE_PREFIX = "figure"
FIGURE_FORMAT = "png"

# Timeout for Docling conversion (seconds)
DOCLING_TIMEOUT_SEC = 300

# Resolution scale for extracted figure images (1.0 = native size).
# Higher values yield sharper figures at the cost of larger files.
IMAGES_SCALE = 2.0

# Minimum width AND height (in pixels, at the extracted image resolution
# which is affected by IMAGES_SCALE) for a picture to be considered a
# real figure.  Pictures where *either* dimension is below this value
# are skipped — journal logos, ORCID icons, CC license badges,
# check-for-updates buttons, narrow banner strips, etc.
#
# Empirically determined from sample PDFs with images_scale=2.0:
#   Decorations: 105x37, 117x44, 87x58 (icons), 323x70 (header),
#                752x155 (banner strip)
#   Real figures: 701x1029, 740x412 (both dims well above 200)
# A threshold of 200 px cleanly separates the two groups.
MIN_FIGURE_DIMENSION_PX = 200

# Placeholder string that Docling inserts in exported Markdown for each
# picture element.  One placeholder per picture, in document order.
IMAGE_PLACEHOLDER = "<!-- image -->"


# ============================================================
# Result types
# ============================================================


@dataclass(frozen=True)
class ExtractedFigure:
    """A single figure extracted from a PDF.

    Attributes:
        image_bytes: Raw PNG image data.
        filename: Target filename (e.g., 'figure-1.png').
        alt_text: Descriptive text for the Markdown image tag.
        source_index: 1-based position of this figure among all pictures
            in the source document.  Corresponds to the k-th
            ``<!-- image -->`` placeholder in the exported Markdown.
            Pictures whose image data could not be extracted are skipped
            in the figure list but still consume a source_index, so the
            mapping between placeholder position and source_index stays
            consistent.
    """

    image_bytes: bytes
    filename: str
    alt_text: str
    source_index: int


@dataclass(frozen=True)
class ExtractionResult:
    """Result of full-text + figure extraction from a PDF.

    If extraction fails, body_markdown is None and figures is empty.
    The caller should check body_markdown before using the result.

    Attributes:
        body_markdown: Extracted Markdown text, or None on failure.
        figures: List of extracted figures with their image data.
        error_message: Description of what went wrong, empty on success.
    """

    body_markdown: str | None = None
    figures: list[ExtractedFigure] = field(default_factory=list)
    error_message: str = ""

    @property
    def is_successful(self) -> bool:
        """Return True if extraction produced usable content."""
        return self.body_markdown is not None


# ============================================================
# Public API
# ============================================================


def extract_pdf_content(pdf_path: str) -> ExtractionResult:
    """Extract full text and figures from a PDF using Docling.

    This function wraps Docling's DocumentConverter to produce a
    Markdown representation of the PDF content along with any
    embedded figures.

    On any failure (import error, conversion error, etc.), returns
    an ExtractionResult with body_markdown=None so the caller can
    gracefully degrade.

    Args:
        pdf_path: Absolute path to the PDF file.

    Returns:
        ExtractionResult with extracted content or failure info.
    """
    path = Path(pdf_path)
    if not path.exists():
        return ExtractionResult(
            error_message=f"PDF file does not exist: {pdf_path}",
        )

    try:
        return _do_extraction(path)
    except Exception as exc:
        logger.warning(
            "Docling extraction failed for %s: %s",
            pdf_path,
            exc,
            exc_info=True,
        )
        return ExtractionResult(
            error_message=f"Extraction failed: {exc}",
        )


def save_figures(
    figures: list[ExtractedFigure],
    assets_dir: Path,
) -> None:
    """Save extracted figures to the assets directory.

    Creates the directory if it does not exist.

    Args:
        figures: List of figures to save.
        assets_dir: Target directory for figure images.
    """
    if not figures:
        return

    assets_dir.mkdir(parents=True, exist_ok=True)

    for figure in figures:
        target = assets_dir / figure.filename
        target.write_bytes(figure.image_bytes)
        logger.debug("Saved figure: %s", target)


def build_assets_dir_name(pdf_stem: str) -> str:
    """Build the assets directory name for a given PDF stem.

    Args:
        pdf_stem: PDF filename without extension.

    Returns:
        Assets directory name (e.g., 'MyPaper.assets').
    """
    return f"{pdf_stem}{ASSETS_FOLDER_SUFFIX}"


# ============================================================
# Private helpers
# ============================================================


def _do_extraction(pdf_path: Path) -> ExtractionResult:
    """Perform the actual Docling-based extraction.

    Separated from the public API to allow the try/except wrapper
    in extract_pdf_content to catch all errors uniformly.
    """
    # Late import to avoid import-time model downloads
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    # Enable picture image generation so figures can be extracted.
    # Without generate_picture_images=True, Docling discards the image
    # data and PictureItem.get_image() returns None -> no figures saved.
    pipeline_options = PdfPipelineOptions()
    pipeline_options.generate_picture_images = True
    pipeline_options.images_scale = IMAGES_SCALE

    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
        }
    )
    result = converter.convert(str(pdf_path))

    # Extract Markdown text
    body_markdown = result.document.export_to_markdown()

    # Extract figures
    figures = _extract_figures(result)

    return ExtractionResult(
        body_markdown=body_markdown,
        figures=figures,
    )


def _extract_figures(result: object) -> list[ExtractedFigure]:
    """Extract figure images from a Docling conversion result.

    Iterates over picture items in the document and collects
    their image representations.  Each figure records its
    ``source_index`` (1-based position among *all* pictures in the
    document) so callers can map figures back to the corresponding
    ``<!-- image -->`` placeholder in the exported Markdown.

    Pictures whose dimensions (width or height) are below
    ``MIN_FIGURE_DIMENSION_PX`` are considered decorative elements
    (journal logos, ORCID icons, etc.) and are skipped.  Their
    ``source_index`` slot is still consumed so placeholder mapping
    remains consistent.

    Args:
        result: Docling ConversionResult object.

    Returns:
        List of ExtractedFigure with image bytes and filenames.
        The list may be shorter than ``len(doc.pictures)`` when
        image extraction fails or pictures are too small.
    """
    figures: list[ExtractedFigure] = []
    # Separate counter for successfully extracted figures (used in
    # filenames) vs source_index which counts every picture slot.
    extracted_count = 0

    try:
        doc = result.document  # type: ignore[attr-defined]
        # Iterate over document elements looking for pictures
        if hasattr(doc, "pictures") and doc.pictures:
            for source_index_0, picture in enumerate(doc.pictures):
                source_index = source_index_0 + 1  # 1-based
                image_bytes = _get_picture_bytes(result, picture)
                if image_bytes is None:
                    continue

                # Filter out small decorative images (logos, icons, etc.)
                if _is_below_minimum_size(image_bytes):
                    logger.debug(
                        "Skipping small decorative picture at source_index=%d",
                        source_index,
                    )
                    continue

                extracted_count += 1
                filename = f"{FIGURE_PREFIX}-{extracted_count}.{FIGURE_FORMAT}"
                alt_text = _get_picture_caption(picture, source_index)

                figures.append(
                    ExtractedFigure(
                        image_bytes=image_bytes,
                        filename=filename,
                        alt_text=alt_text,
                        source_index=source_index,
                    )
                )
    except Exception:
        logger.warning("Failed to extract figures", exc_info=True)

    return figures


def _is_below_minimum_size(image_bytes: bytes) -> bool:
    """Check whether an image is smaller than the minimum figure size.

    Returns True when *either* width or height is below
    ``MIN_FIGURE_DIMENSION_PX``.  Real figures have both dimensions
    well above the threshold, while decorative elements such as
    journal logos, ORCID icons, and banner strips typically have at
    least one very small dimension.

    Args:
        image_bytes: Raw PNG image data.

    Returns:
        True if the image should be filtered out.
    """
    try:
        import io

        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes))
        width, height = img.size
        return width < MIN_FIGURE_DIMENSION_PX or height < MIN_FIGURE_DIMENSION_PX
    except Exception:
        # If we cannot determine the size, keep the image to be safe
        logger.debug("Could not determine image size, keeping picture", exc_info=True)
        return False


def _get_picture_bytes(result: object, picture: object) -> bytes | None:
    """Extract raw image bytes from a Docling picture element.

    Args:
        result: Docling ConversionResult object.
        picture: A picture element from the document.

    Returns:
        PNG bytes if available, None otherwise.
    """
    try:
        # Docling stores images in the conversion result
        if hasattr(picture, "get_image"):
            pil_image = picture.get_image(result.document)
            if pil_image is not None:
                import io

                buf = io.BytesIO()
                pil_image.save(buf, format="PNG")
                return buf.getvalue()
    except Exception:
        logger.debug("Could not extract image bytes for picture", exc_info=True)

    return None


def _get_picture_caption(picture: object, index: int) -> str:
    """Extract or generate a caption for a figure.

    Args:
        picture: A picture element from the document.
        index: 1-based figure index for fallback caption.

    Returns:
        Caption text.
    """
    # Try to get caption from Docling's picture metadata
    if hasattr(picture, "captions") and picture.captions:
        captions = picture.captions
        if isinstance(captions, list) and len(captions) > 0:
            first = captions[0]
            if hasattr(first, "text") and first.text:
                return str(first.text)

    return f"Figure {index}"

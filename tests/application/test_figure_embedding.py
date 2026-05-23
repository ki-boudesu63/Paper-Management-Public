"""Tests for figure embedding in Markdown body text.

Covers the embed_figures_in_markdown() function that replaces
Docling's ``<!-- image -->`` placeholders with actual figure references.
"""

from __future__ import annotations

from src.application.import_service import (
    embed_figures_in_markdown,
)
from src.application.pdf_content_extractor import IMAGE_PLACEHOLDER, ExtractedFigure

# The assets dir name used in URL-encoding tests
ASSETS_DIR_WITH_SPACES = "S et al. 2022 - Some Paper.assets"

ASSETS_DIR = "paper.assets"


def _make_figure(
    index: int,
    source_index: int | None = None,
    alt: str | None = None,
) -> ExtractedFigure:
    """Create a test ExtractedFigure with minimal data."""
    si = source_index if source_index is not None else index
    return ExtractedFigure(
        image_bytes=b"fake-png",
        filename=f"figure-{index}.png",
        alt_text=alt or f"Figure {si}",
        source_index=si,
    )


# ============================================================
# Normal 1:1 mapping
# ============================================================


class TestEmbedFiguresNormalMapping:
    """Tests where placeholder count == figure count."""

    def test_single_figure_replaced_in_place(self) -> None:
        """One placeholder, one figure -> replaced at original position."""
        md = f"# Title\n\nSome text.\n\n{IMAGE_PLACEHOLDER}\n\nMore text."
        fig = _make_figure(1, source_index=1)

        result = embed_figures_in_markdown(md, [fig], ASSETS_DIR)

        assert IMAGE_PLACEHOLDER not in result
        assert "![Figure 1](paper.assets/figure-1.png)" in result
        # Figure should be between "Some text." and "More text."
        assert result.index("figure-1.png") < result.index("More text.")
        assert result.index("Some text.") < result.index("figure-1.png")

    def test_multiple_figures_replaced_in_order(self) -> None:
        """Three placeholders, three figures -> all replaced in order."""
        md = (
            f"# Intro\n\n{IMAGE_PLACEHOLDER}\n\n"
            f"## Methods\n\n{IMAGE_PLACEHOLDER}\n\n"
            f"## Results\n\n{IMAGE_PLACEHOLDER}\n\nConclusion."
        )
        figs = [_make_figure(i, source_index=i) for i in range(1, 4)]

        result = embed_figures_in_markdown(md, figs, ASSETS_DIR)

        assert IMAGE_PLACEHOLDER not in result
        assert "figure-1.png" in result
        assert "figure-2.png" in result
        assert "figure-3.png" in result
        # Order should be preserved
        assert result.index("figure-1.png") < result.index("figure-2.png")
        assert result.index("figure-2.png") < result.index("figure-3.png")

    def test_figures_with_skipped_source_index(self) -> None:
        """Two placeholders but figure source_indices are 1 and 3 (2 was skipped).

        Placeholder 1 -> source_index=1 (matched)
        Placeholder 2 -> source_index=2 (no figure -> silently removed)
        Placeholder 3 -> source_index=3 (matched)
        """
        md = (
            f"Para 1.\n\n{IMAGE_PLACEHOLDER}\n\n"
            f"Para 2.\n\n{IMAGE_PLACEHOLDER}\n\n"
            f"Para 3.\n\n{IMAGE_PLACEHOLDER}\n\nEnd."
        )
        # Figure at source_index 2 failed extraction, only 1 and 3 available
        figs = [
            _make_figure(1, source_index=1),
            _make_figure(2, source_index=3),
        ]

        result = embed_figures_in_markdown(md, figs, ASSETS_DIR)

        assert IMAGE_PLACEHOLDER not in result
        assert "figure-1.png" in result
        assert "figure-2.png" in result  # filename uses extracted_count
        # The missing placeholder for source_index=2 is silently removed
        # (empty string replacement), so no fallback text appears
        assert result.index("figure-1.png") < result.index("figure-2.png")


# ============================================================
# More placeholders than figures
# ============================================================


class TestEmbedFiguresMorePlaceholders:
    """Tests where placeholder count > figure count."""

    def test_extra_placeholders_silently_removed(self) -> None:
        """Three placeholders, one figure -> two are silently removed."""
        md = (
            f"A\n\n{IMAGE_PLACEHOLDER}\n\n"
            f"B\n\n{IMAGE_PLACEHOLDER}\n\n"
            f"C\n\n{IMAGE_PLACEHOLDER}"
        )
        figs = [_make_figure(1, source_index=1)]

        result = embed_figures_in_markdown(md, figs, ASSETS_DIR)

        assert IMAGE_PLACEHOLDER not in result
        assert "figure-1.png" in result
        # Unmatched placeholders are replaced with empty string
        # so no fallback text appears in the output
        assert "A" in result
        assert "B" in result
        assert "C" in result

    def test_no_figures_all_placeholders_removed(self) -> None:
        """Placeholders exist but no figures extracted at all -> all removed."""
        md = f"Text.\n\n{IMAGE_PLACEHOLDER}\n\n{IMAGE_PLACEHOLDER}"

        result = embed_figures_in_markdown(md, [], ASSETS_DIR)

        assert IMAGE_PLACEHOLDER not in result
        # All placeholders silently removed; only the text remains
        assert "Text." in result


# ============================================================
# More figures than placeholders
# ============================================================


class TestEmbedFiguresMoreFigures:
    """Tests where figure count > placeholder count."""

    def test_surplus_figures_appended_at_end(self) -> None:
        """One placeholder, two figures -> second appended at end."""
        md = f"Text.\n\n{IMAGE_PLACEHOLDER}\n\nEnd."
        figs = [
            _make_figure(1, source_index=1),
            _make_figure(2, source_index=2),
        ]

        result = embed_figures_in_markdown(md, figs, ASSETS_DIR)

        assert IMAGE_PLACEHOLDER not in result
        assert "figure-1.png" in result
        assert "figure-2.png" in result
        # First figure should be in its placeholder position
        assert result.index("figure-1.png") < result.index("End.")
        # Second figure should be appended after "End."
        assert result.index("End.") < result.index("figure-2.png")


# ============================================================
# No placeholders
# ============================================================


class TestEmbedFiguresNoPlaceholders:
    """Tests where body has no <!-- image --> placeholders."""

    def test_no_placeholders_figures_appended_at_end(self) -> None:
        """Body has no placeholders -> all figures go at the end."""
        md = "# Title\n\nSome text without any image markers."
        figs = [
            _make_figure(1, source_index=1),
            _make_figure(2, source_index=2),
        ]

        result = embed_figures_in_markdown(md, figs, ASSETS_DIR)

        assert "figure-1.png" in result
        assert "figure-2.png" in result
        # Original text should come first
        assert result.index("Some text") < result.index("figure-1.png")
        assert result.index("figure-1.png") < result.index("figure-2.png")

    def test_no_placeholders_no_figures_returns_unchanged(self) -> None:
        """No placeholders, no figures -> body returned unchanged."""
        md = "# Title\n\nJust plain text."

        result = embed_figures_in_markdown(md, [], ASSETS_DIR)

        assert result == md

    def test_no_placeholders_single_figure_appended(self) -> None:
        """Single figure, no placeholders -> appended at end."""
        md = "Body text."
        figs = [_make_figure(1, source_index=1)]

        result = embed_figures_in_markdown(md, figs, ASSETS_DIR)

        assert result.startswith("Body text.")
        assert "![Figure 1](paper.assets/figure-1.png)" in result


# ============================================================
# Edge cases
# ============================================================


class TestEmbedFiguresEdgeCases:
    """Edge cases for the embedding logic."""

    def test_placeholder_at_very_start(self) -> None:
        """Placeholder as the first thing in the body."""
        md = f"{IMAGE_PLACEHOLDER}\n\nText after."
        figs = [_make_figure(1, source_index=1)]

        result = embed_figures_in_markdown(md, figs, ASSETS_DIR)

        assert result.startswith("![Figure 1]")

    def test_placeholder_at_very_end(self) -> None:
        """Placeholder as the last thing in the body."""
        md = f"Text before.\n\n{IMAGE_PLACEHOLDER}"
        figs = [_make_figure(1, source_index=1)]

        result = embed_figures_in_markdown(md, figs, ASSETS_DIR)

        assert result.endswith("figure-1.png)")

    def test_consecutive_placeholders(self) -> None:
        """Two placeholders with no text between them."""
        md = f"{IMAGE_PLACEHOLDER}\n{IMAGE_PLACEHOLDER}"
        figs = [
            _make_figure(1, source_index=1),
            _make_figure(2, source_index=2),
        ]

        result = embed_figures_in_markdown(md, figs, ASSETS_DIR)

        assert IMAGE_PLACEHOLDER not in result
        assert "figure-1.png" in result
        assert "figure-2.png" in result

    def test_alt_text_with_special_chars(self) -> None:
        """Figure alt text containing brackets is preserved."""
        md = f"Body.\n\n{IMAGE_PLACEHOLDER}"
        fig = ExtractedFigure(
            image_bytes=b"data",
            filename="figure-1.png",
            alt_text="Comparison of [A] vs (B)",
            source_index=1,
        )

        result = embed_figures_in_markdown(md, [fig], ASSETS_DIR)

        assert "![Comparison of [A] vs (B)]" in result

    def test_empty_body_no_figures(self) -> None:
        """Empty string body, no figures."""
        result = embed_figures_in_markdown("", [], ASSETS_DIR)
        assert result == ""


# ============================================================
# URL encoding of image paths
# ============================================================


class TestEmbedFiguresUrlEncoding:
    """Tests that image paths in Markdown references are URL-encoded."""

    def test_spaces_in_assets_dir_are_encoded(self) -> None:
        """Spaces in the assets directory name become %20."""
        md = f"Text.\n\n{IMAGE_PLACEHOLDER}"
        fig = _make_figure(1, source_index=1)

        result = embed_figures_in_markdown(md, [fig], ASSETS_DIR_WITH_SPACES)

        assert "%20" in result
        assert "S%20et%20al.%202022%20-%20Some%20Paper.assets/figure-1.png" in result
        # Alt text should NOT be encoded
        assert "![Figure 1]" in result

    def test_slashes_preserved_in_path(self) -> None:
        """The / between dir and filename is not encoded."""
        md = f"Text.\n\n{IMAGE_PLACEHOLDER}"
        fig = _make_figure(1, source_index=1)

        result = embed_figures_in_markdown(md, [fig], ASSETS_DIR_WITH_SPACES)

        # The slash between dir/filename must remain literal
        assert "%2F" not in result
        assert ".assets/figure-1.png" in result

    def test_japanese_chars_in_path_are_encoded(self) -> None:
        """Japanese characters in directory names are percent-encoded."""
        md = f"Text.\n\n{IMAGE_PLACEHOLDER}"
        fig = _make_figure(1, source_index=1)
        japanese_dir = "田中 2024 - 論文.assets"

        result = embed_figures_in_markdown(md, [fig], japanese_dir)

        # Japanese characters should be percent-encoded
        assert IMAGE_PLACEHOLDER not in result
        assert "figure-1.png" in result
        # Raw Japanese should NOT appear in the path portion
        assert "田中" not in result
        assert "%E7%94%B0%E4%B8%AD" in result  # URL-encoded "田中"

    def test_simple_dir_name_unchanged(self) -> None:
        """A simple directory name with no special chars stays clean."""
        md = f"Text.\n\n{IMAGE_PLACEHOLDER}"
        fig = _make_figure(1, source_index=1)

        result = embed_figures_in_markdown(md, [fig], "paper.assets")

        assert "![Figure 1](paper.assets/figure-1.png)" in result

    def test_no_placeholders_appended_figures_also_encoded(self) -> None:
        """Figures appended at end (no placeholders) also get encoded paths."""
        md = "Body text only."
        fig = _make_figure(1, source_index=1)

        result = embed_figures_in_markdown(md, [fig], ASSETS_DIR_WITH_SPACES)

        assert "S%20et%20al." in result
        assert "/figure-1.png" in result


# ============================================================
# Unmatched placeholder removal (silent deletion)
# ============================================================


class TestEmbedFiguresPlaceholderRemoval:
    """Tests that unmatched placeholders are silently removed."""

    def test_unmatched_placeholder_deleted_not_replaced_with_text(self) -> None:
        """An unmatched placeholder should vanish, not leave fallback text."""
        md = f"Before.\n\n{IMAGE_PLACEHOLDER}\n\nAfter."

        result = embed_figures_in_markdown(md, [], ASSETS_DIR)

        assert IMAGE_PLACEHOLDER not in result
        # No Japanese fallback text should appear
        assert "図を取得できませんでした" not in result
        assert "Before." in result
        assert "After." in result

    def test_multiple_unmatched_placeholders_all_deleted(self) -> None:
        """Multiple unmatched placeholders all vanish cleanly."""
        md = (
            f"A\n\n{IMAGE_PLACEHOLDER}\n\n"
            f"B\n\n{IMAGE_PLACEHOLDER}\n\n"
            f"C\n\n{IMAGE_PLACEHOLDER}\n\nD"
        )

        result = embed_figures_in_markdown(md, [], ASSETS_DIR)

        assert IMAGE_PLACEHOLDER not in result
        assert "A" in result
        assert "B" in result
        assert "C" in result
        assert "D" in result

    def test_mixed_matched_and_unmatched(self) -> None:
        """Some placeholders match, others are silently removed."""
        md = (
            f"Intro\n\n{IMAGE_PLACEHOLDER}\n\n"
            f"Middle\n\n{IMAGE_PLACEHOLDER}\n\n"
            f"End\n\n{IMAGE_PLACEHOLDER}"
        )
        # Only source_index 2 has a figure; 1 and 3 are unmatched
        figs = [_make_figure(1, source_index=2)]

        result = embed_figures_in_markdown(md, figs, ASSETS_DIR)

        assert IMAGE_PLACEHOLDER not in result
        assert "figure-1.png" in result
        # No fallback text
        assert "図を取得できませんでした" not in result

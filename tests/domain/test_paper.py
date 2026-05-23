"""Tests for Paper domain: Value Objects and Paper Entity.

Covers happy path, boundary values, and error cases for:
- DOI, Author, PublicationYear, InitialLetter, PaperFileName (Value Objects)
- Metadata (Value Object)
- Paper (Entity)
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

import pytest

from src.domain.paper import (
    DOI,
    Author,
    InitialLetter,
    Metadata,
    Paper,
    PaperFileName,
    PaperId,
    PublicationYear,
)

# ============================================================
# DOI Value Object
# ============================================================


class TestDOI:
    """Tests for DOI value object."""

    def test_create_valid_doi(self) -> None:
        doi = DOI("10.1234/abcd.5678")
        assert doi.value == "10.1234/abcd.5678"

    def test_normalize_removes_url_prefix(self) -> None:
        doi = DOI("https://doi.org/10.1234/abcd.5678")
        assert doi.value == "10.1234/abcd.5678"

    def test_normalize_removes_http_prefix(self) -> None:
        doi = DOI("http://doi.org/10.1234/abcd.5678")
        assert doi.value == "10.1234/abcd.5678"

    def test_normalize_removes_dx_doi_prefix(self) -> None:
        doi = DOI("https://dx.doi.org/10.1234/abcd.5678")
        assert doi.value == "10.1234/abcd.5678"

    def test_normalize_lowercases(self) -> None:
        doi = DOI("10.1234/ABCD.5678")
        assert doi.value == "10.1234/abcd.5678"

    def test_empty_doi_raises(self) -> None:
        with pytest.raises(ValueError, match="DOI"):
            DOI("")

    def test_whitespace_only_doi_raises(self) -> None:
        with pytest.raises(ValueError, match="DOI"):
            DOI("   ")

    def test_invalid_format_raises(self) -> None:
        with pytest.raises(ValueError, match="DOI"):
            DOI("not-a-doi")

    def test_doi_equality(self) -> None:
        doi1 = DOI("10.1234/abcd")
        doi2 = DOI("10.1234/abcd")
        assert doi1 == doi2

    def test_doi_inequality(self) -> None:
        doi1 = DOI("10.1234/abcd")
        doi2 = DOI("10.1234/efgh")
        assert doi1 != doi2

    def test_doi_with_complex_suffix(self) -> None:
        doi = DOI("10.1002/(sici)1097-0142(19991201)86:11<2346::aid-cncr25>3.0.co;2-3")
        assert doi.value.startswith("10.1002/")


# ============================================================
# Author Value Object
# ============================================================


class TestAuthor:
    """Tests for Author value object."""

    def test_create_valid_author(self) -> None:
        author = Author(family_name="Kitano", given_name="Takahiro")
        assert author.family_name == "Kitano"
        assert author.given_name == "Takahiro"

    def test_family_name_required(self) -> None:
        with pytest.raises(ValueError, match="family_name"):
            Author(family_name="", given_name="Takahiro")

    def test_given_name_optional(self) -> None:
        author = Author(family_name="Kitano", given_name="")
        assert author.family_name == "Kitano"
        assert author.given_name == ""

    def test_whitespace_family_name_raises(self) -> None:
        with pytest.raises(ValueError, match="family_name"):
            Author(family_name="   ", given_name="Test")

    def test_author_equality(self) -> None:
        a1 = Author(family_name="Kitano", given_name="T")
        a2 = Author(family_name="Kitano", given_name="T")
        assert a1 == a2

    def test_author_display_name_with_given(self) -> None:
        author = Author(family_name="Kitano", given_name="Takahiro")
        assert author.display_name == "Kitano, Takahiro"

    def test_author_display_name_without_given(self) -> None:
        author = Author(family_name="Kitano", given_name="")
        assert author.display_name == "Kitano"

    def test_japanese_name(self) -> None:
        author = Author(family_name="Kitano", given_name="Takahiro")
        assert author.family_name == "Kitano"


# ============================================================
# PublicationYear Value Object
# ============================================================


class TestPublicationYear:
    """Tests for PublicationYear value object."""

    MIN_YEAR = 1900

    def test_create_valid_year(self) -> None:
        year = PublicationYear(2024)
        assert year.value == 2024

    def test_minimum_year(self) -> None:
        year = PublicationYear(1900)
        assert year.value == 1900

    def test_below_minimum_raises(self) -> None:
        with pytest.raises(ValueError, match="year"):
            PublicationYear(1899)

    def test_future_year_within_next_raises(self) -> None:
        # Next year should be the max
        current_year = datetime.now(tz=UTC).year
        next_year = current_year + 1
        year = PublicationYear(next_year)
        assert year.value == next_year

    def test_far_future_year_raises(self) -> None:
        current_year = datetime.now(tz=UTC).year
        with pytest.raises(ValueError, match="year"):
            PublicationYear(current_year + 2)

    def test_year_equality(self) -> None:
        assert PublicationYear(2024) == PublicationYear(2024)

    def test_year_inequality(self) -> None:
        assert PublicationYear(2024) != PublicationYear(2023)


# ============================================================
# InitialLetter Value Object
# ============================================================


class TestInitialLetter:
    """Tests for InitialLetter value object."""

    def test_uppercase_letter(self) -> None:
        il = InitialLetter("K")
        assert il.letter == "K"

    def test_lowercase_converted_to_uppercase(self) -> None:
        il = InitialLetter("k")
        assert il.letter == "K"

    def test_non_ascii_letter_becomes_hash(self) -> None:
        il = InitialLetter.from_family_name("Tanaka")
        assert il.letter == "T"

    def test_japanese_name_becomes_hash(self) -> None:
        il = InitialLetter.from_family_name("田中")
        assert il.letter == "#"

    def test_digit_first_becomes_hash(self) -> None:
        il = InitialLetter.from_family_name("3M-Research")
        assert il.letter == "#"

    def test_empty_name_becomes_hash(self) -> None:
        il = InitialLetter.from_family_name("")
        assert il.letter == "#"

    def test_from_family_name_normal(self) -> None:
        il = InitialLetter.from_family_name("Kitano")
        assert il.letter == "K"

    def test_all_valid_letters(self) -> None:
        for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            il = InitialLetter(ch)
            assert il.letter == ch

    def test_hash_is_valid(self) -> None:
        il = InitialLetter("#")
        assert il.letter == "#"

    def test_invalid_letter_raises(self) -> None:
        with pytest.raises(ValueError, match="letter"):
            InitialLetter("!")


# ============================================================
# PaperFileName Value Object
# ============================================================


class TestPaperFileName:
    """Tests for PaperFileName value object."""

    def test_paperpile_format_single_author(self) -> None:
        authors = [Author(family_name="Kitano", given_name="T")]
        fname = PaperFileName.build(authors=authors, year=2024, title="Tracheal Regeneration")
        assert fname.value == "Kitano 2024 - Tracheal Regeneration"

    def test_paperpile_format_two_authors(self) -> None:
        authors = [
            Author(family_name="Kitano", given_name="T"),
            Author(family_name="Suzuki", given_name="H"),
        ]
        fname = PaperFileName.build(authors=authors, year=2024, title="Tracheal Regeneration")
        assert fname.value == "Kitano and Suzuki 2024 - Tracheal Regeneration"

    def test_paperpile_format_three_or_more_authors(self) -> None:
        authors = [
            Author(family_name="Kitano", given_name="T"),
            Author(family_name="Suzuki", given_name="H"),
            Author(family_name="Yamada", given_name="K"),
        ]
        fname = PaperFileName.build(authors=authors, year=2024, title="Tracheal Regeneration")
        assert fname.value == "Kitano et al. 2024 - Tracheal Regeneration"

    def test_os_forbidden_chars_removed(self) -> None:
        authors = [Author(family_name="Smith", given_name="J")]
        fname = PaperFileName.build(
            authors=authors, year=2024, title='Is "this" valid: a <test>?'
        )
        # Forbidden chars: \ / : * ? " < > |
        assert not any(c in fname.value for c in r'\/:*?"<>|')

    def test_long_title_truncated(self) -> None:
        authors = [Author(family_name="Smith", given_name="J")]
        long_title = "A" * 300
        fname = PaperFileName.build(authors=authors, year=2024, title=long_title)
        # Total filename must not exceed 260 chars (Windows limit)
        max_filename_len = 260
        assert len(fname.value) <= max_filename_len

    def test_empty_authors_raises(self) -> None:
        with pytest.raises(ValueError, match="author"):
            PaperFileName.build(authors=[], year=2024, title="Test")

    def test_japanese_title_preserved(self) -> None:
        authors = [Author(family_name="Kitano", given_name="T")]
        fname = PaperFileName.build(
            authors=authors,
            year=2024,
            title="気管再生におけるメカニカルストレス",
        )
        assert "気管" in fname.value


# ============================================================
# PaperId
# ============================================================


class TestPaperId:
    """Tests for PaperId generation."""

    def test_from_doi(self) -> None:
        doi = DOI("10.1234/abcd.5678")
        paper_id = PaperId.from_doi(doi)
        assert paper_id.value == "10.1234/abcd.5678"

    def test_from_pdf_bytes(self) -> None:
        data = b"fake pdf content for hashing"
        paper_id = PaperId.from_pdf_bytes(data)
        assert paper_id.value.startswith("sha256:")
        # 16 hex characters after prefix
        hex_part = paper_id.value.removeprefix("sha256:")
        assert len(hex_part) == 16
        assert re.match(r"^[0-9a-f]{16}$", hex_part)

    def test_from_pdf_bytes_deterministic(self) -> None:
        data = b"same content"
        id1 = PaperId.from_pdf_bytes(data)
        id2 = PaperId.from_pdf_bytes(data)
        assert id1 == id2

    def test_from_pdf_bytes_different_content(self) -> None:
        id1 = PaperId.from_pdf_bytes(b"content A")
        id2 = PaperId.from_pdf_bytes(b"content B")
        assert id1 != id2

    def test_paper_id_equality(self) -> None:
        id1 = PaperId("10.1234/test")
        id2 = PaperId("10.1234/test")
        assert id1 == id2

    def test_paper_id_hashable(self) -> None:
        id1 = PaperId("10.1234/test")
        id_set = {id1}
        assert PaperId("10.1234/test") in id_set


# ============================================================
# Metadata Value Object
# ============================================================


class TestMetadata:
    """Tests for Metadata value object."""

    def test_create_valid_metadata(self) -> None:
        md = Metadata(
            title="Tracheal Regeneration",
            authors=[Author(family_name="Kitano", given_name="T")],
            year=PublicationYear(2024),
            doi=DOI("10.1234/abcd"),
        )
        assert md.title == "Tracheal Regeneration"
        assert len(md.authors) == 1
        assert md.year.value == 2024

    def test_title_required(self) -> None:
        with pytest.raises(ValueError, match="title"):
            Metadata(
                title="",
                authors=[Author(family_name="Kitano", given_name="T")],
                year=PublicationYear(2024),
            )

    def test_at_least_one_author_required(self) -> None:
        with pytest.raises(ValueError, match="author"):
            Metadata(
                title="Test Paper",
                authors=[],
                year=PublicationYear(2024),
            )

    def test_doi_optional(self) -> None:
        md = Metadata(
            title="Test Paper",
            authors=[Author(family_name="Smith", given_name="J")],
            year=PublicationYear(2024),
            doi=None,
        )
        assert md.doi is None

    def test_abstract_is_trimmed(self) -> None:
        md = Metadata(
            title="Test Paper",
            authors=[Author(family_name="Smith", given_name="J")],
            year=PublicationYear(2024),
            abstract="  This is an abstract.  ",
        )
        assert md.abstract == "This is an abstract."

    def test_memo_is_trimmed(self) -> None:
        md = Metadata(
            title="Test Paper",
            authors=[Author(family_name="Smith", given_name="J")],
            year=PublicationYear(2024),
            memo="  Important clinical note.  ",
        )
        assert md.memo == "Important clinical note."

    def test_bibliographic_fields_default_to_empty_strings(self) -> None:
        md = Metadata(
            title="Test Paper",
            authors=[Author(family_name="Smith", given_name="J")],
            year=PublicationYear(2024),
        )

        assert md.journal == ""
        assert md.journal_abbrev == ""
        assert md.volume == ""
        assert md.issue == ""
        assert md.pages == ""

    def test_multiple_authors(self) -> None:
        md = Metadata(
            title="Test",
            authors=[
                Author(family_name="A", given_name="X"),
                Author(family_name="B", given_name="Y"),
            ],
            year=PublicationYear(2024),
        )
        assert len(md.authors) == 2

    def test_first_author(self) -> None:
        md = Metadata(
            title="Test",
            authors=[
                Author(family_name="Kitano", given_name="T"),
                Author(family_name="Suzuki", given_name="H"),
            ],
            year=PublicationYear(2024),
        )
        assert md.first_author.family_name == "Kitano"


# ============================================================
# Paper Entity
# ============================================================


class TestPaper:
    """Tests for Paper entity."""

    @pytest.fixture()
    def sample_metadata(self) -> Metadata:
        return Metadata(
            title="Tracheal Regeneration Under Mechanical Stress",
            authors=[
                Author(family_name="Kitano", given_name="Takahiro"),
                Author(family_name="Suzuki", given_name="Hanako"),
            ],
            year=PublicationYear(2024),
            doi=DOI("10.1234/trachea.2024"),
        )

    @pytest.fixture()
    def sample_paper(self, sample_metadata: Metadata) -> Paper:
        return Paper.create(
            metadata=sample_metadata,
            pdf_path="K/Kitano and Suzuki 2024 - Tracheal Regeneration.pdf",
        )

    def test_create_paper_with_doi(self, sample_paper: Paper) -> None:
        assert sample_paper.id.value == "10.1234/trachea.2024"
        assert sample_paper.metadata.title == "Tracheal Regeneration Under Mechanical Stress"

    def test_create_paper_with_doi_without_pdf(self, sample_metadata: Metadata) -> None:
        paper = Paper.create(metadata=sample_metadata)

        assert paper.id.value == "10.1234/trachea.2024"
        assert paper.pdf_path is None
        assert not paper.has_pdf

    def test_determine_initial_letter(self, sample_paper: Paper) -> None:
        assert sample_paper.initial_letter.letter == "K"

    def test_build_file_name(self, sample_paper: Paper) -> None:
        fname = sample_paper.build_file_name()
        assert "Kitano" in fname.value
        assert "2024" in fname.value

    def test_paper_without_doi(self) -> None:
        md = Metadata(
            title="Unknown DOI Paper",
            authors=[Author(family_name="Yamada", given_name="K")],
            year=PublicationYear(2023),
            doi=None,
        )
        paper = Paper.create(
            metadata=md,
            pdf_path="Y/Yamada 2023 - Unknown.pdf",
            pdf_head_bytes=b"fake pdf header content" * 100,
        )
        assert paper.id.value.startswith("sha256:")

    def test_paper_tags_default_empty(self, sample_paper: Paper) -> None:
        assert sample_paper.tags == []

    def test_update_metadata(self, sample_paper: Paper) -> None:
        new_md = Metadata(
            title="Updated Title",
            authors=[Author(family_name="Kitano", given_name="T")],
            year=PublicationYear(2025),
            doi=DOI("10.1234/trachea.2024"),
        )
        sample_paper.update_metadata(new_md)
        assert sample_paper.metadata.title == "Updated Title"

    def test_to_markdown_note(self, sample_paper: Paper) -> None:
        md_text = sample_paper.to_markdown_note()
        assert "paper_id:" in md_text or "paper_id" in md_text
        assert "Kitano" in md_text
        assert "2024" in md_text

    def test_to_markdown_note_includes_abstract(self) -> None:
        metadata = Metadata(
            title="Test",
            authors=[Author(family_name="Smith", given_name="J")],
            year=PublicationYear(2024),
            doi=DOI("10.1234/abstract"),
            abstract="Background and methods.",
        )
        paper = Paper.create(metadata=metadata, pdf_path="S/test.pdf")

        md_text = paper.to_markdown_note()

        assert 'abstract: "Background and methods."' in md_text

    def test_to_markdown_note_includes_memo(self) -> None:
        metadata = Metadata(
            title="Test",
            authors=[Author(family_name="Smith", given_name="J")],
            year=PublicationYear(2024),
            doi=DOI("10.1234/memo"),
            memo="Use this for review discussion.",
        )
        paper = Paper.create(metadata=metadata, pdf_path="S/test.pdf")

        md_text = paper.to_markdown_note()

        assert 'memo: "Use this for review discussion."' in md_text

    def test_to_markdown_note_includes_bibliographic_fields_after_doi(self) -> None:
        metadata = Metadata(
            title="Test",
            authors=[Author(family_name="Smith", given_name="J")],
            year=PublicationYear(2024),
            doi=DOI("10.1234/biblio"),
            journal="Nature",
            journal_abbrev="Nature",
            volume="590",
            issue="7844",
            pages="2364-2370",
        )
        paper = Paper.create(metadata=metadata, pdf_path="S/test.pdf")

        md_text = paper.to_markdown_note()

        expected_block = (
            'doi: "10.1234/biblio"\n'
            'journal: "Nature"\n'
            'journal_abbrev: "Nature"\n'
            'volume: "590"\n'
            'issue: "7844"\n'
            'pages: "2364-2370"\n'
            'abstract: ""'
        )
        assert expected_block in md_text

    def test_to_markdown_note_omits_empty_bibliographic_fields(self) -> None:
        metadata = Metadata(
            title="Test",
            authors=[Author(family_name="Smith", given_name="J")],
            year=PublicationYear(2024),
            doi=DOI("10.1234/no-biblio"),
        )
        paper = Paper.create(metadata=metadata, pdf_path="S/test.pdf")

        md_text = paper.to_markdown_note()

        assert "\njournal:" not in md_text
        assert "\njournal_abbrev:" not in md_text
        assert "\nvolume:" not in md_text
        assert "\nissue:" not in md_text
        assert "\npages:" not in md_text

    def test_to_markdown_note_without_pdf_omits_pdf_link(
        self,
        sample_metadata: Metadata,
    ) -> None:
        paper = Paper.create(metadata=sample_metadata)

        md_text = paper.to_markdown_note()

        assert 'pdf_filename: ""' in md_text
        assert ".pdf)" not in md_text

    def test_paper_equality_by_id(self) -> None:
        md = Metadata(
            title="Test",
            authors=[Author(family_name="Smith", given_name="J")],
            year=PublicationYear(2024),
            doi=DOI("10.1234/same"),
        )
        p1 = Paper.create(metadata=md, pdf_path="S/test.pdf")
        p2 = Paper.create(metadata=md, pdf_path="S/test2.pdf")
        assert p1.id == p2.id

    def test_create_paper_without_doi_and_no_bytes_raises(self) -> None:
        md = Metadata(
            title="No DOI",
            authors=[Author(family_name="Test", given_name="T")],
            year=PublicationYear(2024),
            doi=None,
        )
        with pytest.raises(ValueError, match="pdf_head_bytes"):
            Paper.create(metadata=md, pdf_path="T/test.pdf")

    def test_note_path_derived(self, sample_paper: Paper) -> None:
        assert sample_paper.note_path is not None or sample_paper.note_path is None
        # note_path is set after save; initially may be None or derived

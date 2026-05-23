"""Tests for MetadataBuffer (Chrome extension metadata receive buffer)."""

from __future__ import annotations

import time

from src.application.metadata_buffer import DEFAULT_TTL_SECONDS, MetadataBuffer
from src.domain.paper import DOI, Author, Metadata, PublicationYear

# ============================================================
# Fixtures
# ============================================================


def _make_metadata(
    title: str = "Test Paper",
    family: str = "Smith",
    given: str = "John",
    year: int = 2024,
    doi_value: str | None = "10.1234/test.001",
) -> Metadata:
    """Helper to create a Metadata instance."""
    doi = DOI(doi_value) if doi_value else None
    return Metadata(
        title=title,
        authors=(Author(family_name=family, given_name=given),),
        year=PublicationYear(year),
        doi=doi,
    )


# ============================================================
# Tests: Basic operations
# ============================================================


class TestMetadataBufferPut:
    """Tests for MetadataBuffer.put()."""

    def test_put_stores_entry(self) -> None:
        buf = MetadataBuffer()
        meta = _make_metadata()
        buf.put(meta)
        assert buf.size() > 0

    def test_put_metadata_with_doi_retrievable_by_doi(self) -> None:
        buf = MetadataBuffer()
        meta = _make_metadata(doi_value="10.1234/abc")
        buf.put(meta)
        result = buf.lookup_by_doi("10.1234/abc")
        assert result is not None
        assert result.title == "Test Paper"

    def test_put_metadata_without_doi_retrievable_by_title(self) -> None:
        buf = MetadataBuffer()
        meta = _make_metadata(doi_value=None)
        buf.put(meta)
        result = buf.lookup_by_title("Test Paper")
        assert result is not None

    def test_put_overwrites_existing_doi_entry(self) -> None:
        buf = MetadataBuffer()
        meta1 = _make_metadata(title="First", doi_value="10.1234/same")
        meta2 = _make_metadata(title="Second", doi_value="10.1234/same")
        buf.put(meta1)
        buf.put(meta2)
        result = buf.lookup_by_doi("10.1234/same")
        assert result is not None
        assert result.title == "Second"


# ============================================================
# Tests: Lookup
# ============================================================


class TestMetadataBufferLookup:
    """Tests for buffer lookup methods."""

    def test_lookup_by_doi_returns_none_for_missing(self) -> None:
        buf = MetadataBuffer()
        assert buf.lookup_by_doi("10.9999/nonexistent") is None

    def test_lookup_by_title_case_insensitive(self) -> None:
        buf = MetadataBuffer()
        meta = _make_metadata(title="Important Research Paper")
        buf.put(meta)
        result = buf.lookup_by_title("important research paper")
        assert result is not None
        assert result.title == "Important Research Paper"

    def test_lookup_by_title_returns_none_for_missing(self) -> None:
        buf = MetadataBuffer()
        assert buf.lookup_by_title("nonexistent") is None

    def test_lookup_by_author_year_match(self) -> None:
        buf = MetadataBuffer()
        meta = _make_metadata(family="Tanaka", year=2023, doi_value="10.1234/t1")
        buf.put(meta)
        result = buf.lookup_by_author_year("Tanaka", 2023)
        assert result is not None
        assert result.first_author.family_name == "Tanaka"

    def test_lookup_by_author_year_case_insensitive(self) -> None:
        buf = MetadataBuffer()
        meta = _make_metadata(family="Tanaka", year=2023, doi_value="10.1234/t2")
        buf.put(meta)
        result = buf.lookup_by_author_year("tanaka", 2023)
        assert result is not None

    def test_lookup_by_author_year_no_match_wrong_year(self) -> None:
        buf = MetadataBuffer()
        meta = _make_metadata(family="Tanaka", year=2023, doi_value="10.1234/t3")
        buf.put(meta)
        result = buf.lookup_by_author_year("Tanaka", 2022)
        assert result is None

    def test_lookup_by_author_year_no_match_wrong_name(self) -> None:
        buf = MetadataBuffer()
        meta = _make_metadata(family="Tanaka", year=2023, doi_value="10.1234/t4")
        buf.put(meta)
        result = buf.lookup_by_author_year("Yamada", 2023)
        assert result is None


# ============================================================
# Tests: TTL expiration
# ============================================================


class TestMetadataBufferTTL:
    """Tests for TTL-based expiration."""

    def test_default_ttl_is_ten_minutes(self) -> None:
        buf = MetadataBuffer()
        assert buf.ttl_seconds == DEFAULT_TTL_SECONDS
        assert buf.ttl_seconds == 600

    def test_custom_ttl(self) -> None:
        buf = MetadataBuffer(ttl_seconds=30)
        assert buf.ttl_seconds == 30

    def test_expired_entry_returns_none_by_doi(self) -> None:
        buf = MetadataBuffer(ttl_seconds=0.01)  # 10ms TTL
        meta = _make_metadata(doi_value="10.1234/expire")
        buf.put(meta)
        time.sleep(0.05)
        assert buf.lookup_by_doi("10.1234/expire") is None

    def test_expired_entry_returns_none_by_title(self) -> None:
        buf = MetadataBuffer(ttl_seconds=0.01)
        meta = _make_metadata(title="Expiring Paper")
        buf.put(meta)
        time.sleep(0.05)
        assert buf.lookup_by_title("Expiring Paper") is None

    def test_expired_entry_returns_none_by_author_year(self) -> None:
        buf = MetadataBuffer(ttl_seconds=0.01)
        meta = _make_metadata(family="Expire", year=2024, doi_value="10.1234/exp")
        buf.put(meta)
        time.sleep(0.05)
        assert buf.lookup_by_author_year("Expire", 2024) is None


# ============================================================
# Tests: Remove and clear
# ============================================================


class TestMetadataBufferRemove:
    """Tests for explicit removal."""

    def test_remove_by_doi(self) -> None:
        buf = MetadataBuffer()
        meta = _make_metadata(doi_value="10.1234/remove")
        buf.put(meta)
        buf.remove_by_doi("10.1234/remove")
        assert buf.lookup_by_doi("10.1234/remove") is None

    def test_remove_by_title(self) -> None:
        buf = MetadataBuffer()
        meta = _make_metadata(title="Remove Me")
        buf.put(meta)
        buf.remove_by_title("Remove Me")
        assert buf.lookup_by_title("Remove Me") is None

    def test_remove_nonexistent_doi_is_noop(self) -> None:
        buf = MetadataBuffer()
        buf.remove_by_doi("10.9999/nope")  # Should not raise

    def test_clear(self) -> None:
        buf = MetadataBuffer()
        buf.put(_make_metadata(doi_value="10.1234/c1"))
        buf.put(_make_metadata(title="Another", doi_value="10.1234/c2"))
        buf.clear()
        assert buf.size() == 0

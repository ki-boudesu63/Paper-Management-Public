"""Domain model for Paper aggregate.

Contains Value Objects (DOI, Author, PublicationYear, InitialLetter,
PaperFileName, PaperId, Metadata) and the Paper entity.

Pure Python, no external library dependencies.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

# ============================================================
# Constants
# ============================================================

DOI_PATTERN = re.compile(r"^10\.\d{4,9}/.+$")
DOI_URL_PREFIXES = (
    "https://doi.org/",
    "http://doi.org/",
    "https://dx.doi.org/",
    "http://dx.doi.org/",
)
MIN_PUBLICATION_YEAR = 1900
VALID_INITIAL_LETTERS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZ#")
OS_FORBIDDEN_CHARS = re.compile(r'[\\/:*?"<>|]')
MAX_FILENAME_LENGTH = 260
SHA256_PREFIX = "sha256:"
SHA256_HEX_LENGTH = 16
PDF_HEAD_SIZE = 65536  # 64KB


# ============================================================
# DOI Value Object
# ============================================================


@dataclass(frozen=True, eq=True)
class DOI:
    """Digital Object Identifier, normalized to lowercase without URL prefix."""

    value: str

    def __post_init__(self) -> None:
        normalized = self._normalize(self.value)
        if not normalized:
            raise ValueError("DOI must not be empty")
        if not DOI_PATTERN.match(normalized):
            raise ValueError(f"DOI format invalid: {normalized}")
        # Bypass frozen to set the normalized value
        object.__setattr__(self, "value", normalized)

    @staticmethod
    def _normalize(raw: str) -> str:
        """Remove URL prefix and lowercase."""
        stripped = raw.strip()
        for prefix in DOI_URL_PREFIXES:
            if stripped.lower().startswith(prefix.lower()):
                stripped = stripped[len(prefix) :]
                break
        return stripped.lower()


# ============================================================
# Author Value Object
# ============================================================


@dataclass(frozen=True, eq=True)
class Author:
    """Author with required family name and optional given name."""

    family_name: str
    given_name: str = ""

    def __post_init__(self) -> None:
        if not self.family_name.strip():
            raise ValueError("family_name must not be empty")

    @property
    def display_name(self) -> str:
        """Format as 'Family, Given' or just 'Family' if no given name."""
        if self.given_name:
            return f"{self.family_name}, {self.given_name}"
        return self.family_name


# ============================================================
# PublicationYear Value Object
# ============================================================


@dataclass(frozen=True, eq=True)
class PublicationYear:
    """Publication year, constrained to 1900..next_year."""

    value: int

    def __post_init__(self) -> None:
        max_year = datetime.now(tz=UTC).year + 1
        if self.value < MIN_PUBLICATION_YEAR:
            raise ValueError(
                f"Publication year must be >= {MIN_PUBLICATION_YEAR}, got {self.value}"
            )
        if self.value > max_year:
            raise ValueError(
                f"Publication year must be <= {max_year}, got {self.value}"
            )


# ============================================================
# InitialLetter Value Object
# ============================================================


@dataclass(frozen=True, eq=True)
class InitialLetter:
    """First letter of the first author's family name (A-Z or '#')."""

    letter: str

    def __post_init__(self) -> None:
        normalized = self.letter.upper()
        if normalized not in VALID_INITIAL_LETTERS:
            raise ValueError(
                f"letter must be A-Z or '#', got '{self.letter}'"
            )
        object.__setattr__(self, "letter", normalized)

    @classmethod
    def from_family_name(cls, name: str) -> InitialLetter:
        """Derive initial letter from a family name.

        Non-ASCII leading characters and digits map to '#'.
        """
        stripped = name.strip()
        if not stripped:
            return cls("#")
        first_char = stripped[0]
        if first_char.isascii() and first_char.isalpha():
            return cls(first_char.upper())
        return cls("#")


# ============================================================
# PaperFileName Value Object
# ============================================================


@dataclass(frozen=True, eq=True)
class PaperFileName:
    """Paperpile-style filename (without extension).

    Format:
    - 1 author:  "Family YYYY - Title"
    - 2 authors: "Family1 and Family2 YYYY - Title"
    - 3+ authors: "Family1 et al. YYYY - Title"
    """

    value: str

    @classmethod
    def build(
        cls,
        authors: Sequence[Author],
        year: int,
        title: str,
    ) -> PaperFileName:
        """Build a Paperpile-format filename from metadata components.

        Raises:
            ValueError: If authors list is empty.
        """
        if not authors:
            raise ValueError("At least one author is required")

        author_part = cls._format_authors(authors)
        raw = f"{author_part} {year} - {title}"
        sanitized = OS_FORBIDDEN_CHARS.sub("", raw)

        if len(sanitized) > MAX_FILENAME_LENGTH:
            sanitized = sanitized[:MAX_FILENAME_LENGTH]

        return cls(value=sanitized)

    @staticmethod
    def _format_authors(authors: Sequence[Author]) -> str:
        """Format author names in Paperpile convention."""
        author_count = len(authors)
        if author_count == 1:
            return authors[0].family_name
        if author_count == 2:
            return f"{authors[0].family_name} and {authors[1].family_name}"
        return f"{authors[0].family_name} et al."


# ============================================================
# PaperId
# ============================================================


@dataclass(frozen=True, eq=True)
class PaperId:
    """Unique identifier for a paper.

    Either a normalized DOI string or 'sha256:<16hex>' hash.
    """

    value: str

    def __hash__(self) -> int:
        return hash(self.value)

    @classmethod
    def from_doi(cls, doi: DOI) -> PaperId:
        """Create PaperId from a DOI (uses normalized DOI value)."""
        return cls(value=doi.value)

    @classmethod
    def from_pdf_bytes(cls, data: bytes) -> PaperId:
        """Create PaperId from PDF head bytes using SHA-256.

        Uses the first 64KB (or full content if shorter).
        Takes the first 16 hex characters of the hash.
        """
        head = data[:PDF_HEAD_SIZE]
        digest = hashlib.sha256(head).hexdigest()[:SHA256_HEX_LENGTH]
        return cls(value=f"{SHA256_PREFIX}{digest}")


# ============================================================
# Metadata Value Object
# ============================================================


@dataclass(frozen=True, eq=True)
class Metadata:
    """Bibliographic metadata for a paper.

    Invariants: title is required, at least one author is required.
    DOI is optional.
    """

    title: str
    authors: tuple[Author, ...] | list[Author]
    year: PublicationYear
    doi: DOI | None = None
    abstract: str = ""
    memo: str = ""
    journal: str = ""
    journal_abbrev: str = ""
    volume: str = ""
    issue: str = ""
    pages: str = ""

    def __post_init__(self) -> None:
        if not self.title.strip():
            raise ValueError("title must not be empty")
        if not self.authors:
            raise ValueError("At least one author is required")
        # Convert list to tuple for immutability
        if isinstance(self.authors, list):
            object.__setattr__(self, "authors", tuple(self.authors))
        object.__setattr__(self, "abstract", self.abstract.strip())
        object.__setattr__(self, "memo", self.memo.strip())
        object.__setattr__(self, "journal", self.journal.strip())
        object.__setattr__(self, "journal_abbrev", self.journal_abbrev.strip())
        object.__setattr__(self, "volume", self.volume.strip())
        object.__setattr__(self, "issue", self.issue.strip())
        object.__setattr__(self, "pages", self.pages.strip())

    @property
    def first_author(self) -> Author:
        """Return the first author."""
        return self.authors[0]


# ============================================================
# Paper Entity (Aggregate Root)
# ============================================================


@dataclass(eq=False)
class Paper:
    """Paper entity, aggregate root of the Paper aggregate.

    Identity is determined by PaperId.
    """

    id: PaperId
    metadata: Metadata
    pdf_path: str | None
    note_path: str | None
    initial_letter: InitialLetter
    tags: list[str] = field(default_factory=list)
    imported_at: datetime = field(
        default_factory=lambda: datetime.now(tz=UTC)
    )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Paper):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

    @classmethod
    def create(
        cls,
        metadata: Metadata,
        pdf_path: str | None = None,
        pdf_head_bytes: bytes | None = None,
        note_path: str | None = None,
        tags: list[str] | None = None,
    ) -> Paper:
        """Factory method to create a Paper with proper ID assignment.

        If metadata has a DOI, PaperId is derived from the DOI.
        Otherwise, pdf_head_bytes must be provided for SHA-256 hashing.

        Raises:
            ValueError: If no DOI and no pdf_head_bytes provided.
        """
        if metadata.doi is not None:
            paper_id = PaperId.from_doi(metadata.doi)
        elif pdf_head_bytes is not None:
            paper_id = PaperId.from_pdf_bytes(pdf_head_bytes)
        else:
            raise ValueError(
                "Either DOI or pdf_head_bytes must be provided "
                "to generate a PaperId"
            )

        initial = InitialLetter.from_family_name(
            metadata.first_author.family_name
        )

        return cls(
            id=paper_id,
            metadata=metadata,
            pdf_path=pdf_path,
            note_path=note_path,
            initial_letter=initial,
            tags=tags if tags is not None else [],
        )

    @property
    def has_pdf(self) -> bool:
        """Return True when this paper has an attached PDF path."""
        return bool(self.pdf_path)

    def determine_initial_letter(self) -> InitialLetter:
        """Recalculate initial letter from the first author."""
        self.initial_letter = InitialLetter.from_family_name(
            self.metadata.first_author.family_name
        )
        return self.initial_letter

    def build_file_name(self) -> PaperFileName:
        """Generate Paperpile-format filename from current metadata."""
        return PaperFileName.build(
            authors=list(self.metadata.authors),
            year=self.metadata.year.value,
            title=self.metadata.title,
        )

    def update_metadata(self, new_metadata: Metadata) -> None:
        """Replace metadata and recalculate derived fields."""
        self.metadata = new_metadata
        self.determine_initial_letter()

    def to_markdown_note(self) -> str:
        """Generate a YAML-frontmatter Markdown note for this paper.

        Format follows the spec in the implementation plan (section 4-2).
        """
        doi_str = self.metadata.doi.value if self.metadata.doi else ""
        paper_id_str = self.id.value
        abstract_str = self.metadata.abstract.replace("\\", "\\\\").replace('"', '\\"')
        abstract_str = abstract_str.replace("\r\n", "\n").replace("\r", "\n")
        abstract_str = abstract_str.replace("\n", "\\n")
        memo_str = self.metadata.memo.replace("\\", "\\\\").replace('"', '\\"')
        memo_str = memo_str.replace("\r\n", "\n").replace("\r", "\n")
        memo_str = memo_str.replace("\n", "\\n")

        authors_yaml = ""
        for author in self.metadata.authors:
            authors_yaml += f'  - family: "{author.family_name}"\n'
            authors_yaml += f'    given: "{author.given_name}"\n'

        source = "crossref" if self.metadata.doi else "unknown"
        status = "complete" if self.metadata.doi else "incomplete"

        file_name = self.build_file_name()
        pdf_filename = f"{file_name.value}.pdf" if self.has_pdf else ""

        imported_str = self.imported_at.strftime("%Y-%m-%dT%H:%M:%S")

        frontmatter = (
            "---\n"
            f'paper_id: "{paper_id_str}"\n'
            f'title: "{self.metadata.title}"\n'
            f"authors:\n{authors_yaml}"
            f"year: {self.metadata.year.value}\n"
            f'doi: "{doi_str}"\n'
            f"{self._bibliographic_frontmatter()}"
            f'abstract: "{abstract_str}"\n'
            f'memo: "{memo_str}"\n'
            f'initial_letter: "{self.initial_letter.letter}"\n'
            f"tags: []\n"
            f'pdf_filename: "{pdf_filename}"\n'
            f'imported_at: "{imported_str}"\n'
            f'source: "{source}"\n'
            f'status: "{status}"\n'
            "---\n"
        )

        heading = f"# {file_name.value}\n"
        pdf_link = f"\n[PDFを開く]({pdf_filename})\n" if self.has_pdf else ""

        return frontmatter + "\n" + heading + pdf_link

    def _bibliographic_frontmatter(self) -> str:
        """Return optional bibliographic YAML fields."""
        fields = (
            ("journal", self.metadata.journal),
            ("journal_abbrev", self.metadata.journal_abbrev),
            ("volume", self.metadata.volume),
            ("issue", self.metadata.issue),
            ("pages", self.metadata.pages),
        )
        return "".join(f'{key}: "{value}"\n' for key, value in fields if value)

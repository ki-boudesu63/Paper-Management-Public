"""Filesystem-based CollectionRepository implementation.

Stores one YAML file per collection under <library_root>/.collections/.
Paper entities are never moved; only PaperId references are stored.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import yaml

from src.domain.collection import Collection, CollectionId, PaperRef
from src.domain.paper import PaperId
from src.domain.ports import CollectionRepository

logger = logging.getLogger(__name__)

COLLECTIONS_DIR = ".collections"
YAML_EXTENSION = ".yaml"
# Characters unsafe for filenames on Windows
UNSAFE_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|]')


class FilesystemCollectionRepository(CollectionRepository):
    """Concrete CollectionRepository backed by YAML files.

    Each collection is persisted as a single YAML file in
    <library_root>/.collections/<collection_id>.yaml.
    """

    def __init__(self, library_root: Path) -> None:
        if not library_root.exists():
            raise FileNotFoundError(f"Library root does not exist: {library_root}")
        self._library_root = library_root
        self._collections_dir = library_root / COLLECTIONS_DIR
        self._collections_dir.mkdir(exist_ok=True)

    # ============================================================
    # Public API (Port implementation)
    # ============================================================

    def find_by_id(self, collection_id: CollectionId) -> Collection | None:
        """Find a collection by its ID, loading from disk."""
        yaml_path = self._id_to_path(collection_id)
        if not yaml_path.exists():
            return None
        return self._load_collection(yaml_path)

    def find_all(self) -> list[Collection]:
        """Return all collections by scanning the .collections/ directory."""
        collections: list[Collection] = []
        for yaml_path in sorted(self._collections_dir.glob(f"*{YAML_EXTENSION}")):
            try:
                coll = self._load_collection(yaml_path)
                collections.append(coll)
            except Exception:
                logger.warning(
                    "Failed to load collection from %s, skipping",
                    yaml_path,
                    exc_info=True,
                )
        return collections

    def save(self, collection: Collection) -> None:
        """Persist a collection to a YAML file."""
        yaml_path = self._id_to_path(collection.id)
        data = self._collection_to_dict(collection)

        with open(yaml_path, "w", encoding="utf-8") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)

    def delete(self, collection_id: CollectionId) -> None:
        """Remove a collection YAML file."""
        yaml_path = self._id_to_path(collection_id)
        if not yaml_path.exists():
            raise KeyError(f"Collection not found: {collection_id.value}")
        yaml_path.unlink()

    # ============================================================
    # Private helpers
    # ============================================================

    def _id_to_path(self, collection_id: CollectionId) -> Path:
        """Convert a CollectionId to its YAML file path.

        Sanitizes the ID for filesystem safety.
        """
        safe_name = UNSAFE_FILENAME_CHARS.sub("_", collection_id.value)
        return self._collections_dir / f"{safe_name}{YAML_EXTENSION}"

    def _load_collection(self, yaml_path: Path) -> Collection:
        """Load a Collection from a YAML file."""
        with open(yaml_path, encoding="utf-8") as f:
            data: dict[str, Any] = yaml.safe_load(f)

        coll_id = CollectionId(data["id"])
        name = data["name"]
        coll = Collection(id=coll_id, name=name)

        for paper_id_str in data.get("paper_ids", []):
            coll.add_paper(PaperRef(paper_id=PaperId(paper_id_str)))

        return coll

    @staticmethod
    def _collection_to_dict(collection: Collection) -> dict[str, Any]:
        """Serialize a Collection to a dictionary for YAML output."""
        return {
            "id": collection.id.value,
            "name": collection.name,
            "paper_ids": [ref.paper_id.value for ref in collection.paper_refs],
        }

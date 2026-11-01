"""Loading and merging localization from multiple folders."""

import hashlib
import logging
from pathlib import Path

from .file_parser import LocalizationFileParser

logger = logging.getLogger(__name__)


class LocalizationLoader:
    """
    Loads localization from multiple folders.

    The order of the folders determines priority:
    values from folders later in the list override values from folders earlier in the list.
    """

    def __init__(
        self,
        folders: list[Path],
        parser: LocalizationFileParser,
    ) -> None:
        self.folders = folders
        self.parser = parser

    def load_all(self) -> dict[str, str]:
        """
        Parses all .yml files in all folders and merges them
        """
        data: dict[str, str] = {}
        for folder in self.folders:
            if not folder.is_dir():
                logger.warning("Localization folder not found: %s", folder)
                continue
            for file in sorted(folder.rglob("*.yml")):
                try:
                    data.update(self.parser.parse(file))
                except (OSError, UnicodeDecodeError) as e:
                    logger.warning("Error loading localization %s: %s", file, e)
        return data

    def compute_hash(self) -> str:
        """
        A hash of all files in all folders — for cache invalidation

        Note: Hash is based on path + mtime + size for speed. If a file is edited
        without changing size (rare for localization), the cache may be stale.
        Run with --clear-cache to force reload.
        """
        hasher = hashlib.sha256()

        for folder in self.folders:
            # Folder contents and structure
            hasher.update(str(folder).encode("utf-8"))
            if not folder.is_dir():
                continue
            # Files in the folder
            for file in sorted(folder.rglob("*.yml")):
                try:
                    stat = file.stat()
                    hasher.update(str(file).encode("utf-8"))
                    hasher.update(str(stat.st_mtime).encode("utf-8"))
                    hasher.update(str(stat.st_size).encode("utf-8"))
                except OSError:
                    continue

        return hasher.hexdigest()

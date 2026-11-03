"""Caches the merged localization to disk"""

import json
import logging
from pathlib import Path

from .loader import LocalizationLoader

logger = logging.getLogger(__name__)


class LocalizationCache:
    """
    Caches the merged localization to disk.

    Invalidates the cache if the set of files or their contents change
    (by comparing a hash provided by the loader).
    """

    # Bump this when the cache format changes (e.g., new fields in payload).
    # Old caches will be ignored and regenerated automatically.
    CACHE_VERSION = 2

    def __init__(
        self,
        loader: LocalizationLoader,
        cache_file: Path,
    ) -> None:
        self.loader = loader
        self.cache_file = cache_file
        self._cache: dict[str, str] | None = None

    def get_data(self) -> dict[str, str]:
        """Returns the localization: from memory → from cache → from files"""
        if self._cache is not None:
            return self._cache

        current_hash = self.loader.compute_hash()
        cached = self._load_cache()
        if cached is not None:
            version, cached_hash, data = cached
            if version == self.CACHE_VERSION and cached_hash == current_hash:
                logger.info("Localization loaded from cache (%d keys)", len(data))
                self._cache = data
                return self._cache
        elif self.cache_file.is_file():
            logger.warning("Cache file exists but could not be read: %s", self.cache_file)

        logger.info("Loading localization from files...")
        data = self.loader.load_all()
        logger.info("Loaded %d localization keys", len(data))
        self._save_cache(current_hash, data)
        self._cache = data
        return data

    def get(self, key: str, default: str | None = None) -> str | None:
        """
        Method for retrieving data from the localization cache
        by key, if it is in the cache, else default.
        """
        return self.get_data().get(key, default)

    def _load_cache(self) -> tuple[int, str, dict[str, str]] | None:
        """
        Method for loading cache from a JSON file
        """
        if not self.cache_file.is_file():
            return None
        try:
            raw = json.loads(self.cache_file.read_text(encoding="utf-8"))
            return raw["version"], raw["hash"], raw["data"]
        except (json.JSONDecodeError, KeyError, OSError, TypeError):
            return None

    def _save_cache(self, hash_: str, data: dict[str, str]) -> None:
        """
        Method for saving the cache to a JSON file
        """
        payload = {
            "version": self.CACHE_VERSION,
            "hash": hash_,
            "data": data,
        }
        self.cache_file.write_text(
            json.dumps(payload, ensure_ascii=False),
            encoding="utf-8",
        )

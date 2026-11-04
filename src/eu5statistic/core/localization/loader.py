"""Loading and merging localization from multiple folders."""

import hashlib
import logging
import re
from pathlib import Path

from .file_parser import LocalizationFileParser

# Regular expression for finding variables.
# In Paradox, this is typically $key$ or $key|command$
VAR_PATTERN = re.compile(r"\$([^$]+)\$")


class LocalizationLoader:
    """
    Loads localization from multiple folders.

    The order of the folders determines priority:
    values from folders later in the list override values from folders earlier in the list.
    """

    def __init__(
        self, folders: list[Path], parser: LocalizationFileParser, logger: logging.Logger
    ) -> None:
        self.folders = folders
        self.parser = parser
        self.logger: logging.Logger = logger

    def load_all(self) -> dict[str, str]:
        """
        Parses all .yml files in all folders and merges them
        """
        data: dict[str, str] = {}
        for folder in self.folders:
            if not folder.is_dir():
                self.logger.warning("Localization folder not found: %s", folder)
                continue
            for file in sorted(folder.rglob("*.yml")):
                try:
                    data.update(self.parser.parse(file))
                except (OSError, UnicodeDecodeError) as e:
                    self.logger.warning("Error loading localization %s: %s", file, e)

        # Once all data has been collected, we exclude references to other keys
        resolved_data = self._resolve_references(data)
        return resolved_data

    def _resolve_references(self, data: dict[str, str]) -> dict[str, str]:
        """
        References of the form $key$ within localization strings are recursively replaced with their values.
        """
        resolved = {}
        # Cache for already found strings of the form $key$
        memo: dict[str, str] = {}
        # A set for tracking circular references
        resolving: set[str] = set()

        def resolve_string(key: str, value: str) -> str:
            if key in resolving:
                self.logger.debug("Circular reference detected for key: %s", key)
                return value

            resolving.add(key)

            def replace_var(match: re.Match[str]) -> str:
                var_content = match.group(1)
                # In Paradox, variables can have modifiers: $key|format$
                # Separate the key name from the modifier
                var_key = var_content.split("|")[0].strip()

                if var_key in data:
                    # If the value has not yet been resolved, resolve it recursively
                    if var_key not in memo:
                        memo[var_key] = resolve_string(var_key, data[var_key])
                    return memo[var_key]

                # If the key is not found, return the original string so that the error is visible
                return str(match.group(0))

            result = VAR_PATTERN.sub(replace_var, value)
            resolving.remove(key)
            return result

        for k, v in data.items():
            if k not in memo:
                memo[k] = resolve_string(k, v)
            resolved[k] = memo[k]

        return resolved

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

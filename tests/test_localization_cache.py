"""Tests for LocalizationCache: disk cache with hash-based invalidation."""

import json
import logging
from pathlib import Path

import pytest

from eu5statistic.core.localization.cache import LocalizationCache
from eu5statistic.core.localization.file_parser import LocalizationFileParser
from eu5statistic.core.localization.loader import LocalizationLoader


@pytest.fixture
def test_logger() -> logging.Logger:
    return logging.getLogger("test_loader")


@pytest.fixture
def parser() -> LocalizationFileParser:
    return LocalizationFileParser(encoding="utf-8")


@pytest.fixture
def loader(
    parser: LocalizationFileParser, tmp_path: Path, test_logger: logging.Logger
) -> LocalizationLoader:
    folder = tmp_path / "loc"
    folder.mkdir()
    (folder / "a.yml").write_text('l_russian:\n KEY: "Value"\n', encoding="utf-8")
    return LocalizationLoader([folder], parser, test_logger)


def test_get_data_loads_from_files(
    loader: LocalizationLoader, tmp_path: Path, test_logger: logging.Logger
) -> None:
    cache_file = tmp_path / "cache.json"
    cache = LocalizationCache(loader, cache_file, test_logger)

    data = cache.get_data()
    assert data["KEY"] == "Value"
    assert cache_file.is_file()  # cache saved


def test_get_data_uses_cache_on_second_call(
    loader: LocalizationLoader, tmp_path: Path, test_logger: logging.Logger
) -> None:
    cache_file = tmp_path / "cache.json"
    cache = LocalizationCache(loader, cache_file, test_logger)

    first = cache.get_data()
    # Second call should hit in-memory cache (no reload from files)
    second = cache.get_data()
    assert first is second  # same object


def test_get_data_invalidates_on_content_change(
    loader: LocalizationLoader,
    tmp_path: Path,
    parser: LocalizationFileParser,
    test_logger: logging.Logger,
) -> None:
    cache_file = tmp_path / "cache.json"
    cache1 = LocalizationCache(loader, cache_file, test_logger)
    cache1.get_data()

    # Change file content
    (tmp_path / "loc" / "a.yml").write_text('l_russian:\n KEY: "Changed"\n', encoding="utf-8")

    # New cache instance: hash differs → reload
    cache2 = LocalizationCache(loader, cache_file, test_logger)
    data = cache2.get_data()
    assert data["KEY"] == "Changed"


def test_cache_version_mismatch_invalidates(
    loader: LocalizationLoader, tmp_path: Path, test_logger: logging.Logger
) -> None:
    cache_file = tmp_path / "cache.json"
    cache1 = LocalizationCache(loader, cache_file, test_logger)
    cache1.get_data()

    # Corrupt cache version
    raw = json.loads(cache_file.read_text(encoding="utf-8"))
    raw["version"] = 999
    cache_file.write_text(json.dumps(raw), encoding="utf-8")

    cache2 = LocalizationCache(loader, cache_file, test_logger)
    data = cache2.get_data()
    assert data["KEY"] == "Value"  # reloaded from files


def test_cache_corrupted_json_invalidates(
    loader: LocalizationLoader, tmp_path: Path, test_logger: logging.Logger
) -> None:
    cache_file = tmp_path / "cache.json"
    cache_file.write_text("not valid json", encoding="utf-8")

    cache = LocalizationCache(loader, cache_file, test_logger)
    data = cache.get_data()
    assert data["KEY"] == "Value"


def test_get_returns_default_for_missing_key(
    loader: LocalizationLoader, tmp_path: Path, test_logger: logging.Logger
) -> None:
    cache = LocalizationCache(loader, tmp_path / "cache.json", test_logger)
    assert cache.get("NONEXISTENT") is None
    assert cache.get("NONEXISTENT", default="fallback") == "fallback"


def test_get_returns_value_for_existing_key(
    loader: LocalizationLoader, tmp_path: Path, test_logger: logging.Logger
) -> None:
    cache = LocalizationCache(loader, tmp_path / "cache.json", test_logger)
    assert cache.get("KEY") == "Value"


def test_cache_missing_keys_invalidates(
    loader: LocalizationLoader, tmp_path: Path, test_logger: logging.Logger
) -> None:
    """Covers the branch where the file exists, but `_load_cache` returned `None` (KeyError)."""
    cache_file = tmp_path / "cache.json"
    # Valid JSON, but missing the "version", "hash", and "data" keys
    cache_file.write_text('{"some": "data"}', encoding="utf-8")

    cache = LocalizationCache(loader, cache_file, test_logger)
    data = cache.get_data()

    # Data should be loaded from the files, rather than causing a crash.
    assert data["KEY"] == "Value"

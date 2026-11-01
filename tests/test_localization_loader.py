"""Tests for LocalizationLoader: loading and merging .yml files."""

from pathlib import Path

import pytest

from eu5statistic.core.localization.file_parser import LocalizationFileParser
from eu5statistic.core.localization.loader import LocalizationLoader


@pytest.fixture
def parser() -> LocalizationFileParser:
    return LocalizationFileParser(encoding="utf-8")


def _write_yml(folder: Path, name: str, content: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    f = folder / name
    f.write_text(content, encoding="utf-8")
    return f


def test_load_single_folder(parser: LocalizationFileParser, tmp_path: Path) -> None:
    folder = tmp_path / "vanilla"
    _write_yml(folder, "a.yml", 'l_russian:\n KEY: "Value"\n')

    loader = LocalizationLoader([folder], parser)
    data = loader.load_all()

    assert data["KEY"] == "Value"


def test_load_merges_folders_later_wins(parser: LocalizationFileParser, tmp_path: Path) -> None:
    vanilla = tmp_path / "vanilla"
    mod = tmp_path / "mod"
    _write_yml(vanilla, "a.yml", 'l_russian:\n KEY: "Vanilla"\n OTHER: "V"\n')
    _write_yml(mod, "b.yml", 'l_russian:\n KEY: "Mod"\n')

    loader = LocalizationLoader([vanilla, mod], parser)
    data = loader.load_all()

    # Later folder overrides earlier
    assert data["KEY"] == "Mod"
    # Non-overridden key survives
    assert data["OTHER"] == "V"


def test_load_skips_missing_folder(parser: LocalizationFileParser, tmp_path: Path) -> None:
    missing = tmp_path / "does_not_exist"
    loader = LocalizationLoader([missing], parser)
    data = loader.load_all()
    assert data == {}


def test_load_handles_broken_file(parser: LocalizationFileParser, tmp_path: Path) -> None:
    folder = tmp_path / "vanilla"
    _write_yml(folder, "good.yml", 'l_russian:\n KEY: "Value"\n')
    # Broken file: invalid UTF-8
    (folder / "bad.yml").write_bytes(b"\xff\xfe invalid")

    loader = LocalizationLoader([folder], parser)
    data = loader.load_all()

    # Good file still loaded, bad file skipped with a warning
    assert data["KEY"] == "Value"


def test_compute_hash_deterministic(parser: LocalizationFileParser, tmp_path: Path) -> None:
    folder = tmp_path / "vanilla"
    _write_yml(folder, "a.yml", 'l_russian:\n KEY: "Value"\n')

    loader = LocalizationLoader([folder], parser)
    h1 = loader.compute_hash()
    h2 = loader.compute_hash()

    assert h1 == h2
    assert isinstance(h1, str)
    assert len(h1) == 64  # sha256 hex


def test_compute_hash_changes_on_content(parser: LocalizationFileParser, tmp_path: Path) -> None:
    folder = tmp_path / "vanilla"
    f = _write_yml(folder, "a.yml", 'l_russian:\n KEY: "Value"\n')

    loader = LocalizationLoader([folder], parser)
    h1 = loader.compute_hash()

    # Change content
    f.write_text('l_russian:\n KEY: "Changed"\n', encoding="utf-8")
    h2 = loader.compute_hash()

    assert h1 != h2

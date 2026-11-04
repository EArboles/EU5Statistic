"""Tests for LocalizationLoader: loading, merging and resolving .yml files."""

import logging
from pathlib import Path

import pytest

from eu5statistic.core.localization.file_parser import LocalizationFileParser
from eu5statistic.core.localization.loader import LocalizationLoader


@pytest.fixture
def test_logger() -> logging.Logger:
    return logging.getLogger("test_loader")


@pytest.fixture
def parser() -> LocalizationFileParser:
    return LocalizationFileParser(encoding="utf-8")


def _write_yml(folder: Path, name: str, content: str) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    f = folder / name
    f.write_text(content, encoding="utf-8")
    return f


# ---------------------------------------------------------------------------
# Tests for reference resolution
# ---------------------------------------------------------------------------


def test_resolve_simple_reference(
    parser: LocalizationFileParser, tmp_path: Path, test_logger: logging.Logger
) -> None:
    folder = tmp_path / "vanilla"
    _write_yml(folder, "a.yml", 'l_russian:\n AAA: "$strumica$"\n strumica: "Струмица"\n')

    loader = LocalizationLoader([folder], parser, test_logger)
    data = loader.load_all()

    assert data["AAA"] == "Струмица"
    assert data["strumica"] == "Струмица"


def test_resolve_reference_across_files(
    parser: LocalizationFileParser, tmp_path: Path, test_logger: logging.Logger
) -> None:
    folder = tmp_path / "vanilla"
    _write_yml(folder, "keys.yml", 'l_russian:\n AAA: "$strumica$"\n')
    _write_yml(folder, "values.yml", 'l_russian:\n strumica: "Струмица"\n')

    loader = LocalizationLoader([folder], parser, test_logger)
    data = loader.load_all()

    assert data["AAA"] == "Струмица"


def test_resolve_nested_references(
    parser: LocalizationFileParser, tmp_path: Path, test_logger: logging.Logger
) -> None:
    folder = tmp_path / "vanilla"
    _write_yml(folder, "a.yml", 'l_russian:\n A: "$B$"\n B: "$C$"\n C: "Final"\n')

    loader = LocalizationLoader([folder], parser, test_logger)
    data = loader.load_all()

    assert data["A"] == "Final"
    assert data["B"] == "Final"
    assert data["C"] == "Final"


def test_resolve_reference_with_modifier(
    parser: LocalizationFileParser, tmp_path: Path, test_logger: logging.Logger
) -> None:
    folder = tmp_path / "vanilla"
    _write_yml(folder, "a.yml", 'l_russian:\n AAA: "Мятежный $ADJ$ военачальник"\n ADJ: "Шведск"\n')

    loader = LocalizationLoader([folder], parser, test_logger)
    data = loader.load_all()

    assert data["AAA"] == "Мятежный Шведск военачальник"


def test_resolve_missing_reference_keeps_placeholder(
    parser: LocalizationFileParser, tmp_path: Path, test_logger: logging.Logger
) -> None:
    folder = tmp_path / "vanilla"
    _write_yml(folder, "a.yml", 'l_russian:\n AAA: "Value $missing$"\n')

    loader = LocalizationLoader([folder], parser, test_logger)
    data = loader.load_all()

    # If the key is not found, the placeholder remains as is
    assert data["AAA"] == "Value $missing$"


def test_resolve_circular_reference_does_not_crash(
    parser: LocalizationFileParser,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    test_logger: logging.Logger,
) -> None:
    folder = tmp_path / "vanilla"
    _write_yml(folder, "a.yml", 'l_russian:\n A: "$B$"\n B: "$A$"\n')

    loader = LocalizationLoader([folder], parser, test_logger)
    data = loader.load_all()

    # The main thing is not to fall into an infinite recursion.
    assert "A" in data
    assert "B" in data
    # There should be a warning about a circular reference
    assert any("Circular reference" in record.message for record in caplog.records)


def test_resolve_multiple_references_in_one_string(
    parser: LocalizationFileParser, tmp_path: Path, test_logger: logging.Logger
) -> None:
    folder = tmp_path / "vanilla"
    _write_yml(
        folder,
        "a.yml",
        'l_russian:\n AAA: "$strumica$ и $other$"\n strumica: "Струмица"\n other: "другое"\n',
    )

    loader = LocalizationLoader([folder], parser, test_logger)
    data = loader.load_all()

    assert data["AAA"] == "Струмица и другое"

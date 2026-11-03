"""Tests for Paradox .yml localization parser."""

from pathlib import Path

import pytest

from eu5statistic.core.localization.file_parser import LocalizationFileParser


@pytest.fixture
def parser() -> LocalizationFileParser:
    return LocalizationFileParser(encoding="utf-8")


def test_parse_simple(parser: LocalizationFileParser, tmp_path: Path) -> None:
    f = tmp_path / "test.yml"
    f.write_text(
        'l_russian:\n KEY: "Value"\n KEY2: Value2\n',
        encoding="utf-8",
    )
    data = parser.parse(f)
    assert data["KEY"] == "Value"
    assert data["KEY2"] == "Value2"


def test_parse_with_quotes(parser: LocalizationFileParser, tmp_path: Path) -> None:
    f = tmp_path / "test.yml"
    f.write_text(
        'l_russian:\n KEY: "He said hello"\n',
        encoding="utf-8",
    )
    data = parser.parse(f)
    assert data["KEY"] == "He said hello"


def test_parse_skips_comments(parser: LocalizationFileParser, tmp_path: Path) -> None:
    f = tmp_path / "test.yml"
    f.write_text(
        '# This is a comment\nl_russian:\n KEY: "Value"\n',
        encoding="utf-8",
    )
    data = parser.parse(f)
    assert data["KEY"] == "Value"
    assert data["l_russian"] == ""
    assert "# This is a comment" not in data


def test_parse_skips_empty_lines(parser: LocalizationFileParser, tmp_path: Path) -> None:
    f = tmp_path / "test.yml"
    f.write_text(
        'l_russian:\n\n KEY: "Value"\n\n',
        encoding="utf-8",
    )
    data = parser.parse(f)
    assert data["KEY"] == "Value"
    assert data["l_russian"] == ""


def test_parse_missing_quotes(parser: LocalizationFileParser, tmp_path: Path) -> None:
    f = tmp_path / "test.yml"
    f.write_text(
        "l_russian:\n KEY: Value without quotes\n",
        encoding="utf-8",
    )
    data = parser.parse(f)
    assert data["KEY"] == "Value without quotes"


def test_parse_bom(tmp_path: Path) -> None:
    """BOM should be stripped when using utf-8-sig."""
    f = tmp_path / "test.yml"
    f.write_text(
        '\ufeffl_russian:\n KEY: "Value"\n',
        encoding="utf-8",
    )
    parser = LocalizationFileParser(encoding="utf-8-sig")
    data = parser.parse(f)
    assert data["KEY"] == "Value"


def test_parse_skips_lines_without_colon(parser: LocalizationFileParser, tmp_path: Path) -> None:
    f = tmp_path / "test.yml"
    f.write_text(
        "l_russian:\n"
        " JUST_A_WORD_WITHOUT_COLON\n"  # Row number 36
        ' KEY: "Value"\n',
        encoding="utf-8",
    )
    data = parser.parse(f)
    assert "JUST_A_WORD_WITHOUT_COLON" not in data
    assert data["KEY"] == "Value"


def test_parse_handles_unclosed_quote(parser: LocalizationFileParser, tmp_path: Path) -> None:
    f = tmp_path / "test.yml"
    f.write_text(
        "l_russian:\n"
        ' KEY: "Unclosed value\n'  # Row number 47
        ' KEY2: "Another"\n',
        encoding="utf-8",
    )
    data = parser.parse(f)
    assert data["KEY"] == "Unclosed value"
    assert data["KEY2"] == "Another"

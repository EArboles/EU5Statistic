"""Tests for JsonParser: extracting data from EU5 save JSON."""

import json
from pathlib import Path

import pytest

from eu5statistic.core.json_parser import JsonParser


@pytest.fixture
def minimal_save(tmp_path: Path) -> Path:
    data = {
        "metadata": {
            "date": "1337.04.01",
            "flag": "MOS={ pattern=... }",
            "compatibility": {"locations": ["Loc1", "Loc2", "Loc3"]},
        },
        "culture_manager": {
            "database": {
                "0": {"name": "russian"},
                "1": {"name": "tatar"},
            }
        },
        "religion_manager": {
            "database": {
                "0": {"name": "orthodox"},
                "1": {"name": "sunni"},
            }
        },
        "countries": {
            "tags": {"0": "MOS", "1": "TAT"},
            "database": {
                "0": {
                    "country_name": "Moscow",
                    "primary_culture": 0,
                    "primary_religion": 0,
                    "owned_locations": [1, 2],
                },
                "1": {
                    "country_name": "Kazan",
                    "primary_culture": 1,
                    "primary_religion": 1,
                    "owned_locations": [3],
                },
            },
        },
        "population": {
            "database": {
                "1": {
                    "type": "peasants",
                    "size": 10.5,
                    "culture": 0,
                    "religion": 0,
                    "literacy": 5.0,
                },
                "2": {
                    "type": "burghers",
                    "size": 2.0,
                    "culture": 0,
                    "religion": 0,
                    "literacy": 30.0,
                },
            }
        },
        "diplomacy_manager": {"dependency": [{"first": 0, "second": 1}]},
        "locations": {
            "locations": {
                "1": {"pops": [1, 2]},
                "2": {"pops": []},
                "3": {"pops": []},
            }
        },
    }
    f = tmp_path / "save.json"
    f.write_text(json.dumps(data), encoding="utf-8")
    return f


def test_parse_all_returns_ok(minimal_save: Path) -> None:
    parser = JsonParser(str(minimal_save))
    ok, data = parser.parse_all()
    assert ok is True
    assert data is not None


def test_parse_metadata(minimal_save: Path) -> None:
    parser = JsonParser(str(minimal_save))
    ok, data = parser.parse_all()
    assert ok
    assert data.year == 1337
    assert data.month == 4
    assert data.day == 1
    assert data.player_tag == "MOS"


def test_parse_cultures(minimal_save: Path) -> None:
    parser = JsonParser(str(minimal_save))
    ok, data = parser.parse_all()
    assert ok
    assert data.cultures == {0: "russian", 1: "tatar"}


def test_parse_religions(minimal_save: Path) -> None:
    parser = JsonParser(str(minimal_save))
    ok, data = parser.parse_all()
    assert ok
    assert data.religions == {0: "orthodox", 1: "sunni"}


def test_parse_country_tags(minimal_save: Path) -> None:
    parser = JsonParser(str(minimal_save))
    ok, data = parser.parse_all()
    assert ok
    assert data.country_tags == {0: "MOS", 1: "TAT"}


def test_parse_countries(minimal_save: Path) -> None:
    parser = JsonParser(str(minimal_save))
    ok, data = parser.parse_all()
    assert ok
    assert 0 in data.countries
    assert data.countries[0].country_name == "Moscow"
    assert data.countries[0].primary_culture == 0
    assert data.countries[0].primary_religion == 0
    assert data.countries[0].owned_locations == [1, 2]


def test_parse_population(minimal_save: Path) -> None:
    parser = JsonParser(str(minimal_save))
    ok, data = parser.parse_all()
    assert ok
    assert 1 in data.population
    assert data.population[1].estate == "peasants"
    assert data.population[1].size == 10500  # 10.5 * 1000
    assert data.population[1].culture == 0
    assert data.population[1].religion == 0
    assert data.population[1].literacy == pytest.approx(0.05)  # 5.0 / 100


def test_parse_vassalage(minimal_save: Path) -> None:
    parser = JsonParser(str(minimal_save))
    ok, data = parser.parse_all()
    assert ok
    assert data.subjects.get(0) == [1]


def test_parse_locations(minimal_save: Path) -> None:
    parser = JsonParser(str(minimal_save))
    ok, data = parser.parse_all()
    assert ok
    assert data.locations[1] == [1, 2]
    assert data.locations[2] == []
    assert data.locations[3] == []


def test_parse_location_names(minimal_save: Path) -> None:
    parser = JsonParser(str(minimal_save))
    ok, data = parser.parse_all()
    assert ok
    assert data.locations_names == {1: "Loc1", 2: "Loc2", 3: "Loc3"}


def test_invalid_date_returns_false(tmp_path: Path) -> None:
    data = {
        "metadata": {
            "date": "1444.07.15",  # month 7 — not in 1-6, not initial
            "flag": "MOS={ ... }",
        }
    }
    f = tmp_path / "save.json"
    f.write_text(json.dumps(data), encoding="utf-8")
    parser = JsonParser(str(f))
    ok, _ = parser.parse_all()
    assert ok is False
    assert parser.get_failure_reason() == "INVALID_DATE"


def test_missing_date_returns_false(tmp_path: Path) -> None:
    data = {"metadata": {"flag": "MOS={ ... }"}}
    f = tmp_path / "save.json"
    f.write_text(json.dumps(data), encoding="utf-8")
    parser = JsonParser(str(f))
    ok, _ = parser.parse_all()
    assert ok is False
    assert parser.get_failure_reason() == "INVALID_DATE"


def test_no_metadata_at_all_returns_false(tmp_path: Path) -> None:
    data = {"culture_manager": {"database": {}}}
    f = tmp_path / "save.json"
    f.write_text(json.dumps(data), encoding="utf-8")
    parser = JsonParser(str(f))
    ok, _ = parser.parse_all()
    assert ok is False
    assert parser.get_failure_reason() == "NOT_FOUND_DATE"

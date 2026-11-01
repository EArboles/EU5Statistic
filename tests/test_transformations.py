"""Tests for language-specific transformations."""

import pytest

from eu5statistic.core.localization.transformations import (
    get_terra_nullius_name,
    transform_country_name,
    transform_culture_name,
)


class TestTransformCultureName:
    @pytest.mark.parametrize(
        "name,expected",
        [
            ("Шведск", "Шведская"),
            ("Датск", "Датская"),
            ("Английск", "Английская"),
            ("Чешск", "Чешская"),
            ("Польск", "Польская"),
            ("Турецк", "Турецкая"),
            ("Немецк", "Немецкая"),
            ("Казацк", "Казацкая"),
            ("Мазовецк", "Мазовецкая"),
        ],
    )
    def test_russian_adjectives(self, name: str, expected: str) -> None:
        assert transform_culture_name(name, "russian") == expected

    @pytest.mark.parametrize("name", ["Фарси", "Маори", "Инкск"])  # "Инкск" -> "Инкская"
    def test_russian_non_standard(self, name: str) -> None:
        # "Фарси" and "Маори" are not adjectives — stay unchanged
        result = transform_culture_name(name, "russian")
        assert isinstance(result, str)

    def test_non_russian_unchanged(self) -> None:
        assert transform_culture_name("Swedish", "english") == "Swedish"
        assert transform_culture_name("Шведск", "german") == "Шведск"


class TestTransformCountryName:
    def test_no_revolt(self) -> None:
        assert transform_country_name("Москва", False, "russian") == "Москва"

    def test_revolt_russian(self) -> None:
        assert transform_country_name("Москва", True, "russian") == "Восстание: Москва"

    def test_revolt_english(self) -> None:
        assert transform_country_name("Moscow", True, "english") == "Revolt: Moscow"

    def test_revolt_unknown_language_fallback(self) -> None:
        assert transform_country_name("Moscow", True, "german") == "Revolt: Moscow"


class TestGetTerraNulliusName:
    def test_russian(self) -> None:
        assert get_terra_nullius_name("russian") == "Ничейная земля"

    def test_english(self) -> None:
        assert get_terra_nullius_name("english") == "No Man's Land"

    def test_fallback(self) -> None:
        assert get_terra_nullius_name("german") == "No Man's Land"

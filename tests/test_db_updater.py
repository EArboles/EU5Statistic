"""Tests for DbUpdater: logic without real DB."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from eu5statistic.core.entities.country_info import CountryInfo
from eu5statistic.core.entities.json_data import JsonData
from eu5statistic.core.entities.population_info import PopulationInfo
from eu5statistic.db.db_operations import EntityCaches
from eu5statistic.db.db_updater import DbUpdater


@pytest.fixture
def logger() -> MagicMock:
    return MagicMock()


@pytest.fixture
def localization() -> MagicMock:
    loc = MagicMock()
    loc.get = MagicMock(side_effect=lambda k, default=None: f"loc_{k}" if k else default)
    return loc


@pytest.fixture
def minimal_data() -> JsonData:
    data = JsonData()
    data.year = 1444
    data.month = 11
    data.day = 11
    data.player_tag = "MOS"
    data.cultures = {0: "russian", 1: "tatar"}
    data.religions = {0: "orthodox"}
    data.country_tags = {0: "MOS", 1: "TAT"}
    data.countries = {
        0: CountryInfo(
            country_name="Moscow",
            primary_culture=0,
            primary_religion=0,
            owned_locations=[1, 2],
        ),
    }
    data.population = {
        1: PopulationInfo(estate="peasants", size=1000, culture=0, religion=0, literacy=0.05),
    }
    data.locations = {1: [1], 2: []}
    data.locations_names = {1: "Loc1", 2: "Loc2"}
    data.subjects = {}
    return data


class TestGetIndex:
    def test_returns_index_when_found(
        self, minimal_data: JsonData, localization: MagicMock, logger: MagicMock
    ) -> None:
        updater = DbUpdater(minimal_data, localization, logger)
        updater.caches = EntityCaches(cultures={"russian": 42})

        result = updater._get_culture_index(0)
        assert result == 42
        assert updater.exist_errors is False

    def test_returns_none_and_sets_error_when_name_missing(
        self, minimal_data: JsonData, localization: MagicMock, logger: MagicMock
    ) -> None:
        updater = DbUpdater(minimal_data, localization, logger)
        updater.caches = EntityCaches(cultures={})

        result = updater._get_culture_index(999)  # no such culture
        assert result is None
        assert updater.exist_errors is True


class TestGroupPopulation:
    def test_groups_by_culture_and_religion(
        self, minimal_data: JsonData, localization: MagicMock, logger: MagicMock
    ) -> None:
        updater = DbUpdater(minimal_data, localization, logger)
        updater.caches = EntityCaches()

        # Add a second POP with same culture/religion
        minimal_data.population[2] = PopulationInfo(
            estate="burghers", size=2000, culture=0, religion=0, literacy=0.10
        )
        minimal_data.locations[1] = [1, 2]

        groups = updater._group_population([1])
        # Key (0, 0): total 3000, weighted literacy sum = 1000*0.05 + 2000*0.10 = 250
        assert (0, 0) in groups
        size, weighted = groups[(0, 0)]
        assert size == 3000
        assert weighted == pytest.approx(250.0)

    def test_skips_none_culture_or_religion(
        self, minimal_data: JsonData, localization: MagicMock, logger: MagicMock
    ) -> None:
        updater = DbUpdater(minimal_data, localization, logger)
        updater.caches = EntityCaches()

        minimal_data.population[2] = PopulationInfo(
            estate="peasants", size=100, culture=None, religion=0
        )
        minimal_data.locations[1] = [1, 2]

        groups = updater._group_population([1])
        # Only pop 1 contributes (pop 2 skipped due to None culture)
        assert len(groups) == 1


class TestBuildCountryPopulationPairs:
    def test_builds_pairs(
        self, minimal_data: JsonData, localization: MagicMock, logger: MagicMock
    ) -> None:
        updater = DbUpdater(minimal_data, localization, logger)
        updater.caches = EntityCaches(
            cultures={"russian": 10},
            religions={"orthodox": 20},
        )

        groups = {(0, 0): (1000, 50.0)}
        pairs = updater._build_country_population_pairs(42, groups)

        assert len(pairs) == 1
        country_id, culture_id, religion_id, total_size, literacy = next(iter(pairs))
        assert country_id == 42
        assert culture_id == 10
        assert religion_id == 20
        assert total_size == 1000
        assert literacy == pytest.approx(0.05)


class TestEnsureTerraNullius:
    @pytest.mark.asyncio
    async def test_creates_if_missing(
        self, minimal_data: JsonData, localization: MagicMock, logger: MagicMock
    ) -> None:
        updater = DbUpdater(minimal_data, localization, logger)
        updater.caches = EntityCaches(countries={})

        with (
            patch(
                "eu5statistic.db.db_updater.upsert_country", new_callable=AsyncMock
            ) as mock_upsert,
            patch(
                "eu5statistic.db.db_updater.get_country_id", new_callable=AsyncMock
            ) as mock_get_id,
        ):
            mock_get_id.return_value = 999

            result = await updater._ensure_terra_nullius()

            assert result == 999
            mock_upsert.assert_called_once()
            mock_get_id.assert_called_once_with("TERRA_NULLIUS")

    @pytest.mark.asyncio
    async def test_returns_existing_id(
        self, minimal_data: JsonData, localization: MagicMock, logger: MagicMock
    ) -> None:
        updater = DbUpdater(minimal_data, localization, logger)
        updater.caches = EntityCaches(countries={"TERRA_NULLIUS": 555})

        result = await updater._ensure_terra_nullius()
        assert result == 555

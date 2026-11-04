"""Tests for db_operations: EntityCaches and upsert helpers."""

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from eu5statistic.db.db_operations import (
    EntityCaches,
    clear_year_data,
    get_country_id,
    load_caches,
    refresh_location_stats_view,
    upsert_batch,
    upsert_country,
    upsert_country_population_statistics,
    upsert_country_statistics,
    upsert_cultures,
    upsert_estates,
    upsert_location,
    upsert_location_population_statistics,
    upsert_location_statistics,
    upsert_religions,
    upsert_vassalage,
)
from eu5statistic.db.models import (
    Country,
    CountryPopulationStatistics,
    CountryStatistics,
    Culture,
    Estate,
    Location,
    LocationPopulationStatistics,
    LocationStatistics,
    Religion,
    Vassalage,
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "func,model,input_data,expected_records,conflict,update",
    [
        (
            upsert_estates,
            Estate,
            [("peasants", "Крестьяне")],
            [{"name": "peasants", "localization_name": "Крестьяне"}],
            ["name"],
            ["localization_name"],
        ),
        (
            upsert_cultures,
            Culture,
            [("russian", "Русская")],
            [{"name": "russian", "localization_name": "Русская"}],
            ["name"],
            ["localization_name"],
        ),
        (
            upsert_religions,
            Religion,
            [("orthodox", "Православная")],
            [{"name": "orthodox", "localization_name": "Православная"}],
            ["name"],
            ["localization_name"],
        ),
        (
            upsert_location,
            Location,
            [(1, "Москва")],
            [{"id": 1, "localization_name": "Москва"}],
            ["id"],
            ["localization_name"],
        ),
        (
            upsert_country,
            Country,
            [("MOS", "Москва")],
            [{"tag": "MOS", "localization_name": "Москва"}],
            ["tag"],
            ["localization_name"],
        ),
        (
            upsert_vassalage,
            Vassalage,
            [(10, 20)],  # suzerain_id, vassal_id
            [{"year": 1444, "suzerain_id": 10, "vassal_id": 20}],
            ["year", "suzerain_id", "vassal_id"],
            None,  # DO NOTHING
        ),
        (
            upsert_location_population_statistics,
            LocationPopulationStatistics,
            [(1, 2, 1000, 0.05)],  # location_id, estate_id, population, literacy
            [
                {
                    "year": 1444,
                    "location_id": 1,
                    "estate_id": 2,
                    "population_size": 1000,
                    "literacy": 0.05,
                }
            ],
            ["year", "location_id", "estate_id"],
            ["population_size", "literacy"],
        ),
        (
            upsert_country_statistics,
            CountryStatistics,
            [(1, 2, 3, 5)],  # country_id, primary_culture, primary_religion, num_locations
            [
                {
                    "year": 1444,
                    "country_id": 1,
                    "primary_culture_id": 2,
                    "primary_religion_id": 3,
                    "num_locations": 5,
                }
            ],
            ["year", "country_id"],
            ["primary_culture_id", "primary_religion_id", "num_locations"],
        ),
        (
            upsert_country_population_statistics,
            CountryPopulationStatistics,
            [(1, 2, 3, 1000, 0.05)],  # country_id, culture_id, religion_id, population, literacy
            [
                {
                    "year": 1444,
                    "country_id": 1,
                    "culture_id": 2,
                    "religion_id": 3,
                    "population_size": 1000,
                    "literacy": 0.05,
                }
            ],
            ["year", "country_id", "culture_id", "religion_id"],
            ["population_size", "literacy"],
        ),
        (
            upsert_location_statistics,
            LocationStatistics,
            [(1, 2)],  # location_id, country_id
            [{"year": 1444, "location_id": 1, "country_id": 2}],
            ["year", "location_id"],
            ["country_id"],
        ),
    ],
)
async def test_upsert_helpers(
    func: Any, model: Any, input_data: Any, expected_records: Any, conflict: Any, update: Any
) -> None:
    with patch("eu5statistic.db.db_operations.upsert_batch", new_callable=AsyncMock) as mock:
        # For functions that take year, call with year
        if func in (
            upsert_vassalage,
            upsert_location_population_statistics,
            upsert_country_statistics,
            upsert_country_population_statistics,
            upsert_location_statistics,
        ):
            await func(input_data, year=1444)
        else:
            await func(input_data)

        mock.assert_called_once()
        args = mock.call_args.args
        kwargs = mock.call_args.kwargs

        # model — first positional argument
        assert args[0] == model
        # records — second positional argument
        assert args[1] == expected_records
        # conflict_columns, update_columns — named
        assert kwargs["conflict_columns"] == conflict
        assert kwargs.get("update_columns") == update


class TestEntityCaches:
    def test_defaults_are_empty(self) -> None:
        caches = EntityCaches()
        assert caches.estates == {}
        assert caches.cultures == {}
        assert caches.religions == {}
        assert caches.locations == set()
        assert caches.countries == {}

    def test_initialization(self) -> None:
        caches = EntityCaches(
            estates={"peasants": 1},
            cultures={"russian": 2},
            religions={"orthodox": 3},
            locations={1, 2, 3},
            countries={"MOS": 4},
        )
        assert caches.estates["peasants"] == 1
        assert caches.cultures["russian"] == 2
        assert caches.religions["orthodox"] == 3
        assert caches.locations == {1, 2, 3}
        assert caches.countries["MOS"] == 4


class TestUpsertBatch:
    async def test_empty_records_does_nothing(self) -> None:
        """upsert_batch with empty list should return immediately."""
        # No DB call should happen; if it did, AsyncSessionLocal would fail
        await upsert_batch(
            model=Estate,
            records=[],
            conflict_columns=["id"],
        )

    @pytest.mark.asyncio
    async def test_batches_are_flushed_in_chunks(self) -> None:
        records = [{"name": f"n{i}", "localization_name": f"l{i}"} for i in range(5)]

        with patch("eu5statistic.db.db_operations.AsyncSessionLocal") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__.return_value = mock_session

            await upsert_batch(
                model=Estate,
                records=records,
                conflict_columns=["name"],
                update_columns=["localization_name"],
                batch_size=2,
            )

            # 5 records / batch_size 2 = 3 batches (2 + 2 + 1)
            assert mock_session.execute.call_count == 3
            assert mock_session.commit.call_count == 1


# ---------- load_caches ----------


def make_scalar(value: Any) -> MagicMock:
    mock = MagicMock()
    mock.scalars.return_value = [value]
    return mock


@pytest.mark.asyncio
async def test_load_caches_returns_entity_caches() -> None:
    with patch("eu5statistic.db.db_operations.AsyncSessionLocal") as mock_session_cls:
        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__.return_value = mock_session

        mock_session.execute.side_effect = [
            make_scalar(SimpleNamespace(id=1, name="peasants")),
            make_scalar(SimpleNamespace(id=2, name="russian")),
            make_scalar(SimpleNamespace(id=3, name="orthodox")),
            make_scalar(SimpleNamespace(id=10)),  # Location: only id
            make_scalar(SimpleNamespace(id=20, tag="MOS")),  # Country: id + tag
        ]

        caches = await load_caches()

        assert caches.estates == {"peasants": 1}
        assert caches.cultures == {"russian": 2}
        assert caches.religions == {"orthodox": 3}
        assert caches.locations == {10}
        assert caches.countries == {"MOS": 20}


# ---------- get_country_id ----------


class TestGetCountryId:
    @pytest.mark.asyncio
    async def test_returns_id_when_found(self) -> None:
        with patch("eu5statistic.db.db_operations.AsyncSessionLocal") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__.return_value = mock_session

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = MagicMock(id=42)
            mock_session.execute.return_value = mock_result

            assert await get_country_id("MOS") == 42

    @pytest.mark.asyncio
    async def test_returns_none_when_not_found(self) -> None:
        with patch("eu5statistic.db.db_operations.AsyncSessionLocal") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__.return_value = mock_session

            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = None
            mock_session.execute.return_value = mock_result

            assert await get_country_id("NONEXISTENT") is None


# ---------- clear_year_data ----------


class TestClearYearData:
    @pytest.mark.asyncio
    async def test_deletes_all_models_and_commits(self) -> None:
        with patch("eu5statistic.db.db_operations.AsyncSessionLocal") as mock_session_cls:
            mock_session = AsyncMock()
            mock_session_cls.return_value.__aenter__.return_value = mock_session

            await clear_year_data(1444)

            # 5 models: CountryPopulationStatistics, CountryStatistics, Vassalage,
            # LocationPopulationStatistics, LocationStatistics
            assert mock_session.execute.call_count == 5
            mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_upsert_batch_do_nothing_when_no_update_columns() -> None:
    records = [{"name": "n1", "localization_name": "l1"}]

    with patch("eu5statistic.db.db_operations.AsyncSessionLocal") as mock_session_cls:
        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__.return_value = mock_session

        await upsert_batch(
            model=Estate,
            records=records,
            conflict_columns=["name"],
            update_columns=None,  # ← DO NOTHING
        )

        assert mock_session.execute.call_count == 1
        mock_session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_refresh_location_stats_view() -> None:
    with patch("eu5statistic.db.db_operations.AsyncSessionLocal") as mock_session_cls:
        mock_session = AsyncMock()
        mock_session_cls.return_value.__aenter__.return_value = mock_session

        await refresh_location_stats_view()

        # Check that SQL REFRESH was executed
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()

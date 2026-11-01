from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, cast

from sqlalchemy import delete, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlmodel import SQLModel, select

from .database import AsyncSessionLocal
from .models import (
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

# ---------- Helper functions for inserting reference data ----------


@dataclass
class EntityCaches:
    """Reference data caches loaded from the database"""

    estates: dict[str, int] = field(default_factory=dict)
    cultures: dict[str, int] = field(default_factory=dict)
    religions: dict[str, int] = field(default_factory=dict)
    locations: set[int] = field(default_factory=set)
    countries: dict[str, int] = field(default_factory=dict)


async def load_caches() -> EntityCaches:
    """
    Loads all reference data into memory.

    Sizes (EU5 vanilla):
    - locations: ~20k entries (~2 MB as a set of ints)
    - cultures, religions, estates, countries: < 1k each

    This is acceptable for a single-user tool. If the dataset grows,
    consider lazy loading or filtering by relevant IDs.
    """
    async with AsyncSessionLocal() as session:
        estates = {
            e.name: cast(int, e.id) for e in (await session.execute(select(Estate))).scalars()
        }
        cultures = {
            c.name: cast(int, c.id) for c in (await session.execute(select(Culture))).scalars()
        }
        religions = {
            r.name: cast(int, r.id) for r in (await session.execute(select(Religion))).scalars()
        }
        locations = {loc.id for loc in (await session.execute(select(Location))).scalars()}
        countries = {
            c.tag: cast(int, c.id) for c in (await session.execute(select(Country))).scalars()
        }

    return EntityCaches(
        estates=estates,
        cultures=cultures,
        religions=religions,
        locations=locations,
        countries=countries,
    )


async def get_country_id(country_tag: str) -> int | None:
    """
    Method for retrieving a country's ID from the database using its tag
    :param country_tag: the in-game tag of the country
    :return: the country's ID, or None
    """
    stmt = select(Country).where(Country.tag == country_tag)

    async with AsyncSessionLocal() as session:
        result = await session.execute(stmt)
        country = result.scalar_one_or_none()

    if country is None:
        return None
    return country.id


async def clear_year_data(year: int) -> None:
    """
    Deletes all statistics for the given year before re-inserting.

    This makes processing idempotent: re-processing a save for the same year
    replaces the data instead of duplicating it.

    Note: if the subsequent insert fails mid-way, data for this year will be
    lost. For a single-user tool this is acceptable — re-process the save to
    restore. For multi-user scenarios, wrap clear + insert in a single
    transaction (not done here because of batching).
    """
    async with AsyncSessionLocal() as session:
        for model in (
            CountryPopulationStatistics,
            CountryStatistics,
            Vassalage,
            LocationPopulationStatistics,
            LocationStatistics,
        ):
            await session.execute(delete(model).where(model.year == year))  # type: ignore[arg-type]
        await session.commit()


async def upsert_batch(
    model: type[SQLModel],
    records: Sequence[dict[str, Any]],
    conflict_columns: Sequence[str],
    update_columns: Sequence[str] | None = None,
    batch_size: int = 1000,
) -> None:
    """
    Bulk insert/update with partitioning into blocks.
    :param model: SQLModel class of the table.
    :param records: List of dictionaries (column -> value).
    :param conflict_columns: Columns for ON CONFLICT.
    :param update_columns: Columns for DO UPDATE. If None, DO NOTHING.
    :param batch_size: Batch size.
    """
    if not records:
        return

    async with AsyncSessionLocal() as session:
        for i in range(0, len(records), batch_size):
            batch = records[i : i + batch_size]
            stmt = pg_insert(model).values(batch)

            if update_columns:
                set_ = {col: getattr(stmt.excluded, col) for col in update_columns}
                stmt = stmt.on_conflict_do_update(
                    index_elements=list(conflict_columns),
                    set_=set_,
                )
            else:
                stmt = stmt.on_conflict_do_nothing(
                    index_elements=list(conflict_columns),
                )

            await session.execute(stmt)
        await session.commit()


async def upsert_estates(estates: list[tuple[str, str]], batch_size: int = 1000) -> None:
    """
    Performs a bulk insert/update for the Estate table.
    :param estates: A list of tuples (name, localization_name)
    :param batch_size: The size of the batch
    """
    records = [{"name": name, "localization_name": loc} for name, loc in estates]
    await upsert_batch(
        Estate,
        records,
        conflict_columns=["name"],
        update_columns=["localization_name"],
        batch_size=batch_size,
    )


async def upsert_cultures(cultures: list[tuple[str, str]], batch_size: int = 1000) -> None:
    """
    Performs a bulk insert/update for the Culture table.
    :param cultures: List of tuples (name, localization_name)
    :param batch_size: Batch size
    """
    records = [{"name": name, "localization_name": loc} for name, loc in cultures]
    await upsert_batch(
        Culture,
        records,
        conflict_columns=["name"],
        update_columns=["localization_name"],
        batch_size=batch_size,
    )


async def upsert_religions(religions: list[tuple[str, str]], batch_size: int = 1000) -> None:
    """
    Performs a bulk insert/update for the Religion table.
    :param religions: A list of tuples (name, localization_name)
    :param batch_size: The size of the batch
    """
    records = [{"name": name, "localization_name": loc} for name, loc in religions]
    await upsert_batch(
        Religion,
        records,
        conflict_columns=["name"],
        update_columns=["localization_name"],
        batch_size=batch_size,
    )


async def upsert_location(locations: list[tuple[int, str]], batch_size: int = 1000) -> None:
    """
    Performs a bulk insert/update for the Location table.
    :param locations: A list of tuples (id, localization_name)
    :param batch_size: The size of the batch
    """
    records = [{"id": i, "localization_name": loc} for i, loc in locations]
    await upsert_batch(
        Location,
        records,
        conflict_columns=["id"],
        update_columns=["localization_name"],
        batch_size=batch_size,
    )


async def upsert_country(countries: list[tuple[str, str]], batch_size: int = 1000) -> None:
    """
    Performs a bulk insert/update for the Country table.
    :param countries: A list of tuples (tag, localization_name)
    :param batch_size: The size of the batch
    """
    records = [{"tag": tag, "localization_name": loc} for tag, loc in countries]
    await upsert_batch(
        Country,
        records,
        conflict_columns=["tag"],
        update_columns=["localization_name"],
        batch_size=batch_size,
    )


async def upsert_vassalage(
    dependencies: list[tuple[int, int]], year: int, batch_size: int = 1000
) -> None:
    """
    Performs a bulk insert into the Vassalage table.
    :param dependencies: A list of tuples (suzerain_id, vassal_id)
    :param year: The year
    :param batch_size: The size of the batch
    """
    records = [
        {"year": year, "suzerain_id": suzerain, "vassal_id": vassal}
        for suzerain, vassal in dependencies
    ]
    await upsert_batch(
        Vassalage,
        records,
        conflict_columns=["year", "suzerain_id", "vassal_id"],
        update_columns=None,
        batch_size=batch_size,
    )


async def upsert_location_population_statistics(
    stats: list[tuple[int, int, int, float]], year: int, batch_size: int = 1000
) -> None:
    """
    Performs a bulk insert/update for the LocationStats table.
    :param stats: A list of tuples (location_id, estate_id, population_size, literacy)
    :param year: The year
    :param batch_size: The batch size
    """
    records = [
        {
            "year": year,
            "location_id": location_id,
            "estate_id": estate_id,
            "population_size": population_size,
            "literacy": literacy,
        }
        for location_id, estate_id, population_size, literacy in stats
    ]
    await upsert_batch(
        LocationPopulationStatistics,
        records,
        conflict_columns=["year", "location_id", "estate_id"],
        update_columns=["population_size", "literacy"],
        batch_size=batch_size,
    )


async def upsert_country_statistics(
    stats: list[tuple[int, int | None, int | None, int]], year: int, batch_size: int = 1000
) -> None:
    """
    Performs a bulk insert/update for the CountryStatistics table.
    :param stats: A list of tuples (country_id, primary_culture_id, primary_religion_id, num_locations)
    :param year: The year
    :param batch_size: The batch size
    """
    records = [
        {
            "year": year,
            "country_id": country_id,
            "primary_culture_id": primary_culture_id,
            "primary_religion_id": primary_religion_id,
            "num_locations": num_locations,
        }
        for country_id, primary_culture_id, primary_religion_id, num_locations in stats
    ]
    await upsert_batch(
        CountryStatistics,
        records,
        conflict_columns=["year", "country_id"],
        update_columns=["primary_culture_id", "primary_religion_id", "num_locations"],
        batch_size=batch_size,
    )


async def upsert_country_population_statistics(
    stats: list[tuple[int, int, int, int, float]], year: int, batch_size: int = 1000
) -> None:
    """
    Performs a bulk insert/update for the CountryPopulationStatistics table.
    :param stats: List of tuples (country_id, culture_id, religion_id, total_size, literacy)
    :param year: Year
    :param batch_size: Batch size
    """
    records = [
        {
            "year": year,
            "country_id": country_id,
            "culture_id": culture_id,
            "religion_id": religion_id,
            "population_size": population_size,
            "literacy": literacy,
        }
        for country_id, culture_id, religion_id, population_size, literacy in stats
    ]
    await upsert_batch(
        CountryPopulationStatistics,
        records,
        conflict_columns=["year", "country_id", "culture_id", "religion_id"],
        update_columns=["population_size", "literacy"],
        batch_size=batch_size,
    )


async def upsert_location_statistics(
    stats: list[tuple[int, int]], year: int, batch_size: int = 1000
) -> None:
    """
    Performs a bulk insert/update for the LocationStats table.
    :param stats: A list of tuples (location_id, country_id)
    :param year: The year
    :param batch_size: The batch size
    """
    records = [
        {"year": year, "location_id": location_id, "country_id": country_id}
        for location_id, country_id in stats
    ]
    await upsert_batch(
        LocationStatistics,
        records,
        conflict_columns=["year", "location_id"],
        update_columns=["country_id"],
        batch_size=batch_size,
    )


async def refresh_location_stats_view() -> None:
    """
    Refreshes the materialized view after loading new data.
    Called at the end of the update process.
    """
    async with AsyncSessionLocal() as session:
        # CONCURRENTLY allows reading the view while it refreshes
        # (requires a unique index on the view, which we have created via migration)
        await session.execute(text("REFRESH MATERIALIZED VIEW CONCURRENTLY location_stats_view"))
        await session.commit()


__all__ = [
    "EntityCaches",
    "clear_year_data",
    "get_country_id",
    "load_caches",
    "upsert_batch",
    "upsert_country",
    "upsert_country_population_statistics",
    "upsert_country_statistics",
    "upsert_cultures",
    "upsert_estates",
    "upsert_location",
    "upsert_location_population_statistics",
    "upsert_location_statistics",
    "upsert_religions",
    "upsert_vassalage",
    "refresh_location_stats_view",
]

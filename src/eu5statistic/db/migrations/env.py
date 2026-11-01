from logging.config import fileConfig

from alembic import context
from alembic_utils.pg_function import PGFunction
from alembic_utils.pg_materialized_view import PGMaterializedView
from alembic_utils.replaceable_entity import register_entities
from sqlalchemy import engine_from_config, pool
from sqlmodel import SQLModel

from eu5statistic.config import DATABASE_URL
from eu5statistic.db.functions import (
    get_all_vassals,
    get_available_years,
    get_country_location_stats,
    get_country_summary,
    get_culture_statistics,
    get_religion_statistics,
    get_target_country_cultures,
    get_target_country_religions,
    get_world_location_stats,
    location_stats_view,
)

config = context.config
SYNC_DATABASE_URL = DATABASE_URL.replace("+asyncpg", "+psycopg2")
config.set_main_option("sqlalchemy.url", SYNC_DATABASE_URL)
register_entities(
    [
        # independent functions
        get_available_years,
        # functions dependent on get_available_years
        get_all_vassals,
        get_religion_statistics,
        get_culture_statistics,
        get_country_summary,
        get_target_country_cultures,  # also depends on get_all_vassals
        get_target_country_religions,  # also depends on get_all_vassals
        # view
        location_stats_view,
        # functions dependent on  view
        get_world_location_stats,
        get_country_location_stats,
    ],
    entity_types=[PGFunction, PGMaterializedView],
)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata


def run_migrations_offline() -> None:
    """
    Method for running migrations in offline mode
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Method for running migrations in online mode
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

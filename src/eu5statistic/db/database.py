from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ..config import DATABASE_URL, SQL_ECHO

# Building an asynchronous engine for PostgreSQL
engine = create_async_engine(
    DATABASE_URL,
    echo=SQL_ECHO,
    pool_pre_ping=True,
    connect_args={
        "server_settings": {
            "application_name": "eu5statistic",
            "statement_timeout": "60000",  # 60 sec.
        }
    },
)

# Session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def dispose_engine_async() -> None:
    """
    Asynchronously closes the connection pool.
    Must be called from within an active asyncio event loop.
    """
    await engine.dispose()

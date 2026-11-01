from sqlalchemy import BigInteger, Column, Integer, PrimaryKeyConstraint
from sqlmodel import Field, SQLModel

SQLModel.metadata.naming_convention = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


# --------------------- Reference tables ---------------------
class Country(SQLModel, table=True):
    __tablename__ = "countries"
    id: int | None = Field(default=None, primary_key=True)
    tag: str = Field(unique=True, index=True)  # Example, "TNC"
    localization_name: str  # Example, "Tenochtitlan"


class Culture(SQLModel, table=True):
    __tablename__ = "cultures"
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True)
    localization_name: str


class Religion(SQLModel, table=True):
    __tablename__ = "religions"
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True)
    localization_name: str


class Estate(SQLModel, table=True):
    __tablename__ = "estates"
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True)
    localization_name: str


class Location(SQLModel, table=True):
    __tablename__ = "locations"
    id: int = Field(
        sa_column=Column(Integer, primary_key=True, autoincrement=False)
    )  # Location ID from the game (not auto-increment)
    localization_name: str


# --------------------- Main data tables ---------------------
class CountryPopulationStatistics(SQLModel, table=True):
    __tablename__ = "country_population_statistics"
    year: int
    country_id: int = Field(foreign_key="countries.id")
    culture_id: int = Field(foreign_key="cultures.id")
    religion_id: int = Field(foreign_key="religions.id")
    population_size: int = Field(sa_type=BigInteger)  # BIGINT
    literacy: float

    __table_args__ = (PrimaryKeyConstraint("year", "country_id", "culture_id", "religion_id"),)


class CountryStatistics(SQLModel, table=True):
    __tablename__ = "country_statistics"
    year: int
    country_id: int = Field(foreign_key="countries.id")
    primary_culture_id: int | None = Field(default=None, foreign_key="cultures.id")
    primary_religion_id: int | None = Field(default=None, foreign_key="religions.id")
    num_locations: int

    __table_args__ = (PrimaryKeyConstraint("year", "country_id"),)


class Vassalage(SQLModel, table=True):
    __tablename__ = "vassalage"
    year: int
    suzerain_id: int = Field(foreign_key="countries.id")  # сюзерен
    vassal_id: int = Field(foreign_key="countries.id")  # вассал

    __table_args__ = (PrimaryKeyConstraint("year", "suzerain_id", "vassal_id"),)


class LocationPopulationStatistics(SQLModel, table=True):
    __tablename__ = "location_population_statistics"
    year: int
    location_id: int = Field(foreign_key="locations.id")
    estate_id: int = Field(foreign_key="estates.id")
    population_size: int = Field(sa_type=BigInteger)
    literacy: float

    __table_args__ = (PrimaryKeyConstraint("year", "location_id", "estate_id"),)


class LocationStatistics(SQLModel, table=True):
    __tablename__ = "location_statistics"
    year: int
    location_id: int = Field(foreign_key="locations.id")
    country_id: int = Field(foreign_key="countries.id")

    __table_args__ = (PrimaryKeyConstraint("year", "location_id"),)

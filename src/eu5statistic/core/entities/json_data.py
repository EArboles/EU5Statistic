from dataclasses import dataclass, field

from .country_info import CountryInfo
from .population_info import PopulationInfo


@dataclass
class JsonData:
    """A dataset extracted from a JSON save file."""

    year: int | None = None
    month: int | None = None
    day: int | None = None
    player_tag: str | None = None

    cultures: dict[int, str] = field(default_factory=dict)
    religions: dict[int, str] = field(default_factory=dict)
    country_tags: dict[int, str] = field(default_factory=dict)
    countries: dict[int, CountryInfo] = field(default_factory=dict)
    population: dict[int, PopulationInfo] = field(default_factory=dict)
    subjects: dict[int, list[int]] = field(default_factory=dict)
    locations: dict[int, list[int]] = field(default_factory=dict)
    locations_names: dict[int, str] = field(default_factory=dict)

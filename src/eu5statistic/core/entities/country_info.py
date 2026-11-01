from dataclasses import dataclass, field


@dataclass
class CountryInfo:
    """Country information from the save file"""

    country_name: str | None = None
    primary_culture: int | None = None
    primary_religion: int | None = None
    owned_locations: list[int] = field(default_factory=list)
    is_revolt: bool = False

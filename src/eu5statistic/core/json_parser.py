from dataclasses import dataclass, field
from typing import Any

import ijson.backends.yajl2_c as ijson

from eu5statistic.config import INITIAL_YEAR, PERIOD_SIZE

from .entities.country_info import CountryInfo
from .entities.json_data import JsonData
from .entities.population_info import PopulationInfo

POPULATION_SCALE: int = 1000


@dataclass
class _CountryState:
    """Entity for data from a block countries.database."""

    current_id: int | None = None
    current: CountryInfo | None = None
    in_name: bool = False
    name_buffer: dict[str, Any] = field(default_factory=dict)
    collecting_owned: bool = False


@dataclass
class _PopulationState:
    """Entity for data from a block population.database."""

    current_id: int | None = None
    current: PopulationInfo | None = None


@dataclass
class _LocationState:
    """Entity for data from a block locations.locations."""

    current_id: int | None = None
    collecting_pops: bool = False
    pops: list[int] = field(default_factory=list)


@dataclass
class _CultureState:
    """Entity for data from a block culture_manager.database"""

    current_id: int | None = None


@dataclass
class _ReligionState:
    """Entity for data from a block religion_manager.database"""

    current_id: int | None = None


@dataclass
class _CountryTagState:
    """Entity for data from a block countries.tags"""

    current_id: int | None = None


@dataclass
class _DependencyState:
    """Entity for data from a block diplomacy_manager, with the name dependency"""

    temp: dict[str, int] = field(default_factory=dict)


@dataclass
class _MetadataState:
    """Entity for data from a block metadata"""

    date_found: bool = False
    location_name_index: int = 1


class JsonParser:
    """
    Reads data from a JSON file, preserving it
    """

    def __init__(self, json_path: str):
        """
        :param json_path: Full path to the target JSON file
        """
        self.json_path = json_path
        self.data = JsonData()
        self.reason: str | None = None
        self.initial_date: int = INITIAL_YEAR
        self.period_size: int = PERIOD_SIZE
        self.empty_countries: set[int] = set()

        self._meta = _MetadataState()
        self._country = _CountryState()
        self._pop = _PopulationState()
        self._location = _LocationState()
        self._culture = _CultureState()
        self._religion = _ReligionState()
        self._tag = _CountryTagState()
        self._dep = _DependencyState()

    def parse_all(self) -> tuple[bool, JsonData | None]:
        with open(self.json_path, "rb") as f:
            parser = ijson.parse(f)
            for prefix, event, value in parser:
                # Root fields (at the beginning of the file)
                if prefix == "metadata.date" and event == "string":
                    self._handle_date(value)
                elif prefix == "metadata.flag" and event == "string":
                    self._handle_flag(value)

                    # EU5 starts in April 1337. Saves can fall on month 4 (start) or 10 (autumn).
                    # We accept months 1-6 to be tolerant of mods that shift the start date.
                    is_initial_valid = self.data.year == self.initial_date and self.data.month == 4
                    is_periodic_valid = (
                        self.data.year is not None
                        and self.data.month is not None
                        and self.data.year % self.period_size == 0
                        and 1 <= self.data.month <= 6
                    )

                    if not (is_initial_valid or is_periodic_valid):
                        self.reason = "INVALID_DATE"
                        return False, self.data

                elif prefix.startswith("metadata.compatibility.locations"):
                    self._handle_location_name(prefix, event, value)
                elif prefix.startswith("culture_manager.database"):
                    self._handle_culture(prefix, event, value)
                elif prefix.startswith("religion_manager.database"):
                    self._handle_religion(prefix, event, value)
                elif prefix.startswith("countries.tags"):
                    self._handle_country_tag(prefix, event, value)
                elif prefix.startswith("countries.database"):
                    self._handle_country(prefix, event, value)
                elif prefix.startswith("population.database"):
                    self._handle_population(prefix, event, value)
                elif prefix.startswith("diplomacy_manager.dependency"):
                    self._handle_dependency(prefix, event, value)
                elif prefix.startswith("locations.locations"):
                    self._handle_location(prefix, event, value)

            if not self._meta.date_found:
                self.reason = "NOT_FOUND_DATE"
                return False, None

            return True, self.data

    # ---------- handlers ----------
    def _handle_date(self, value: str) -> None:
        """
        Date block handler
        :param value: string containing a date
        """
        parts = value.split(".")
        if len(parts) >= 3:
            try:
                self.data.year = int(parts[0])
                self.data.month = int(parts[1])
                self.data.day = int(parts[2])
                self._meta.date_found = True
            except ValueError:
                pass

    def _handle_flag(self, value: str) -> None:
        """
        Handler for a block containing a managed country tag
        :param value: a string containing the tag

        The JSON input looks something like this:
        "TNC={ pattern=... color1=... }"
        We take the part before the first '=' — this is the country tag.
        """
        self.data.player_tag = value.split("=", 1)[0] if "=" in value else value

    def _handle_location_name(self, prefix: str, event: str, value: Any) -> None:
        """
        Handler for a block containing location names
        """
        if prefix == "metadata.compatibility.locations" and event == "start_array":
            self._meta.location_name_index = 1
        elif prefix == "metadata.compatibility.locations.item" and event == "string":
            self.data.locations_names[self._meta.location_name_index] = value
            self._meta.location_name_index += 1

    def _handle_culture(self, prefix: str, event: str, value: Any) -> None:
        """
        Handler for a block containing cultures
        """
        if prefix == "culture_manager.database" and event == "map_key":
            self._culture.current_id = int(value)
        elif (
            event == "string" and prefix.endswith(".name") and self._culture.current_id is not None
        ):
            self.data.cultures[self._culture.current_id] = value
            self._culture.current_id = None
        elif (
            event == "end_map"
            and prefix.startswith("culture_manager.database.")
            and self._culture.current_id is not None
        ):
            # If the name has not been set (no string event was received), we still finalize the object
            self._culture.current_id = None

    def _handle_religion(self, prefix: str, event: str, value: Any) -> None:
        """
        Handler for a block containing religions
        """
        if prefix == "religion_manager.database" and event == "map_key":
            self._religion.current_id = int(value)
        elif (
            event == "string" and prefix.endswith(".name") and self._religion.current_id is not None
        ):
            self.data.religions[self._religion.current_id] = value
            self._religion.current_id = None
        elif (
            event == "end_map"
            and prefix.startswith("religion_manager.database.")
            and self._religion.current_id is not None
        ):
            # If the name has not been set (no string event was received), we still finalize the object
            self._religion.current_id = None

    def _handle_country_tag(self, prefix: str, event: str, value: Any) -> None:
        """
        Handler for a block for countries containing dictionary: key (ID), value (string tag)
        """
        parts = prefix.split(".")
        if prefix == "countries.tags" and event == "map_key":
            self._tag.current_id = int(value)
        elif (
            event == "string"
            and len(parts) == 3
            and parts[0] == "countries"
            and parts[1] == "tags"
            and self._tag.current_id is not None
        ):
            self.data.country_tags[self._tag.current_id] = value
            self._tag.current_id = None

    def _handle_country(self, prefix: str, event: str, value: Any) -> None:
        """
        Handler for the block containing country data
        """
        parts = prefix.split(".")
        if prefix == "countries.database" and event == "map_key":
            self._country.current_id = int(value)
            self._country.current = CountryInfo()
            self._country.in_name = False
            self._country.name_buffer.clear()
            self._country.collecting_owned = False

        elif event == "start_map" and parts[-1] == "country_name":
            self._country.in_name = True
            self._country.name_buffer.clear()

        elif event == "end_map" and parts[-1] == "country_name":
            self._country.in_name = False
            if self._country.current is not None and self._country.name_buffer:
                name = self._country.name_buffer.get("name", "")
                # Civil war factions have country_name like { name="CIVILWAR_FACTION" bases={Base="..."} }
                # We extract the base country name and mark it as a revolt.
                if "CIVILWAR_FACTION" in name:
                    self._country.current.country_name = self._country.name_buffer.get(
                        "bases", {}
                    ).get("Base")
                    self._country.current.is_revolt = True
                else:
                    self._country.current.country_name = name
            self._country.name_buffer.clear()

        elif event == "string" and self._country.in_name:
            if self._country.current is not None:
                if parts[-1] == "name":
                    self._country.name_buffer["name"] = value
                elif parts[-1] == "Base" and len(parts) >= 2 and parts[-2] == "bases":
                    self._country.name_buffer.setdefault("bases", {})["Base"] = value

        # String fields (country_name can be a string)
        elif event == "string" and not self._country.in_name and parts[-1] != "database":
            if (
                self._country.current is not None
                and parts[-1] == "country_name"
                and not isinstance(value, dict)
            ):
                self._country.current.country_name = value

        # Processing the owned_locations array (higher priority)
        elif event == "start_array" and parts[-1] == "owned_locations":
            if self._country.current is not None:
                self._country.current.owned_locations = []
                self._country.collecting_owned = True
        elif event == "number" and self._country.collecting_owned:
            if self._country.current is not None:
                self._country.current.owned_locations.append(int(value))
        elif event == "end_array" and parts[-1] == "owned_locations":
            self._country.collecting_owned = False

        # Other numeric fields (primary_culture, primary_religion)
        # Important: verify that we are not inside the owned_locations array
        elif event == "number" and not self._country.in_name and not self._country.collecting_owned:
            if self._country.current is not None:
                if parts[-1] == "primary_culture":
                    self._country.current.primary_culture = int(value)
                elif parts[-1] == "primary_religion":
                    self._country.current.primary_religion = int(value)

        # Completion of the country object
        elif (
            event == "end_map"
            and self._country.current_id is not None
            and prefix == f"countries.database.{self._country.current_id}"
        ):
            if self._country.current is not None:
                if (
                    self._country.current.primary_culture is None
                    or self._country.current.primary_religion is None
                    or not self._country.current.owned_locations
                ):
                    self.empty_countries.add(self._country.current_id)
                else:
                    self.data.countries[self._country.current_id] = self._country.current
            self._country.current_id = None
            self._country.current = None

    def _handle_population(self, prefix: str, event: str, value: Any) -> None:
        """
        Handler for the block containing population data
        """
        if prefix == "population.database" and event == "map_key":
            self._pop.current_id = int(value)
            self._pop.current = PopulationInfo()
        elif event == "string" and self._pop.current is not None:
            if prefix.endswith(".type"):
                self._pop.current.estate = value
        elif event == "number" and self._pop.current is not None:
            if prefix.endswith(".size"):
                self._pop.current.size = int(value * POPULATION_SCALE)
            elif prefix.endswith(".culture"):
                self._pop.current.culture = value
            elif prefix.endswith(".religion"):
                self._pop.current.religion = value
            elif prefix.endswith(".literacy"):
                self._pop.current.literacy = float(value or 0) / 100.0
        elif (
            event == "end_map"
            and prefix.startswith("population.database.")
            and self._pop.current_id is not None
            and self._pop.current is not None
        ):
            if self._pop.current.size is not None:
                self.data.population[self._pop.current_id] = self._pop.current
            self._pop.current_id = None
            self._pop.current = None

    def _handle_dependency(self, prefix: str, event: str, value: Any) -> None:
        """
        Handler for the block containing information on the vassal status of countries
        """
        if event == "start_map" and prefix == "diplomacy_manager.dependency.item":
            self._dep.temp.clear()
        elif event == "number" and prefix.endswith(".first"):
            self._dep.temp["first"] = value
        elif event == "number" and prefix.endswith(".second"):
            self._dep.temp["second"] = value
        elif event == "end_map" and prefix == "diplomacy_manager.dependency.item":
            first = self._dep.temp.get("first")
            second = self._dep.temp.get("second")
            if (
                first is not None
                and second is not None
                and first not in self.empty_countries
                and second not in self.empty_countries
            ):
                self.data.subjects.setdefault(first, []).append(second)
            self._dep.temp.clear()

    def _handle_location(self, prefix: str, event: str, value: Any) -> None:
        """
        Handler for the block containing location data
        """
        parts = prefix.split(".")
        if prefix == "locations.locations" and event == "map_key":
            self._location.current_id = int(value)
            self._location.collecting_pops = False
            self._location.pops = []
        elif event == "start_array" and parts[-1] == "pops":
            self._location.collecting_pops = True
        elif event == "number" and self._location.collecting_pops:
            self._location.pops.append(int(value))
        elif event == "end_array" and parts[-1] == "pops":
            self._location.collecting_pops = False
        elif (
            event == "end_map"
            and prefix.startswith("locations.locations.")
            and self._location.current_id is not None
        ):
            self.data.locations[self._location.current_id] = self._location.pops
            self._location.current_id = None

    def get_failure_reason(self) -> str:
        """Returns the reason for parser failure. Call only when parse_all() returned ok=False."""
        return self.reason or "UNKNOWN_ERROR"

from collections import defaultdict
from collections.abc import Iterable
from logging import Logger

from eu5statistic.config import LOCALIZATION_LANGUAGE
from eu5statistic.core.entities.json_data import JsonData
from eu5statistic.core.localization.transformations import (
    get_terra_nullius_name,
    transform_country_name,
    transform_culture_name,
)

from ..core import LocalizationCache
from ..core.entities import PopulationInfo
from .db_operations import (
    EntityCaches,
    clear_year_data,
    get_country_id,
    load_caches,
    refresh_location_stats_view,
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


class DbUpdater:
    def __init__(self, data: JsonData, localization_data: LocalizationCache, detail_log: Logger):
        if data.year is None:
            raise ValueError("JsonData.year is None; cannot update database")
        self.data: JsonData = data
        self.year: int = data.year
        self.localization_data: LocalizationCache = localization_data
        self.caches: EntityCaches
        self.detail_log: Logger = detail_log
        self.exist_errors: bool = False

    def _get_index(
        self,
        game_id: int,
        id_to_name: dict[int, str],
        name_to_index: dict[str, int],
        entity_name: str,
    ) -> int | None:
        """
        A generalized method for retrieving an entity's database ID using its `game_id`
        :param game_id: the game ID
        :param id_to_name: a dictionary mapping `game_id` to `name`
        :param name_to_index: a dictionary mapping `name` to `id`
        :param entity_name: the name of the entity
        :return: the entity's database ID
        """
        name = id_to_name.get(game_id)
        if name is None:
            self.detail_log.error("%s: no name for game_id=%d", entity_name, game_id)
            self.exist_errors = True
            return None
        index = name_to_index.get(name)
        if index is None:
            self.detail_log.error("%s '%s' not found in cache", entity_name, name)
            self.exist_errors = True
            return None
        return index

    def _get_culture_index(self, culture_id: int) -> int | None:
        """
        Method for retrieving a culture's database ID
        :param culture_id: the in-game ID of the culture
        :return: the culture's database ID
        """
        return self._get_index(culture_id, self.data.cultures, self.caches.cultures, "Culture")

    def _get_religion_index(self, religion_id: int) -> int | None:
        """
        Method for retrieving a religion's ID from the database
        :param religion_id: the in-game ID of the religion
        :return: the religion's ID from the database
        """
        return self._get_index(religion_id, self.data.religions, self.caches.religions, "Religion")

    def _get_country_index(self, country_id: int) -> int | None:
        """
        Method for retrieving a state's ID from the database
        :param country_id: the state's in-game ID
        :return: the state's ID from the database
        """
        return self._get_index(country_id, self.data.country_tags, self.caches.countries, "Country")

    def _is_known_location(self, location_id: int) -> bool:
        """
        Method for checking the existence of a location ID
        :param location_id: location ID
        :return: whether it exists
        """
        if location_id not in self.caches.locations:
            self.detail_log.error("Location id=%d not found in cache", location_id)
            self.exist_errors = True
            return False
        return True

    async def update(self) -> None:
        """Data update method"""

        # Updating reference data
        await self._update_estates()
        await self._update_cultures()
        await self._update_religions()
        await self._update_locations()
        await self._update_countries()
        self.detail_log.info("Loading cache from the database")

        # Loading cache
        self.caches = await load_caches()
        await clear_year_data(self.year)
        # Adding information for the specified year
        await self._add_vassalage()
        await self._add_location_statistics()
        await self._add_location_population_statistics()
        await self._add_country_statistics()
        await self._add_country_population_statistics()
        await self._add_terra_incognita_fake_country()

        self.detail_log.info("Refreshing location_stats_view")
        await refresh_location_stats_view()

    async def _update_estates(self) -> None:
        """The method of updating estates"""
        self.detail_log.info("Updating estates")

        estate_pairs = set()
        for pop_id, pop in self.data.population.items():
            if pop.estate is None:
                self.detail_log.error("Population id=%d has no estate", pop_id)
                self.exist_errors = True
                continue

            estate_name = pop.estate
            localization_name = self.localization_data.get(estate_name)
            if localization_name is None:
                self.detail_log.error(
                    "No localization for estate '%s' in population id=%d", estate_name, pop_id
                )
                self.exist_errors = True
                continue

            estate_pairs.add((estate_name, localization_name))

        if estate_pairs:
            await upsert_estates(list(estate_pairs))

    async def _update_cultures(self) -> None:
        """
        The method of updating cultures
        """
        self.detail_log.info("Updating cultures")

        culture_pairs = set()

        for pop_id, pop in self.data.population.items():
            if pop.culture is None:
                self.detail_log.error("Population id=%d has no culture", pop_id)
                self.exist_errors = True
                continue

            culture_id = pop.culture
            culture_name = self.data.cultures.get(culture_id)
            if culture_name is None:
                self.detail_log.error(
                    "No internal game name for culture id=%d in population id=%d",
                    culture_id,
                    pop_id,
                )
                self.exist_errors = True
                continue

            culture_localization_name = self.localization_data.get(culture_name)
            if culture_localization_name is None:
                self.detail_log.error(
                    "No localization for culture id=%d with internal name '%s'",
                    culture_id,
                    culture_name,
                )
                self.exist_errors = True
                continue

            culture_localization_name = transform_culture_name(
                culture_localization_name, LOCALIZATION_LANGUAGE
            )

            culture_pairs.add((culture_name, culture_localization_name))

        if culture_pairs:
            await upsert_cultures(list(culture_pairs))

    async def _update_religions(self) -> None:
        """
        The method of updating religions
        """
        self.detail_log.info("Updating religions")

        religions_pairs = set()

        for pop_id, pop in self.data.population.items():
            if pop.religion is None:
                self.detail_log.error("Population id=%d has no religion", pop_id)
                self.exist_errors = True
                continue

            religion_id = pop.religion
            religion_name = self.data.religions.get(religion_id)
            if religion_name is None:
                self.detail_log.error(
                    "No internal game name for religion id=%d in population id=%d",
                    religion_id,
                    pop_id,
                )
                self.exist_errors = True
                continue

            religion_localization_name = self.localization_data.get(religion_name)
            if religion_localization_name is None:
                self.detail_log.error(
                    "No localization for religion id=%d with internal name '%s'",
                    religion_id,
                    religion_name,
                )
                self.exist_errors = True
                continue

            religions_pairs.add((religion_name, religion_localization_name))

        if religions_pairs:
            await upsert_religions(list(religions_pairs))

    async def _update_locations(self) -> None:
        """
        The method of updating locations
        """
        self.detail_log.info("Updating locations")

        location_pairs = set()

        for location_id in self.data.locations:
            location_name = self.data.locations_names.get(location_id)
            if location_name is None:
                self.detail_log.error("No internal game name for location id=%d", location_id)
                self.exist_errors = True
                continue

            location_localization_name = self.localization_data.get(location_name)
            if location_localization_name is None:
                self.detail_log.error(
                    "No localization for location id=%d with internal name '%s'",
                    location_id,
                    location_name,
                )
                self.exist_errors = True
                continue

            location_pairs.add((location_id, location_localization_name))

        if location_pairs:
            await upsert_location(list(location_pairs))

    async def _update_countries(self) -> None:
        """
        The method of updating countries
        """
        self.detail_log.info("Updating countries")
        country_pairs = set()

        for country_id, value in self.data.countries.items():
            country_tag = self.data.country_tags.get(country_id)
            if country_tag is None:
                self.detail_log.error("No internal game tag for country id=%d", country_id)
                self.exist_errors = True
                continue

            country_name = value.country_name
            if country_name is None:
                self.detail_log.error("Country id=%d has no name", country_id)
                self.exist_errors = True
                continue

            country_localization_name = self.localization_data.get(country_name)
            if country_localization_name is None:
                country_localization_name = self.localization_data.get(country_tag, None)
                if country_localization_name is None:
                    self.detail_log.error(
                        "No localization for country id=%d with internal name '%s'",
                        country_id,
                        country_name,
                    )
                    self.exist_errors = True
                    continue

            country_localization_name = transform_country_name(
                country_localization_name, value.is_revolt, LOCALIZATION_LANGUAGE
            )

            country_pairs.add((country_tag, country_localization_name))

        if country_pairs:
            await upsert_country(list(country_pairs))

    async def _add_vassalage(self) -> None:
        """
        Method of adding vassal relations
        """
        self.detail_log.info("Adding vassal relations")
        vassalage_pairs = set()

        for suzerain_id, vassals in self.data.subjects.items():
            suzerain_index = self._get_country_index(suzerain_id)
            if suzerain_index is None:
                continue

            for vassal_id in vassals:
                vassal_index = self._get_country_index(vassal_id)
                if vassal_index is None:
                    continue

                vassalage_pairs.add((suzerain_index, vassal_index))

        if vassalage_pairs:
            await upsert_vassalage(list(vassalage_pairs), self.year)

    async def _add_location_population_statistics(self) -> None:
        """
        Method for adding statistics on the population of locations
        """
        self.detail_log.info("Adding statistics on the population of locations")
        location_population_statistics_pairs = set()

        for location_id, pop_ids in self.data.locations.items():
            if not self._is_known_location(location_id):
                continue

            # Group POPs by estate name
            estate_to_pops: dict[str, list[PopulationInfo]] = {}
            for pop_id in pop_ids:
                pop_info = self.data.population.get(pop_id)
                if pop_info is None:
                    continue

                estate_name = pop_info.estate
                if estate_name is None:
                    continue

                if estate_name not in estate_to_pops:
                    estate_to_pops[estate_name] = []
                estate_to_pops[estate_name].append(pop_info)

            # Processing of each estate group
            for estate_name, pops in estate_to_pops.items():
                estate_id = self.caches.estates.get(estate_name)
                if estate_id is None:
                    self.detail_log.error(
                        "Estate with internal name '%s' not found in cache", estate_name
                    )
                    self.exist_errors = True
                    continue

                # Calculating the total population and average literacy (weighted)
                total_pop = round(sum(pop.size or 0 for pop in pops))
                if total_pop == 0:
                    continue  # there is no point in adding an entry with a population of zero

                weighted_literacy = round(
                    sum((pop.size or 0) * pop.literacy for pop in pops) / total_pop, 4
                )

                # Add a record to the batch
                location_population_statistics_pairs.add(
                    (
                        location_id,
                        estate_id,
                        total_pop,
                        weighted_literacy,
                    )
                )

        # Bulk insert/update
        if location_population_statistics_pairs:
            await upsert_location_population_statistics(
                list(location_population_statistics_pairs), self.year
            )

    async def _add_location_statistics(self) -> None:
        """
        Method for adding location-based statistics
        """
        self.detail_log.info("Adding location-based statistics")
        location_statistics_pairs = set()

        for country_id, value in self.data.countries.items():
            country_index = self._get_country_index(country_id)
            if country_index is None:
                continue

            for location_id in value.owned_locations:
                if not self._is_known_location(location_id):
                    continue

                # Add a record to the batch
                location_statistics_pairs.add((location_id, country_index))

        # Bulk insert/update
        if location_statistics_pairs:
            await upsert_location_statistics(list(location_statistics_pairs), self.year)

    async def _add_country_statistics(self) -> None:
        """
        Method for adding country-specific statistics
        """
        self.detail_log.info("Adding country-specific statistics")
        country_statistics_pairs = set()

        for country_id, value in self.data.countries.items():
            country_index = self._get_country_index(country_id)
            if (
                country_index is None
                or value.primary_culture is None
                or value.primary_religion is None
            ):
                continue

            primary_culture_index = self._get_culture_index(value.primary_culture)
            if primary_culture_index is None:
                continue

            primary_religion_index = self._get_religion_index(value.primary_religion)
            if primary_religion_index is None:
                continue

            country_statistics_pairs.add(
                (
                    country_index,
                    primary_culture_index,
                    primary_religion_index,
                    len(value.owned_locations),
                )
            )

        if country_statistics_pairs:
            await upsert_country_statistics(list(country_statistics_pairs), self.year)

    async def _add_country_population_statistics(self) -> None:
        """
        Method for adding statistics on country populations
        """
        self.detail_log.info("Adding statistics on country populations")
        country_population_pairs = set()

        for country_id, country_info in self.data.countries.items():
            country_index = self._get_country_index(country_id)
            if country_index is None:
                continue

            groups = self._group_population(country_info.owned_locations)
            country_population_pairs |= self._build_country_population_pairs(country_index, groups)

        if country_population_pairs:
            await upsert_country_population_statistics(list(country_population_pairs), self.year)

    def _get_ownerless_locations(self) -> set[int]:
        """
        Returns locations that do not belong to any country
        :return: a set of locations
        """
        all_locations = set(self.caches.locations)
        occupied: set[int] = set()
        for country_info in self.data.countries.values():
            occupied.update(country_info.owned_locations)
        return all_locations - occupied

    async def _ensure_terra_nullius(self) -> int | None:
        """
        A method that retrieves the ID of the TERRA_NULLIUS state from the database, creating it if necessary.
        :return: The ID of the TERRA_NULLIUS state from the database
        """
        tag = "TERRA_NULLIUS"
        country_id = self.caches.countries.get(tag)
        if country_id is not None:
            return country_id

        await upsert_country([(tag, get_terra_nullius_name(LOCALIZATION_LANGUAGE))])
        country_id = await get_country_id(tag)
        if country_id is None:
            self.detail_log.error("Failed to get id for '%s'", tag)
            self.exist_errors = True
            return None

        self.caches.countries[tag] = country_id
        return country_id

    def _group_population(self, location_ids: Iterable[int]) -> dict[tuple[int, int], list[float]]:
        """
        Groups the population of the specified locations by (culture_id, religion_id).
        :return: A grouping of population and literacy by (culture_id, religion_id).
        """
        groups: dict[tuple[int, int], list[float]] = defaultdict(lambda: [0, 0.0])
        for location_id in location_ids:
            for pop_id in self.data.locations.get(location_id, []):
                pop = self.data.population.get(pop_id)
                if pop is None or pop.culture is None or pop.religion is None:
                    continue
                key = (pop.culture, pop.religion)
                groups[key][0] += pop.size or 0
                groups[key][1] += (pop.size or 0) * pop.literacy
        return groups

    def _build_country_population_pairs(
        self, country_id: int, groups: dict[tuple[int, int], list[float]]
    ) -> set[tuple[int, int, int, int, float]]:
        """
        Stores the TERRA_NULLIUS population, broken down by culture and religion.
        :param country_id:
        :param groups: a grouping of population and literacy data by (culture_id, religion_id)
        :return
        """
        pairs = set()
        for (culture, religion), (total_size, weighted_sum) in groups.items():
            culture_index = self._get_culture_index(culture)
            if culture_index is None:
                continue
            religion_index = self._get_religion_index(religion)
            if religion_index is None:
                continue
            average_literacy = round(weighted_sum / total_size, 4) if total_size > 0 else 0.0
            pairs.add(
                (
                    country_id,
                    culture_index,
                    religion_index,
                    int(total_size),
                    average_literacy,
                )
            )
        return pairs

    async def _save_terra_country_statistics(
        self,
        country_id: int,
        groups: dict[tuple[int, int], list[float]],
        num_locations: int,
    ) -> None:
        """
        Saves CountryStatistics for TERRA_NULLIUS (based on the majority primary culture/religion).
        :param country_id: country ID
        :param groups: population and literacy data grouped by (culture_id, religion_id)
        :param num_locations: number of locations
        """
        culture_total: defaultdict[int, int] = defaultdict(int)
        religion_total: defaultdict[int, int] = defaultdict(int)
        for (culture, religion), (size, _) in groups.items():
            culture_total[culture] += int(size)
            religion_total[religion] += int(size)

        primary_culture_index = (
            self._get_culture_index(max(culture_total, key=lambda k: culture_total[k]))
            if culture_total
            else None
        )
        primary_religion_index = (
            self._get_religion_index(max(religion_total, key=lambda k: religion_total[k]))
            if religion_total
            else None
        )

        await upsert_country_statistics(
            [(country_id, primary_culture_index, primary_religion_index, num_locations)],
            self.year,
        )

    async def _save_terra_location_statistics(
        self, country_id: int, ownerless_locations: set[int]
    ) -> None:
        """
        Saves LocationStatistics for TERRA_NULLIUS
        :param country_id: state ID
        :param ownerless_locations: list of locations
        """
        pairs = set()
        for location_id in ownerless_locations:
            if not self._is_known_location(location_id):
                continue
            pairs.add((location_id, country_id))

        if pairs:
            await upsert_location_statistics(list(pairs), self.year)

    async def _add_terra_incognita_fake_country(self) -> None:
        """
        Method for adding statistics on unclaimed territories (TERRA_NULLIUS)
        """
        self.detail_log.info("Adding statistics on unclaimed territories")

        ownerless_locations = self._get_ownerless_locations()
        if not ownerless_locations:
            return

        country_id = await self._ensure_terra_nullius()
        if country_id is None:
            return

        groups = self._group_population(ownerless_locations)

        pairs = self._build_country_population_pairs(country_id, groups)
        if pairs:
            await upsert_country_population_statistics(list(pairs), self.year)

        await self._save_terra_country_statistics(country_id, groups, len(ownerless_locations))
        await self._save_terra_location_statistics(country_id, ownerless_locations)

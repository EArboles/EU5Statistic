"""Processing a single EU5 save file: conversion, parsing, and loading into a database"""

import logging
import shutil
import time
from datetime import datetime
from logging import Logger
from pathlib import Path

from eu5statistic.config import (
    ERROR_DIR,
    JSON_EXTENSION,
    LOG_FILENAME_WIDTH,
    LOG_STATUS_WIDTH,
    PROCESSED_DIR,
    RAKALY_PATH,
    SAVE_EXTENSION,
)
from eu5statistic.core import LocalizationCache
from eu5statistic.core.binary_converter import BinaryToJsonConverter
from eu5statistic.core.entities import JsonData
from eu5statistic.core.json_parser import JsonParser
from eu5statistic.db import DbUpdater

from .logging_setup import rename_log_file


class FileProcessor:
    def __init__(
        self, localization_cache: LocalizationCache, file_path: Path, detail_log: Logger
    ) -> None:
        self.localization_cache: LocalizationCache = localization_cache
        self.file_path = file_path
        self.file_name = file_path.name
        self.json_path = file_path.with_suffix(JSON_EXTENSION)
        self.detail_log = detail_log
        if RAKALY_PATH is None:
            raise RuntimeError(
                "RAKALY_PATH is not set. Specify it in .env or add rakaly to your PATH"
            )
        self.rakaly_path: Path = RAKALY_PATH

    async def process(self) -> None:
        """
        Processes a file asynchronously:
        - converts .eu5 → .json (if necessary)
        - parses the JSON
        - loads the data into the database

        Upon successful processing, the original file remains in WATCH_DIR (it is not moved),
        while a copy is placed in PROCESSED_DIR. This is a deliberate design choice:
        - autosaves are managed by the game (which handles their cleanup)
        - regular save files belong to the player.
        Files are also copied to the `errors/` directory, while the originals remain in place.
        """
        # 1. Conversion, if it’s an .eu5 file
        self.detail_log.info(f"Starting file processing: {self.file_name}")
        start_time = time.time()
        if self.file_path.suffix == SAVE_EXTENSION:
            self.detail_log.info("Conversion .eu5 -> .json")
            try:
                converter = BinaryToJsonConverter(self.rakaly_path)
                converter.convert_to_json(self.file_path, self.json_path)
            except Exception as e:
                self.detail_log.exception(f"Conversion error: {e}")
                # перемещаем в errors
                self._copy_to_errors(self.file_path, "conversion_error")
                return

        # 2. Parsing JSON
        self.detail_log.info("Parsing JSON")
        try:
            parser = JsonParser(str(self.json_path))
            ok, data = parser.parse_all()

            if data is not None and data.player_tag and data.year:
                rename_log_file(self.detail_log, self.get_tag_and_date_style_name(data, ".log"))

            if not ok:
                reason = parser.get_failure_reason()
                if reason == "INVALID_DATE":
                    self.detail_log.warning("Parsing stopped: inappropriate date")
                    self.json_path.unlink(missing_ok=True)
                    date_str = (
                        f"{data.year}.{data.month}.{data.day}" if data is not None else "unknown"
                    )
                    self._log_brief("Omitted", f"Inappropriate date: {date_str}")
                else:
                    self.detail_log.error(f"Parsing stopped: {reason}")
                    self._copy_to_errors(self.file_path, reason)
                return

            if data is None:
                self.detail_log.error("Parser returned ok=True but data is None")
                self._copy_to_errors(self.file_path, "parser_none_data")
                return
        except Exception as e:
            self.detail_log.exception(f"Parsing error: {e}")
            self._copy_to_errors(self.file_path, "parse_exception")
            return

        file_year = data.year

        # 3. Loading into the database (asynchronously)
        self.detail_log.info("Loading data into the database")
        try:
            updater = DbUpdater(data, self.localization_cache, self.detail_log)
            await updater.update()
            if updater.exist_errors:
                self._copy_to_errors(self.file_path, "db_error")
                self.detail_log.warning("Not all data was successfully loaded")
                return
            self.detail_log.info("Data successfully loaded")
        except Exception as e:
            self.detail_log.exception(f"Error loading into the database: {e}")
            self._copy_to_errors(self.file_path, "db_error", year=file_year)
            return

        # 4. Успех
        elapsed = time.time() - start_time
        self.detail_log.info(f"Processing completed successfully, time: {elapsed:.2f} sec")
        self.json_path.unlink(missing_ok=True)
        dest_path = PROCESSED_DIR / self.get_tag_and_date_style_name(data, SAVE_EXTENSION)
        shutil.copy2(self.file_path, dest_path)
        self._log_brief("Successfully", f"{elapsed:.2f} sec")

    def _log_brief(self, status: str, detail: str) -> None:
        """Write to brief log"""
        brief = logging.getLogger("brief")
        brief.info(
            f"{self.file_name:<{LOG_FILENAME_WIDTH}} | {status:<{LOG_STATUS_WIDTH}} | {detail}"
        )

    def _copy_to_errors(self, source_path: Path, reason: str, year: int | None = None) -> None:
        """
        Copies the source file to data/errors and renames it.
        Name: {reason}_{year}_{original name}
        """
        ERROR_DIR.mkdir(parents=True, exist_ok=True)
        if year:
            new_name = f"{reason}_{year}_{source_path.name}"
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            new_name = f"{reason}_{timestamp}_{source_path.name}"
        dest_path = ERROR_DIR / new_name
        shutil.copy2(source_path, dest_path)

        self.detail_log.warning(f"File: {source_path.name} copied to errors as {new_name}")
        self.json_path.unlink(missing_ok=True)
        self._log_brief("ERROR", reason)

    def get_tag_and_date_style_name(self, data: JsonData, ext: str) -> str:
        """
        Method for obtaining a stylized filename
        :param data: dataset from a JSON save file
        :param ext: file extension
        :return: new file name
        """
        if data.month is None or data.day is None:
            self.detail_log.warning("Missing month/day in save metadata, defaulting to 01")

        month_str = f"{data.month:02d}" if data.month else "01"
        day_str = f"{data.day:02d}" if data.day else "01"
        return f"{data.player_tag}-{data.year}.{month_str}.{day_str}{ext}"

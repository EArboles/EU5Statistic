"""Application entry point."""

import argparse
import asyncio
import logging
import time
from pathlib import Path
from typing import cast

from eu5statistic.config import (
    CACHE_DIR,
    GAME_FOLDER,
    LOCALIZATION_LANGUAGE,
    LOG_DIVIDING_LINE_LENGTH,
    SAVE_EXTENSION,
    USER_DATA_FOLDER,
)
from eu5statistic.core.localization import (
    LocalizationCache,
    LocalizationFileParser,
    LocalizationLoader,
)
from eu5statistic.core.mods_resolver import ModsResolver
from eu5statistic.db import dispose_engine_async
from eu5statistic.services import FileProcessor
from eu5statistic.services.logging_setup import get_detail_logger, setup_brief_logger
from eu5statistic.services.watcher import FileWatcher


def _build_localization_cache(brief: logging.Logger) -> LocalizationCache:
    """Collects localization cache: vanilla + active mods."""
    folders: list[Path] = []

    # 1. Vanilla
    game_loc = GAME_FOLDER / "main_menu" / "localization" / LOCALIZATION_LANGUAGE
    if not game_loc.is_dir():
        raise RuntimeError(f"Vanilla localization folder not found: {game_loc}\nCheck GAME_FOLDER.")
    folders.append(game_loc)

    # 2. Active mods
    mod_paths = ModsResolver(cast(Path, USER_DATA_FOLDER), brief).get_active_mod_paths()

    local_mods_without_loc: list[str] = []
    workshop_mods_without_loc: list[str] = []
    if mod_paths:
        brief.info("Active mods found: %d", len(mod_paths))
    for mod in mod_paths:
        mod_loc = mod / "main_menu" / "localization" / LOCALIZATION_LANGUAGE
        if mod_loc.is_dir():
            folders.append(mod_loc)
        else:
            mod_name = mod.name

            if "workshop" in str(mod).lower():
                workshop_mods_without_loc.append(mod_name)
            else:
                local_mods_without_loc.append(mod_name)

    if local_mods_without_loc or workshop_mods_without_loc:
        parts = []
        if local_mods_without_loc:
            parts.append(f"Local: {', '.join(local_mods_without_loc)}")
        if workshop_mods_without_loc:
            parts.append(f"Workshop: {', '.join(workshop_mods_without_loc)}")

        brief.warning(
            "Mods without '%s' localization: %s", LOCALIZATION_LANGUAGE, " | ".join(parts)
        )

    # 3. Parser + loader + cache
    parser = LocalizationFileParser(encoding="utf-8")
    loader = LocalizationLoader(folders, parser, brief)
    cache_file = CACHE_DIR / "localization_cache.json"
    return LocalizationCache(loader, cache_file, brief)


async def _process_one_file(
    file_path: Path, localization_cache: LocalizationCache, logger: logging.Logger
) -> None:
    """Runs FileProcessor for a single save file asynchronously."""
    run_id = f"{file_path.stem}_{time.strftime('%Y%m%d_%H%M%S')}_{time.time_ns() % 1_000_000}"
    detail_log = get_detail_logger(run_id)
    detail_log.info("Processing file: %s", file_path)

    file_processor = FileProcessor(localization_cache, file_path, detail_log)
    await file_processor.process()


async def _run_single_file_async(
    file_path: Path, localization_cache: LocalizationCache, logger: logging.Logger
) -> None:
    logger.info("Manual initiation of file processing: %s", file_path)
    await _process_one_file(file_path, localization_cache, logger)


async def _run_folder_async(
    folder_path: Path, localization_cache: LocalizationCache, logger: logging.Logger
) -> None:
    files = [f for f in folder_path.iterdir() if f.is_file() and f.suffix.lower() == SAVE_EXTENSION]
    if not files:
        logger.info("No *%s files found in %s", SAVE_EXTENSION, folder_path)
        return

    logger.info("Found %d file(s) to process in %s", len(files), folder_path)
    for file_path in files:
        try:
            await _process_one_file(file_path, localization_cache, logger)
        except Exception as e:
            logger.error("Failed to process %s: %s", file_path.name, e)


async def _run_app_async(
    args: argparse.Namespace, localization_cache: LocalizationCache, brief: logging.Logger
) -> None:
    """A single asynchronous entry point for all modes."""
    try:
        if args.file:
            file_path = Path(args.file)
            if not file_path.exists():
                brief.info("File not found: %s", file_path)
                return
            if file_path.suffix.lower() != SAVE_EXTENSION:
                brief.info("File %s does not have extension: %s", file_path, SAVE_EXTENSION)
                return
            await _run_single_file_async(file_path, localization_cache, brief)

        elif args.folder:
            folder_path = Path(args.folder)
            if not folder_path.is_dir():
                brief.info("Folder not found: %s", folder_path)
                return
            await _run_folder_async(folder_path, localization_cache, brief)

        else:
            # For watcher (It runs in its own thread, so we just call it synchronously)
            _run_watcher(localization_cache)
    finally:
        # Closing the DB INSIDE a running event loop
        await dispose_engine_async()


def main() -> None:
    parser = argparse.ArgumentParser(description="EU5 save file processor")
    parser.add_argument("--file", type=str, help="Process the specified file and exit")
    parser.add_argument(
        "--folder",
        type=str,
        help="Process all .eu5 files in the specified folder and exit",
    )
    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="Clear localization cache before launching",
    )
    args = parser.parse_args()

    setup_brief_logger()
    brief = logging.getLogger("brief")

    if args.file and args.folder:
        brief.error("Use either --file or --folder, not both.")
        return

    if args.clear_cache:
        cache_file = CACHE_DIR / "localization_cache.json"
        if cache_file.exists():
            cache_file.unlink()
            brief.info("Cache removed: %s", cache_file)

    localization_cache = _build_localization_cache(brief)
    brief.info("-" * LOG_DIVIDING_LINE_LENGTH)

    try:
        # We launch a SINGLE event loop for the entire program
        asyncio.run(_run_app_async(args, localization_cache, brief))
    finally:
        brief.info("-" * LOG_DIVIDING_LINE_LENGTH)
        brief.info("Processing complete.")


def _run_watcher(localization_cache: LocalizationCache) -> None:
    watcher = FileWatcher(localization_cache)
    watcher.start()  # blocks until a KeyboardInterrupt occurs


if __name__ == "__main__":
    main()

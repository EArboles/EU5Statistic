"""Application configuration EU5Statistics."""

import json
import os
import platform
import shutil
from pathlib import Path
from typing import overload

from dotenv import load_dotenv

# ============================================================================
# Project root and .env
# ============================================================================
BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")


# ============================================================================
# Helpers
# ============================================================================
def _get_int_env(name: str, default: int) -> int:
    """Reads an integer environment variable, with a fallback to a default value."""
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return int(value.strip())
    except ValueError:
        return default


def _get_bool_env(name: str, default: bool = False) -> bool:
    """Reads a boolean environment variable, with a fallback to a default value."""
    value = os.getenv(name, "").strip().lower()
    if not value:
        return default
    return value in ("1", "true", "yes", "on")


@overload
def _get_path_env(name: str, default: Path) -> Path: ...
@overload
def _get_path_env(name: str, default: None = None) -> Path | None: ...
def _get_path_env(name: str, default: Path | None = None) -> Path | None:
    """
    Reads a path from an environment variable.

    Relative paths are resolved with respect to BASE_DIR (the project root), rather than the current working directory.
    """
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    path = Path(raw)
    if not path.is_absolute():
        path = (BASE_DIR / path).resolve()
    return path


def _require_env(name: str) -> str:
    """Returns a required environment variable or fails with a clear error."""
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(
            f"Required environment variable {name} is not set.\n"
            f"Copy .env.example to .env and fill it in."
        )
    return value


def _default_user_data_folder() -> Path | None:
    """Automatic detection of the EU5 profile folder for standard installations."""
    home = Path.home()
    system = platform.system()

    if system == "Windows" or system == "Darwin":
        candidate = home / "Documents" / "Paradox Interactive" / "Europa Universalis V"
    else:  # Linux and others
        candidate = home / ".local" / "share" / "Paradox Interactive" / "Europa Universalis V"

    return candidate if candidate.is_dir() else None


def _detect_language(user_data_folder: Path | None) -> str:
    """
    Specifies the language: pdx_settings.json > english
    :param user_data_folder: Paradox player profile folder path for EU5
    :return: User language
    """
    # 1. From pdx_settings.json
    if user_data_folder is not None:
        settings = user_data_folder / "pdx_settings.json"
        if settings.is_file():
            try:
                raw = json.loads(settings.read_text(encoding="utf-8"))
                lang = raw.get("System", {}).get("language", "").strip()
                lang = lang.removeprefix("l_")
                if lang:
                    return lang
            except (json.JSONDecodeError, OSError):
                pass

    # 2. Default
    return "english"


def _definition_rakaly_path() -> Path | None:
    """
    Method for determining the path to the Rakaly utility
    :return: Path if is found otherwise None
    """
    raw = os.getenv("RAKALY_PATH", "").strip()
    if raw:
        path = Path(raw)
        if not path.is_absolute():
            path = (BASE_DIR / path).resolve()
        return path
    found = shutil.which("rakaly") or shutil.which("rakaly.exe")
    return Path(found) if found else None


# ============================================================================
# Mandatory: Database and game
# ============================================================================
DATABASE_URL: str = _require_env("DATABASE_URL")
_game_folder = _get_path_env("GAME_FOLDER")
if _game_folder is None:
    raise RuntimeError("GAME_FOLDER not specified. Specify the path to .env.")
GAME_FOLDER: Path = _game_folder

# ============================================================================
# Paradox player profile folder
# ============================================================================
USER_DATA_FOLDER: Path | None = _get_path_env("USER_DATA_FOLDER") or _default_user_data_folder()
if USER_DATA_FOLDER is None:
    raise RuntimeError(
        "Could not determine USER_DATA_FOLDER. "
        "Specify the path to the 'Paradox Interactive/Europa Universalis V' folder in the .env file."
    )

# ============================================================================
# Derivative paths
# ============================================================================
WATCH_DIR: Path = USER_DATA_FOLDER / "save games"
if not WATCH_DIR.is_dir():
    raise RuntimeError(
        f"Save folder not found: {WATCH_DIR}\nCheck USER_DATA_FOLDER or play EU5 at least once."
    )

LOCALIZATION_LANGUAGE: str = _detect_language(USER_DATA_FOLDER)
GAME_LOCALIZATION_DIR: Path = GAME_FOLDER / "main_menu" / "localization" / LOCALIZATION_LANGUAGE
if not GAME_LOCALIZATION_DIR.is_dir():
    raise RuntimeError(
        f"Localization folder not found: {GAME_LOCALIZATION_DIR}\nCheck GAME_FOLDER."
    )


# ============================================================================
# Application paths (data, logs, cache)
# ============================================================================
DATA_DIR: Path = _get_path_env("DATA_DIR", BASE_DIR / "data")
LOG_DIR: Path = DATA_DIR / "logs"
PROCESSED_DIR: Path = DATA_DIR / "processed"
ERROR_DIR: Path = DATA_DIR / "errors"
CACHE_DIR: Path = DATA_DIR / "cache"


# ============================================================================
# External utilities
# ============================================================================
RAKALY_PATH: Path | None = _definition_rakaly_path()


# ============================================================================
# Logging settings
# ============================================================================
BRIEF_LOG: Path = LOG_DIR / "brief.log"
DETAIL_LOG_PREFIX: str = "detail_"
MAX_BRIEF_LOG_SIZE: int = 10 * 1024 * 1024

LOG_FILENAME_WIDTH: int = _get_int_env("LOG_FILENAME_WIDTH", 50)
LOG_STATUS_WIDTH: int = _get_int_env("LOG_STATUS_WIDTH", 12)
LOG_DIVIDING_LINE_LENGTH: int = LOG_FILENAME_WIDTH + LOG_STATUS_WIDTH * 2 + 6

# ============================================================================
# Processing parameters
# ============================================================================
INITIAL_YEAR: int = _get_int_env("INITIAL_YEAR", 1337)
PERIOD_SIZE: int = _get_int_env("PERIOD_SIZE", 5)

# ============================================================================
# SQL
# ============================================================================
SQL_ECHO: bool = _get_bool_env("SQL_ECHO", default=False)


# ============================================================================
# Creating directories
# ============================================================================
for directory in (DATA_DIR, LOG_DIR, PROCESSED_DIR, ERROR_DIR, CACHE_DIR):
    directory.mkdir(parents=True, exist_ok=True)

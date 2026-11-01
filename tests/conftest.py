"""Pytest configuration: set fake env vars and create temp dirs before importing app."""

import os
import tempfile
from pathlib import Path

# Create a temporary directory that persists for the session
_temp_dir = Path(tempfile.mkdtemp(prefix="eu5statistic_test_"))

# Create subdirectories that config.py expects
_game_folder = _temp_dir / "game"
_user_data_folder = _temp_dir / "user_data"
_watch_dir = _user_data_folder / "save games"
_localization_dir = _game_folder / "main_menu" / "localization" / "english"

for d in (_game_folder, _user_data_folder, _watch_dir, _localization_dir):
    d.mkdir(parents=True, exist_ok=True)

# Set environment variables before any eu5statistic import
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
os.environ.setdefault("GAME_FOLDER", str(_game_folder))
os.environ.setdefault("USER_DATA_FOLDER", str(_user_data_folder))
os.environ.setdefault("DATA_DIR", str(_temp_dir / "data"))
os.environ.setdefault("LOCALIZATION_LANGUAGE", "english")

"""Logging configuration: brief and detailed loggers.

- brief: a summary for all files, consolidated into a single rotating log.
- detail: a detailed log for the processing of an individual file; it is renamed
based on a tag and the date once parsing has been successfully completed.
"""

import logging
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

from eu5statistic.config import BRIEF_LOG, LOG_DIR, MAX_BRIEF_LOG_SIZE


class BriefFormatter(logging.Formatter):
    """
    Formatter for the 'brief' log.

    - Table rows ("file | status | time") → no prefix, no timestamp.
    - Separator lines (all dashes) → no prefix, no timestamp.
    - System messages → [LEVEL] timestamp - message.
    """

    def __init__(self, include_date: bool = True):
        super().__init__()
        self.datefmt = "%Y-%m-%d %H:%M:%S" if include_date else "%H:%M:%S"

    def format(self, record: logging.LogRecord) -> str:
        asctime = self.formatTime(record, self.datefmt)
        msg = record.getMessage()
        # Table rows: no prefix
        if " | " in msg and not msg.startswith(" "):
            return f"{asctime} - {msg}"

        # Separator lines (all dashes): no prefix, no timestamp
        stripped = msg.strip()
        if stripped and set(stripped) == {"-"}:
            return f"{asctime} - {msg}"

        # System messages
        level = record.levelname
        return f"{asctime} - [{level}] {msg}"


def setup_brief_logger() -> logging.Logger:
    """Returns a brief logger containing general information about save processing"""
    brief = logging.getLogger("brief")
    if not brief.handlers:
        brief.setLevel(logging.INFO)

        # 1. File handler (with datetime)
        fh = RotatingFileHandler(
            BRIEF_LOG, maxBytes=MAX_BRIEF_LOG_SIZE, backupCount=5, encoding="utf-8"
        )
        fh.setFormatter(BriefFormatter(include_date=True))
        brief.addHandler(fh)

        # 2. Console handler (timeonly)
        ch = logging.StreamHandler()
        ch.setFormatter(BriefFormatter(include_date=False))
        brief.addHandler(ch)

    return brief


def get_detail_logger(run_id: str) -> logging.Logger:
    """Returns a logger with an attached file for a specific run"""
    logger = logging.getLogger(f"detail_{run_id}")
    logger.setLevel(logging.DEBUG)
    # To avoid duplicating handlers, we perform a check
    if not logger.handlers:
        fh = logging.FileHandler(LOG_DIR / f"detail_{run_id}.log", encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
        logger.addHandler(fh)
    return logger


def rename_log_file(logger: logging.Logger, new_name: str) -> None:
    """
    A method for renaming a log file and restarting the logger responsible for it
    :param logger: the logger
    :param new_name: the new name for the log
    """
    brief = logging.getLogger("brief")
    for handler in logger.handlers:
        if not isinstance(handler, logging.FileHandler):
            continue

        old_path = Path(handler.baseFilename)
        new_path = old_path.parent / new_name

        if new_path.exists():
            new_path = new_path.with_stem(f"{new_path.stem}_{time.time_ns()}")
        try:
            # Close the handle BEFORE renaming (a Windows requirement)
            handler.close()
            old_path.rename(new_path)
        except OSError as e:
            # Renaming failed — restoring the handler to its original state
            brief.warning("Failed to rename log %s: %s", old_path, e)
            new_path = old_path
        new_handler = logging.FileHandler(new_path, encoding="utf-8")
        new_handler.setFormatter(handler.formatter)

        logger.removeHandler(handler)
        logger.addHandler(new_handler)
        break

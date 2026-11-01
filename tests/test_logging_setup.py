"""Tests for logging_setup: brief and detail loggers."""

import logging
from pathlib import Path

import pytest

from eu5statistic.services.logging_setup import (
    get_detail_logger,
    rename_log_file,
    setup_brief_logger,
)


@pytest.fixture(autouse=True)
def clean_loggers():
    """Remove handlers BEFORE and AFTER each test."""

    def _clean():
        for name in list(logging.Logger.manager.loggerDict.keys()):
            if name == "brief" or name.startswith("detail_"):
                logger = logging.getLogger(name)
                for h in list(logger.handlers):
                    h.close()
                    logger.removeHandler(h)

    _clean()
    yield
    _clean()


def test_setup_brief_logger_creates_file(tmp_path: Path, monkeypatch) -> None:
    log_file = tmp_path / "brief.log"
    monkeypatch.setattr("eu5statistic.services.logging_setup.BRIEF_LOG", log_file)

    logger = setup_brief_logger()
    logger.info("test message")

    # Flush handlers
    for h in logger.handlers:
        h.flush()

    assert log_file.is_file()
    assert "test message" in log_file.read_text(encoding="utf-8")


def test_setup_brief_logger_idempotent(tmp_path: Path, monkeypatch) -> None:
    log_file = tmp_path / "brief.log"
    monkeypatch.setattr("eu5statistic.services.logging_setup.BRIEF_LOG", log_file)

    logger1 = setup_brief_logger()
    logger2 = setup_brief_logger()

    assert logger1 is logger2  # same logger object


def test_get_detail_logger_creates_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("eu5statistic.services.logging_setup.LOG_DIR", tmp_path)
    logger = get_detail_logger("test_run")
    logger.info("detail message")

    for h in logger.handlers:
        h.flush()

    log_file = tmp_path / "detail_test_run.log"
    assert log_file.is_file()
    assert "detail message" in log_file.read_text(encoding="utf-8")


def test_rename_log_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("eu5statistic.services.logging_setup.LOG_DIR", tmp_path)
    logger = get_detail_logger("test_run")
    logger.info("before rename")

    for h in logger.handlers:
        h.flush()

    old_path = tmp_path / "detail_test_run.log"
    assert old_path.is_file()

    rename_log_file(logger, "MOS-1444.11.11.log")

    new_path = tmp_path / "MOS-1444.11.11.log"
    assert new_path.is_file()
    assert not old_path.exists()
    assert "before rename" in new_path.read_text(encoding="utf-8")

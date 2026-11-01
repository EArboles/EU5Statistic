"""Monitoring the save folder and triggering the processing of new files.

Uses `watchdog` to track file system events.
Processing is serialized via `asyncio.Lock` to prevent
concurrent database writes for the same year.
"""

import asyncio
import logging
import threading
import time
from pathlib import Path

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers.polling import PollingObserver

from eu5statistic.config import (
    SAVE_EXTENSION,
    TEMP_SAVE_EXTENSION,
    WATCH_DIR,
)

from ..core import LocalizationCache
from .file_processor import FileProcessor
from .logging_setup import get_detail_logger

_FILE_STABLE_TIMEOUT = 30
_FILE_STABLE_INTERVAL = 1
_FILE_STABLE_CHECKS = 2


class FileWatcher:
    def __init__(self, localization_cache: LocalizationCache) -> None:
        self.localization_cache = localization_cache
        self.observer = PollingObserver()
        self.processing_files: dict[str, float] = {}
        self.lock = threading.Lock()
        self._db_lock = asyncio.Lock()

        # Creating and running a custom event loop in a background thread
        self.loop = asyncio.new_event_loop()
        self.loop_thread = threading.Thread(target=self._run_loop, daemon=True)
        self.loop_thread.start()

    async def _process_serialized(self, fp: FileProcessor) -> None:
        async with self._db_lock:
            await fp.process()

    def _run_loop(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def start(self) -> None:
        event_handler = _FileEventHandler(self)
        self.observer.schedule(event_handler, str(WATCH_DIR), recursive=False)
        self.observer.start()

        brief = logging.getLogger("brief")
        brief.info(f"Monitoring of {WATCH_DIR} has started")
        try:
            self.observer.join()
        except KeyboardInterrupt:
            brief.info("Stopping watcher...")
            self.observer.stop()
        self.observer.join()


class _FileEventHandler(FileSystemEventHandler):
    def __init__(self, watcher: FileWatcher) -> None:
        self.watcher = watcher

    # Creating .eu5 (rare, but just in case)
    def on_created(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        path = Path(str(event.src_path))
        if path.suffix.lower() == SAVE_EXTENSION:
            self._start_processing(path)

    # Change to .eu5 (may occur after a move)
    def on_modified(self, event: FileSystemEvent) -> None:
        """
         Handle .eu5 modifications.

        Note: if a file is modified while it's being processed, the change is
        ignored. This is acceptable for EU5 saves because the game writes them
        atomically (.tmp -> .eu5), and on_moved catches the final state.
        """
        if event.is_directory:
            return
        path = Path(str(event.src_path))
        if path.suffix.lower() == SAVE_EXTENSION:
            self._start_processing(path)

    # Movement – that’s the key logic here
    def on_moved(self, event: FileSystemEvent) -> None:
        if event.is_directory:
            return
        src = Path(str(event.src_path))
        dst = Path(str(event.dest_path))

        # Finalizing new save: .tmp -> .eu5
        if src.suffix.lower() == TEMP_SAVE_EXTENSION and dst.suffix.lower() == SAVE_EXTENSION:
            self._start_processing(dst)

    def _start_processing(self, path: Path) -> None:
        # Preventing the reprocessing of a single file
        with self.watcher.lock:
            if str(path) in self.watcher.processing_files:
                return
            self.watcher.processing_files[str(path)] = time.time()

        threading.Thread(target=self._process, args=(path,), daemon=True).start()

    def _process(self, file_path: Path) -> None:
        brief = logging.getLogger("brief")
        try:
            # Waiting for the file to finish writing (size remains stable for 2 seconds)
            if not self._wait_for_file_stable(file_path, timeout=30):
                brief.warning(
                    "File %s did not stabilize within %s seconds; skipping",
                    file_path,
                    _FILE_STABLE_TIMEOUT,
                )
                return

            run_id = (
                f"{file_path.stem}_{time.strftime('%Y%m%d_%H%M%S')}_{time.time_ns() % 1_000_000}"
            )
            detail_log = get_detail_logger(run_id)

            file_processor = FileProcessor(self.watcher.localization_cache, file_path, detail_log)
            coro = self.watcher._process_serialized(file_processor)
            future = asyncio.run_coroutine_threadsafe(coro, self.watcher.loop)
            future.result()

        except Exception as e:
            brief.error(f"File: {file_path.name} | ERROR | {e!s}")
        finally:
            # Remove the file from the list of files being processed
            with self.watcher.lock:
                self.watcher.processing_files.pop(str(file_path), None)

    def _wait_for_file_stable(
        self,
        path: Path,
        timeout: int = _FILE_STABLE_TIMEOUT,
        interval: int = _FILE_STABLE_INTERVAL,
        stable_checks: int = _FILE_STABLE_CHECKS,
    ) -> bool:
        """
        Waits until the file size stops changing.

        :param timeout: Maximum time to wait (in seconds).
        :param interval: Interval between checks (in seconds).
        :param stable_checks: Number of consecutive checks for which the size must remain unchanged.
        :return: True if the file has stabilized; False if a timeout occurs or the file disappears.
        """
        start = time.time()
        last_size = -1
        stable_count = 0
        while time.time() - start < timeout:
            if not path.exists():
                return False
            try:
                current_size = path.stat().st_size
            except OSError:
                return False

            if current_size == last_size:
                stable_count += 1
                if stable_count >= stable_checks:
                    return True
            else:
                stable_count = 0
                last_size = current_size
            time.sleep(interval)
        return False

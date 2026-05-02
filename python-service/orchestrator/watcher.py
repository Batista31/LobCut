"""
orchestrator/watcher.py
Watchdog-based folder monitor for OpenClaw.
"""

import shutil
import time
from pathlib import Path

from watchdog.events import FileCreatedEvent, FileSystemEventHandler
from watchdog.observers import Observer

from config.logger import get_logger
from config.path_resolver import PathResolver
from config.settings import (
    FILE_STABILITY_POLL_INTERVAL,
    FILE_STABILITY_POLLS_REQUIRED,
    INPUT_IMAGES,
    INPUT_VIDEOS,
)
from orchestrator.database import STATUS_UNKNOWN, insert_job, job_exists
from orchestrator.router import TYPE_UNKNOWN, classify

log = get_logger(__name__)


def _wait_until_stable(path: Path) -> bool:
    stable_count = 0
    last_size = -1
    missing_retries = 5

    while stable_count < FILE_STABILITY_POLLS_REQUIRED:
        if not path.exists():
            if missing_retries > 0:
                log.debug(
                    "Stability check: %s missing, retrying (%d left)",
                    path.name,
                    missing_retries,
                )
                missing_retries -= 1
                time.sleep(FILE_STABILITY_POLL_INTERVAL)
                continue
            log.warning("Stability check: %s disappeared — skipping", path.name)
            return False

        try:
            current_size = path.stat().st_size
        except OSError:
            if missing_retries > 0:
                log.debug(
                    "Stability check: %s stat failed, retrying (%d left)",
                    path.name,
                    missing_retries,
                )
                missing_retries -= 1
                time.sleep(FILE_STABILITY_POLL_INTERVAL)
                continue
            log.warning("Stability check: %s stat failed — skipping", path.name)
            return False

        if current_size == last_size and current_size > 0:
            stable_count += 1
        else:
            stable_count = 0
            last_size = current_size

        time.sleep(FILE_STABILITY_POLL_INTERVAL)

    log.debug("Stability confirmed for %s (%d bytes)", path.name, last_size)
    return True


class MediaHandler(FileSystemEventHandler):

    def on_created(self, event: FileCreatedEvent) -> None:
        if event.is_directory:
            return

        path = Path(event.src_path).resolve()

        name = path.name
        if (
            name.startswith("~")
            or name.startswith(".")
            or name.startswith("Unconfirmed")
            or name.endswith(".crdownload")
            or name.endswith(".part")
            or name.endswith(".tmp")
        ):
            log.debug("Skipping temp/hidden or partial file: %s", name)
            return

        log.info("─" * 60)
        log.info("[DETECTED] %s", path.name)

        if job_exists(path):
            log.warning("[DUPLICATE] %s already in database — skipping", path.name)
            return

        log.debug("Waiting for %s to finish writing…", path.name)
        if not _wait_until_stable(path):
            return

        detected_type, pipeline = classify(path)

        db_status = STATUS_UNKNOWN if detected_type == TYPE_UNKNOWN else "PENDING"
        job_id = insert_job(
            source_path=path,
            detected_type=detected_type,
            pipeline=pipeline,
            status=db_status,
        )

        if job_id is None:
            log.warning("[DUPLICATE] %s — race condition, already inserted", path.name)
            return

        if detected_type == TYPE_UNKNOWN:
            _handle_unknown(path, job_id)
        else:
            log.info(
                "[ROUTED]   %s | Type: %-5s | Pipeline: %-15s | Job ID: #%d",
                path.name,
                detected_type,
                pipeline,
                job_id,
            )

        log.info("─" * 60)


def _handle_unknown(path: Path, job_id: int) -> None:
    dest = PathResolver.quarantine(path)
    try:
        shutil.move(str(path), dest)
        log.warning(
            "[UNKNOWN]  %s | Extension: %r | Moved to quarantine | Job ID: #%d",
            path.name,
            path.suffix,
            job_id,
        )
    except Exception as exc:
        log.error(
            "[UNKNOWN]  %s | Could not quarantine: %s | Job ID: #%d",
            path.name,
            exc,
            job_id,
        )


def build_observer() -> Observer:
    observer = Observer()
    handler = MediaHandler()

    for folder in (INPUT_VIDEOS, INPUT_IMAGES):
        folder.mkdir(parents=True, exist_ok=True)
        observer.schedule(handler, str(folder), recursive=False)
        log.info("Watching: %s", folder)

    return observer

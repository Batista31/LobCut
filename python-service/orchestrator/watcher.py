"""
orchestrator/watcher.py
Watchdog-based folder monitor for LobCut.
"""

import shutil
import time
import os
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
    PIPELINE_IMAGE,
    PIPELINE_VIDEO,
)
from orchestrator.database import (
    DEFAULT_USER_ID,
    STATUS_UNKNOWN,
    insert_job,
    job_exists,
    list_enabled_watchers,
)
from orchestrator.router import TYPE_IMAGE, TYPE_UNKNOWN, TYPE_VIDEO, classify

log = get_logger(__name__)

_scheduled_watches = set()
_active_watches = {}
_missing_watch_warnings = set()


def _is_ignored_file(path: Path) -> bool:
    name = path.name
    return (
        name.startswith("~")
        or name.startswith(".")
        or name.startswith("Unconfirmed")
        or name.endswith(".crdownload")
        or name.endswith(".part")
        or name.endswith(".tmp")
    )


def _map_watch_path(path: Path) -> Path:
    raw_path = str(path)
    mappings = os.environ.get("WATCH_PATH_MAPPINGS", "")
    for mapping in mappings.split(";"):
        if "=" not in mapping:
            continue
        host_prefix, container_prefix = mapping.split("=", 1)
        host_prefix = host_prefix.strip()
        container_prefix = container_prefix.strip()
        if not host_prefix or not container_prefix:
            continue
        if raw_path.lower().startswith(host_prefix.lower()):
            suffix = raw_path[len(host_prefix):].lstrip("\\/")
            mapped_path = Path(container_prefix) / Path(suffix.replace("\\", "/"))
            if mapped_path.exists() or not path.exists():
                return mapped_path
            return path
    return path


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
            log.warning("Stability check: %s disappeared - skipping", path.name)
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
            log.warning("Stability check: %s stat failed - skipping", path.name)
            return False

        if current_size == last_size and current_size > 0:
            stable_count += 1
        else:
            stable_count = 0
            last_size = current_size

        time.sleep(FILE_STABILITY_POLL_INTERVAL)

    log.debug("Stability confirmed for %s (%d bytes)", path.name, last_size)
    return True


def _classify_with_override(path: Path, pipeline_override: str = None) -> tuple[str, str]:
    if pipeline_override == PIPELINE_IMAGE:
        return TYPE_IMAGE, PIPELINE_IMAGE
    if pipeline_override == PIPELINE_VIDEO:
        return TYPE_VIDEO, PIPELINE_VIDEO
    return classify(path)


class MediaHandler(FileSystemEventHandler):
    def __init__(self, user_id: str = DEFAULT_USER_ID, pipeline_override: str = None) -> None:
        self.user_id = user_id
        self.pipeline_override = pipeline_override

    def on_created(self, event: FileCreatedEvent) -> None:
        if event.is_directory:
            return
        self.handle_path(Path(event.src_path))

    def handle_path(self, source_path: Path) -> None:
        path = source_path.resolve()
        if _is_ignored_file(path):
            log.debug("Skipping temp/hidden or partial file: %s", path.name)
            return

        log.info("-" * 60)
        log.info("[DETECTED] %s", path.name)

        if job_exists(path, user_id=self.user_id):
            log.warning("[DUPLICATE] %s already in database - skipping", path.name)
            return

        log.debug("Waiting for %s to finish writing...", path.name)
        if not _wait_until_stable(path):
            return

        detected_type, pipeline = _classify_with_override(path, self.pipeline_override)

        db_status = STATUS_UNKNOWN if detected_type == TYPE_UNKNOWN else "PENDING"
        job_id = insert_job(
            source_path=path,
            detected_type=detected_type,
            pipeline=pipeline,
            status=db_status,
            user_id=self.user_id,
        )

        if job_id is None:
            log.warning("[DUPLICATE] %s - race condition, already inserted", path.name)
            return

        if detected_type == TYPE_UNKNOWN:
            _handle_unknown(path, job_id)
        else:
            log.info(
                "[ROUTED]   %s | Type: %-5s | Pipeline: %-15s | User: %s | Job ID: #%d",
                path.name,
                detected_type,
                pipeline,
                self.user_id,
                job_id,
            )

        log.info("-" * 60)


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


def _schedule_folder(
    observer: Observer,
    folder: Path,
    user_id: str = DEFAULT_USER_ID,
    pipeline_override: str = None,
    scan_existing: bool = False,
) -> None:
    mapped_folder = _map_watch_path(folder)
    resolved = mapped_folder.expanduser().resolve()
    key = (str(resolved).lower(), pipeline_override or "auto")
    if key in _scheduled_watches:
        return

    if not resolved.exists():
        warning_key = (str(resolved).lower(), user_id, pipeline_override or "auto")
        if warning_key not in _missing_watch_warnings:
            log.warning("[WATCHER] Configured folder does not exist: %s", resolved)
            _missing_watch_warnings.add(warning_key)
        return
    if not resolved.is_dir():
        log.warning("[WATCHER] Configured path is not a folder: %s", resolved)
        return

    handler = MediaHandler(user_id=user_id, pipeline_override=pipeline_override)
    observer.schedule(handler, str(resolved), recursive=False)
    _scheduled_watches.add(key)
    _active_watches[key] = (resolved, handler)
    log.info("Watching: %s | User: %s | Pipeline: %s", resolved, user_id, pipeline_override or "auto")

    if scan_existing:
        _scan_folder(resolved, handler)


def _scan_folder(folder: Path, handler: MediaHandler) -> None:
    try:
        candidates = list(folder.iterdir())
    except OSError as exc:
        log.warning("[WATCHER] Could not scan %s: %s", folder, exc)
        return

    for candidate in candidates:
        if not candidate.is_file() or _is_ignored_file(candidate):
            continue

        path = candidate.resolve()
        if job_exists(path, user_id=handler.user_id):
            continue

        log.info("[SCAN] Found unprocessed file in watched folder: %s", path.name)
        handler.handle_path(path)


def scan_active_watches() -> None:
    """Polling fallback for watched folders.

    Docker Desktop bind mounts on Windows do not always deliver file-created
    events reliably. This scan keeps LobCut moving even when Watchdog misses
    an event.
    """
    for folder, handler in list(_active_watches.values()):
        _scan_folder(folder, handler)


def sync_configured_watchers(observer: Observer) -> None:
    for watcher in list_enabled_watchers():
        _schedule_folder(
            observer,
            Path(watcher["path"]),
            user_id=watcher["user_id"],
            pipeline_override=watcher["pipeline_override"],
            scan_existing=True,
        )


def build_observer() -> Observer:
    observer = Observer()

    for folder in (INPUT_VIDEOS, INPUT_IMAGES):
        folder.mkdir(parents=True, exist_ok=True)
        _schedule_folder(observer, folder, scan_existing=True)

    sync_configured_watchers(observer)
    return observer

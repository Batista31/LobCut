"""
Background folder processor for MediaScribe.

This turns the input folders into a practical drop-zone workflow:
new files in input/images and input/videos are picked up, processed once,
and written to the configured output folders.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path

from config.logger import get_logger
from config.settings import (
    ENABLE_FOLDER_PROCESSOR,
    FOLDER_PROCESSOR_POLL_INTERVAL,
    INPUT_IMAGES,
    INPUT_VIDEOS,
)
from orchestrator import router
from orchestrator.database import (
    STATUS_DONE,
    STATUS_FAILED,
    STATUS_PENDING,
    STATUS_UNKNOWN,
    get_job_by_id,
    insert_job,
    job_exists,
    update_job_analysis,
)
from pipelines.image_pipeline import pipeline as image_pipeline
from pipelines.video_pipeline import pipeline as video_pipeline

log = get_logger(__name__)

_stop_event = threading.Event()
_thread: threading.Thread | None = None


def _is_candidate(path: Path) -> bool:
    name = path.name
    return (
        path.is_file()
        and not name.startswith(".")
        and not name.startswith("~")
        and not name.startswith("Unconfirmed")
        and not name.endswith(".crdownload")
        and not name.endswith(".part")
        and not name.endswith(".tmp")
    )


def _wait_until_stable(path: Path) -> bool:
    last_size = -1
    stable_count = 0
    while stable_count < 2:
        if not path.exists():
            return False
        current_size = path.stat().st_size
        if current_size > 0 and current_size == last_size:
            stable_count += 1
        else:
            stable_count = 0
            last_size = current_size
        time.sleep(1)
    return True


def _process_file(path: Path) -> None:
    if job_exists(path):
        return

    if not _wait_until_stable(path):
        log.warning("[FOLDER] Skipping unstable or missing file: %s", path)
        return

    detected_type, pipeline_name = router.classify(path)
    status = STATUS_UNKNOWN if detected_type == router.TYPE_UNKNOWN else STATUS_PENDING
    job_id = insert_job(path, detected_type, pipeline_name, status=status)
    if job_id is None:
        return

    if detected_type == router.TYPE_UNKNOWN:
        log.warning("[FOLDER] Unsupported file type skipped: %s", path.name)
        return

    job = get_job_by_id(job_id)
    if job is None:
        log.error("[FOLDER] Job disappeared after insert: #%s", job_id)
        return

    if pipeline_name == "image_pipeline":
        image_pipeline.process_job(job)
    elif pipeline_name == "video_pipeline":
        video_pipeline.run(job_id, path)
        updated = get_job_by_id(job_id)
        if updated is not None and updated["status"] == STATUS_DONE:
            update_job_analysis(
                job_id,
                ai_category="video_clips",
                ai_summary="Video processed into caption-ready clips with clip-level subtitle files.",
                classifier="whisper+ffmpeg+highlight_clips",
            )
    else:
        log.warning("[FOLDER] No processor for pipeline %s", pipeline_name)

    updated = get_job_by_id(job_id)
    if updated is not None:
        if updated["status"] == STATUS_DONE:
            log.info("[FOLDER] DONE #%s | %s", job_id, path.name)
        elif updated["status"] == STATUS_FAILED:
            log.error("[FOLDER] FAILED #%s | %s | %s", job_id, path.name, updated["error_message"])


def _scan_once() -> None:
    for folder in (INPUT_IMAGES, INPUT_VIDEOS):
        folder.mkdir(parents=True, exist_ok=True)
        for path in sorted(folder.iterdir()):
            if _is_candidate(path):
                _process_file(path.resolve())


def _loop() -> None:
    log.info("[FOLDER] Processor watching images=%s videos=%s", INPUT_IMAGES, INPUT_VIDEOS)
    while not _stop_event.is_set():
        try:
            _scan_once()
        except Exception:
            log.exception("[FOLDER] Processor loop failed")
        _stop_event.wait(FOLDER_PROCESSOR_POLL_INTERVAL)


def start() -> None:
    global _thread
    if not ENABLE_FOLDER_PROCESSOR:
        log.info("[FOLDER] Processor disabled")
        return
    if _thread and _thread.is_alive():
        return
    _stop_event.clear()
    _thread = threading.Thread(target=_loop, name="folder-processor", daemon=True)
    _thread.start()


def stop() -> None:
    _stop_event.set()

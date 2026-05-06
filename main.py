"""
main.py — LobCut entrypoint
Usage: python main.py
Ctrl+C to stop cleanly.
"""

import signal
import sys
import time
import os
from pathlib import Path

import requests

from config.logger import get_logger
from config.settings import (
    ENABLE_CAPTION_PIPELINE,
    JOB_DISPATCH_POLL_INTERVAL,
    PIPELINE_IMAGE,
    PIPELINE_VIDEO,
    ROOT,
    UNCLASSIFIED_RETRY_INTERVAL_SEC,
)
from orchestrator.database import (
    STATUS_FAILED,
    STATUS_PROCESSING,
    get_first_linked_telegram_chat_id,
    get_telegram_chat_id,
    get_pending_jobs,
    get_pending_retry_jobs,
    init_db,
    list_pending_telegram_jobs,
    mark_telegram_delivered,
    recover_interrupted_jobs,
    reset_pending_retry_job,
    update_job_status,
)
from orchestrator.watcher import build_observer, scan_active_watches, sync_configured_watchers
from pipelines.caption_pipeline.reel_watcher import build_reel_observer
from pipelines.image_pipeline import process_job as process_image_job
from pipelines.image_pipeline.pipeline import check_gemini_ready
from pipelines.video_pipeline import run as run_video_job

log = get_logger(__name__)

BANNER = r"""
  _           _      ____      _
 | |    ___  | |__  / ___|   _| |_
 | |   / _ \ | '_ \| |  | | | | __|
 | |__| (_) || |_) | |__| |_| | |_
 |_____\___/ |_.__/ \____\__,_|\__|

  Autonomous Media Processing Agent
"""


_last_retry_scan: float = 0.0


def _retry_unclassified_image_jobs() -> None:
    """Every UNCLASSIFIED_RETRY_INTERVAL_SEC seconds, re-queue any image jobs
    that previously failed Gemini classification and are sitting in unclassified/.
    They are flipped back to PENDING so the normal dispatch loop picks them up.
    """
    global _last_retry_scan
    now = time.time()
    if now - _last_retry_scan < UNCLASSIFIED_RETRY_INTERVAL_SEC:
        return
    _last_retry_scan = now

    jobs = get_pending_retry_jobs(PIPELINE_IMAGE)
    if not jobs:
        return

    log.info("[RETRY] Auto-retrying %d unclassified image job(s)...", len(jobs))
    requeued = 0
    for job in jobs:
        if reset_pending_retry_job(int(job["id"])):
            requeued += 1
    if requeued:
        log.info("[RETRY] Re-queued %d job(s) for Gemini classification.", requeued)


def _dispatch_pending_image_jobs() -> None:
    pending_jobs = get_pending_jobs(PIPELINE_IMAGE)
    for job in pending_jobs:
        job_id = int(job["id"])
        source_name = Path(job["source_path"]).name

        try:
            update_job_status(job_id, STATUS_PROCESSING)
            log.info("[DISPATCH] Image Job #%d | %s", job_id, source_name)
            process_image_job(job)
        except Exception as exc:
            log.exception("[DISPATCH] Image Job #%d crashed", job_id)
            update_job_status(job_id, STATUS_FAILED, error_message=str(exc))


def _dispatch_pending_video_jobs() -> None:
    pending_jobs = get_pending_jobs(PIPELINE_VIDEO)
    for job in pending_jobs:
        job_id = int(job["id"])
        source_name = Path(job["source_path"]).name
        try:
            update_job_status(job_id, STATUS_PROCESSING)
            log.info("[DISPATCH] Video Job #%d | %s", job_id, source_name)
            run_video_job(job_id, job["source_path"])
        except Exception as exc:
            log.exception("[DISPATCH] Video Job #%d crashed", job_id)
            update_job_status(job_id, STATUS_FAILED, error_message=str(exc))


def deliver_pending_notifications() -> None:
    """Send Telegram notifications for DONE jobs not yet delivered."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        return

    for job in list_pending_telegram_jobs(limit=20):
        job_id = int(job["id"])
        try:
            telegram_chat_id = get_telegram_chat_id(job["user_id"])
            if not telegram_chat_id and job["user_id"] == "local":
                # Legacy/local watcher jobs are visible in every signed-in dashboard.
                # Send them to the first user who has linked Telegram.
                telegram_chat_id = get_first_linked_telegram_chat_id()
            if not telegram_chat_id:
                continue

            category = job["ai_category"] if "ai_category" in job.keys() and job["ai_category"] else "N/A"
            msg = f"Job #{job_id} done\nFile: {job['filename']}\nCategory: {category}"
            resp = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": telegram_chat_id, "text": msg},
                timeout=10,
            )
            if resp.ok:
                mark_telegram_delivered(job_id)
            else:
                log.warning(
                    "Telegram delivery failed for job #%d: HTTP %s",
                    job_id,
                    resp.status_code,
                )
        except Exception as exc:
            log.warning("Telegram delivery failed for job #%d: %s", job_id, exc)


def main() -> None:
    print(BANNER)
    log.info("Starting LobCut | Root: %s", ROOT)

    init_db()
    recover_interrupted_jobs()

    # --- Gemini startup diagnostic ---
    gemini = check_gemini_ready()
    if gemini["ready"]:
        print(f"  ✅ Gemini API  : connected ({gemini['model']})")
    else:
        print(f"  ❌ Gemini API  : {gemini['error']}")
        print("     Images will be held in unclassified/ until Gemini is available.")
    print()

    observer = build_observer()
    observer.start()

    reel_observer = None
    if ENABLE_CAPTION_PIPELINE:
        reel_observer = build_reel_observer()
        reel_observer.start()

    log.info("Watcher active. Drop files into input/videos/ or input/images/")
    log.info("Press Ctrl+C to stop.\n")

    def _shutdown(signum, frame):
        log.info("Signal %d received — shutting down…", signum)
        observer.stop()
        if reel_observer:
            reel_observer.stop()

    signal.signal(signal.SIGTERM, _shutdown)

    try:
        while observer.is_alive():
            sync_configured_watchers(observer)
            scan_active_watches()
            _dispatch_pending_image_jobs()
            _dispatch_pending_video_jobs()
            _retry_unclassified_image_jobs()
            deliver_pending_notifications()
            time.sleep(JOB_DISPATCH_POLL_INTERVAL)
    except KeyboardInterrupt:
        log.info("KeyboardInterrupt — stopping watcher…")
        observer.stop()
        if reel_observer:
            reel_observer.stop()

    observer.join()
    if reel_observer:
        reel_observer.join()
    log.info("LobCut stopped cleanly.")
    sys.exit(0)


if __name__ == "__main__":
    main()

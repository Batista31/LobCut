from __future__ import annotations

import time
from pathlib import Path

from watchdog.events import FileCreatedEvent, FileSystemEventHandler
from watchdog.observers import Observer

from config.logger import get_logger
from config.settings import OUTPUT_VIDEOS
from pipelines.caption_pipeline.pipeline import run as run_caption_pipeline

log = get_logger(__name__)


def _wait_until_stable(path: Path, polls_required: int = 4, poll_interval: float = 1.0) -> bool:
    stable = 0
    last_size = -1
    retries_missing = 8
    while stable < polls_required:
        if not path.exists():
            if retries_missing <= 0:
                return False
            retries_missing -= 1
            time.sleep(poll_interval)
            continue
        try:
            size = path.stat().st_size
        except OSError:
            time.sleep(poll_interval)
            continue
        if size > 0 and size == last_size:
            stable += 1
        else:
            stable = 0
            last_size = size
        time.sleep(poll_interval)
    return True


class ReelHandler(FileSystemEventHandler):
    def on_created(self, event: FileCreatedEvent) -> None:
        if event.is_directory:
            return
        path = Path(event.src_path).resolve()
        if path.suffix.lower() != ".mp4":
            return
        if "_captioned" in path.stem:
            return
        if "captioned" in {p.lower() for p in path.parts}:
            return
        if path.parent.name.lower() != "reels":
            return
        if not _wait_until_stable(path):
            log.warning("[CAPTION] Reel did not stabilize: %s", path.name)
            return
        log.info("[CAPTION] Detected reel: %s", path.name)
        run_caption_pipeline(str(path))


def build_reel_observer() -> Observer:
    reels_dir = OUTPUT_VIDEOS / "reels"
    reels_dir.mkdir(parents=True, exist_ok=True)
    observer = Observer()
    observer.schedule(ReelHandler(), str(reels_dir), recursive=False)
    log.info("Caption watcher active on: %s", reels_dir)
    return observer

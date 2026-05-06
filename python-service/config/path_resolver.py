"""
config/path_resolver.py
Single authority for resolving where any file should go.
Pipelines must never construct paths themselves.
"""

import re
from pathlib import Path

from config.settings import (
    OUTPUT_BLURRY,
    OUTPUT_IMAGES,
    OUTPUT_OTHERS,
    OUTPUT_PEOPLE,
    OUTPUT_UNCLASSIFIED,
    OUTPUT_VIDEOS,
    PIPELINE_VIDEO,
    QUARANTINE_DIR,
    TEMP_DIR,
)


class PathResolver:

    @staticmethod
    def temp_copy(source: Path) -> Path:
        TEMP_DIR.mkdir(parents=True, exist_ok=True)
        return TEMP_DIR / source.name

    @staticmethod
    def output_for_pipeline(pipeline: str, source: Path):
        if pipeline == PIPELINE_VIDEO:
            OUTPUT_VIDEOS.mkdir(parents=True, exist_ok=True)
            return OUTPUT_VIDEOS / source.name
        return None

    @staticmethod
    def blurry(source: Path) -> Path:
        OUTPUT_BLURRY.mkdir(parents=True, exist_ok=True)
        return OUTPUT_BLURRY / source.name

    @staticmethod
    def people(source: Path) -> Path:
        OUTPUT_PEOPLE.mkdir(parents=True, exist_ok=True)
        return OUTPUT_PEOPLE / source.name

    @staticmethod
    def others(source: Path) -> Path:
        OUTPUT_OTHERS.mkdir(parents=True, exist_ok=True)
        return OUTPUT_OTHERS / source.name

    @staticmethod
    def unclassified(source: Path) -> Path:
        """Holding folder for images that could not be classified by Gemini.

        Jobs routed here get STATUS_PENDING_RETRY and are automatically
        retried every UNCLASSIFIED_RETRY_INTERVAL_SEC seconds.
        """
        OUTPUT_UNCLASSIFIED.mkdir(parents=True, exist_ok=True)
        return OUTPUT_UNCLASSIFIED / source.name

    @staticmethod
    def category(source: Path, category: str) -> Path:
        safe_category = re.sub(r"[^a-z0-9_-]+", "_", category.strip().lower()).strip("_")
        if not safe_category:
            safe_category = "other"
        destination_dir = OUTPUT_IMAGES / safe_category
        destination_dir.mkdir(parents=True, exist_ok=True)
        return destination_dir / source.name

    @staticmethod
    def quarantine(source: Path) -> Path:
        QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)
        return QUARANTINE_DIR / source.name

    @staticmethod
    def video_genre_dir(genre: str) -> Path:
        safe = re.sub(r"[^a-z0-9_-]+", "_", str(genre).strip().lower()).strip("_") or "clips"
        if safe == "unknown":
            safe = "clips"
        target = OUTPUT_VIDEOS / safe
        target.mkdir(parents=True, exist_ok=True)
        return target

    @staticmethod
    def reels_dir() -> Path:
        target = OUTPUT_VIDEOS / "reels"
        target.mkdir(parents=True, exist_ok=True)
        return target

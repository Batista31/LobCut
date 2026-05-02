"""
orchestrator/router.py
Classifies an incoming file and returns the pipeline it belongs to.
"""

from pathlib import Path

from config.logger import get_logger
from config.settings import (
    IMAGE_EXTENSIONS, PIPELINE_IMAGE, PIPELINE_UNKNOWN,
    PIPELINE_VIDEO, VIDEO_EXTENSIONS,
)

log = get_logger(__name__)

TYPE_IMAGE   = "IMAGE"
TYPE_VIDEO   = "VIDEO"
TYPE_UNKNOWN = "UNKNOWN"


def classify(path: Path) -> tuple[str, str]:
    """
    Returns (detected_type, pipeline_name).
    e.g. ("IMAGE", "image_pipeline")
    """
    suffix = path.suffix.lower()

    if suffix in IMAGE_EXTENSIONS:
        log.debug("classify: %s → IMAGE", path.name)
        return TYPE_IMAGE, PIPELINE_IMAGE

    if suffix in VIDEO_EXTENSIONS:
        log.debug("classify: %s → VIDEO", path.name)
        return TYPE_VIDEO, PIPELINE_VIDEO

    log.warning("classify: %s → UNKNOWN (extension: %r)", path.name, suffix)
    return TYPE_UNKNOWN, PIPELINE_UNKNOWN

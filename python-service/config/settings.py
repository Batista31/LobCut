"""
config/settings.py
Single source of truth for MediaScribe's embedded OpenClaw pipelines.
"""

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _bool_from_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _path_from_env(name: str, default: Path | str) -> Path:
    raw = os.getenv(name)
    if raw:
        return Path(raw).expanduser()
    return Path(default)


INPUT_ROOT = _path_from_env("INPUT_ROOT", ROOT / "input")
INPUT_VIDEOS = _path_from_env("INPUT_VIDEOS", INPUT_ROOT / "videos")
INPUT_IMAGES = _path_from_env("INPUT_IMAGES", INPUT_ROOT / "images")

OUTPUT_ROOT = _path_from_env("OUTPUT_DIR", ROOT / "output")
OUTPUT_VIDEOS = OUTPUT_ROOT / "videos"
OUTPUT_IMAGES = OUTPUT_ROOT / "images"
OUTPUT_BLURRY = OUTPUT_IMAGES / "blurry"
OUTPUT_PEOPLE = OUTPUT_IMAGES / "people"
OUTPUT_OTHERS = OUTPUT_IMAGES / "others"

TEMP_DIR = _path_from_env("TEMP_DIR", ROOT / "temp")

LOGS_DIR = _path_from_env("LOGS_DIR", ROOT / "logs")
LOG_FILE = _path_from_env("LOG_FILE", LOGS_DIR / "openclaw.log")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_MAX_BYTES = 5 * 1024 * 1024
LOG_BACKUP_COUNT = 3

DB_PATH = _path_from_env("DB_PATH", ROOT / "orchestrator" / "jobs.db")
MEMORY_LOG_PATH = _path_from_env(
    "MEMORY_LOG_PATH",
    Path.home() / ".openclaw" / "workspace" / "mediascribe" / "memory" / "MEMORY_LOG.md",
)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp", ".heic"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".webm", ".m4v"}

FILE_STABILITY_POLL_INTERVAL = 1.0
FILE_STABILITY_POLLS_REQUIRED = 5

BLUR_LAPLACIAN_THRESHOLD = 100.0

GEMINI_IMAGE_MODEL = "gemini-2.5-flash"
GEMINI_FALLBACK_MODELS = (
    "gemini-2.5-flash",
    "gemini-2.0-flash",
)
GEMINI_API_KEY_ENV_VAR = "GEMINI_API_KEY"
GEMINI_CLASSIFICATION_TIMEOUT = 60
GEMINI_MAX_RETRIES_PER_MODEL = 3
GEMINI_RETRY_DELAY_SECONDS = 5
GEMINI_BASE_CATEGORIES = (
    "people",
    "portrait",
    "wildlife",
    "pet",
    "landscape",
    "nature",
    "cityscape",
    "architecture",
    "food",
    "product",
    "document",
    "screenshot",
    "vehicle",
    "sports",
    "art",
    "indoor",
    "event",
    "travel",
    "abstract",
    "other",
)
DEFAULT_IMAGE_CATEGORY = "other"

JOB_DISPATCH_POLL_INTERVAL = 1.0
ENABLE_FOLDER_PROCESSOR = _bool_from_env("ENABLE_FOLDER_PROCESSOR", True)
FOLDER_PROCESSOR_POLL_INTERVAL = float(os.getenv("FOLDER_PROCESSOR_POLL_INTERVAL", "5.0"))

PIPELINE_IMAGE = "image_pipeline"
PIPELINE_VIDEO = "video_pipeline"
PIPELINE_UNKNOWN = "unknown"

QUARANTINE_DIR = ROOT / "temp" / "quarantine"

WHISPER_MODEL_SIZE = "base"
MAX_HIGHLIGHTS = 5
MIN_HIGHLIGHT_GAP_SEC = 15
CLIP_PRE_BUFFER_SEC = 5
CLIP_POST_BUFFER_SEC = 10
BURN_SUBTITLES = _bool_from_env("BURN_SUBTITLES", False)
TRIM_SILENCE = _bool_from_env("TRIM_SILENCE", False)
GEMINI_RERANK_CLIPS = True
BUILD_HIGHLIGHT_REEL = True
MAX_REEL_CLIPS = 5
FRAME_SAMPLE_INTERVAL_SEC = 30

VIDEO_GENRES = (
    "fps",
    "battle_royale",
    "moba",
    "rpg",
    "survival",
    "sandbox",
    "sports",
    "racing",
    "strategy",
    "fighting",
    "puzzle",
    "unknown",
)

STATUS_NOT_IMPLEMENTED = "NOT_IMPLEMENTED"

CLIP_TRIGGERS_CONFIG_PATH = ROOT / "config" / "clip_triggers.json"


def _load_clip_triggers():
    if not CLIP_TRIGGERS_CONFIG_PATH.exists():
        return {"enabled": False, "triggers": []}
    try:
        data = json.loads(CLIP_TRIGGERS_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"enabled": False, "triggers": []}
    if not isinstance(data, dict):
        return {"enabled": False, "triggers": []}
    enabled = bool(data.get("enabled", False))
    triggers = data.get("triggers", [])
    if not isinstance(triggers, list):
        triggers = []
    return {"enabled": enabled, "triggers": triggers}


CLIP_TRIGGERS = _load_clip_triggers()

# -------------------------------
# CAPTION PIPELINE
# -------------------------------
ENABLE_CAPTION_PIPELINE = True
CAPTION_STYLE = "highlight"  # highlight | word_by_word | block
CAPTION_FONT = "Arial"
CAPTION_FONT_SIZE = 18
CAPTION_COLOR = "&H00FFFFFF"
CAPTION_HIGHLIGHT_COLOR = "&H0000FFFF"
CAPTION_POSITION = "bottom"  # bottom | center | top
CAPTION_MAX_WORDS_PER_LINE = 4
CAPTION_OUTLINE = True
CAPTION_SHADOW = True
CAPTION_CRF = 18

"""
MediaScribe Python Service
FastAPI bridge over the embedded OpenClaw pipeline modules.
"""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR.parent / ".env", override=False)
load_dotenv(BASE_DIR / ".env", override=False)

from config.logger import get_logger
from config.path_resolver import PathResolver
from config.settings import BLUR_LAPLACIAN_THRESHOLD, GEMINI_API_KEY_ENV_VAR, MEMORY_LOG_PATH
from orchestrator import router
from orchestrator.database import (
    STATUS_DONE,
    STATUS_PENDING,
    STATUS_UNKNOWN,
    get_job_by_id,
    get_job_by_source,
    init_db,
    insert_job,
    job_exists,
    list_jobs as db_list_jobs,
    update_job_analysis,
    update_job_status,
)
from orchestrator import folder_processor
from pipelines.image_pipeline import pipeline as image_pipeline
from pipelines.video_pipeline import pipeline as video_pipeline

log = get_logger(__name__)

app = FastAPI(
    title="MediaScribe Python Service",
    description="FastAPI bridge over the OpenClaw-powered MediaScribe pipelines.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class FileRequest(BaseModel):
    file_path: str


class ImageResult(BaseModel):
    job_id: int
    file: str
    type: str = "image"
    category: str
    tags: list[str]
    summary: str
    blur_score: float | None
    is_blurry: bool
    classifier: str
    output_path: str | None = None


class VideoResult(BaseModel):
    job_id: int
    file: str
    type: str = "video"
    transcript: str
    summary: str
    subtitle_path: str | None
    duration_seconds: float | None
    output_path: str | None = None


@app.on_event("startup")
def startup() -> None:
    init_db()
    folder_processor.start()
    log.info("MediaScribe service ready")


@app.on_event("shutdown")
def shutdown() -> None:
    folder_processor.stop()


def _job_to_dict(row) -> dict[str, Any]:
    return dict(row) if row is not None else {}


def _parse_tags(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return [str(item) for item in data]
    except json.JSONDecodeError:
        return [part.strip() for part in raw.split(",") if part.strip()]
    return []


def _append_memory(filename: str, media_type: str, category: str, summary: str) -> None:
    MEMORY_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    snippet = " ".join((summary or "").split())
    if len(snippet) > 50:
        snippet = f"{snippet[:47].rstrip()}..."
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] | {filename} | {media_type} | {category} | {snippet}\n"
    with MEMORY_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(line)


def _ensure_file_exists(file_path: Path) -> None:
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    if not file_path.is_file():
        raise HTTPException(status_code=400, detail=f"Path is not a file: {file_path}")


def _quarantine_unknown(file_path: Path) -> None:
    quarantine_path = PathResolver.quarantine(file_path)
    if not quarantine_path.exists():
        shutil.copy2(file_path, quarantine_path)
    if not job_exists(file_path):
        job_id = insert_job(file_path, router.TYPE_UNKNOWN, "unknown", status=STATUS_UNKNOWN)
        if job_id:
            update_job_status(job_id, STATUS_UNKNOWN, output_path=quarantine_path)


def _existing_image_response(row) -> ImageResult:
    category = row["ai_category"] or "other"
    blur_score = row["blur_score"]
    return ImageResult(
        job_id=int(row["id"]),
        file=row["filename"],
        category=category,
        tags=_parse_tags(row["ai_tags"]),
        summary=row["ai_summary"] or "",
        blur_score=blur_score,
        is_blurry=category == "blurry" or (blur_score is not None and float(blur_score) < BLUR_LAPLACIAN_THRESHOLD),
        classifier=row["classifier"] or "unknown",
        output_path=row["output_path"],
    )


def _existing_video_response(row) -> VideoResult:
    return VideoResult(
        job_id=int(row["id"]),
        file=row["filename"],
        transcript=row["transcript"] or "",
        summary=row["ai_summary"] or "",
        subtitle_path=row["srt_path"],
        duration_seconds=row["video_duration"],
        output_path=row["output_path"],
    )


def _run_image_job(file_path: Path) -> ImageResult:
    existing = get_job_by_source(file_path)
    if existing is not None:
        if existing["detected_type"] == router.TYPE_UNKNOWN:
            raise HTTPException(
                status_code=400,
                detail="Unsupported file type. Supported image types are jpg, jpeg, png, webp, bmp, tiff, tif, and heic.",
            )
        return _existing_image_response(existing)

    detected_type, pipeline_name = router.classify(file_path)
    if detected_type == router.TYPE_UNKNOWN:
        _quarantine_unknown(file_path)
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Supported image types are jpg, jpeg, png, webp, bmp, tiff, tif, and heic.",
        )
    if pipeline_name != "image_pipeline":
        raise HTTPException(status_code=400, detail=f"File is not an image: {file_path.name}")

    job_id = insert_job(file_path, detected_type, pipeline_name, status=STATUS_PENDING)
    if job_id is None:
        existing = get_job_by_source(file_path)
        if existing is None:
            raise HTTPException(status_code=500, detail="Could not create or recover the image job.")
        return _existing_image_response(existing)

    job = get_job_by_id(job_id)
    image_pipeline.process_job(job)
    updated = get_job_by_id(job_id)
    if updated is None:
        raise HTTPException(status_code=500, detail="Image job completed but could not be reloaded from the database.")
    if updated["status"] != STATUS_DONE:
        raise HTTPException(status_code=500, detail=updated["error_message"] or "Image processing failed.")

    response = _existing_image_response(updated)
    _append_memory(response.file, response.type, response.category, response.summary)
    return response


def _run_video_job(file_path: Path) -> VideoResult:
    existing = get_job_by_source(file_path)
    if existing is not None:
        if existing["detected_type"] == router.TYPE_UNKNOWN:
            raise HTTPException(
                status_code=400,
                detail="Unsupported file type. Supported video types are mp4, mov, avi, mkv, wmv, flv, webm, and m4v.",
            )
        return _existing_video_response(existing)

    detected_type, pipeline_name = router.classify(file_path)
    if detected_type == router.TYPE_UNKNOWN:
        _quarantine_unknown(file_path)
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Supported video types are mp4, mov, avi, mkv, wmv, flv, webm, and m4v.",
        )
    if pipeline_name != "video_pipeline":
        raise HTTPException(status_code=400, detail=f"File is not a video: {file_path.name}")

    job_id = insert_job(file_path, detected_type, pipeline_name, status=STATUS_PENDING)
    if job_id is None:
        existing = get_job_by_source(file_path)
        if existing is None:
            raise HTTPException(status_code=500, detail="Could not create or recover the video job.")
        return _existing_video_response(existing)

    try:
        result = video_pipeline.process_api_job(job_id, file_path)
    except Exception as exc:
        updated = get_job_by_id(job_id)
        raise HTTPException(status_code=500, detail=(updated["error_message"] if updated else str(exc)) or str(exc)) from exc

    update_job_analysis(
        job_id,
        ai_category="video",
        ai_tags=json.dumps(["transcription", "subtitle_generation"]),
        ai_summary=result["summary"],
        classifier="whisper+srt",
    )

    updated = get_job_by_id(job_id)
    if updated is None:
        raise HTTPException(status_code=500, detail="Video job completed but could not be reloaded from the database.")
    if updated["status"] != STATUS_DONE:
        raise HTTPException(status_code=500, detail=updated["error_message"] or "Video processing failed.")

    response = _existing_video_response(updated)
    _append_memory(response.file, response.type, "video", response.summary)
    return response


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "service": "mediascribe-python",
        "gemini_configured": bool(os.environ.get(GEMINI_API_KEY_ENV_VAR)),
        "memory_log": str(MEMORY_LOG_PATH),
    }


@app.post("/process/image", response_model=ImageResult)
def process_image(req: FileRequest) -> ImageResult:
    file_path = Path(req.file_path).expanduser()
    _ensure_file_exists(file_path)
    return _run_image_job(file_path)


@app.post("/process/video", response_model=VideoResult)
def process_video(req: FileRequest) -> VideoResult:
    file_path = Path(req.file_path).expanduser()
    _ensure_file_exists(file_path)
    return _run_video_job(file_path)


@app.get("/jobs")
def get_jobs(
    limit: int = Query(default=50, ge=1, le=500),
    file_type: str | None = None,
    category: str | None = None,
) -> list[dict[str, Any]]:
    detected_type = file_type.upper() if file_type else None
    rows = db_list_jobs(limit=limit, detected_type=detected_type, ai_category=category)
    return [_job_to_dict(row) for row in rows]

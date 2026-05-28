from __future__ import annotations

import os
import re
import secrets
import socket
import sqlite3
import sys
import mimetypes
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode, urlparse

import httpx
from fastapi import BackgroundTasks, Depends, FastAPI, Form, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from jose import JWTError, jwt
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import (
    DB_PATH,
    FREE_TIER_JOBS_PER_WEEK,
    HTTPS_ONLY,
    MAX_UPLOAD_MB_FREE,
    MAX_UPLOAD_MB_PRO,
    PIPELINE_IMAGE,
    PIPELINE_VIDEO,
    STUCK_JOB_TIMEOUT_MINUTES,
)
from orchestrator.database import (
    STATUS_DELETED,
    STATUS_PENDING,
    STATUS_PROCESSING,
    add_watcher,
    count_jobs_for_dashboard,
    count_user_jobs_this_week,
    delete_watcher,
    expire_stuck_jobs,
    get_setting,
    get_job_by_id,
    get_job_by_source,
    get_user_notification_settings,
    get_user_tier,
    insert_job,
    init_db,
    list_settings,
    list_jobs_for_dashboard,
    list_watchers,
    recover_interrupted_jobs,
    retry_job,
    set_telegram_chat_id,
    set_user_tier,
    set_watcher_enabled,
    soft_delete_job,
    upsert_setting,
    upsert_user,
    update_job_meta,
    update_job_status,
    update_job_video_fields,
)
from orchestrator.router import TYPE_IMAGE, TYPE_VIDEO
from pipelines.image_pipeline import process_job as process_image_job
from pipelines.video_pipeline.pipeline import process_api_job

VERSION = "1.0.1-preview-stream"
COOKIE_NAME = "lobcut_token"
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_DAYS = 7
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
GOOGLE_SCOPES = "openid email profile"


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required for LobCut API startup.")
    return value


AUTH_MODE = os.environ.get("LOBCUT_AUTH_MODE", "").strip().lower()
if not AUTH_MODE:
    AUTH_MODE = "google" if os.environ.get("GOOGLE_CLIENT_ID") and os.environ.get("GOOGLE_CLIENT_SECRET") else "local"

JWT_SECRET = os.environ.get("JWT_SECRET", "").strip()
if AUTH_MODE == "google":
    JWT_SECRET = _required_env("JWT_SECRET")
    if not re.fullmatch(r"[0-9a-fA-F]{32,}", JWT_SECRET):
        raise RuntimeError("JWT_SECRET must be at least 32 hex characters.")
else:
    JWT_SECRET = JWT_SECRET or "0" * 32

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "").strip()
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
if AUTH_MODE == "google":
    GOOGLE_CLIENT_ID = _required_env("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET = _required_env("GOOGLE_CLIENT_SECRET")
REDIRECT_URI = os.environ.get("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/callback")
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", "http://localhost:3000")
CORS_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("CORS_ALLOW_ORIGINS", "http://localhost:3000").split(",")
    if origin.strip()
]

app = FastAPI(title="LobCut API", version=VERSION)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class JobOut(BaseModel):
    id: int
    user_id: str
    filename: str
    source_path: str
    detected_type: Optional[str] = None
    pipeline: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    ai_category: Optional[str] = None
    ai_tags: Optional[str] = None
    ai_summary: Optional[str] = None
    blur_score: Optional[float] = None
    output_path: Optional[str] = None
    srt_path: Optional[str] = None
    transcript: Optional[str] = None
    game_genre: Optional[str] = None
    game_title: Optional[str] = None
    video_duration: Optional[float] = None
    clip_paths: Optional[str] = None
    reel_path: Optional[str] = None
    highlight_timestamps: Optional[str] = None
    image_url: Optional[str] = None
    created_at: str
    updated_at: str


class WatcherIn(BaseModel):
    path: str = Field(min_length=1)
    media_type: Optional[str] = "auto"
    pipeline_override: Optional[str] = None
    enabled: Optional[bool] = True


class WatcherPatch(BaseModel):
    enabled: bool


class WatcherOut(BaseModel):
    id: int
    user_id: str
    path: str
    media_type: Optional[str] = "auto"
    pipeline_override: Optional[str] = None
    enabled: bool
    created_at: str
    updated_at: str


class TelegramLinkIn(BaseModel):
    chat_id: str = Field(min_length=1)


class TelegramSettingsOut(BaseModel):
    configured: bool
    linked: bool
    chat_id: Optional[str] = None


class TelegramTestOut(BaseModel):
    status: str


class SettingIn(BaseModel):
    key: str = Field(min_length=1)
    value: str = ""


class SettingOut(BaseModel):
    key: str
    value: Optional[str] = None


class TelegramDirectTestOut(BaseModel):
    success: bool
    error: Optional[str] = None


class ProcessIn(BaseModel):
    file_path: str = Field(min_length=1)


class JobMetaIn(BaseModel):
    game_genre: Optional[str] = None
    game_title: Optional[str] = None
    ai_tags: Optional[str] = None


class CustomClipRange(BaseModel):
    start: float
    end: float


class RebuildReelIn(BaseModel):
    clip_paths: list[str] = []
    custom_ranges: list[CustomClipRange] = []


def _row_to_dict(row) -> dict:
    return dict(row) if row is not None else {}


def _is_image_job(data: dict) -> bool:
    detected_type = str(data.get("detected_type") or "").upper()
    suffix = Path(str(data.get("filename") or "")).suffix.lower()
    return detected_type == "IMAGE" or suffix in {
        ".jpg",
        ".jpeg",
        ".png",
        ".bmp",
        ".tiff",
        ".tif",
        ".webp",
        ".heic",
    }


def _image_media_type(path: Path) -> str:
    mime_type, _ = mimetypes.guess_type(str(path))
    if mime_type:
        return mime_type
    return {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".jfif": "image/jpeg",
        ".png": "image/png",
        ".gif": "image/gif",
        ".bmp": "image/bmp",
        ".tif": "image/tiff",
        ".tiff": "image/tiff",
        ".webp": "image/webp",
        ".avif": "image/avif",
        ".heic": "image/heic",
    }.get(path.suffix.lower(), "application/octet-stream")


def _stream_image(path: Path) -> StreamingResponse:
    def iterator():
        with path.open("rb") as file:
            while chunk := file.read(1024 * 1024):
                yield chunk

    return StreamingResponse(
        iterator(),
        media_type=_image_media_type(path),
        headers={"Content-Disposition": f'inline; filename="{path.name}"'},
    )


def _job_out(row) -> JobOut:
    data = _row_to_dict(row)
    if _is_image_job(data):
        data["image_url"] = f"/jobs/{data['id']}/image"
    return JobOut(**data)


def _resolve_media_path(raw_path: str) -> Path:
    path_text = str(raw_path or "")

    # Remap Docker-style /app/ paths to the local ROOT
    if path_text.startswith("/app/python-service/"):
        path = ROOT / path_text.removeprefix("/app/python-service/")
    elif path_text.startswith("/app/"):
        path = ROOT / path_text.removeprefix("/app/")
    else:
        path = Path(path_text)

    resolved = path.resolve()

    # Primary check: does the file exist under this app's own media directories?
    own_roots = [
        (ROOT / "input").resolve(),
        (ROOT / "output").resolve(),
        (ROOT / "temp").resolve(),
    ]
    in_own_roots = any(resolved == r or r in resolved.parents for r in own_roots)

    # Fallback: if the recorded path points to a different LobCut installation
    # (e.g. the app was moved/renamed), try remapping the subtree under our ROOT.
    if not in_own_roots:
        for segment in ("input", "output", "temp"):
            try:
                # Find the first occurrence of this segment in the path parts
                parts = resolved.parts
                idx = next(i for i, p in enumerate(parts) if p == segment)
                remapped = ROOT / segment / Path(*parts[idx + 1:])
                if remapped.exists() and remapped.is_file():
                    return remapped.resolve()
            except StopIteration:
                continue

    # For this local desktop app we allow any absolute path that resolves to an
    # existing file — the strict root-containment check is not needed locally.
    if not resolved.exists() or not resolved.is_file():
        raise HTTPException(status_code=404, detail="File not found.")
    return resolved


def _first_existing_media_path(*raw_paths: Optional[str]) -> Path:
    last_error: HTTPException | None = None
    for raw_path in raw_paths:
        if not raw_path:
            continue
        try:
            return _resolve_media_path(raw_path)
        except HTTPException as exc:
            last_error = exc
    if last_error is not None:
        raise last_error
    raise HTTPException(status_code=404, detail="File not found.")


def _delete_job_row(job_id: int, user_id: str) -> bool:
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.execute(
            """
            DELETE FROM jobs
            WHERE id = ?
              AND (user_id = ? OR user_id = 'local')
            """,
            (job_id, user_id),
        )
        conn.commit()
    return cur.rowcount > 0


def _watcher_out(row) -> WatcherOut:
    data = _row_to_dict(row)
    data["enabled"] = bool(data.get("enabled", 1))
    return WatcherOut(**data)


def _create_token(user: dict) -> str:
    expires = datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRY_DAYS)
    payload = {
        "sub": user["sub"],
        "email": user.get("email"),
        "name": user.get("name"),
        "picture": user.get("picture"),
        "exp": expires,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


async def get_current_user(request: Request) -> dict:
    if AUTH_MODE == "local":
        return {"sub": "local", "email": None, "name": "Local", "picture": None}
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required.")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid authentication token.") from exc
    return {
        "sub": payload["sub"],
        "email": payload.get("email"),
        "name": payload.get("name"),
        "picture": payload.get("picture"),
    }


async def get_optional_user(request: Request) -> dict:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return {"sub": "local", "email": None, "name": "Local", "picture": None}
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        return {
            "sub": payload["sub"],
            "email": payload.get("email"),
            "name": payload.get("name"),
            "picture": payload.get("picture"),
        }
    except JWTError:
        return {"sub": "local", "email": None, "name": "Local", "picture": None}


@app.on_event("startup")
def startup() -> None:
    init_db()
    recovered = recover_interrupted_jobs()
    if recovered:
        log.info("[STARTUP] Re-queued %d interrupted job(s)", recovered)
    expired = expire_stuck_jobs(max_age_minutes=STUCK_JOB_TIMEOUT_MINUTES)
    if expired:
        log.info("[STARTUP] Expired %d stuck job(s) older than %dmin", expired, STUCK_JOB_TIMEOUT_MINUTES)


@app.get("/health")
def health_check() -> dict:
    db_ok = True
    try:
        import sqlite3 as _sqlite3
        with _sqlite3.connect(DB_PATH) as _conn:
            _conn.execute("SELECT 1")
    except Exception:
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "db": "ok" if db_ok else "error",
        "version": VERSION,
    }


@app.get("/health")
def health() -> dict[str, str]:
    try:
        init_db()
        db_status = "ok" if DB_PATH.exists() else "missing"
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Database unavailable: {exc}") from exc
    return {"status": "ok", "db": db_status, "version": VERSION}


@app.get("/auth/login")
def auth_login() -> Response:
    if AUTH_MODE == "local":
        user = {"sub": "local", "email": None, "name": "Local", "picture": None}
        response = RedirectResponse(DASHBOARD_URL)
        response.set_cookie(
            COOKIE_NAME,
            _create_token(user),
            httponly=True,
            secure=HTTPS_ONLY,
            samesite="lax",
            max_age=JWT_EXPIRY_DAYS * 24 * 60 * 60,
        )
        return response

    state = secrets.token_urlsafe(24)
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": GOOGLE_SCOPES,
        "access_type": "offline",
        "prompt": "select_account",
        "state": state,
    }
    response = RedirectResponse(f"{GOOGLE_AUTH_URL}?{urlencode(params)}")
    response.set_cookie("lobcut_oauth_state", state, httponly=True, samesite="lax", max_age=600)
    return response


@app.get("/auth/callback")
async def auth_callback(request: Request, code: str, state: str) -> Response:
    expected_state = request.cookies.get("lobcut_oauth_state")
    if not expected_state or not secrets.compare_digest(expected_state, state):
        raise HTTPException(status_code=400, detail="Invalid OAuth state.")

    async with httpx.AsyncClient(timeout=15) as client:
        token_response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": REDIRECT_URI,
            },
        )
        token_response.raise_for_status()
        access_token = token_response.json().get("access_token")
        if not access_token:
            raise HTTPException(status_code=400, detail="Google did not return an access token.")

        user_response = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )
        user_response.raise_for_status()
        google_user = user_response.json()

    user = {
        "sub": google_user["sub"],
        "email": google_user.get("email"),
        "name": google_user.get("name"),
        "picture": google_user.get("picture"),
    }
    upsert_user(**user)

    response = RedirectResponse(DASHBOARD_URL)
    response.set_cookie(
        COOKIE_NAME,
        _create_token(user),
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=JWT_EXPIRY_DAYS * 24 * 60 * 60,
    )
    response.delete_cookie("lobcut_oauth_state")
    return response


@app.get("/auth/me")
async def auth_me(user: dict = Depends(get_optional_user)) -> dict:
    return user


@app.get("/auth/me/usage")
def get_usage(user: dict = Depends(get_optional_user)) -> dict:
    user_id = user["sub"]
    tier = get_user_tier(user_id)
    jobs_this_week = count_user_jobs_this_week(user_id)
    limit = None if tier == "pro" else FREE_TIER_JOBS_PER_WEEK
    return {
        "tier": tier,
        "jobs_this_week": jobs_this_week,
        "jobs_limit": limit,
        "jobs_remaining": max(0, limit - jobs_this_week) if limit is not None else None,
        "max_upload_mb": MAX_UPLOAD_MB_PRO if tier == "pro" else MAX_UPLOAD_MB_FREE,
    }


@app.post("/auth/upgrade")
def upgrade_tier(
    user: dict = Depends(get_current_user),
    gemini_api_key: str = "",
) -> dict:
    set_user_tier(user["sub"], "pro")
    return {"tier": "pro", "status": "upgraded"}


def _validate_process_source(file_path: str) -> Path:
    source = Path(file_path).expanduser().resolve()
    if not source.exists() or not source.is_file():
        raise HTTPException(status_code=404, detail="File not found.")
    return source


def _tags_as_list(value: Optional[str]) -> list[str]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return [str(item) for item in parsed]
    except Exception:
        pass
    return [item.strip() for item in value.split(",") if item.strip()]


@app.post("/process/image")
def process_image(body: ProcessIn, user: dict = Depends(get_optional_user)) -> dict:
    source = _validate_process_source(body.file_path)
    job_id = insert_job(source, TYPE_IMAGE, PIPELINE_IMAGE, user_id=user["sub"])
    if job_id is None:
        row = get_job_by_source(source, user_id=user["sub"]) or get_job_by_source(source, user_id="local")
        if row is None:
            raise HTTPException(status_code=409, detail="File is already queued or processed.")
        job_id = int(row["id"])
    row = get_job_by_id(job_id)
    if row is None:
        raise HTTPException(status_code=500, detail="Job was created but could not be loaded.")

    update_job_status(job_id, STATUS_PROCESSING)
    process_image_job(row)
    updated = get_job_by_id(job_id)
    if updated is None:
        raise HTTPException(status_code=500, detail="Job disappeared after processing.")

    return {
        "job_id": str(job_id),
        "file": updated["filename"],
        "type": "image",
        "category": updated["ai_category"],
        "tags": _tags_as_list(updated["ai_tags"]),
        "summary": updated["ai_summary"],
        "blur_score": updated["blur_score"],
        "is_blurry": updated["ai_category"] == "blurry",
        "classifier": updated["classifier"],
        "status": updated["status"],
    }


@app.post("/process/video")
def process_video(body: ProcessIn, user: dict = Depends(get_optional_user)) -> dict:
    source = _validate_process_source(body.file_path)
    job_id = insert_job(source, TYPE_VIDEO, PIPELINE_VIDEO, user_id=user["sub"])
    if job_id is None:
        row = get_job_by_source(source, user_id=user["sub"]) or get_job_by_source(source, user_id="local")
        if row is None:
            raise HTTPException(status_code=409, detail="File is already queued or processed.")
        job_id = int(row["id"])

    result = process_api_job(job_id, str(source))
    return {
        "job_id": str(job_id),
        "file": source.name,
        "type": "video",
        "transcript": result.get("transcript", ""),
        "summary": result.get("summary", ""),
        "subtitle_path": result.get("subtitle_path"),
        "duration_seconds": result.get("duration_seconds", 0),
        "output_path": result.get("output_path"),
    }


@app.post("/auth/logout")
def auth_logout() -> Response:
    response = JSONResponse({"status": "ok"})
    response.delete_cookie(COOKIE_NAME)
    return response


@app.post("/auth/telegram/link")
def link_telegram(
    body: TelegramLinkIn,
    user: dict = Depends(get_current_user),
) -> dict[str, str]:
    set_telegram_chat_id(user["sub"], body.chat_id)
    upsert_setting("telegram_chat_id", body.chat_id)
    return {"status": "ok"}


@app.get("/auth/telegram/settings", response_model=TelegramSettingsOut)
def telegram_settings(user: dict = Depends(get_current_user)) -> TelegramSettingsOut:
    settings = get_user_notification_settings(user["sub"])
    chat_id = get_setting("telegram_chat_id") or settings.get("telegram_chat_id")
    return TelegramSettingsOut(
        configured=bool(os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()),
        linked=bool(chat_id),
        chat_id=chat_id,
    )


@app.post("/auth/telegram/test", response_model=TelegramTestOut)
async def test_telegram(user: dict = Depends(get_current_user)) -> TelegramTestOut:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="TELEGRAM_BOT_TOKEN is not configured.")

    settings = get_user_notification_settings(user["sub"])
    chat_id = settings.get("telegram_chat_id")
    if not chat_id:
        raise HTTPException(status_code=400, detail="Link your Telegram chat ID first.")

    message = "🧪 LobCut test notification is working!"
    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": message},
        )

    if not response.is_success:
        raise HTTPException(status_code=502, detail=response.text)
    return TelegramTestOut(status="sent")


@app.get("/openclaw/status")
async def openclaw_status(user: dict = Depends(get_current_user)) -> dict:
    gateway_url = os.environ.get("OPENCLAW_GATEWAY_URL", "http://localhost:18789")
    public_url = os.environ.get("OPENCLAW_PUBLIC_URL", "http://localhost:18789")
    service_url = os.environ.get("OPENCLAW_SERVICE_URL", "http://localhost:8000")
    config_path = ROOT / "openclaw-workspace" / "openclaw.json"
    memory_path = ROOT / "openclaw-workspace" / "memory" / "MEMORY_LOG.md"

    gateway = {"url": gateway_url, "status": "unknown"}
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            response = await client.get(gateway_url)
        gateway["status"] = "reachable" if response.status_code < 500 else f"http_{response.status_code}"
    except Exception as exc:
        parsed = urlparse(gateway_url)
        host = parsed.hostname
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        try:
            if not host:
                raise OSError("OpenClaw gateway URL has no host.")
            with socket.create_connection((host, port), timeout=3):
                pass
            gateway["status"] = "reachable"
            gateway["note"] = "Gateway accepted a TCP connection but did not return a plain HTTP response."
        except OSError:
            gateway["status"] = "unreachable"
            gateway["error"] = str(exc)

    config = {}
    if config_path.exists():
        try:
            import json

            config = json.loads(config_path.read_text(encoding="utf-8"))
        except Exception as exc:
            config = {"error": str(exc)}

    return {
        "gateway": {**gateway, "public_url": public_url},
        "python_service": {"url": service_url},
        "config_path": str(config_path),
        "memory_log_path": str(memory_path),
        "memory_log_exists": memory_path.exists(),
        "config": config,
    }


@app.get("/jobs", response_model=list[JobOut])
def get_jobs(
    limit: int = 50,
    offset: int = 0,
    user: dict = Depends(get_optional_user),
) -> list[JobOut]:
    return [
        _job_out(row)
        for row in list_jobs_for_dashboard(user_id=user["sub"], limit=min(limit, 200), offset=offset)
    ]


@app.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: int, user: dict = Depends(get_optional_user)) -> JobOut:
    row = get_job_by_id(job_id, user_id=user["sub"])
    if row is None or row["status"] == STATUS_DELETED:
        raise HTTPException(status_code=404, detail="Job not found.")
    return _job_out(row)


@app.get("/jobs/{job_id}/image")
def get_job_image(job_id: int, user: dict = Depends(get_optional_user)) -> StreamingResponse:
    row = get_job_by_id(job_id, user_id=user["sub"]) or get_job_by_id(job_id, user_id="local")
    if row is None or row["status"] == STATUS_DELETED:
        raise HTTPException(status_code=404, detail="Job not found.")

    data = _row_to_dict(row)
    if not _is_image_job(data):
        raise HTTPException(status_code=404, detail="Job is not an image.")

    path = _first_existing_media_path(data.get("output_path"), data.get("source_path"))
    return _stream_image(path)


@app.get("/jobs/{job_id}/preview")
def get_job_preview(job_id: int, user: dict = Depends(get_optional_user)) -> StreamingResponse:
    row = get_job_by_id(job_id, user_id=user["sub"]) or get_job_by_id(job_id, user_id="local")
    if row is None or row["status"] == STATUS_DELETED:
        raise HTTPException(status_code=404, detail="Job not found.")

    data = _row_to_dict(row)
    if not _is_image_job(data):
        raise HTTPException(status_code=404, detail="Job is not an image.")

    path = _first_existing_media_path(data.get("source_path"), data.get("output_path"))
    return _stream_image(path)


@app.post("/jobs/retry/{job_id}")
def retry_existing_job(
    job_id: int,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_optional_user),
) -> dict[str, str]:
    if not retry_job(job_id, user["sub"]):
        raise HTTPException(status_code=404, detail="Job not found.")
    row = get_job_by_id(job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    source = str(row["source_path"])
    detected = str(row["detected_type"] or "").upper()
    if detected == "IMAGE":
        background_tasks.add_task(_bg_image, job_id, row)
    else:
        pipeline = str(row["pipeline"] or "")
        action = "reel" if pipeline == PIPELINE_VIDEO else "subtitles"
        background_tasks.add_task(_bg_video, job_id, source, action)
    return {"status": STATUS_PENDING}


@app.delete("/jobs/{job_id}")
def delete_existing_job(job_id: int, user: dict = Depends(get_optional_user)) -> dict[str, bool | int]:
    if not soft_delete_job(job_id, user["sub"]):
        raise HTTPException(status_code=404, detail="Job not found.")
    return {"deleted": True, "job_id": job_id}


@app.get("/watchers", response_model=list[WatcherOut])
def get_watchers(user: dict = Depends(get_optional_user)) -> list[WatcherOut]:
    return [_watcher_out(row) for row in list_watchers(user["sub"])]


@app.post("/watchers", response_model=WatcherOut)
def create_watcher(body: WatcherIn, user: dict = Depends(get_optional_user)) -> WatcherOut:
    watcher_id = add_watcher(
        user["sub"],
        Path(body.path).expanduser(),
        media_type=body.media_type or "auto",
        pipeline_override=body.pipeline_override,
        enabled=True if body.enabled is None else body.enabled,
    )
    row = next((item for item in list_watchers(user["sub"]) if int(item["id"]) == watcher_id), None)
    if row is None:
        raise HTTPException(status_code=500, detail="Watcher was saved but could not be loaded.")
    return _watcher_out(row)


@app.patch("/watchers/{watcher_id}", response_model=WatcherOut)
def update_watcher(
    watcher_id: int,
    body: WatcherPatch,
    user: dict = Depends(get_optional_user),
) -> WatcherOut:
    if not set_watcher_enabled(watcher_id, user["sub"], body.enabled):
        raise HTTPException(status_code=404, detail="Watcher not found.")
    row = next((item for item in list_watchers(user["sub"]) if int(item["id"]) == watcher_id), None)
    if row is None:
        raise HTTPException(status_code=404, detail="Watcher not found.")
    return _watcher_out(row)


@app.delete("/watchers/{watcher_id}")
def remove_watcher(watcher_id: int, user: dict = Depends(get_optional_user)) -> dict[str, str]:
    if not delete_watcher(watcher_id, user["sub"]):
        raise HTTPException(status_code=404, detail="Watcher not found.")
    return {"status": "deleted"}


@app.get("/jobs/{job_id}/download")
def download_job_output(job_id: int, user: dict = Depends(get_optional_user)):
    row = get_job_by_id(job_id, user_id=user["sub"]) or get_job_by_id(job_id, user_id="local")
    if row is None or row["status"] == STATUS_DELETED:
        raise HTTPException(status_code=404, detail="Job not found.")
    data = _row_to_dict(row)
    raw_path = data.get("output_path") or data.get("source_path")
    path = _resolve_media_path(raw_path)
    return FileResponse(path, filename=path.name, media_type="application/octet-stream")


@app.get("/jobs/{job_id}/video")
def stream_job_video(job_id: int, user: dict = Depends(get_optional_user)):
    row = get_job_by_id(job_id, user_id=user["sub"]) or get_job_by_id(job_id, user_id="local")
    if row is None or row["status"] == STATUS_DELETED:
        raise HTTPException(status_code=404, detail="Job not found.")
    data = _row_to_dict(row)
    _VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".webm", ".m4v"}
    for raw in (data.get("source_path"), data.get("output_path")):
        if not raw:
            continue
        try:
            path = _resolve_media_path(raw)
            if path.suffix.lower() in _VIDEO_EXTS:
                media_type = "video/webm" if path.suffix.lower() == ".webm" else "video/mp4"
                return FileResponse(str(path), media_type=media_type)
        except HTTPException:
            continue
    raise HTTPException(status_code=404, detail="Video file not found.")


@app.patch("/jobs/{job_id}/meta", response_model=JobOut)
def update_job_meta_endpoint(
    job_id: int,
    body: JobMetaIn,
    user: dict = Depends(get_optional_user),
) -> JobOut:
    if not update_job_meta(job_id, user["sub"], game_genre=body.game_genre, game_title=body.game_title, ai_tags=body.ai_tags):
        raise HTTPException(status_code=404, detail="Job not found.")
    row = get_job_by_id(job_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return _job_out(row)


@app.post("/jobs/{job_id}/rebuild-reel")
async def rebuild_reel_endpoint(
    job_id: int,
    body: RebuildReelIn,
    background_tasks: BackgroundTasks,
    user: dict = Depends(get_optional_user),
) -> dict:
    row = get_job_by_id(job_id, user_id=user["sub"]) or get_job_by_id(job_id, user_id="local")
    if row is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    if not body.clip_paths and not body.custom_ranges:
        raise HTTPException(status_code=400, detail="clip_paths or custom_ranges must not be empty.")
    update_job_status(job_id, STATUS_PROCESSING)
    custom_ranges_data = [{"start": cr.start, "end": cr.end} for cr in body.custom_ranges]
    background_tasks.add_task(_bg_rebuild_reel, job_id, body.clip_paths, custom_ranges_data)
    return {"status": "rebuilding", "job_id": job_id}


CAPTION_OVERRIDES_PATH = Path(DB_PATH).parent / "caption_overrides.json"


@app.get("/settings")
def get_settings() -> dict[str, Optional[str]]:
    return list_settings()


@app.post("/settings", response_model=SettingOut)
def save_setting(body: SettingIn) -> SettingOut:
    upsert_setting(body.key, body.value)
    return SettingOut(key=body.key, value=body.value)


@app.post("/telegram/test", response_model=TelegramDirectTestOut)
async def test_telegram_direct() -> TelegramDirectTestOut:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        return TelegramDirectTestOut(success=False, error="TELEGRAM_BOT_TOKEN is not configured.")

    chat_id = get_setting("telegram_chat_id") or os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not chat_id:
        return TelegramDirectTestOut(success=False, error="Telegram Chat ID is not configured.")

    async with httpx.AsyncClient(timeout=10) as client:
        response = await client.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": "🧪 LobCut test notification is working!"},
        )

    if not response.is_success:
        return TelegramDirectTestOut(success=False, error=response.text)
    return TelegramDirectTestOut(success=True)


@app.get("/settings/captions")
def get_caption_settings(user: dict = Depends(get_current_user)) -> dict:
    defaults = {
        "font": "Arial",
        "font_size": 18,
        "color": "&H00FFFFFF",
        "highlight_color": "&H0000FFFF",
        "outline_color": "&H00000000",
        "outline_width": 3,
        "shadow": 1,
        "bold": True,
        "position": "bottom",
        "style": "highlight",
        "max_words_per_line": 4,
    }
    if CAPTION_OVERRIDES_PATH.exists():
        try:
            import json as _json

            overrides = _json.loads(CAPTION_OVERRIDES_PATH.read_text(encoding="utf-8"))
            defaults.update(overrides)
        except Exception:
            pass
    return defaults


class CaptionSettingsIn(BaseModel):
    font: Optional[str] = None
    font_size: Optional[int] = None
    color: Optional[str] = None
    highlight_color: Optional[str] = None
    outline_color: Optional[str] = None
    outline_width: Optional[float] = None
    shadow: Optional[float] = None
    bold: Optional[bool] = None
    position: Optional[str] = None
    style: Optional[str] = None
    max_words_per_line: Optional[int] = None


def _clean_caption_updates(updates: dict) -> dict:
    cleaned = dict(updates)
    if "font" in cleaned:
        allowed_fonts = {"Arial", "Arial Black", "Impact", "Verdana", "Tahoma", "Trebuchet MS", "Georgia"}
        if cleaned["font"] not in allowed_fonts:
            cleaned["font"] = "Arial"
    if "font_size" in cleaned:
        cleaned["font_size"] = min(72, max(12, int(cleaned["font_size"])))
    if "outline_width" in cleaned:
        cleaned["outline_width"] = min(8, max(0, float(cleaned["outline_width"])))
    if "shadow" in cleaned:
        cleaned["shadow"] = min(5, max(0, float(cleaned["shadow"])))
    if "max_words_per_line" in cleaned:
        cleaned["max_words_per_line"] = min(8, max(1, int(cleaned["max_words_per_line"])))
    if "position" in cleaned and cleaned["position"] not in {"top", "middle", "center", "bottom"}:
        cleaned["position"] = "bottom"
    if "position" in cleaned and cleaned["position"] == "center":
        cleaned["position"] = "middle"
    if "style" in cleaned and cleaned["style"] not in {"highlight", "word_by_word", "block"}:
        cleaned["style"] = "highlight"
    for key in ("color", "highlight_color", "outline_color"):
        value = cleaned.get(key)
        if isinstance(value, str) and not re.fullmatch(r"&H[0-9A-Fa-f]{8}", value):
            cleaned.pop(key, None)
    return cleaned


@app.put("/settings/captions")
def update_caption_settings(
    body: CaptionSettingsIn,
    user: dict = Depends(get_current_user),
) -> dict:
    import json as _json

    CAPTION_OVERRIDES_PATH.parent.mkdir(parents=True, exist_ok=True)
    existing = {}
    if CAPTION_OVERRIDES_PATH.exists():
        try:
            existing = _json.loads(CAPTION_OVERRIDES_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    updates = _clean_caption_updates(body.model_dump(exclude_none=True))
    existing.update(updates)
    CAPTION_OVERRIDES_PATH.write_text(_json.dumps(existing, indent=2), encoding="utf-8")
    return {"status": "ok"}


@app.get("/settings/{key}", response_model=SettingOut)
def get_setting_value(key: str) -> SettingOut:
    value = get_setting(key)
    if value is None:
        raise HTTPException(status_code=404, detail="Setting not found.")
    return SettingOut(key=key, value=value)


# ── Workstation upload endpoint ──────────────────────────────────────────────
_UPLOAD_DIR = ROOT / "temp" / "uploads"

_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp", ".heic"}
_VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".webm", ".m4v"}


def _bg_image(job_id: int, row) -> None:
    """Run image pipeline in the background after upload."""
    from pipelines.image_pipeline import process_job as _process_image
    try:
        update_job_status(job_id, STATUS_PROCESSING)
        _process_image(row)
    except Exception as exc:
        update_job_status(job_id, STATUS_FAILED, error_message=str(exc))


def _bg_video(job_id: int, source_path: str, action: str = "subtitles") -> None:
    """Run the appropriate video pipeline based on action.

    action:
      'subtitles' — transcribe + generate .srt (default, fast)
      'captions'  — transcribe + burn captions to full video using Settings
      'reel'      — transcribe + highlight-reel selection + burn captions
    """
    try:
        if action == "captions":
            _bg_burn_captions(job_id, source_path)
        elif action == "reel":
            from pipelines.video_pipeline.pipeline import run as _run_video
            _run_video(job_id, source_path)
        else:
            # default: subtitles only — transcribe + .srt, no burn
            from pipelines.video_pipeline.pipeline import process_api_job as _process_video
            _process_video(job_id, source_path)
    except Exception as exc:
        update_job_status(job_id, STATUS_FAILED, error_message=str(exc))


def _bg_burn_captions(job_id: int, source_path: str) -> None:
    """Transcribe video and burn captions (per user Settings) into the full video."""
    import shutil
    from pathlib import Path as _Path
    from pipelines.video_pipeline import ffmpeg_utils, subtitler, transcriber
    from pipelines.caption_pipeline import ass_builder, caption_burner
    from config.settings import WHISPER_MODEL_SIZE
    from orchestrator.database import (
        update_job_video_fields,
        TEMP_DIR,
        STATUS_PROCESSING,
        STATUS_DONE,
        STATUS_FAILED,
        PIPELINE_VIDEO,
    )
    from orchestrator.path_resolver import PathResolver

    source = _Path(source_path)
    temp_video = None
    temp_wav = None

    try:
        update_job_status(job_id, STATUS_PROCESSING)
        temp_video = PathResolver.temp_copy(source)
        shutil.copy2(str(source), str(temp_video))

        probe = ffmpeg_utils.probe_video(temp_video)
        width  = int(probe.get("width",  1920))
        height = int(probe.get("height", 1080))

        temp_wav = TEMP_DIR / f"{source.stem}_{job_id}.wav"
        ffmpeg_utils.extract_audio(temp_video, temp_wav)

        transcript = transcriber.transcribe(temp_wav, model_size=WHISPER_MODEL_SIZE)

        # Build SRT alongside the output video
        output_video_path = PathResolver.output_for_pipeline(PIPELINE_VIDEO, source)
        output_video_path.parent.mkdir(parents=True, exist_ok=True)

        srt_path = output_video_path.with_suffix(".srt")
        subtitler.generate_srt(transcript, str(srt_path))

        # Build ASS with user caption settings (reads caption_overrides.json from DB dir)
        words = transcript.get("words", [])
        ass_content = ass_builder.build_ass(words, width, height)
        ass_path = output_video_path.with_suffix(".ass")
        ass_builder.save_ass(ass_content, str(ass_path))

        # Burn captions into the full video
        captioned_path = output_video_path.parent / f"{source.stem}_captioned.mp4"
        caption_burner.burn_captions(str(temp_video), str(ass_path), str(captioned_path))

        update_job_video_fields(
            job_id=job_id,
            transcript=transcript.get("full_text", ""),
            video_duration=probe.get("duration", 0.0),
        )
        update_job_status(
            job_id,
            STATUS_DONE,
            output_path=captioned_path,
            srt_path=srt_path,
        )
    except Exception as exc:
        update_job_status(job_id, STATUS_FAILED, error_message=str(exc))
        raise
    finally:
        for p in (temp_wav, temp_video):
            if p and _Path(p).exists():
                try:
                    _Path(p).unlink()
                except OSError:
                    pass


def _bg_rebuild_reel(
    job_id: int,
    clip_paths: list[str],
    custom_ranges: list[dict] | None = None,
) -> None:
    import json as _json
    import subprocess as _subprocess
    from pathlib import Path as _Path
    from config.path_resolver import PathResolver
    from pipelines.video_pipeline import reel_assembler
    from pipelines.caption_pipeline.pipeline import run as _run_captions

    try:
        valid = [p for p in clip_paths if _Path(p).exists()]

        # Extract user-defined custom time-range clips from the source video
        if custom_ranges:
            row = get_job_by_id(job_id)
            source_path = (row.get("source_path") or "") if row else ""
            if source_path and _Path(source_path).exists():
                temp_dir = PathResolver.temp_dir()
                temp_dir.mkdir(parents=True, exist_ok=True)
                for idx, cr in enumerate(custom_ranges):
                    start = float(cr.get("start", 0))
                    end   = float(cr.get("end",   0))
                    if end <= start:
                        continue
                    clip_name = f"custom_{job_id}_{idx}_{int(start * 10)}_{int(end * 10)}.mp4"
                    clip_out  = temp_dir / clip_name
                    try:
                        _subprocess.run(
                            ["ffmpeg", "-y",
                             "-ss", str(start), "-to", str(end),
                             "-i", source_path,
                             "-c", "copy",
                             str(clip_out)],
                            check=True, capture_output=True,
                        )
                        if clip_out.exists() and clip_out.stat().st_size > 0:
                            valid.append(str(clip_out))
                    except Exception:
                        pass   # skip failed extractions; continue with remaining clips

        if not valid:
            update_job_status(job_id, STATUS_FAILED, error_message="No clip files found on disk")
            return
        row = get_job_by_id(job_id)
        source_name = _Path(row["source_path"]).stem if row else f"job{job_id}"
        reel_name = f"{source_name}_reel_custom.mp4"
        reel_target = PathResolver.reels_dir() / reel_name
        reel_path = reel_assembler.assemble_reel(valid, str(reel_target), max_clips=len(valid))
        captioned = None
        try:
            captioned = _run_captions(reel_path)
        except Exception:
            pass
        final = captioned or reel_path
        update_job_video_fields(job_id=job_id, reel_path=captioned or reel_path, clip_paths=_json.dumps(valid))
        update_job_status(job_id, STATUS_DONE, output_path=_Path(final))
    except Exception as exc:
        update_job_status(job_id, STATUS_FAILED, error_message=str(exc))


@app.post("/upload")
async def upload_media(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    action: str = Form("subtitles"),
    user: dict = Depends(get_optional_user),
) -> dict:
    """Accept a file upload, save it, create a job, and process in the background.

    action (form field):
      For images: 'classify' (default)
      For videos: 'subtitles' | 'captions' | 'reel'

    Returns {job_id, status, type} immediately. Poll GET /jobs/{job_id} for result.
    """
    filename = Path(file.filename or "upload").name
    suffix = Path(filename).suffix.lower()

    if suffix in _IMAGE_EXTS:
        detected_type = TYPE_IMAGE
        pipeline = PIPELINE_IMAGE
    elif suffix in _VIDEO_EXTS:
        detected_type = TYPE_VIDEO
        pipeline = PIPELINE_VIDEO
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{suffix}'. Accepted: images (jpg, png, webp, heic…) and videos (mp4, mov, mkv, webm…).",
        )

    # Usage limit check
    user_id = user["sub"]
    if user_id != "local":
        tier = get_user_tier(user_id)
        jobs_this_week = count_user_jobs_this_week(user_id)
        if tier == "free" and jobs_this_week >= FREE_TIER_JOBS_PER_WEEK:
            raise HTTPException(
                status_code=429,
                detail=f"Weekly limit reached ({FREE_TIER_JOBS_PER_WEEK} jobs/week on Free tier). "
                       "Upgrade to Pro for unlimited processing.",
            )
        max_mb = MAX_UPLOAD_MB_PRO if tier == "pro" else MAX_UPLOAD_MB_FREE
    else:
        tier = "pro"
        max_mb = MAX_UPLOAD_MB_PRO

    _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    unique_name = f"{secrets.token_hex(6)}_{filename}"
    save_path = _UPLOAD_DIR / unique_name

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(content) > max_mb * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({len(content) // (1024*1024)}MB). "
                   f"{tier.capitalize()} tier allows up to {max_mb}MB per file.",
        )
    save_path.write_bytes(content)

    job_id = insert_job(save_path, detected_type, pipeline, user_id=user["sub"])
    if job_id is None:
        save_path.unlink(missing_ok=True)
        existing = get_job_by_source(save_path, user_id=user["sub"])
        job_id = int(existing["id"]) if existing else None
        if job_id is None:
            raise HTTPException(status_code=409, detail="File already queued or processed.")

    row = get_job_by_id(job_id)
    if row is None:
        raise HTTPException(status_code=500, detail="Job created but could not be loaded.")

    if detected_type == TYPE_IMAGE:
        background_tasks.add_task(_bg_image, job_id, row)
    else:
        background_tasks.add_task(_bg_video, job_id, str(save_path), action)

    return {"job_id": job_id, "status": "PENDING", "type": detected_type, "action": action}


class SPAStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        if response.status_code == 404:
            return await super().get_response("index.html", scope)
        return response


DIST_DIR = ROOT / "dashboard" / "dist"
if DIST_DIR.exists():
    app.mount("/", SPAStaticFiles(directory=DIST_DIR, html=True), name="dashboard")
else:
    @app.get("/", response_class=HTMLResponse)
    def dashboard_not_built() -> str:
        return (
            "<!doctype html><html><head><title>LobCut</title></head>"
            "<body style='font-family: system-ui; padding: 32px;'>"
            "<h1>Dashboard not built yet.</h1>"
            "<p>Run: <code>cd dashboard && npm run build</code></p>"
            "</body></html>"
        )

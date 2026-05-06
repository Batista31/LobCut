from __future__ import annotations

import os
import re
import secrets
import socket
import sqlite3
import sys
import mimetypes
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode, urlparse

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from jose import JWTError, jwt
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config.settings import DB_PATH
from orchestrator.database import (
    STATUS_DELETED,
    STATUS_PENDING,
    add_watcher,
    delete_watcher,
    get_job_by_id,
    get_user_notification_settings,
    init_db,
    list_jobs_for_dashboard,
    list_watchers,
    retry_job,
    set_telegram_chat_id,
    set_watcher_enabled,
    upsert_user,
)

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


JWT_SECRET = _required_env("JWT_SECRET")
if not re.fullmatch(r"[0-9a-fA-F]{32,}", JWT_SECRET):
    raise RuntimeError("JWT_SECRET must be at least 32 hex characters.")

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
    image_url: Optional[str] = None
    created_at: str
    updated_at: str


class WatcherIn(BaseModel):
    path: str = Field(min_length=1)
    pipeline_override: Optional[str] = None


class WatcherPatch(BaseModel):
    enabled: bool


class WatcherOut(BaseModel):
    id: int
    user_id: str
    path: str
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
    if path_text.startswith("/app/"):
        path = ROOT / path_text.removeprefix("/app/")
    else:
        path = Path(path_text)

    resolved = path.resolve()
    allowed_roots = [
        (ROOT / "input").resolve(),
        (ROOT / "output").resolve(),
        (ROOT / "temp").resolve(),
    ]
    if not any(resolved == root or root in resolved.parents for root in allowed_roots):
        raise HTTPException(status_code=403, detail="File is outside LobCut media folders.")
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


@app.on_event("startup")
def startup() -> None:
    init_db()


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
async def auth_me(user: dict = Depends(get_current_user)) -> dict:
    return user


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
    return {"status": "ok"}


@app.get("/auth/telegram/settings", response_model=TelegramSettingsOut)
def telegram_settings(user: dict = Depends(get_current_user)) -> TelegramSettingsOut:
    settings = get_user_notification_settings(user["sub"])
    chat_id = settings.get("telegram_chat_id")
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

    message = "LobCut Telegram notifications are working."
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
def get_jobs(user: dict = Depends(get_current_user)) -> list[JobOut]:
    return [_job_out(row) for row in list_jobs_for_dashboard(user_id=user["sub"], limit=50)]


@app.get("/jobs/{job_id}", response_model=JobOut)
def get_job(job_id: int, user: dict = Depends(get_current_user)) -> JobOut:
    row = get_job_by_id(job_id, user_id=user["sub"])
    if row is None or row["status"] == STATUS_DELETED:
        raise HTTPException(status_code=404, detail="Job not found.")
    return _job_out(row)


@app.get("/jobs/{job_id}/image")
def get_job_image(job_id: int, user: dict = Depends(get_current_user)) -> StreamingResponse:
    row = get_job_by_id(job_id, user_id=user["sub"]) or get_job_by_id(job_id, user_id="local")
    if row is None or row["status"] == STATUS_DELETED:
        raise HTTPException(status_code=404, detail="Job not found.")

    data = _row_to_dict(row)
    if not _is_image_job(data):
        raise HTTPException(status_code=404, detail="Job is not an image.")

    path = _first_existing_media_path(data.get("output_path"), data.get("source_path"))
    return _stream_image(path)


@app.get("/jobs/{job_id}/preview")
def get_job_preview(job_id: int, user: dict = Depends(get_current_user)) -> StreamingResponse:
    row = get_job_by_id(job_id, user_id=user["sub"]) or get_job_by_id(job_id, user_id="local")
    if row is None or row["status"] == STATUS_DELETED:
        raise HTTPException(status_code=404, detail="Job not found.")

    data = _row_to_dict(row)
    if not _is_image_job(data):
        raise HTTPException(status_code=404, detail="Job is not an image.")

    path = _first_existing_media_path(data.get("source_path"), data.get("output_path"))
    return _stream_image(path)


@app.post("/jobs/retry/{job_id}")
def retry_existing_job(job_id: int, user: dict = Depends(get_current_user)) -> dict[str, str]:
    if not retry_job(job_id, user["sub"]):
        raise HTTPException(status_code=404, detail="Job not found.")
    return {"status": STATUS_PENDING}


@app.delete("/jobs/{job_id}")
def delete_existing_job(job_id: int, user: dict = Depends(get_current_user)) -> dict[str, bool | int]:
    if not _delete_job_row(job_id, user["sub"]):
        raise HTTPException(status_code=404, detail="Job not found.")
    return {"deleted": True, "job_id": job_id}


@app.get("/watchers", response_model=list[WatcherOut])
def get_watchers(user: dict = Depends(get_current_user)) -> list[WatcherOut]:
    return [_watcher_out(row) for row in list_watchers(user["sub"])]


@app.post("/watchers", response_model=WatcherOut)
def create_watcher(body: WatcherIn, user: dict = Depends(get_current_user)) -> WatcherOut:
    watcher_id = add_watcher(
        user["sub"],
        Path(body.path).expanduser(),
        pipeline_override=body.pipeline_override,
    )
    row = next((item for item in list_watchers(user["sub"]) if int(item["id"]) == watcher_id), None)
    if row is None:
        raise HTTPException(status_code=500, detail="Watcher was saved but could not be loaded.")
    return _watcher_out(row)


@app.patch("/watchers/{watcher_id}", response_model=WatcherOut)
def update_watcher(
    watcher_id: int,
    body: WatcherPatch,
    user: dict = Depends(get_current_user),
) -> WatcherOut:
    if not set_watcher_enabled(watcher_id, user["sub"], body.enabled):
        raise HTTPException(status_code=404, detail="Watcher not found.")
    row = next((item for item in list_watchers(user["sub"]) if int(item["id"]) == watcher_id), None)
    if row is None:
        raise HTTPException(status_code=404, detail="Watcher not found.")
    return _watcher_out(row)


@app.delete("/watchers/{watcher_id}")
def remove_watcher(watcher_id: int, user: dict = Depends(get_current_user)) -> dict[str, str]:
    if not delete_watcher(watcher_id, user["sub"]):
        raise HTTPException(status_code=404, detail="Watcher not found.")
    return {"status": "deleted"}


@app.get("/jobs/{job_id}/download")
def download_job_output(job_id: int, user: dict = Depends(get_current_user)):
    row = get_job_by_id(job_id, user_id=user["sub"]) or get_job_by_id(job_id, user_id="local")
    if row is None or row["status"] == STATUS_DELETED:
        raise HTTPException(status_code=404, detail="Job not found.")
    data = _row_to_dict(row)
    raw_path = data.get("output_path") or data.get("source_path")
    path = _resolve_media_path(raw_path)
    return FileResponse(path, filename=path.name, media_type="application/octet-stream")


CAPTION_OVERRIDES_PATH = Path(os.environ.get("DB_PATH", "data/jobs.db")).parent / "caption_overrides.json"


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

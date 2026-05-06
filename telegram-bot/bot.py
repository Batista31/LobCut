import asyncio
import json
import logging
import os
import sqlite3
from collections import Counter; from datetime import datetime
from pathlib import Path; from typing import Any
import httpx; from telegram import Update
from telegram.ext import Application, ApplicationBuilder, CommandHandler, ContextTypes
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("lobcut-telegram-bot")
API_BASE_URL = os.environ.get("API_BASE_URL", "http://api:8000").rstrip("/")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
MEMORY_PATH = Path("/app/memory/lobcut-jobs.md")
DB_PATH = Path(os.environ.get("DB_PATH", "/app/data/jobs.db"))
known_states: dict[int, str] = {}
def jid(job: dict[str, Any]) -> int:
    return int(job.get("id") or job.get("job_id") or 0)
def status(job: dict[str, Any]) -> str:
    return str(job.get("status") or "UNKNOWN").upper()
def kind(job: dict[str, Any]) -> str:
    raw = str(job.get("detected_type") or job.get("type") or job.get("pipeline") or "UNKNOWN")
    raw = raw.replace("_pipeline", "").replace("_", " ").strip().lower()
    return {"image": "IMAGE", "video": "VIDEO"}.get(raw, raw.upper())
def name(job: dict[str, Any]) -> str:
    return str(job.get("filename") or job.get("file") or Path(str(job.get("source_path") or "")).name or "unknown")
def text(value: Any, fallback: str = "none") -> str:
    if value is None:
        return fallback
    if isinstance(value, list):
        return ", ".join(str(v) for v in value) or fallback
    if not isinstance(value, str):
        return str(value)
    value = value.strip()
    if not value:
        return fallback
    try:
        parsed = json.loads(value)
        return ", ".join(str(v) for v in parsed) if isinstance(parsed, list) else value
    except json.JSONDecodeError:
        return value
def clip(value: Any, limit: int = 280) -> str:
    value = text(value, "")
    return value if 0 < len(value) <= limit else (f"{value[:limit - 3].rstrip()}..." if value else "none")
def count_json_list(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    try:
        parsed = json.loads(value) if isinstance(value, str) and value.strip() else []
        return len(parsed) if isinstance(parsed, list) else 0
    except json.JSONDecodeError:
        return 0
def duration(value: Any) -> str:
    try:
        total = int(round(float(value or 0)))
    except (TypeError, ValueError):
        total = 0
    minutes, seconds = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m {seconds}s" if hours else (f"{minutes}m {seconds}s" if minutes else f"{seconds}s")
def write_memory(states: dict[int, str]) -> None:
    MEMORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = ["---", f'last_updated: "{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}"', "jobs:"]
    lines += [f"  {key}: {states[key]}" for key in sorted(states)] if states else ["  {}"]
    lines.append("---")
    MEMORY_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
async def fetch_jobs(client: httpx.AsyncClient) -> list[dict[str, Any]]:
    response = await client.get(f"{API_BASE_URL}/jobs")
    if response.status_code in {401, 403}:
        return db_jobs()
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, list) else []
async def fetch_job(client: httpx.AsyncClient, job_id: int) -> dict[str, Any] | None:
    response = await client.get(f"{API_BASE_URL}/jobs/{job_id}")
    if response.status_code in {401, 403}:
        return db_job(job_id)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, dict) else None
def db_query(sql: str, params: tuple = ()) -> list[dict[str, Any]]:
    if not DB_PATH.exists():
        return []
    conn = sqlite3.connect(str(DB_PATH), timeout=5)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()
def db_jobs() -> list[dict[str, Any]]:
    return db_query("SELECT * FROM jobs ORDER BY created_at DESC LIMIT 50")
def db_job(job_id: int) -> dict[str, Any] | None:
    rows = db_query("SELECT * FROM jobs WHERE id = ?", (job_id,))
    return rows[0] if rows else None
def started(job: dict[str, Any]) -> str:
    return f"🎬 Job #{jid(job)} started\n📄 File: {name(job)}\n🔧 Type: {kind(job)}"
def queued(job: dict[str, Any]) -> str:
    return f"🕐 Job #{jid(job)} queued\n📄 File: {name(job)}\n🔧 Type: {kind(job)}"
def failed(job: dict[str, Any]) -> str:
    reason = job.get("error_message") or job.get("error") or "Unknown failure"
    return f"❌ Job #{jid(job)} failed\n📄 File: {name(job)}\n💬 Reason: {clip(reason)}"
def completed(job: dict[str, Any]) -> str:
    lines = [f"✅ Job #{jid(job)} completed", f"📄 File: {name(job)}", f"🔧 Type: {kind(job)}"]
    if kind(job) == "VIDEO":
        lines += [
            f"🎮 Game: {text(job.get('game_title'), 'unknown')}",
            f"🎯 Genre: {text(job.get('game_genre'), 'unknown')}",
            f"⏱️ Duration: {duration(job.get('video_duration') or job.get('duration_seconds'))}",
            f"✂️ Clips: {count_json_list(job.get('clip_paths'))} | 🎞️ Reels: {1 if job.get('reel_path') else 0}",
            f"📝 Transcript: \"{clip(job.get('transcript'), 220)}\"",
        ]
    else:
        lines += [
            f"📁 Category: {text(job.get('ai_category') or job.get('category'), 'unknown')}",
            f"🏷️ Tags: {text(job.get('ai_tags') or job.get('tags'), 'none')}",
            f"📝 Summary: {clip(job.get('ai_summary') or job.get('summary'), 280)}",
        ]
    return "\n".join(lines)
def details(job: dict[str, Any]) -> str:
    state = status(job)
    if state == "DONE":
        return completed(job)
    if state == "FAILED":
        return failed(job)
    if state == "PROCESSING":
        return started(job)
    if state in {"PENDING", "QUEUED"}:
        return "\n".join([queued(job), f"Status: {state}"])
    return f"Job #{jid(job)}\n📄 File: {name(job)}\n🔧 Type: {kind(job)}\nStatus: {state}"
async def notify(app: Application, message: str) -> None:
    if not TELEGRAM_CHAT_ID:
        log.warning("TELEGRAM_CHAT_ID is not configured; skipping proactive notification.")
        return
    try:
        await app.bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
    except Exception:
        log.exception("Telegram send failed")
async def poll_jobs(app: Application) -> None:
    first_load = True
    async with httpx.AsyncClient(timeout=10) as client:
        while True:
            try:
                jobs = await fetch_jobs(client)
                current = {jid(job): status(job) for job in jobs if jid(job)}
                if first_load:
                    known_states.clear()
                    known_states.update(current)
                    write_memory(known_states)
                    first_load = False
                else:
                    by_id = {jid(job): job for job in jobs if jid(job)}
                    for job_id, state in current.items():
                        if known_states.get(job_id) == state:
                            continue
                        job = by_id[job_id]
                        if state in {"PENDING", "QUEUED"}:
                            await notify(app, queued(job))
                        elif state == "PROCESSING":
                            await notify(app, started(job))
                        elif state in {"DONE", "FAILED"}:
                            detail = await fetch_job(client, job_id) or job
                            await notify(app, completed(detail) if state == "DONE" else failed(detail))
                    known_states.clear()
                    known_states.update(current)
                    write_memory(known_states)
            except (httpx.HTTPError, OSError, Exception):
                log.exception("Job polling failed; skipping this cycle.")
            await asyncio.sleep(10)
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "🤖 LobCut Bot is online\nMonitoring your AI media processing pipeline.\n\n"
        "Commands:\n/status — job summary\n/job <id> — details of a specific job"
    )
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            jobs = await fetch_jobs(client)
            log.info("/status sees %d job(s); latest id: %s", len(jobs), max([jid(job) for job in jobs] or [0]))
            counts = Counter(status(job) for job in jobs)
        except Exception:
            log.exception("/status failed")
            await update.message.reply_text("Could not reach LobCut API.")
            return
    total = sum(counts.values())
    await update.message.reply_text(
        f"📊 LobCut Pipeline Status\n\nTotal: {total}\n✅ Done: {counts['DONE']}\n"
        f"❌ Failed: {counts['FAILED']}\n⏳ Processing: {counts['PROCESSING']}\n🕐 Pending: {counts['PENDING']}"
    )
async def job_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args or not context.args[0].isdigit():
        await update.message.reply_text("Use /job <id>")
        return
    job_id = int(context.args[0])
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            job = await fetch_job(client, job_id)
            if not job:
                jobs = await fetch_jobs(client)
                log.info("/job %s fallback list latest id: %s", job_id, max([jid(job) for job in jobs] or [0]))
                job = next((item for item in jobs if jid(item) == job_id), None)
        except Exception:
            log.exception("/job failed")
            job = None
    await update.message.reply_text(details(job) if job else f"Job #{job_id} not found.")
async def post_init(app: Application) -> None:
    await notify(app, "🤖 LobCut Bot online\nWatching for job updates...")
    app.create_task(poll_jobs(app))
def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required.")
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("job", job_command))
    app.run_polling()
if __name__ == "__main__":
    main()

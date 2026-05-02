"""
orchestrator/database.py
All SQLite interactions for OpenClaw job tracking.
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from config.logger import get_logger
from config.settings import DB_PATH

log = get_logger(__name__)

STATUS_PENDING = "PENDING"
STATUS_PROCESSING = "PROCESSING"
STATUS_DONE = "DONE"
STATUS_FAILED = "FAILED"
STATUS_UNKNOWN = "UNKNOWN"
STATUS_DUPLICATE = "DUPLICATE"
STATUS_NOT_IMPLEMENTED = "NOT_IMPLEMENTED"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    filename         TEXT    NOT NULL,
    source_path      TEXT    NOT NULL UNIQUE,
    detected_type    TEXT,
    pipeline         TEXT,
    status           TEXT    NOT NULL DEFAULT 'PENDING',
    error_message    TEXT,
    srt_path         TEXT,
    output_path      TEXT,
    created_at       TEXT    NOT NULL,
    updated_at       TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_jobs_status   ON jobs (status);
CREATE INDEX IF NOT EXISTS idx_jobs_pipeline ON jobs (pipeline);
CREATE INDEX IF NOT EXISTS idx_jobs_source   ON jobs (source_path);

CREATE TABLE IF NOT EXISTS reel_jobs (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    reel_path        TEXT NOT NULL,
    captioned_path   TEXT,
    status           TEXT DEFAULT 'PENDING',
    error            TEXT,
    word_count       INTEGER,
    created_at       TEXT,
    completed_at     TEXT
);
CREATE INDEX IF NOT EXISTS idx_reel_jobs_status ON reel_jobs (status);
CREATE INDEX IF NOT EXISTS idx_reel_jobs_path   ON reel_jobs (reel_path);
"""

_OPTIONAL_COLUMNS = {
    "ai_category": "TEXT",
    "ai_tags": "TEXT",
    "ai_summary": "TEXT",
    "blur_score": "REAL",
    "classifier": "TEXT",
    "transcript": "TEXT",
    "game_genre": "TEXT",
    "game_title": "TEXT",
    "highlight_timestamps": "TEXT",
    "clip_paths": "TEXT",
    "reel_path": "TEXT",
    "audio_stats": "TEXT",
    "video_duration": "REAL",
}


def _now() -> str:
    return datetime.utcnow().isoformat(sep=" ", timespec="seconds")


def init_db() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _connect() as conn:
        conn.executescript(_SCHEMA)
        _ensure_optional_columns(conn)
    log.info("Database ready at %s", DB_PATH)


def _ensure_optional_columns(conn) -> None:
    existing_columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(jobs)").fetchall()
    }
    for column_name, column_type in _OPTIONAL_COLUMNS.items():
        if column_name not in existing_columns:
            conn.execute(f"ALTER TABLE jobs ADD COLUMN {column_name} {column_type}")
            log.info("Database migration applied: added jobs.%s", column_name)


@contextmanager
def _connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def insert_job(
    source_path: Path,
    detected_type: str,
    pipeline: str,
    status: str = STATUS_PENDING,
) -> Optional[int]:
    now = _now()
    try:
        with _connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO jobs
                    (filename, source_path, detected_type, pipeline, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (source_path.name, str(source_path), detected_type, pipeline, status, now, now),
            )
            job_id = cur.lastrowid
            log.debug("Inserted job #%d for %s", job_id, source_path.name)
            return job_id
    except sqlite3.IntegrityError:
        log.warning("Duplicate ignored: %s already in DB", source_path.name)
        return None


def update_job_status(
    job_id: int,
    status: str,
    error_message: str = None,
    output_path: Path = None,
    srt_path: Path = None,
) -> None:
    now = _now()
    with _connect() as conn:
        conn.execute(
            """
            UPDATE jobs
            SET status        = ?,
                error_message = COALESCE(?, error_message),
                output_path   = COALESCE(?, output_path),
                srt_path      = COALESCE(?, srt_path),
                updated_at    = ?
            WHERE id = ?
            """,
            (
                status,
                error_message,
                str(output_path) if output_path else None,
                str(srt_path) if srt_path else None,
                now,
                job_id,
            ),
        )
    log.debug("Job #%d status -> %s", job_id, status)


def update_job_analysis(
    job_id: int,
    ai_category: str = None,
    ai_tags: str = None,
    ai_summary: str = None,
    blur_score: float = None,
    classifier: str = None,
) -> None:
    now = _now()
    with _connect() as conn:
        conn.execute(
            """
            UPDATE jobs
            SET ai_category = COALESCE(?, ai_category),
                ai_tags     = COALESCE(?, ai_tags),
                ai_summary  = COALESCE(?, ai_summary),
                blur_score  = COALESCE(?, blur_score),
                classifier  = COALESCE(?, classifier),
                updated_at  = ?
            WHERE id = ?
            """,
            (
                ai_category,
                ai_tags,
                ai_summary,
                blur_score,
                classifier,
                now,
                job_id,
            ),
        )
    log.debug("Job #%d analysis metadata updated", job_id)


def update_job_video_fields(
    job_id: int,
    transcript: str = None,
    game_genre: str = None,
    game_title: str = None,
    highlight_timestamps: str = None,
    clip_paths: str = None,
    reel_path: str = None,
    audio_stats: str = None,
    video_duration: float = None,
) -> None:
    now = _now()
    with _connect() as conn:
        conn.execute(
            """
            UPDATE jobs
            SET transcript           = COALESCE(?, transcript),
                game_genre           = COALESCE(?, game_genre),
                game_title           = COALESCE(?, game_title),
                highlight_timestamps = COALESCE(?, highlight_timestamps),
                clip_paths           = COALESCE(?, clip_paths),
                reel_path            = COALESCE(?, reel_path),
                audio_stats          = COALESCE(?, audio_stats),
                video_duration       = COALESCE(?, video_duration),
                updated_at           = ?
            WHERE id = ?
            """,
            (
                transcript,
                game_genre,
                game_title,
                highlight_timestamps,
                clip_paths,
                reel_path,
                audio_stats,
                video_duration,
                now,
                job_id,
            ),
        )
    log.debug("Job #%d video metadata updated", job_id)


def job_exists(source_path: Path) -> bool:
    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM jobs WHERE source_path = ? LIMIT 1",
            (str(source_path),),
        ).fetchone()
    return row is not None


def get_pending_jobs(pipeline: str) -> list:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM jobs WHERE status = ? AND pipeline = ? ORDER BY created_at",
            (STATUS_PENDING, pipeline),
        ).fetchall()
    return rows


def get_job_by_id(job_id: int) -> Optional[sqlite3.Row]:
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM jobs WHERE id = ?",
            (job_id,),
        ).fetchone()


def get_job_by_source(source_path: Path) -> Optional[sqlite3.Row]:
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM jobs WHERE source_path = ? ORDER BY created_at DESC LIMIT 1",
            (str(source_path),),
        ).fetchone()


def list_jobs(limit: int = 50, detected_type: str = None, ai_category: str = None) -> list[sqlite3.Row]:
    query = "SELECT * FROM jobs WHERE 1=1"
    params = []

    if detected_type:
        query += " AND detected_type = ?"
        params.append(detected_type)

    if ai_category:
        query += " AND ai_category = ?"
        params.append(ai_category)

    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    with _connect() as conn:
        return conn.execute(query, params).fetchall()


def insert_reel_job(reel_path: Path, status: str = "IN_PROGRESS") -> int:
    now = _now()
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO reel_jobs (reel_path, status, created_at)
            VALUES (?, ?, ?)
            """,
            (str(reel_path), status, now),
        )
        return int(cur.lastrowid)


def update_reel_job(
    reel_job_id: int,
    status: str = None,
    captioned_path: Path = None,
    error: str = None,
    word_count: int = None,
) -> None:
    with _connect() as conn:
        conn.execute(
            """
            UPDATE reel_jobs
            SET status         = COALESCE(?, status),
                captioned_path = COALESCE(?, captioned_path),
                error          = COALESCE(?, error),
                word_count     = COALESCE(?, word_count),
                completed_at   = CASE WHEN ? IN ('DONE', 'FAILED') THEN ? ELSE completed_at END
            WHERE id = ?
            """,
            (
                status,
                str(captioned_path) if captioned_path else None,
                error,
                word_count,
                status,
                _now(),
                reel_job_id,
            ),
        )

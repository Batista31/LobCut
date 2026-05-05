"""
orchestrator/database.py
All SQLite interactions for LobCut job tracking.
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
STATUS_DELETED = "DELETED"
DEFAULT_USER_ID = "local"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id          TEXT    NOT NULL DEFAULT 'local',
    filename         TEXT    NOT NULL,
    source_path      TEXT    NOT NULL,
    detected_type    TEXT,
    pipeline         TEXT,
    status           TEXT    NOT NULL DEFAULT 'PENDING',
    error_message    TEXT,
    srt_path         TEXT,
    output_path      TEXT,
    telegram_delivered INTEGER NOT NULL DEFAULT 0,
    created_at       TEXT    NOT NULL,
    updated_at       TEXT    NOT NULL,
    UNIQUE(user_id, source_path)
);
CREATE INDEX IF NOT EXISTS idx_jobs_status   ON jobs (status);
CREATE INDEX IF NOT EXISTS idx_jobs_pipeline ON jobs (pipeline);
CREATE INDEX IF NOT EXISTS idx_jobs_source   ON jobs (source_path);
CREATE INDEX IF NOT EXISTS idx_jobs_user     ON jobs (user_id);
CREATE INDEX IF NOT EXISTS idx_jobs_delivery ON jobs (status, telegram_delivered);

CREATE TABLE IF NOT EXISTS users (
    sub              TEXT PRIMARY KEY,
    email            TEXT,
    name             TEXT,
    picture          TEXT,
    telegram_chat_id TEXT,
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS watchers (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id           TEXT NOT NULL,
    path              TEXT NOT NULL,
    pipeline_override TEXT,
    enabled           INTEGER DEFAULT 1,
    created_at        TEXT NOT NULL,
    updated_at        TEXT NOT NULL,
    UNIQUE(user_id, path)
);
CREATE INDEX IF NOT EXISTS idx_watchers_user ON watchers (user_id);

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
    "user_id": "TEXT NOT NULL DEFAULT 'local'",
    "telegram_delivered": "INTEGER NOT NULL DEFAULT 0",
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
        _ensure_pre_schema_columns(conn)
        conn.executescript(_SCHEMA)
        _ensure_optional_columns(conn)
        _ensure_jobs_schema(conn)
        _ensure_optional_columns(conn)
        _ensure_user_columns(conn)
        _ensure_watcher_columns(conn)
    log.info("Database ready at %s", DB_PATH)


def _ensure_pre_schema_columns(conn) -> None:
    table = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'jobs'"
    ).fetchone()
    if table is None:
        return

    existing_columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(jobs)").fetchall()
    }
    pre_schema_columns = {
        "user_id": "TEXT NOT NULL DEFAULT 'local'",
        "telegram_delivered": "INTEGER NOT NULL DEFAULT 0",
    }
    for column_name, column_type in pre_schema_columns.items():
        if column_name not in existing_columns:
            conn.execute(f"ALTER TABLE jobs ADD COLUMN {column_name} {column_type}")
            log.info("Database migration applied: added jobs.%s", column_name)


def _ensure_optional_columns(conn) -> None:
    existing_columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(jobs)").fetchall()
    }
    for column_name, column_type in _OPTIONAL_COLUMNS.items():
        if column_name not in existing_columns:
            conn.execute(f"ALTER TABLE jobs ADD COLUMN {column_name} {column_type}")
            log.info("Database migration applied: added jobs.%s", column_name)


def _ensure_jobs_schema(conn) -> None:
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'jobs'"
    ).fetchone()
    sql = row["sql"] if row else ""
    if "UNIQUE(user_id, source_path)" in sql and "source_path      TEXT    NOT NULL UNIQUE" not in sql:
        return

    legacy_table = "jobs_legacy_migration"
    conn.execute(f"DROP TABLE IF EXISTS {legacy_table}")
    conn.execute("ALTER TABLE jobs RENAME TO jobs_legacy_migration")
    conn.executescript(_SCHEMA)
    _ensure_optional_columns(conn)

    legacy_columns = [
        row["name"]
        for row in conn.execute(f"PRAGMA table_info({legacy_table})").fetchall()
    ]
    new_columns = [
        row["name"]
        for row in conn.execute("PRAGMA table_info(jobs)").fetchall()
    ]
    common_columns = [column for column in new_columns if column in legacy_columns]

    if common_columns:
        columns_sql = ", ".join(common_columns)
        conn.execute(
            f"INSERT OR IGNORE INTO jobs ({columns_sql}) "
            f"SELECT {columns_sql} FROM {legacy_table}"
        )

    conn.execute(f"DROP TABLE {legacy_table}")
    conn.executescript(_SCHEMA)
    log.info("Database migration applied: rebuilt jobs table for per-user isolation")


def _ensure_user_columns(conn) -> None:
    existing_columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(users)").fetchall()
    }
    optional_columns = {
        "telegram_chat_id": "TEXT",
        "created_at": "TEXT NOT NULL DEFAULT ''",
        "updated_at": "TEXT NOT NULL DEFAULT ''",
    }
    for column_name, column_type in optional_columns.items():
        if column_name not in existing_columns:
            conn.execute(f"ALTER TABLE users ADD COLUMN {column_name} {column_type}")
            log.info("Database migration applied: added users.%s", column_name)


def _ensure_watcher_columns(conn) -> None:
    existing_columns = {
        row["name"]
        for row in conn.execute("PRAGMA table_info(watchers)").fetchall()
    }
    optional_columns = {
        "pipeline_override": "TEXT",
        "enabled": "INTEGER DEFAULT 1",
        "updated_at": "TEXT NOT NULL DEFAULT ''",
    }
    for column_name, column_type in optional_columns.items():
        if column_name not in existing_columns:
            conn.execute(f"ALTER TABLE watchers ADD COLUMN {column_name} {column_type}")
            log.info("Database migration applied: added watchers.%s", column_name)


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
    user_id: str = DEFAULT_USER_ID,
) -> Optional[int]:
    now = _now()
    try:
        with _connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO jobs
                    (user_id, filename, source_path, detected_type, pipeline, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, source_path.name, str(source_path), detected_type, pipeline, status, now, now),
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


def job_exists(source_path: Path, user_id: str = DEFAULT_USER_ID) -> bool:
    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM jobs WHERE user_id = ? AND source_path = ? LIMIT 1",
            (user_id, str(source_path)),
        ).fetchone()
    return row is not None


def get_pending_jobs(pipeline: str, user_id: str = None) -> list:
    with _connect() as conn:
        if user_id is None:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE status = ? AND pipeline = ? ORDER BY created_at",
                (STATUS_PENDING, pipeline),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM jobs WHERE user_id = ? AND status = ? AND pipeline = ? ORDER BY created_at",
                (user_id, STATUS_PENDING, pipeline),
            ).fetchall()
    return rows


def get_job_by_id(job_id: int, user_id: str = None) -> Optional[sqlite3.Row]:
    with _connect() as conn:
        if user_id is None:
            return conn.execute(
                "SELECT * FROM jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
        return conn.execute(
            "SELECT * FROM jobs WHERE id = ? AND user_id = ?",
            (job_id, user_id),
        ).fetchone()


def get_job_by_source(source_path: Path, user_id: str = DEFAULT_USER_ID) -> Optional[sqlite3.Row]:
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM jobs WHERE user_id = ? AND source_path = ? ORDER BY created_at DESC LIMIT 1",
            (user_id, str(source_path)),
        ).fetchone()


def list_jobs(
    limit: int = 50,
    detected_type: str = None,
    ai_category: str = None,
    user_id: str = DEFAULT_USER_ID,
) -> list[sqlite3.Row]:
    query = "SELECT * FROM jobs WHERE user_id = ? AND status != ?"
    params = [user_id, STATUS_DELETED]

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


def list_jobs_for_dashboard(user_id: str, limit: int = 50) -> list[sqlite3.Row]:
    with _connect() as conn:
        return conn.execute(
            """
            SELECT *
            FROM jobs
            WHERE status != ?
              AND (user_id = ? OR user_id = ?)
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (STATUS_DELETED, user_id, DEFAULT_USER_ID, limit),
        ).fetchall()


def retry_job(job_id: int, user_id: str) -> bool:
    now = _now()
    with _connect() as conn:
        cur = conn.execute(
            """
            UPDATE jobs
            SET status = ?,
                error_message = NULL,
                telegram_delivered = 0,
                updated_at = ?
            WHERE id = ?
              AND (user_id = ? OR user_id = ?)
              AND status != ?
            """,
            (STATUS_PENDING, now, job_id, user_id, DEFAULT_USER_ID, STATUS_DELETED),
        )
    return cur.rowcount > 0


def soft_delete_job(job_id: int, user_id: str) -> bool:
    now = _now()
    with _connect() as conn:
        cur = conn.execute(
            """
            UPDATE jobs
            SET status = ?, updated_at = ?
            WHERE id = ?
              AND (user_id = ? OR user_id = ?)
            """,
            (STATUS_DELETED, now, job_id, user_id, DEFAULT_USER_ID),
        )
    return cur.rowcount > 0


def recover_interrupted_jobs() -> int:
    now = _now()
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE jobs SET status = ?, updated_at = ? WHERE status = ?",
            (STATUS_PENDING, now, STATUS_PROCESSING),
        )
    log.info("[RECOVERY] Re-queued %d interrupted PROCESSING job(s)", cur.rowcount)
    return cur.rowcount


def list_pending_telegram_jobs(limit: int = 20) -> list[sqlite3.Row]:
    with _connect() as conn:
        return conn.execute(
            """
            SELECT *
            FROM jobs
            WHERE status = ? AND telegram_delivered = 0
            ORDER BY updated_at
            LIMIT ?
            """,
            (STATUS_DONE, limit),
        ).fetchall()


def mark_telegram_delivered(job_id: int) -> None:
    now = _now()
    with _connect() as conn:
        conn.execute(
            "UPDATE jobs SET telegram_delivered = 1, updated_at = ? WHERE id = ?",
            (now, job_id),
        )


def upsert_user(
    sub: str,
    email: str = None,
    name: str = None,
    picture: str = None,
) -> None:
    now = _now()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO users (sub, email, name, picture, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(sub) DO UPDATE SET
                email = excluded.email,
                name = excluded.name,
                picture = excluded.picture,
                updated_at = excluded.updated_at
            """,
            (sub, email, name, picture, now, now),
        )


def get_user(sub: str) -> Optional[sqlite3.Row]:
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE sub = ?",
            (sub,),
        ).fetchone()


def set_telegram_chat_id(user_id: str, chat_id: str) -> None:
    now = _now()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO users (sub, telegram_chat_id, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(sub) DO UPDATE SET
                telegram_chat_id = excluded.telegram_chat_id,
                updated_at = excluded.updated_at
            """,
            (user_id, chat_id, now, now),
        )


def get_telegram_chat_id(user_id: str) -> Optional[str]:
    user = get_user(user_id)
    if user is None:
        return None
    return user["telegram_chat_id"]


def get_user_notification_settings(user_id: str) -> dict:
    user = get_user(user_id)
    return {
        "telegram_chat_id": user["telegram_chat_id"] if user is not None else None,
    }


def get_first_linked_telegram_chat_id() -> Optional[str]:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT telegram_chat_id
            FROM users
            WHERE telegram_chat_id IS NOT NULL
              AND telegram_chat_id != ''
            ORDER BY updated_at DESC
            LIMIT 1
            """
        ).fetchone()
    return row["telegram_chat_id"] if row is not None else None


def list_watchers(user_id: str) -> list[sqlite3.Row]:
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM watchers WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,),
        ).fetchall()


def list_enabled_watchers() -> list[sqlite3.Row]:
    with _connect() as conn:
        return conn.execute(
            "SELECT * FROM watchers WHERE enabled = 1 ORDER BY created_at",
        ).fetchall()


def add_watcher(
    user_id: str,
    path: Path,
    pipeline_override: str = None,
) -> int:
    now = _now()
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO watchers (user_id, path, pipeline_override, enabled, created_at, updated_at)
            VALUES (?, ?, ?, 1, ?, ?)
            ON CONFLICT(user_id, path) DO UPDATE SET
                pipeline_override = excluded.pipeline_override,
                enabled = 1,
                updated_at = excluded.updated_at
            """,
            (user_id, str(path), pipeline_override, now, now),
        )
        if cur.lastrowid:
            return int(cur.lastrowid)
        row = conn.execute(
            "SELECT id FROM watchers WHERE user_id = ? AND path = ?",
            (user_id, str(path)),
        ).fetchone()
        return int(row["id"])


def set_watcher_enabled(watcher_id: int, user_id: str, enabled: bool) -> bool:
    now = _now()
    with _connect() as conn:
        cur = conn.execute(
            "UPDATE watchers SET enabled = ?, updated_at = ? WHERE id = ? AND user_id = ?",
            (1 if enabled else 0, now, watcher_id, user_id),
        )
    return cur.rowcount > 0


def delete_watcher(watcher_id: int, user_id: str) -> bool:
    with _connect() as conn:
        cur = conn.execute(
            "DELETE FROM watchers WHERE id = ? AND user_id = ?",
            (watcher_id, user_id),
        )
    return cur.rowcount > 0


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

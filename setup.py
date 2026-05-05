"""
setup.py — LobCut one-shot installer
Run this from D:\\LobCut:
    python setup.py

It will:
  1. Create the full folder structure
  2. Write every source file
  3. Install the Phase 1 dependency (watchdog)
  4. Print next steps
"""

import os
import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# ── ANSI colours (work on Windows 10+ with ANSI enabled) ─────────────────────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

def ok(msg):  print(f"  {GREEN}✓{RESET}  {msg}")
def info(msg):print(f"  {YELLOW}→{RESET}  {msg}")
def err(msg): print(f"  {RED}✗{RESET}  {msg}")


# ─────────────────────────────────────────────────────────────────────────────
# 1. FOLDER STRUCTURE
# ─────────────────────────────────────────────────────────────────────────────

FOLDERS = [
    "config",
    "orchestrator",
    "pipelines/image_pipeline",
    "pipelines/video_pipeline",
    "input/videos",
    "input/images",
    "output/videos",
    "output/images/blurry",
    "output/images/people",
    "output/images/others",
    "temp/quarantine",
    "logs",
]


# ─────────────────────────────────────────────────────────────────────────────
# 2. FILE CONTENTS  (path → content)
# ─────────────────────────────────────────────────────────────────────────────

FILES = {}

# ── config/__init__.py ────────────────────────────────────────────────────────
FILES["config/__init__.py"] = ""

# ── config/settings.py ───────────────────────────────────────────────────────
FILES["config/settings.py"] = textwrap.dedent('''\
    """
    config/settings.py
    Single source of truth for LobCut.
    No other module may hardcode paths, extensions, or thresholds.
    """

    from pathlib import Path

    # ── Root ──────────────────────────────────────────────────────────────────────
    ROOT = Path(__file__).resolve().parent.parent

    # ── Watched input folders ─────────────────────────────────────────────────────
    INPUT_VIDEOS = ROOT / "input" / "videos"
    INPUT_IMAGES = ROOT / "input" / "images"

    # ── Output folders ────────────────────────────────────────────────────────────
    OUTPUT_VIDEOS   = ROOT / "output" / "videos"
    OUTPUT_IMAGES   = ROOT / "output" / "images"
    OUTPUT_BLURRY   = OUTPUT_IMAGES / "blurry"
    OUTPUT_PEOPLE   = OUTPUT_IMAGES / "people"
    OUTPUT_OTHERS   = OUTPUT_IMAGES / "others"

    # ── Scratch space ─────────────────────────────────────────────────────────────
    TEMP_DIR = ROOT / "temp"

    # ── Logs ──────────────────────────────────────────────────────────────────────
    LOGS_DIR         = ROOT / "logs"
    LOG_FILE         = LOGS_DIR / "lobcut.log"
    LOG_LEVEL        = "DEBUG"
    LOG_MAX_BYTES    = 5 * 1024 * 1024   # 5 MB
    LOG_BACKUP_COUNT = 3

    # ── Database ──────────────────────────────────────────────────────────────────
    DB_PATH = ROOT / "orchestrator" / "jobs.db"

    # ── File type classification ──────────────────────────────────────────────────
    IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp", ".heic"}
    VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".webm", ".m4v"}

    # ── Watcher ───────────────────────────────────────────────────────────────────
    FILE_STABILITY_POLL_INTERVAL  = 0.5
    FILE_STABILITY_POLLS_REQUIRED = 3

    # ── Image pipeline thresholds (Phase 2) ──────────────────────────────────────
    BLUR_LAPLACIAN_THRESHOLD  = 100.0
    YOLO_CONFIDENCE_THRESHOLD = 0.5

    # ── Pipeline names ────────────────────────────────────────────────────────────
    PIPELINE_IMAGE   = "image_pipeline"
    PIPELINE_VIDEO   = "video_pipeline"
    PIPELINE_UNKNOWN = "unknown"

    # ── Quarantine ────────────────────────────────────────────────────────────────
    QUARANTINE_DIR = ROOT / "temp" / "quarantine"
''')

# ── config/logger.py ─────────────────────────────────────────────────────────
FILES["config/logger.py"] = textwrap.dedent('''\
    """
    config/logger.py
    Centralised logging for LobCut.
    Call get_logger(__name__) in every module.
    """

    import logging
    import sys
    from logging.handlers import RotatingFileHandler

    from config.settings import (
        LOG_FILE, LOG_LEVEL, LOG_MAX_BYTES, LOG_BACKUP_COUNT, LOGS_DIR,
    )

    _FORMATTER = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    _configured = False


    def _configure_root() -> None:
        global _configured
        if _configured:
            return

        LOGS_DIR.mkdir(parents=True, exist_ok=True)

        root = logging.getLogger()
        root.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.DEBUG))

        fh = RotatingFileHandler(
            LOG_FILE, maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT, encoding="utf-8",
        )
        fh.setFormatter(_FORMATTER)
        root.addHandler(fh)

        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(_FORMATTER)
        root.addHandler(sh)

        _configured = True


    def get_logger(name: str) -> logging.Logger:
        _configure_root()
        return logging.getLogger(name)
''')

# ── config/path_resolver.py ───────────────────────────────────────────────────
FILES["config/path_resolver.py"] = textwrap.dedent('''\
    """
    config/path_resolver.py
    Single authority for resolving where any file should go.
    Pipelines must never construct paths themselves.
    """

    from pathlib import Path

    from config.settings import (
        OUTPUT_BLURRY, OUTPUT_OTHERS, OUTPUT_PEOPLE, OUTPUT_VIDEOS,
        QUARANTINE_DIR, TEMP_DIR, PIPELINE_VIDEO, PIPELINE_IMAGE,
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
        def quarantine(source: Path) -> Path:
            QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)
            return QUARANTINE_DIR / source.name
''')

# ── orchestrator/__init__.py ──────────────────────────────────────────────────
FILES["orchestrator/__init__.py"] = ""

# ── orchestrator/database.py ──────────────────────────────────────────────────
FILES["orchestrator/database.py"] = textwrap.dedent('''\
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

    STATUS_PENDING    = "PENDING"
    STATUS_PROCESSING = "PROCESSING"
    STATUS_DONE       = "DONE"
    STATUS_FAILED     = "FAILED"
    STATUS_UNKNOWN    = "UNKNOWN"
    STATUS_DUPLICATE  = "DUPLICATE"

    _SCHEMA = """
    CREATE TABLE IF NOT EXISTS jobs (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        filename         TEXT    NOT NULL,
        source_path      TEXT    NOT NULL UNIQUE,
        detected_type    TEXT,
        pipeline         TEXT,
        status           TEXT    NOT NULL DEFAULT \'PENDING\',
        error_message    TEXT,
        srt_path         TEXT,
        output_path      TEXT,
        created_at       TEXT    NOT NULL,
        updated_at       TEXT    NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_jobs_status   ON jobs (status);
    CREATE INDEX IF NOT EXISTS idx_jobs_pipeline ON jobs (pipeline);
    CREATE INDEX IF NOT EXISTS idx_jobs_source   ON jobs (source_path);
    """


    def _now() -> str:
        return datetime.utcnow().isoformat(sep=" ", timespec="seconds")


    def init_db() -> None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _connect() as conn:
            conn.executescript(_SCHEMA)
        log.info("Database ready at %s", DB_PATH)


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
        log.debug("Job #%d status → %s", job_id, status)


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
                "SELECT * FROM jobs WHERE id = ?", (job_id,)
            ).fetchone()
''')

# ── orchestrator/router.py ────────────────────────────────────────────────────
FILES["orchestrator/router.py"] = textwrap.dedent('''\
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
''')

# ── orchestrator/watcher.py ───────────────────────────────────────────────────
FILES["orchestrator/watcher.py"] = textwrap.dedent('''\
    """
    orchestrator/watcher.py
    Watchdog-based folder monitor for LobCut.
    """

    import shutil
    import time
    from pathlib import Path

    from watchdog.events import FileCreatedEvent, FileSystemEventHandler
    from watchdog.observers import Observer

    from config.logger import get_logger
    from config.path_resolver import PathResolver
    from config.settings import (
        FILE_STABILITY_POLL_INTERVAL,
        FILE_STABILITY_POLLS_REQUIRED,
        INPUT_IMAGES,
        INPUT_VIDEOS,
    )
    from orchestrator.database import (
        STATUS_UNKNOWN, insert_job, job_exists,
    )
    from orchestrator.router import TYPE_UNKNOWN, classify

    log = get_logger(__name__)


    def _wait_until_stable(path: Path) -> bool:
        stable_count = 0
        last_size = -1

        while stable_count < FILE_STABILITY_POLLS_REQUIRED:
            if not path.exists():
                log.warning("Stability check: %s disappeared — skipping", path.name)
                return False

            current_size = path.stat().st_size

            if current_size == last_size and current_size > 0:
                stable_count += 1
            else:
                stable_count = 0
                last_size = current_size

            time.sleep(FILE_STABILITY_POLL_INTERVAL)

        log.debug("Stability confirmed for %s (%d bytes)", path.name, last_size)
        return True


    class MediaHandler(FileSystemEventHandler):

        def on_created(self, event: FileCreatedEvent) -> None:
            if event.is_directory:
                return

            path = Path(event.src_path).resolve()

            if path.name.startswith(".") or path.suffix == ".tmp":
                log.debug("Skipping temp/hidden file: %s", path.name)
                return

            log.info("─" * 60)
            log.info("[DETECTED] %s", path.name)

            if job_exists(path):
                log.warning("[DUPLICATE] %s already in database — skipping", path.name)
                return

            log.debug("Waiting for %s to finish writing…", path.name)
            if not _wait_until_stable(path):
                return

            detected_type, pipeline = classify(path)

            db_status = STATUS_UNKNOWN if detected_type == TYPE_UNKNOWN else "PENDING"
            job_id = insert_job(
                source_path=path,
                detected_type=detected_type,
                pipeline=pipeline,
                status=db_status,
            )

            if job_id is None:
                log.warning("[DUPLICATE] %s — race condition, already inserted", path.name)
                return

            if detected_type == TYPE_UNKNOWN:
                _handle_unknown(path, job_id)
            else:
                log.info(
                    "[ROUTED]   %s | Type: %-5s | Pipeline: %-15s | Job ID: #%d",
                    path.name, detected_type, pipeline, job_id,
                )

            log.info("─" * 60)


    def _handle_unknown(path: Path, job_id: int) -> None:
        dest = PathResolver.quarantine(path)
        try:
            shutil.move(str(path), dest)
            log.warning(
                "[UNKNOWN]  %s | Extension: %r | Moved to quarantine | Job ID: #%d",
                path.name, path.suffix, job_id,
            )
        except Exception as exc:
            log.error(
                "[UNKNOWN]  %s | Could not quarantine: %s | Job ID: #%d",
                path.name, exc, job_id,
            )


    def build_observer() -> Observer:
        observer = Observer()
        handler = MediaHandler()

        for folder in (INPUT_VIDEOS, INPUT_IMAGES):
            folder.mkdir(parents=True, exist_ok=True)
            observer.schedule(handler, str(folder), recursive=False)
            log.info("Watching: %s", folder)

        return observer
''')

# ── pipelines/__init__.py ─────────────────────────────────────────────────────
FILES["pipelines/__init__.py"] = ""
FILES["pipelines/image_pipeline/__init__.py"] = '"""Image pipeline — implemented in Phase 2."""'
FILES["pipelines/video_pipeline/__init__.py"] = '"""Video pipeline — implemented in Phase 3."""'

# ── main.py ───────────────────────────────────────────────────────────────────
FILES["main.py"] = textwrap.dedent('''\
    """
    main.py — LobCut entrypoint
    Usage: python main.py
    Ctrl+C to stop cleanly.
    """

    import signal
    import sys
    import time

    from config.logger import get_logger
    from config.settings import ROOT
    from orchestrator.database import init_db
    from orchestrator.watcher import build_observer

    log = get_logger(__name__)

    BANNER = r"""
      ___                   ____ _
     / _ \\  _ __   ___ _ __ / ___| | __ ___      __
    | | | || \'_ \\ / _ \\ \'_ \\| |   | |/ _` \\ \\ /\\ / /
    | |_| || |_) |  __/ | | | |__| | (_| |\\ V  V /
     \\___/ | .__/ \\___|_| |_|\\____|_|\\__,_| \\_/\\_/
           |_|
      Autonomous Media Processing Agent — Phase 1
    """


    def main() -> None:
        print(BANNER)
        log.info("Starting LobCut | Root: %s", ROOT)

        init_db()

        observer = build_observer()
        observer.start()
        log.info("Watcher active. Drop files into input/videos/ or input/images/")
        log.info("Press Ctrl+C to stop.\\n")

        def _shutdown(signum, frame):
            log.info("Signal %d received — shutting down…", signum)
            observer.stop()

        signal.signal(signal.SIGTERM, _shutdown)

        try:
            while observer.is_alive():
                time.sleep(1)
        except KeyboardInterrupt:
            log.info("KeyboardInterrupt — stopping watcher…")
            observer.stop()

        observer.join()
        log.info("LobCut stopped cleanly.")
        sys.exit(0)


    if __name__ == "__main__":
        main()
''')

# ── requirements.txt ──────────────────────────────────────────────────────────
FILES["requirements.txt"] = textwrap.dedent("""\
    # LobCut — Phase 1
    watchdog>=4.0.0

    # Phase 2 (uncomment when ready)
    # opencv-python>=4.9.0
    # ultralytics>=8.0.0

    # Phase 3 (uncomment when ready)
    # openai-whisper>=20231117
    # faster-whisper>=1.0.0
    # ffmpeg-python>=0.2.0
""")

# ── test_phase1.py ────────────────────────────────────────────────────────────
FILES["test_phase1.py"] = textwrap.dedent('''\
    """
    test_phase1.py — Phase 1 acceptance test

    Two modes:
      python test_phase1.py                  # drop files (main.py must be running)
      python test_phase1.py --self-contained # spins up observer internally
      python test_phase1.py --check-only     # just check DB + quarantine
    """

    import argparse
    import sys
    import time
    from pathlib import Path

    ROOT = Path(__file__).resolve().parent
    sys.path.insert(0, str(ROOT))

    from config.settings import INPUT_IMAGES, INPUT_VIDEOS, QUARANTINE_DIR
    from orchestrator.database import init_db, job_exists

    TEST_FILES = [
        (INPUT_IMAGES / "photo_test.jpg",    "IMAGE",   "image_pipeline"),
        (INPUT_VIDEOS / "clip_test.mp4",     "VIDEO",   "video_pipeline"),
        (INPUT_IMAGES / "garbage_test.xyz",  "UNKNOWN", "unknown"),
    ]

    PASS_STR = "\\033[92m✓ PASS\\033[0m"
    FAIL_STR = "\\033[91m✗ FAIL\\033[0m"


    def drop_files():
        for dest, _, _ in TEST_FILES:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(b"\\x00" * 1024)
            print(f"  Dropped: {dest.name} → {dest.parent.name}/")
        print()


    def check_results() -> bool:
        all_pass = True
        for src, expected_type, _ in TEST_FILES:
            effective = QUARANTINE_DIR / src.name if not src.exists() else src
            in_db = job_exists(effective) or job_exists(src)

            if expected_type == "UNKNOWN":
                quarantined = (QUARANTINE_DIR / src.name).exists()
                ok = in_db and quarantined
                label = PASS_STR if ok else FAIL_STR
                print(f"  {label}  {src.name}: in_db={in_db}  quarantined={quarantined}")
            else:
                ok = in_db
                label = PASS_STR if ok else FAIL_STR
                print(f"  {label}  {src.name}: in_db={in_db}")

            if not ok:
                all_pass = False
        return all_pass


    def run_self_contained():
        from orchestrator.watcher import build_observer
        init_db()
        observer = build_observer()
        observer.start()
        print("\\n[self-contained] Observer started.\\n")
        time.sleep(1)
        print("Dropping test files…")
        drop_files()
        wait = (0.5 * 3 * 3) + 3
        print(f"Waiting {wait:.1f}s for processing…")
        time.sleep(wait)
        observer.stop()
        observer.join()
        print("\\nResults:")
        sys.exit(0 if check_results() else 1)


    def run_external():
        print("Dropping test files (main.py should be running)…\\n")
        drop_files()
        print("Files dropped. Check the main.py terminal for output.")
        print("Then run: python test_phase1.py --check-only")


    if __name__ == "__main__":
        parser = argparse.ArgumentParser()
        parser.add_argument("--self-contained", action="store_true")
        parser.add_argument("--check-only", action="store_true")
        args = parser.parse_args()

        init_db()

        if args.self_contained:
            run_self_contained()
        elif args.check_only:
            print("Checking results…\\n")
            sys.exit(0 if check_results() else 1)
        else:
            run_external()
''')


# ─────────────────────────────────────────────────────────────────────────────
# 3. INSTALLER
# ─────────────────────────────────────────────────────────────────────────────

def enable_ansi_windows():
    """Enable ANSI escape codes on Windows 10+."""
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            pass


def create_folders():
    print(f"\n{BOLD}[1/3] Creating folder structure…{RESET}")
    for folder in FOLDERS:
        path = ROOT / folder
        path.mkdir(parents=True, exist_ok=True)
        ok(str(Path(folder)))


def write_files():
    print(f"\n{BOLD}[2/3] Writing source files…{RESET}")
    for rel_path, content in FILES.items():
        dest = ROOT / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")
        ok(rel_path)


def install_deps():
    print(f"\n{BOLD}[3/3] Installing Phase 1 dependency (watchdog)…{RESET}")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "watchdog>=4.0.0", "--quiet"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            ok("watchdog installed")
        else:
            err(f"pip failed:\n{result.stderr.strip()}")
            info("Run manually:  pip install watchdog")
    except Exception as e:
        err(f"Could not run pip: {e}")
        info("Run manually:  pip install watchdog")


def print_next_steps():
    print(f"""
{BOLD}{'─' * 55}
  LobCut Phase 1 — Setup Complete
{'─' * 55}{RESET}

  {GREEN}To start the watcher:{RESET}
    cd {ROOT}
    python main.py

  {GREEN}To run the acceptance test (separate terminal):{RESET}
    python test_phase1.py

  {GREEN}Or test in a single terminal:{RESET}
    python test_phase1.py --self-contained

  {YELLOW}Phase 2 (image pipeline) can begin once you confirm
  files are being detected and routed correctly.{RESET}
""")


if __name__ == "__main__":
    enable_ansi_windows()
    print(f"\n{BOLD}LobCut — one-shot setup for D:\\LobCut{RESET}")
    print(f"Installing into: {ROOT}\n")

    create_folders()
    write_files()
    install_deps()
    print_next_steps()

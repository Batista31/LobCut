"""
test_phase2.py - Phase 2 acceptance test

Runs the watcher plus the image dispatch loop with mocked blur/Gemini results,
so the Phase 2 flow can be validated without real API calls.

Modes:
  py test_phase2.py --self-contained
  py test_phase2.py --check-only
"""

import argparse
import sqlite3
import sys
import time
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config.settings import (
    DB_PATH,
    INPUT_IMAGES,
    OUTPUT_BLURRY,
    OUTPUT_IMAGES,
    QUARANTINE_DIR,
)
from main import _dispatch_pending_image_jobs
from orchestrator.database import init_db, job_exists
from orchestrator.watcher import build_observer

TEST_FILES = [
    {
        "name": "blurry_test.jpg",
        "category": "blurry",
        "blur_score": 12.0,
        "tags": ["low_sharpness"],
    },
    {
        "name": "wildlife_test.jpg",
        "category": "wildlife",
        "blur_score": 320.0,
        "tags": ["bird", "nature"],
    },
    {
        "name": "people_test.jpg",
        "category": "people",
        "blur_score": 275.0,
        "tags": ["portrait", "person"],
    },
]

PASS_STR = "\033[92mPASS\033[0m"
FAIL_STR = "\033[91mFAIL\033[0m"


def _source_path(name: str) -> Path:
    return INPUT_IMAGES / name


def _expected_output(category: str, name: str) -> Path:
    if category == "blurry":
        return OUTPUT_BLURRY / name
    return OUTPUT_IMAGES / category / name


def _reset_test_state() -> None:
    for item in TEST_FILES:
        source = _source_path(item["name"])
        output = _expected_output(item["category"], item["name"])
        if source.exists():
            source.unlink()
        if output.exists():
            output.unlink()

    if QUARANTINE_DIR.exists():
        for test_file in TEST_FILES:
            candidate = QUARANTINE_DIR / test_file["name"]
            if candidate.exists():
                candidate.unlink()

    if DB_PATH.exists():
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("DELETE FROM jobs WHERE pipeline = 'image_pipeline' AND status IN ('PENDING', 'PROCESSING')")
            for item in TEST_FILES:
                conn.execute(
                    "DELETE FROM jobs WHERE source_path = ? OR filename = ?",
                    (str(_source_path(item["name"])), item["name"]),
                )
            conn.commit()


def _drop_files() -> None:
    INPUT_IMAGES.mkdir(parents=True, exist_ok=True)
    for item in TEST_FILES:
        _source_path(item["name"]).write_bytes(b"openclaw-phase2-test")


def _mock_blur_score(image_path: Path) -> float:
    for item in TEST_FILES:
        if image_path.name == item["name"]:
            return item["blur_score"]
    return 250.0


def _mock_gemini(image_path: Path) -> dict:
    for item in TEST_FILES:
        if image_path.name == item["name"]:
            return {
                "primary_category": item["category"],
                "secondary_tags": item["tags"],
                "contains_people": item["category"] in {"people", "portrait"},
                "summary": f"Mocked classification for {item['category']}.",
                "confidence": 0.95,
            }
    return {
        "primary_category": "other",
        "secondary_tags": ["unknown"],
        "contains_people": False,
        "summary": "Mocked fallback classification.",
        "confidence": 0.5,
    }


def _fetch_job_row(source: Path):
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        return conn.execute(
            "SELECT * FROM jobs WHERE source_path = ?",
            (str(source),),
        ).fetchone()


def _all_test_jobs_done() -> bool:
    for item in TEST_FILES:
        row = _fetch_job_row(_source_path(item["name"]))
        if row is None or row["status"] != "DONE":
            return False
    return True


def check_results() -> bool:
    all_pass = True

    for item in TEST_FILES:
        source = _source_path(item["name"])
        output = _expected_output(item["category"], item["name"])
        row = _fetch_job_row(source)

        in_db = row is not None
        status_ok = bool(row and row["status"] == "DONE")
        output_ok = output.exists()
        category_ok = bool(row and row["ai_category"] == item["category"])

        ok = in_db and status_ok and output_ok and category_ok
        label = PASS_STR if ok else FAIL_STR
        print(
            f"  {label}  {item['name']}: "
            f"in_db={in_db} status_done={status_ok} output_exists={output_ok} category_ok={category_ok}"
        )

        if not ok:
            all_pass = False

    duplicate_ok = job_exists(_source_path(TEST_FILES[0]["name"]))
    label = PASS_STR if duplicate_ok else FAIL_STR
    print(f"  {label}  duplicate guard reference row exists for {TEST_FILES[0]['name']}")
    return all_pass and duplicate_ok


def run_self_contained() -> None:
    _reset_test_state()
    init_db()
    observer = build_observer()

    with patch("pipelines.image_pipeline.pipeline._laplacian_variance", side_effect=_mock_blur_score), patch(
        "pipelines.image_pipeline.pipeline._classify_with_gemini",
        side_effect=_mock_gemini,
    ):
        observer.start()
        time.sleep(1)
        _drop_files()
        wait_time = 15
        deadline = time.time() + wait_time
        while time.time() < deadline:
            _dispatch_pending_image_jobs()
            if _all_test_jobs_done():
                break
            time.sleep(1)

        observer.stop()
        observer.join()

    print("\nResults:")
    sys.exit(0 if check_results() else 1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-contained", action="store_true")
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()

    init_db()

    if args.self_contained:
        run_self_contained()
    elif args.check_only:
        print("Checking results...\n")
        sys.exit(0 if check_results() else 1)
    else:
        print("Run with --self-contained to execute the mocked Phase 2 flow.")

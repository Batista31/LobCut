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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from config.settings import INPUT_IMAGES, INPUT_VIDEOS, QUARANTINE_DIR
from orchestrator.database import init_db, job_exists

TEST_FILES = [
    (INPUT_IMAGES / "photo_test.jpg",    "IMAGE",   "image_pipeline"),
    (INPUT_VIDEOS / "clip_test.mp4",     "VIDEO",   "video_pipeline"),
    (INPUT_IMAGES / "garbage_test.xyz",  "UNKNOWN", "unknown"),
]

PASS_STR = "\033[92m✓ PASS\033[0m"
FAIL_STR = "\033[91m✗ FAIL\033[0m"


def drop_files():
    for dest, _, _ in TEST_FILES:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"\x00" * 1024)
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
    print("\n[self-contained] Observer started.\n")
    time.sleep(1)
    print("Dropping test files…")
    drop_files()
    wait = (0.5 * 3 * 3) + 3
    print(f"Waiting {wait:.1f}s for processing…")
    time.sleep(wait)
    observer.stop()
    observer.join()
    print("\nResults:")
    sys.exit(0 if check_results() else 1)


def run_external():
    print("Dropping test files (main.py should be running)…\n")
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
        print("Checking results…\n")
        sys.exit(0 if check_results() else 1)
    else:
        run_external()

"""
Live test for video pipeline.
Usage:
  py test_phase3_live.py "D:\\path\\to\\video.mp4"
"""

import sys
from pathlib import Path

from orchestrator.database import init_db
from pipelines.video_pipeline.pipeline import run


def main():
    if len(sys.argv) < 2:
        print("Provide a source video path.")
        sys.exit(1)
    src = Path(sys.argv[1]).resolve()
    if not src.exists():
        print(f"File does not exist: {src}")
        sys.exit(1)
    init_db()
    run(9999, str(src))
    print("Live run completed.")


if __name__ == "__main__":
    main()

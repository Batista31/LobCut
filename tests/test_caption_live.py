"""
Live caption pipeline test.
Usage:
  python test_caption_live.py "D:\\path\\to\\reel.mp4"
"""

import sys
from pathlib import Path

from pipelines.caption_pipeline.pipeline import run


def main():
    if len(sys.argv) < 2:
        print("Please provide a reel path.")
        sys.exit(1)
    reel = Path(sys.argv[1]).resolve()
    if not reel.exists():
        print(f"File not found: {reel}")
        sys.exit(1)
    output = run(str(reel))
    print(output or "no-speech-or-failed")


if __name__ == "__main__":
    main()

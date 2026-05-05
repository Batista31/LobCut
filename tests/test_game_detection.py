"""
Usage:
  py test_game_detection.py "D:\\path\\to\\frames_folder"
"""

import sys
from pathlib import Path

from pipelines.video_pipeline.game_detector import detect_game


def main():
    if len(sys.argv) < 2:
        print("Provide frames folder path.")
        sys.exit(1)
    folder = Path(sys.argv[1]).resolve()
    frames = [str(p) for p in sorted(folder.glob("*.jpg"))][:5]
    print(detect_game(frames, ""))


if __name__ == "__main__":
    main()

"""
Mocked caption pipeline test.
Usage:
  python test_caption_mocked.py
"""

from pathlib import Path
from unittest.mock import patch

from pipelines.caption_pipeline.pipeline import run


def main():
    reels_dir = Path("output/videos/reels")
    reels_dir.mkdir(parents=True, exist_ok=True)
    reel = reels_dir / "mock_reel.mp4"
    if not reel.exists():
        # 2-second black sample reel
        import subprocess

        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "lavfi",
                "-i",
                "color=c=black:s=1280x720:d=2",
                "-f",
                "lavfi",
                "-i",
                "anullsrc=channel_layout=stereo:sample_rate=48000",
                "-shortest",
                str(reel),
            ],
            check=True,
            capture_output=True,
            text=True,
        )

    mock_words = [
        {"word": "lets", "start": 0.10, "end": 0.35},
        {"word": "go", "start": 0.36, "end": 0.55},
        {"word": "nice", "start": 0.56, "end": 0.80},
    ]
    with patch("pipelines.caption_pipeline.caption_transcriber.transcribe_for_captions", return_value=mock_words):
        out = run(str(reel))
    print(out or "no-caption-output")


if __name__ == "__main__":
    main()

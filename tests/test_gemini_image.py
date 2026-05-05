"""
test_gemini_image.py

Live Gemini smoke test for one image.

Usage:
  py test_gemini_image.py "D:\\path\\to\\image.jpg"
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from pipelines.image_pipeline.pipeline import _classify_with_gemini, _laplacian_variance


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", help="Absolute or relative path to an image file")
    args = parser.parse_args()

    image_path = Path(args.image).expanduser().resolve()
    if not image_path.exists():
        print(f"Image not found: {image_path}")
        return 1

    blur_score = _laplacian_variance(image_path)
    classification = _classify_with_gemini(image_path)

    payload = {
        "image": str(image_path),
        "blur_score": blur_score,
        "classification": classification,
    }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import subprocess
from pathlib import Path

from config.settings import CAPTION_CRF
from pipelines.caption_pipeline.errors import CaptionPipelineError


def burn_captions(reel_path: str, ass_path: str, output_path: str) -> str:
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    ass_file = Path(ass_path).resolve()
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        reel_path,
        "-vf",
        f"ass={ass_file.name}",
        "-c:v",
        "libx264",
        "-crf",
        str(CAPTION_CRF),
        "-c:a",
        "copy",
        str(out),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ass_file.parent))
    if proc.returncode != 0:
        raise CaptionPipelineError(proc.stderr.strip() or "Caption burn failed", recoverable=False)
    return str(out)

from __future__ import annotations

import subprocess
from pathlib import Path

from pipelines.video_pipeline.errors import VideoPipelineError


def assemble_reel(clip_paths: list[str], output_path: str, max_clips=5) -> str:
    selected = clip_paths[:max_clips]
    if not selected:
        raise VideoPipelineError("No clips to assemble", recoverable=True)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    list_file = output.parent / f"{output.stem}_concat.txt"
    lines = [f"file '{Path(p).resolve().as_posix()}'" for p in selected]
    list_file.write_text("\n".join(lines), encoding="utf-8")

    cmd = [
        "ffmpeg",
        "-y",
        "-fflags",
        "+genpts",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_file),
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        "-r",
        "30",
        "-c:a",
        "aac",
        "-b:a",
        "160k",
        "-ar",
        "48000",
        "-af",
        "aresample=async=1:first_pts=0",
        "-movflags",
        "+faststart",
        "-shortest",
        str(output),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise VideoPipelineError("Failed to assemble reel", recoverable=True)
    return str(output)

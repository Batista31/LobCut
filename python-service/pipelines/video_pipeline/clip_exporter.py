from __future__ import annotations

import re
import subprocess
from pathlib import Path

from config.path_resolver import PathResolver
from config.settings import TRIM_SILENCE
from pipelines.video_pipeline import ffmpeg_utils
from pipelines.video_pipeline.errors import VideoPipelineError


def _safe(s: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]+", "_", (s or "").strip()).strip("_") or "unknown"


def trim_silence(clip_path: str, output_path: str, silence_thresh_db=-40, min_silence_sec=1.5) -> str:
    if not TRIM_SILENCE:
        return clip_path
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        clip_path,
        "-af",
        f"silenceremove=start_periods=1:start_silence={min_silence_sec}:start_threshold={silence_thresh_db}dB:"
        f"stop_periods=1:stop_silence={min_silence_sec}:stop_threshold={silence_thresh_db}dB",
        "-c:v",
        "copy",
        output_path,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        return clip_path
    return output_path if Path(output_path).exists() else clip_path


def export_clips(
    source_path: str,
    moments: list[dict],
    game_genre: str,
    game_title: str,
    job_id: str,
    base_name: str | None = None,
) -> list[dict]:
    out_dir = PathResolver.video_genre_dir(game_genre or "unknown")
    exported = []
    stem = _safe(base_name or game_title or game_genre or "video")
    for i, moment in enumerate(moments, start=1):
        name = f"{stem}_clip{i}.mp4"
        clip_path = out_dir / name
        try:
            ffmpeg_utils.cut_clip(source_path, moment["clip_start"], moment["clip_end"], clip_path)
            final_clip = trim_silence(str(clip_path), str(out_dir / f"{clip_path.stem}_trim.mp4"))
            if final_clip != str(clip_path):
                Path(final_clip).replace(clip_path)
            exported.append({"clip_path": str(clip_path), "moment": moment})
        except Exception:
            continue
    return exported

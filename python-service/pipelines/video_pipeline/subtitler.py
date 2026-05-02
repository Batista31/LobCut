from __future__ import annotations

from pathlib import Path
import subprocess


def _fmt_srt_time(sec: float) -> str:
    sec = max(0.0, float(sec))
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int(round((sec - int(sec)) * 1000))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def generate_srt(transcript: dict, output_srt_path: str) -> str:
    output = Path(output_srt_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    i = 1
    for seg in transcript.get("segments", []):
        start = float(seg.get("start", 0.0))
        end = float(seg.get("end", 0.0))
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        lines.extend([str(i), f"{_fmt_srt_time(start)} --> {_fmt_srt_time(end)}", text, ""])
        i += 1
    output.write_text("\n".join(lines), encoding="utf-8")
    return str(output)


def clip_srt(transcript: dict, clip_start: float, clip_end: float, output_srt_path: str) -> str:
    clipped = {"segments": []}
    for seg in transcript.get("segments", []):
        seg_start = float(seg.get("start", 0.0))
        seg_end = float(seg.get("end", 0.0))
        if seg_end < clip_start or seg_start > clip_end:
            continue
        clipped["segments"].append(
            {
                "start": max(0.0, seg_start - clip_start),
                "end": max(0.0, min(clip_end, seg_end) - clip_start),
                "text": seg.get("text", ""),
            }
        )
    return generate_srt(clipped, output_srt_path)


def burn_subtitles(clip_path: str, srt_path: str, output_path: str) -> str:
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        clip_path,
        "-vf",
        f"subtitles={srt_path}",
        output_path,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "Subtitle burn failed")
    return output_path

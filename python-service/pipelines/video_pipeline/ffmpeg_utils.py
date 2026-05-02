import json
import subprocess
from pathlib import Path

from pipelines.video_pipeline.errors import VideoPipelineError


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise VideoPipelineError(proc.stderr.strip() or "FFmpeg command failed")
    return proc


def probe_video(path) -> dict:
    path = Path(path)
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_streams",
        "-show_format",
        str(path),
    ]
    proc = _run(cmd)
    data = json.loads(proc.stdout or "{}")
    streams = data.get("streams", [])
    fmt = data.get("format", {})
    video_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)
    fps_raw = video_stream.get("avg_frame_rate", "0/1")
    try:
        n, d = fps_raw.split("/")
        fps = float(n) / float(d) if float(d) else 0.0
    except Exception:
        fps = 0.0
    return {
        "duration": float(fmt.get("duration", 0.0) or 0.0),
        "width": int(video_stream.get("width", 0) or 0),
        "height": int(video_stream.get("height", 0) or 0),
        "fps": fps,
        "has_audio": audio_stream is not None,
        "codec": str(video_stream.get("codec_name", "")),
        "size_bytes": int(fmt.get("size", 0) or 0),
    }


def extract_audio(video_path, output_wav_path) -> str:
    video_path = Path(video_path)
    output_wav_path = Path(output_wav_path)
    output_wav_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vn",
        "-ar",
        "16000",
        "-ac",
        "1",
        "-f",
        "wav",
        str(output_wav_path),
    ]
    _run(cmd)
    if (not output_wav_path.exists()) or output_wav_path.stat().st_size == 0:
        raise VideoPipelineError("Extracted WAV is empty", recoverable=False)
    return str(output_wav_path)


def extract_frames(video_path, output_dir, interval_seconds=30) -> list[str]:
    video_path = Path(video_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    pattern = output_dir / "frame_%06d.jpg"
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vf",
        f"fps=1/{max(1, int(interval_seconds))}",
        str(pattern),
    ]
    _run(cmd)
    return [str(p) for p in sorted(output_dir.glob("*.jpg"))]


def cut_clip(source_path, start_sec, end_sec, output_path) -> str:
    source_path = Path(source_path)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    duration = max(0.1, float(end_sec) - float(start_sec))
    # Re-encode with normalized timing for player compatibility and sync stability.
    encode_cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(source_path),
        "-ss",
        str(max(0.0, float(start_sec))),
        "-t",
        str(duration),
        "-map",
        "0:v:0",
        "-map",
        "0:a?",
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
        str(output_path),
    ]
    _run(encode_cmd)
    if not output_path.exists():
        raise VideoPipelineError(f"Clip cut failed for {source_path.name}")
    return str(output_path)

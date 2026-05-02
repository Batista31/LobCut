from __future__ import annotations

import time
from pathlib import Path

from config.settings import TEMP_DIR, WHISPER_MODEL_SIZE
from pipelines.caption_pipeline.errors import CaptionPipelineError
from pipelines.video_pipeline import ffmpeg_utils, transcriber


def _normalize_words(words: list[dict]) -> list[dict]:
    merged = []
    for word in words:
        w = (word.get("word") or "").strip()
        if not w:
            continue
        start = float(word.get("start", 0.0))
        end = float(word.get("end", start))
        if end <= start:
            end = start + 0.1
        if merged and (w.startswith("'") or w.startswith("-")):
            prev = merged[-1]
            prev["word"] = f"{prev['word']}{w}"
            prev["end"] = end
            continue
        merged.append({"word": w, "start": start, "end": end})
    return merged


def transcribe_for_captions(reel_path: str) -> list[dict]:
    reel = Path(reel_path)
    temp_wav = TEMP_DIR / f"{reel.stem}_caption.wav"
    try:
        last_error = None
        for _ in range(6):
            try:
                ffmpeg_utils.extract_audio(reel, temp_wav)
                last_error = None
                break
            except Exception as exc:
                last_error = exc
                msg = str(exc).lower()
                if ("moov atom not found" in msg) or ("invalid data found" in msg):
                    time.sleep(1.5)
                    continue
                raise
        if last_error is not None:
            raise last_error
        result = transcriber.transcribe(temp_wav, model_size=WHISPER_MODEL_SIZE, word_timestamps=True)
        words = []
        for segment in result.get("segments", []):
            for word in segment.get("words", []):
                words.append(
                    {
                        "word": word.get("word", ""),
                        "start": float(word.get("start", segment.get("start", 0.0))),
                        "end": float(word.get("end", segment.get("end", 0.0))),
                    }
                )
        return _normalize_words(words)
    except Exception as exc:
        raise CaptionPipelineError(f"Caption transcription failed: {exc}", recoverable=False) from exc
    finally:
        if temp_wav.exists():
            try:
                temp_wav.unlink()
            except OSError:
                pass

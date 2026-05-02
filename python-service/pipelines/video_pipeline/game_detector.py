from __future__ import annotations

import base64
import json
import os
from pathlib import Path

from config.settings import GEMINI_API_KEY_ENV_VAR, GEMINI_IMAGE_MODEL, VIDEO_GENRES


def _read_image_b64(path: str) -> str:
    data = Path(path).read_bytes()
    return base64.b64encode(data).decode("ascii")


def detect_game(frame_paths: list[str], transcript_text: str) -> dict:
    sampled = frame_paths[:5]
    transcript_excerpt = " ".join((transcript_text or "").split()[:500])
    fallback = {
        "game_title": None,
        "game_genre": "unknown",
        "confidence": "low",
        "genre_notes": "fallback",
    }
    if not sampled:
        return fallback

    try:
        from google import genai
    except ImportError:
        return fallback

    prompt = (
        "You are a video game analyst. Based on gameplay frames and transcript, "
        "identify game and genre. Respond ONLY in JSON with keys: game_title, game_genre, "
        "confidence, genre_notes."
    )
    contents = [prompt, transcript_excerpt]
    for path in sampled:
        contents.append({"mime_type": "image/jpeg", "data": _read_image_b64(path)})
    try:
        api_key = os.getenv(GEMINI_API_KEY_ENV_VAR)
        client = genai.Client(api_key=api_key) if api_key else genai.Client()
        resp = client.models.generate_content(model=GEMINI_IMAGE_MODEL, contents=contents)
        parsed = json.loads(resp.text)
    except Exception:
        return fallback

    genre = str(parsed.get("game_genre", "unknown")).strip().lower()
    if genre not in VIDEO_GENRES:
        genre = "unknown"
    return {
        "game_title": parsed.get("game_title"),
        "game_genre": genre,
        "confidence": parsed.get("confidence", "low"),
        "genre_notes": parsed.get("genre_notes", ""),
    }

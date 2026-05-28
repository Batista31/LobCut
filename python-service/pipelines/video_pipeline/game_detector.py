from __future__ import annotations

import base64
import json
from pathlib import Path

from config.gemini_client import generate_with_fallback
from config.settings import GEMINI_IMAGE_MODEL, VIDEO_GENRES


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

    valid_genres = (
        "fps, battle_royale, moba, rpg, survival, sandbox, racing, strategy, "
        "fighting, puzzle, esports, football, cricket, basketball, tennis, "
        "sports, commentary, vlog, unknown"
    )
    prompt = (
        "You are a video content analyst. Based on the provided frames and transcript excerpt, "
        "identify the content type and genre. The video may be a video game, a real sport "
        "(football, cricket, basketball, tennis, etc.), a YouTube vlog, sports commentary, "
        "or any other content. "
        f"Respond ONLY with valid JSON using these exact keys: "
        "game_title (string name of the game/sport/show, or null if not identifiable), "
        f"game_genre (one of: {valid_genres}), "
        "confidence (high/medium/low), "
        "genre_notes (brief explanation of what you saw)."
    )
    contents = [prompt, transcript_excerpt]
    for path in sampled:
        contents.append({"mime_type": "image/jpeg", "data": _read_image_b64(path)})
    try:
        response_text = generate_with_fallback(model_name=GEMINI_IMAGE_MODEL, contents=contents)
        parsed = json.loads(response_text)
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

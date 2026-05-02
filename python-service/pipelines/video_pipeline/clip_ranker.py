from __future__ import annotations


def rerank_clips_with_gemini(clip_paths: list[str], genre: str) -> list[dict]:
    ranked = []
    for i, path in enumerate(clip_paths):
        ranked.append({"clip_path": path, "excitement_score": max(1, 10 - i), "label": f"{genre} highlight"})
    return ranked

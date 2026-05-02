from __future__ import annotations

from config.settings import MIN_HIGHLIGHT_GAP_SEC
from pipelines.video_pipeline.highlight_detector import deduplicate_moments


def find_keyword_moments(transcript: dict, triggers: list[dict], duration_sec: float) -> list[dict]:
    moments = []
    for seg in transcript.get("segments", []):
        text = (seg.get("text") or "").lower()
        ts = float(seg.get("start", 0.0))
        for trig in triggers:
            phrase = str(trig.get("phrase", "")).strip().lower()
            if phrase and phrase in text:
                pre = float(trig.get("pre_sec", 3))
                post = float(trig.get("post_sec", 8))
                moments.append(
                    {
                        "timestamp": ts,
                        "score": 75,
                        "clip_start": max(0.0, ts - pre),
                        "clip_end": min(duration_sec, ts + post) if duration_sec > 0 else ts + post,
                        "reason": f"keyword:{phrase}",
                        "label": trig.get("label", "keyword"),
                        "source": "keyword",
                    }
                )
    return deduplicate_moments(moments, min_gap_sec=MIN_HIGHLIGHT_GAP_SEC)

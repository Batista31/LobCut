from __future__ import annotations

from config.settings import (
    CLIP_POST_BUFFER_SEC,
    CLIP_PRE_BUFFER_SEC,
    MAX_HIGHLIGHTS,
    MIN_HIGHLIGHT_GAP_SEC,
)

KEYWORDS = {
    "fps": ["kill", "headshot", "ace", "clutch", "snipe", "down", "out", "let's go", "ez", "quad", "4k"],
    "battle_royale": ["knocked", "third party", "circle", "final circle", "winner winner", "last squad"],
    "moba": ["first blood", "pentakill", "baron", "dragon", "surrender", "gg", "tower"],
    "rpg": ["boss", "rare drop", "level up", "quest complete", "died", "checkpoint"],
    "survival": ["raid", "boom", "found", "base", "creeper", "explosion", "hostile"],
    "sandbox": ["build", "done", "look at this", "finished", "finally"],
    "sports": ["goal", "save", "miss", "penalty", "foul", "overtime", "winner"],
    "racing": ["overtake", "crash", "pit stop", "fastest lap", "podium"],
    "strategy": ["attacked", "rush", "gg", "economy", "tech", "wonder"],
    "fighting": ["perfect", "ultra", "finish him", "combo", "ko"],
    "puzzle": ["solved", "failed", "nice", "wait", "got it"],
}

CONTINUATION_KEYWORDS = (
    "ace",
    "clutch",
    "quad",
    "4k",
    "4 kill",
    "four kill",
    "five kill",
    "team wipe",
    "last one",
    "one more",
    "he's lit",
    "hes lit",
)


def _timeline_value(timeline, ts):
    if not timeline:
        return 0.0
    nearest = min(timeline, key=lambda x: abs(float(x[0]) - float(ts)))
    return float(nearest[1])


def _near_text(transcript, ts, window=5.0):
    parts = []
    for seg in transcript.get("segments", []):
        if float(seg.get("start", 0.0)) <= ts + window and float(seg.get("end", 0.0)) >= ts - window:
            parts.append(seg.get("text", ""))
    return " ".join(parts).lower()


def _extra_post_buffer(text: str) -> float:
    if any(keyword in text for keyword in CONTINUATION_KEYWORDS):
        return 10.0
    if text.count("kill") >= 2 or text.count("down") >= 2:
        return 6.0
    return 0.0


def score_moments(candidates, audio_stats, transcript, genre) -> list[dict]:
    onset = audio_stats.get("onset_timeline", [])
    centroid = audio_stats.get("spectral_timeline", [])
    silences = audio_stats.get("silence_periods", [])
    duration = float(audio_stats.get("duration_sec", 0.0))
    kw = KEYWORDS.get(genre, [])
    onset_values = [float(x[1]) for x in onset] or [0.0]
    onset_mean = sum(onset_values) / len(onset_values)
    onset_max = max(onset_values) or 1.0
    moments = []
    for ts in candidates:
        ts = float(ts)
        onset_v = _timeline_value(onset, ts)
        centroid_v = _timeline_value(centroid, ts)
        audio_score = min(1.0, max(0.0, (onset_v - onset_mean) / max(1e-6, onset_max))) * 40
        text = _near_text(transcript, ts, window=8.0)
        kw_hits = sum(1 for k in kw if k in text)
        kw_score = min(1.0, kw_hits / 2.0) * 35
        silence_bonus = 0
        for start, end in silences:
            if 0 <= ts - float(end) <= 3:
                silence_bonus = 15
                break
        spectral_bonus = 10 if centroid_v > 3000 else 0
        score = int(round(audio_score + kw_score + silence_bonus + spectral_bonus))
        post_buffer = CLIP_POST_BUFFER_SEC + _extra_post_buffer(text)
        moments.append(
            {
                "timestamp": ts,
                "score": min(100, max(0, score)),
                "clip_start": max(0.0, ts - CLIP_PRE_BUFFER_SEC),
                "clip_end": min(duration if duration > 0 else ts + post_buffer, ts + post_buffer),
                "reason": f"audio={onset_v:.2f}, keywords={kw_hits}, post={post_buffer:.0f}s",
                "source": "audio",
            }
        )
    moments.sort(key=lambda x: x["score"], reverse=True)
    return moments[: max(1, MAX_HIGHLIGHTS * 2)]


def deduplicate_moments(moments, min_gap_sec=MIN_HIGHLIGHT_GAP_SEC):
    kept = []
    for m in sorted(moments, key=lambda x: x["score"], reverse=True):
        nearby = next((k for k in kept if abs(float(m["timestamp"]) - float(k["timestamp"])) < min_gap_sec), None)
        if nearby is None:
            kept.append(dict(m))
            continue
        nearby["clip_start"] = min(float(nearby.get("clip_start", 0.0)), float(m.get("clip_start", 0.0)))
        nearby["clip_end"] = max(float(nearby.get("clip_end", 0.0)), float(m.get("clip_end", 0.0)))
        if float(m.get("score", 0)) > float(nearby.get("score", 0)):
            nearby["timestamp"] = m.get("timestamp", nearby.get("timestamp"))
            nearby["score"] = m.get("score", nearby.get("score"))
        nearby["reason"] = f"{nearby.get('reason', '')} | merged {m.get('reason', '')}".strip()
    kept.sort(key=lambda x: x["score"], reverse=True)
    return kept[:MAX_HIGHLIGHTS]

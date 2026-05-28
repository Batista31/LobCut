from __future__ import annotations

import json
from pathlib import Path

from config.settings import (
    CAPTION_COLOR,
    CAPTION_FONT,
    CAPTION_FONT_SIZE,
    CAPTION_HIGHLIGHT_COLOR,
    CAPTION_MAX_WORDS_PER_LINE,
    CAPTION_OUTLINE,
    CAPTION_POSITION,
    CAPTION_SHADOW,
    CAPTION_STYLE,
    DB_PATH,
)


def seconds_to_ass_time(sec: float) -> str:
    sec = max(0.0, float(sec))
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    cs = int(round((sec - int(sec)) * 100))
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def group_words_into_lines(words: list[dict], max_words_per_line: int) -> list[list[dict]]:
    return [words[i : i + max(1, max_words_per_line)] for i in range(0, len(words), max(1, max_words_per_line))]


CAPTION_OVERRIDES_PATH = Path(DB_PATH).parent / "caption_overrides.json"


def _load_style_config(style_config: dict | None = None) -> dict:
    merged = {}
    if CAPTION_OVERRIDES_PATH.exists():
        try:
            data = json.loads(CAPTION_OVERRIDES_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                merged.update(data)
        except Exception:
            pass
    if style_config:
        merged.update(style_config)
    return merged


def _alignment_and_margin(video_height: int, position: str):
    margin_v = int(video_height * 0.08)
    if position == "top":
        return 8, margin_v
    if position in {"middle", "center"}:
        return 5, 0
    return 2, margin_v


def build_ass(words: list[dict], video_width: int, video_height: int, style_config: dict | None = None) -> str:
    style_config = _load_style_config(style_config)
    font = style_config.get("font", CAPTION_FONT)
    base_size = int(style_config.get("font_size", CAPTION_FONT_SIZE))
    color = style_config.get("color", CAPTION_COLOR)
    highlight = style_config.get("highlight_color", CAPTION_HIGHLIGHT_COLOR)
    outline_color = style_config.get("outline_color", "&H00000000")
    position = style_config.get("position", CAPTION_POSITION)
    style_mode = style_config.get("style", CAPTION_STYLE)
    max_words = int(style_config.get("max_words_per_line", CAPTION_MAX_WORDS_PER_LINE))
    outline_enabled = bool(style_config.get("outline", CAPTION_OUTLINE))
    outline = float(style_config.get("outline_width", 3 if outline_enabled else 0)) if outline_enabled else 0
    shadow = float(style_config.get("shadow", 1 if CAPTION_SHADOW else 0))
    bold = -1 if bool(style_config.get("bold", True)) else 0
    align, margin_v = _alignment_and_margin(video_height, str(position))
    font_size = max(12, int(base_size * (video_height / 1080.0)))

    header = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {video_width}",
        f"PlayResY: {video_height}",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Italic, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV",
        f"Style: Default,{font},{font_size},{color},{outline_color},&H00000000,{bold},0,1,{outline},{shadow},{align},10,10,{margin_v}",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    events = []

    for group in group_words_into_lines(words, max_words):
        full_group = [w["word"] for w in group]
        for idx, active in enumerate(group):
            start_sec = float(active["start"])
            # Clamp end to next word's start to prevent overlapping dialogue events
            if idx < len(group) - 1:
                end_sec = float(group[idx + 1]["start"])
            else:
                end_sec = float(active["end"])
            if end_sec <= start_sec:
                end_sec = start_sec + 0.05
            start = seconds_to_ass_time(start_sec)
            end = seconds_to_ass_time(end_sec)
            if style_mode == "word_by_word":
                text = f"{{\\c{highlight}}}{active['word']}"
            elif style_mode == "block":
                text = " ".join(full_group)
            else:
                parts = []
                for i, token in enumerate(full_group):
                    c = highlight if i == idx else color
                    parts.append(f"{{\\c{c}}}{token}")
                text = " ".join(parts)
            events.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}")

    return "\n".join(header + events) + "\n"


def save_ass(content: str, output_path: str) -> str:
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")
    return str(out)

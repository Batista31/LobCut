from __future__ import annotations

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


def _alignment_and_margin(video_height: int):
    margin_v = int(video_height * 0.08)
    if CAPTION_POSITION == "top":
        return 8, margin_v
    if CAPTION_POSITION == "center":
        return 5, 0
    return 2, margin_v


def build_ass(words: list[dict], video_width: int, video_height: int, style_config: dict | None = None) -> str:
    style_config = style_config or {}
    font = style_config.get("font", CAPTION_FONT)
    base_size = int(style_config.get("font_size", CAPTION_FONT_SIZE))
    color = style_config.get("color", CAPTION_COLOR)
    highlight = style_config.get("highlight_color", CAPTION_HIGHLIGHT_COLOR)
    style_mode = style_config.get("style", CAPTION_STYLE)
    max_words = int(style_config.get("max_words_per_line", CAPTION_MAX_WORDS_PER_LINE))
    outline = 2 if style_config.get("outline", CAPTION_OUTLINE) else 0
    shadow = 1 if style_config.get("shadow", CAPTION_SHADOW) else 0
    align, margin_v = _alignment_and_margin(video_height)
    font_size = max(12, int(base_size * (video_height / 1080.0)))

    header = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {video_width}",
        f"PlayResY: {video_height}",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Italic, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV",
        f"Style: Default,{font},{font_size},{color},&H00000000,&H00000000,0,0,1,{outline},{shadow},{align},10,10,{margin_v}",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    events = []

    for group in group_words_into_lines(words, max_words):
        full_group = [w["word"] for w in group]
        for idx, active in enumerate(group):
            start = seconds_to_ass_time(active["start"])
            end = seconds_to_ass_time(active["end"])
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

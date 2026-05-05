# LobCut — Live Captions for Reels

**Scope:** Process every video inside `output/videos/reels/` and produce a captioned version with word-level animated captions burned directly into the video.
**Stack:** OpenAI Whisper (local) · FFmpeg · Python
**Output folder:** `output/videos/reels/captioned/`
**Context:** This runs after Phase 4.3 (Reel Assembly) produces `output/videos/reels/*.mp4` files.

---

## What "Live Captions" Means Here

This is NOT a static subtitle file burned on screen.

The goal is **TikTok/Shorts-style animated word captions** — where each word pops up one at a time (or in small groups), centered on screen, with a highlight color on the active word. This is what makes reels feel modern and engaging.

The approach:
1. Whisper transcribes the reel audio with **word-level timestamps**
2. A Python script converts those word timestamps into an **ASS subtitle file** (Advanced SubStation Alpha — a subtitle format that supports per-word styling, animations, and positioning)
3. FFmpeg burns the ASS file into the video using the `ass` filter

ASS is used over SRT here because SRT has no support for per-word timing or animation. ASS handles all of that natively.

---

## Phase C1 — Caption Bootstrap

**Goal:** Create the captioning module structure and a watcher that monitors the reels folder.

**Files to create:**
- `pipelines/caption_pipeline/__init__.py`
- `pipelines/caption_pipeline/pipeline.py`
- `pipelines/caption_pipeline/reel_watcher.py`

**Tasks:**

1. Create `reel_watcher.py`:
   - Uses `watchdog` (already used by the main watcher) to monitor `output/videos/reels/`
   - Triggers on new `.mp4` files that do NOT already have a `_captioned` suffix (to avoid reprocessing)
   - Calls `caption_pipeline.pipeline.run(reel_path)` for each new file
   - Ignores files inside `output/videos/reels/captioned/` (that's the output subfolder — never watch it)

2. Wire `reel_watcher.py` into `main.py` alongside the existing watcher:
   - Both watchers run concurrently using Python threads (same pattern as the existing watcher)
   - If `ENABLE_CAPTION_PIPELINE` is `False` in settings, skip starting this watcher entirely

3. Create `pipeline.py` with `run(reel_path: str) -> str`:
   - Skeleton only for now — logs the reel path, returns early
   - Will be filled in Phase C3

4. Add to `config/settings.py`:
   ```python
   ENABLE_CAPTION_PIPELINE = True
   CAPTION_STYLE = "highlight"       # highlight | word_by_word | block
   CAPTION_FONT = "Arial"
   CAPTION_FONT_SIZE = 18            # base font size (pt), scaled to video height later
   CAPTION_COLOR = "&H00FFFFFF"      # ASS color format: white
   CAPTION_HIGHLIGHT_COLOR = "&H0000FFFF"  # yellow highlight on active word
   CAPTION_POSITION = "bottom"       # bottom | center | top
   CAPTION_MAX_WORDS_PER_LINE = 4    # how many words appear on screen at once
   CAPTION_OUTLINE = True            # black outline for readability
   CAPTION_SHADOW = True
   ```

5. Add to DB (new table, not the jobs table — reels aren't tracked there):
   - Create a new table `reel_jobs` in `orchestrator/database.py`:
     ```sql
     CREATE TABLE IF NOT EXISTS reel_jobs (
       id INTEGER PRIMARY KEY AUTOINCREMENT,
       reel_path TEXT NOT NULL,
       captioned_path TEXT,
       status TEXT DEFAULT 'PENDING',
       error TEXT,
       created_at TEXT,
       completed_at TEXT
     );
     ```

**Test:** Drop a `.mp4` into `output/videos/reels/`. Confirm the watcher fires and logs the file path. Confirm no crash.

---

## Phase C2 — Whisper Word-Level Transcription for Reels

**Goal:** Re-use and extend the existing `transcriber.py` to produce word-level timestamps suitable for caption animation.

**Files to modify:**
- `pipelines/video_pipeline/transcriber.py`

**Files to create:**
- `pipelines/caption_pipeline/caption_transcriber.py`

**Tasks:**

1. Create `caption_transcriber.py` — a thin wrapper around the existing Whisper transcriber, tuned for caption needs:

   ```python
   def transcribe_for_captions(reel_path: str) -> list[dict]:
       ...
   ```

   - Extracts audio from the reel using `ffmpeg_utils.extract_audio()` into a temp WAV
   - Calls the existing `transcriber.transcribe(wav_path, word_timestamps=True)`
   - Returns a flat list of word objects (not segments):
     ```json
     [
       { "word": "Let's",  "start": 0.20, "end": 0.50 },
       { "word": "go",     "start": 0.52, "end": 0.70 },
       { "word": "headshot", "start": 0.72, "end": 1.10 }
     ]
     ```
   - Strips leading/trailing whitespace from each word
   - Merges consecutive words that Whisper splits weirdly (e.g. "don" + "'t" → "don't") — check for words starting with `'` or `-`

2. Edge cases:
   - If the reel has no speech (e.g. pure music or sound effects) → return empty list and log a warning, do not crash
   - If a word's `start == end` (Whisper occasionally produces this) → set `end = start + 0.1`

3. Config: use the same `WHISPER_MODEL_SIZE` setting from `config/settings.py`. No new setting needed.

**Test:** Run `caption_transcriber.py` standalone on a reel file. Print all words with timestamps in order. Verify no duplicate or empty entries.

---

## Phase C3 — ASS File Generation

**Goal:** Convert the flat word list into a properly formatted ASS subtitle file with per-word animation.

**Files to create:**
- `pipelines/caption_pipeline/ass_builder.py`

**Why ASS over SRT or WebVTT:**
SRT only supports basic text with line breaks. ASS supports: per-character timing, font size/color/outline per word, screen positioning with pixel precision, inline overrides for active-word highlighting. It is the correct tool for this.

**Tasks:**

1. Write `build_ass(words: list[dict], video_width: int, video_height: int, style_config: dict) -> str`:

   Returns the full content of a `.ass` file as a string.

2. ASS file structure to generate:

   ```
   [Script Info]
   ScriptType: v4.00+
   PlayResX: {video_width}
   PlayResY: {video_height}

   [V4+ Styles]
   Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Italic, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV
   Style: Default,{font},{font_size},{color},&H00000000,&H00000000,0,0,1,2,1,2,10,10,{margin_v}

   [Events]
   Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
   ```

3. Caption grouping logic — `group_words_into_lines(words, max_words_per_line) -> list[list[dict]]`:

   - Groups words into display chunks of `CAPTION_MAX_WORDS_PER_LINE` words
   - Each chunk appears on screen from the start of its first word to the end of its last word
   - Within the chunk's display window, each word gets highlighted as it is spoken

4. For each word group, generate ONE `Dialogue` line per word (not per group):

   ```
   Dialogue: 0,{start},{end},Default,,0,0,0,,{text_with_inline_overrides}
   ```

   Where `{text_with_inline_overrides}` renders the full group with the current word highlighted:

   ```
   {\c&H00FFFFFF&}Let's {\c&H0000FFFF&}go {\c&H00FFFFFF&}headshot
   ```

   - `\c&H0000FFFF&` = yellow (active word)
   - `\c&H00FFFFFF&` = white (inactive words in the group)
   - This means for a 4-word group, you generate 4 Dialogue lines, each showing the group but shifting the highlight to the next word

5. Positioning:
   - `CAPTION_POSITION = "bottom"` → `Alignment=2` (bottom center), `MarginV` = 8% of video height
   - `CAPTION_POSITION = "center"` → `Alignment=5` (middle center)
   - `CAPTION_POSITION = "top"` → `Alignment=8` (top center), `MarginV` = 8% of video height

6. Font size scaling:
   - Base font size from `CAPTION_FONT_SIZE` setting assumes 1080p
   - Scale: `actual_size = int(CAPTION_FONT_SIZE * (video_height / 1080))`
   - This keeps captions proportional on 720p, 4K, or vertical video (1920x1080 rotated)

7. Write `save_ass(content: str, output_path: str) -> str`:
   - Writes the ASS content to the given path
   - Returns the path

8. ASS timestamp format: `H:MM:SS.cc` (centiseconds, not milliseconds)
   - Write a helper `seconds_to_ass_time(sec: float) -> str`

**Test:** Generate an ASS file from a mocked 10-word word list. Open it in VLC or Aegisub to visually verify word highlighting steps through correctly.

---

## Phase C4 — FFmpeg Caption Burn-in

**Goal:** Burn the ASS file into the reel video using FFmpeg, producing a final captioned MP4.

**Files to create:**
- `pipelines/caption_pipeline/caption_burner.py`

**Tasks:**

1. Write `burn_captions(reel_path: str, ass_path: str, output_path: str) -> str`:

   FFmpeg command:
   ```
   ffmpeg -i input.mp4 -vf "ass=captions.ass" -c:v libx264 -crf 18 -c:a copy output_captioned.mp4
   ```

   - `-crf 18` = high quality re-encode (captions require re-encoding, stream copy won't work)
   - `-c:a copy` = copy audio unchanged (no re-encode of audio)
   - Use `subprocess.run()` with `check=True` and capture stderr for logging

2. Path for the output file:
   ```
   output/videos/reels/captioned/{original_stem}_captioned.mp4
   ```
   Create the `captioned/` subfolder if it doesn't exist.

3. Handle re-encode failure:
   - If FFmpeg exits non-zero, log the stderr output
   - Raise `CaptionPipelineError(message, recoverable=False)`

4. After successful burn:
   - Delete the temp `.ass` file (it was only needed for FFmpeg)
   - Delete the temp `.wav` file extracted for Whisper
   - Update `reel_jobs` DB row: `status = DONE`, `captioned_path = output_path`, `completed_at = now`

**Test:** Burn captions onto a short test reel. Verify the output plays in VLC with animated word highlighting. Check that timing matches the audio.

---

## Phase C5 — Full Caption Pipeline Integration

**Goal:** Connect all caption components into the `run()` function in `pipeline.py`.

**Update `pipelines/caption_pipeline/pipeline.py`:**

```
run(reel_path)
  │
  ├── Insert reel_jobs row (status = IN_PROGRESS)
  ├── caption_transcriber.transcribe_for_captions()    → word list
  │     └── if empty words → mark DONE with note "no speech", return
  │
  ├── ffmpeg_utils.probe_video()                        → width, height
  ├── ass_builder.build_ass()                           → ASS content string
  ├── ass_builder.save_ass()                            → temp/reel_name.ass
  │
  ├── caption_burner.burn_captions()                    → captioned MP4
  │
  └── cleanup temp files → update DB → log DONE
```

Error handling:
- Wrap each step in try/except `CaptionPipelineError`
- `recoverable=False` errors → set `status = FAILED`, log, return
- Do not delete the original reel under any circumstance

**Test:** Drop a reel into `output/videos/reels/`. Watch the full pipeline run. Confirm `output/videos/reels/captioned/` contains the output and the `reel_jobs` DB row is `DONE`.

---

## Caption Style Modes

Controlled by `CAPTION_STYLE` in `settings.py`. All three use ASS — only the grouping and animation logic differs.

| Mode | Behaviour | Best For |
|---|---|---|
| `highlight` | Full group visible, active word turns yellow | General use — feels natural |
| `word_by_word` | Only the current word is visible, others hidden | High energy / dramatic effect |
| `block` | Full group appears all at once, no word highlight | Quick to generate, plain look |

Implement `highlight` first. Add `word_by_word` and `block` as alternate code paths in `ass_builder.py` behind a mode switch.

---

## Output Folder Structure

```
output/
└── videos/
    └── reels/
        ├── valorant_job42_reel.mp4           ← original reel (untouched)
        └── captioned/
            └── valorant_job42_reel_captioned.mp4
```

The original reel is **never modified or deleted.** The captioned version is always a new file.

---

## New Settings Reference

Add to `config/settings.py` under a `CAPTION_PIPELINE` section:

```python
ENABLE_CAPTION_PIPELINE = True
CAPTION_STYLE = "highlight"           # highlight | word_by_word | block
CAPTION_FONT = "Arial"
CAPTION_FONT_SIZE = 18                # pt at 1080p — auto-scaled to actual resolution
CAPTION_COLOR = "&H00FFFFFF"          # ASS hex: white
CAPTION_HIGHLIGHT_COLOR = "&H0000FFFF"  # ASS hex: yellow
CAPTION_POSITION = "bottom"           # bottom | center | top
CAPTION_MAX_WORDS_PER_LINE = 4
CAPTION_OUTLINE = True
CAPTION_SHADOW = True
CAPTION_CRF = 18                      # FFmpeg quality (lower = better, larger file)
```

---

## New DB Table

```sql
CREATE TABLE IF NOT EXISTS reel_jobs (
  id               INTEGER PRIMARY KEY AUTOINCREMENT,
  reel_path        TEXT NOT NULL,
  captioned_path   TEXT,
  status           TEXT DEFAULT 'PENDING',
  error            TEXT,
  word_count       INTEGER,
  created_at       TEXT,
  completed_at     TEXT
);
```

---

## Dependencies to Add to `requirements.txt`

No new pip packages required — everything needed is already in the stack:

- `openai-whisper` — already required by Phase 3
- `ffmpeg-python` — already required by Phase 3
- `watchdog` — already used by the main watcher

The only new binary dependency is FFmpeg supporting the `ass` filter — this is included in standard FFmpeg builds and requires no separate install.

---

## Implementation Order

| Phase | Priority | Depends On |
|---|---|---|
| C1 Bootstrap + Watcher | High | Phase 4.3 (reel assembler) |
| C2 Word Transcription | High | C1 |
| C3 ASS Builder | High | C2 |
| C4 FFmpeg Burn-in | High | C3 |
| C5 Integration | High | C1–C4 |
| `word_by_word` style | Medium | C3 |
| `block` style | Low | C3 |

---

## Error Handling Contract

Raise `CaptionPipelineError(message, recoverable: bool)` for all failures.

- Whisper fails → `recoverable=False` (can't caption without words)
- ASS build fails → `recoverable=False`
- FFmpeg burn fails → `recoverable=False`, but original reel stays untouched
- No speech detected → NOT an error — set status `DONE` with note, skip captioning

---

## Test Scripts

```
test_caption_mocked.py --self-contained
```
- Uses a synthetic word list (no real Whisper call)
- Generates an ASS file
- Burns it onto a synthetic black video (generated by FFmpeg)
- Verifies output file exists and duration matches input

```
test_caption_live.py "D:\path\to\reel.mp4"
```
- Runs the full pipeline on a real reel file
- Prints detected words + timestamps before burning

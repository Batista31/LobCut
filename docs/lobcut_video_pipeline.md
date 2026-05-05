# LobCut — Video Pipeline Implementation Plan

**Stack:** FFmpeg · OpenAI Whisper · Google Gemini 1.5 Flash · Librosa
**Target output folder:** `output/videos/`
**Context:** Phases 0–2 (image pipeline) are complete. This document covers Phases 3 and 4 of LobCut, focused entirely on the video pipeline.

---

## Overview

The video pipeline does three things in sequence:

1. **Understand the video** — transcribe audio, extract audio signals, detect game genre
2. **Find key moments** — use genre-aware heuristics + audio analysis to timestamp highlights
3. **Produce clips** — cut, subtitle, and export highlight clips via FFmpeg

Each phase below is meant to be implemented and tested independently before moving to the next.

---

## Phase 3 — Core Video Pipeline

### Phase 3.0 — Video Pipeline Bootstrap

**Goal:** Wire the existing watcher/router into a working (but hollow) video pipeline skeleton.

**Files to create:**
- `pipelines/video_pipeline/pipeline.py`
- `pipelines/video_pipeline/__init__.py`

**Tasks:**

1. Create `pipeline.py` with a single entry function `run(job_id, source_path)` that mirrors the image pipeline contract.
2. The function should:
   - Copy the source video to `temp/`
   - Log the start of processing
   - Update the job row to `IN_PROGRESS`
   - Return early with a `NOT_IMPLEMENTED` status for now
3. Wire `orchestrator/router.py` to call `video_pipeline.pipeline.run()` when a `VIDEO` job is created. (Currently the video pipeline call is likely a stub or missing.)
4. Add video-specific DB columns to `orchestrator/database.py`:
   - `transcript` (TEXT)
   - `game_genre` (TEXT)
   - `game_title` (TEXT)
   - `highlight_timestamps` (TEXT — JSON array)
   - `clip_paths` (TEXT — JSON array)
   - `audio_stats` (TEXT — JSON object)
   - `video_duration` (REAL)

**Test:** Drop a video into `input/videos/`. Confirm a DB row is created with `IN_PROGRESS` then transitions to `NOT_IMPLEMENTED`. No crash.

---

### Phase 3.1 — FFmpeg Probe + Audio Extraction

**Goal:** Extract basic video metadata and a clean audio track from any incoming video.

**Files to create:**
- `pipelines/video_pipeline/ffmpeg_utils.py`

**Tasks:**

1. Write `probe_video(path) -> dict` using `ffprobe` (bundled with FFmpeg):
   - Returns: `duration`, `width`, `height`, `fps`, `has_audio`, `codec`, `size_bytes`
   - Use `subprocess` with JSON output (`-print_format json -show_streams -show_format`)
   - If ffprobe fails, raise a descriptive `VideoPipelineError`

2. Write `extract_audio(video_path, output_wav_path) -> str`:
   - Uses FFmpeg to extract audio as a 16kHz mono WAV (required by Whisper)
   - Command: `ffmpeg -i input -vn -ar 16000 -ac 1 -f wav output.wav`
   - Raises `VideoPipelineError` if extraction fails or file is silent/empty

3. Write `extract_frames(video_path, output_dir, interval_seconds=30) -> list[str]`:
   - Extracts one frame every N seconds as JPEG
   - Used later by Gemini for visual game detection
   - Returns list of frame file paths

4. Write `cut_clip(source_path, start_sec, end_sec, output_path) -> str`:
   - Cuts a clip using stream copy (no re-encode, fast)
   - Falls back to re-encode if stream copy fails (e.g. non-keyframe start)
   - Returns the output path

**Test:** Run `ffmpeg_utils.py` standalone on a sample video. Print the probe dict, confirm WAV is extracted, confirm frames folder has images.

---

### Phase 3.2 — Whisper Transcription

**Goal:** Transcribe the video's audio track into a word-level timestamped transcript.

**Files to create:**
- `pipelines/video_pipeline/transcriber.py`

**Tasks:**

1. Install: `openai-whisper` via pip (not the API — local model)

2. Write `transcribe(wav_path, model_size="base") -> dict`:
   - Loads the Whisper model (cache it — don't reload on every call)
   - Runs `model.transcribe(wav_path, word_timestamps=True)`
   - Returns a structured dict:
     ```json
     {
       "full_text": "...",
       "language": "en",
       "segments": [
         {
           "start": 12.4,
           "end": 15.1,
           "text": "Let's go, headshot!",
           "words": [...]
         }
       ]
     }
     ```

3. Handle edge cases:
   - Silent audio → return empty transcript, do not crash
   - Short clips (<5s) → return transcript as-is
   - Non-English → Whisper auto-detects; store detected language in DB

4. Config: add `WHISPER_MODEL_SIZE` to `config/settings.py` (default: `"base"`). Larger = slower but better. Let the user tune it.

**Test:** Run `transcriber.py` standalone on the extracted WAV. Print the full_text and first 3 segments with timestamps.

---

### Phase 3.3 — Librosa Audio Analysis

**Goal:** Extract audio signal features that reveal excitement, volume spikes, sudden silences, and energy bursts — the raw material for highlight detection.

**Files to create:**
- `pipelines/video_pipeline/audio_analyzer.py`

**Tasks:**

1. Install: `librosa`, `numpy`, `scipy`

2. Write `analyze_audio(wav_path) -> dict` that computes:

   - **RMS energy over time** (`librosa.feature.rms`): rolling loudness at ~0.5s resolution
   - **Onset strength** (`librosa.onset.onset_strength`): detects sudden audio events (shots, explosions, goal sounds, etc.)
   - **Silence periods**: segments where RMS drops below a threshold for >2s
   - **Energy spikes**: timestamps where onset strength exceeds `mean + 2 * std`
   - **Spectral centroid**: tracks "brightness" of sound — screams, high-pitched alerts spike this
   - **Zero-crossing rate**: useful for detecting speech vs noise bursts

3. The returned dict must include:
   ```json
   {
     "duration_sec": 312.0,
     "mean_rms": 0.042,
     "rms_timeline": [[0.0, 0.031], [0.5, 0.044], ...],
     "energy_spikes": [45.2, 112.7, 203.4],
     "silence_periods": [[88.0, 91.5], [200.0, 204.1]],
     "onset_timeline": [[0.0, 0.12], [0.5, 0.87], ...]
   }
   ```

4. Normalise all timelines to absolute seconds (not frame indices).

5. Write `find_candidate_moments(audio_stats: dict, top_n=20) -> list[float]`:
   - Returns the top N timestamps (in seconds) ranked by onset strength
   - Applies a **minimum gap** of 10s between candidates to avoid clustering
   - These are raw candidates — genre-aware ranking happens in the next phase

**Test:** Run standalone on a WAV, print the spike list and silence periods. Plot the RMS timeline to a PNG if matplotlib is available (optional, dev-only).

---

### Phase 3.4 — Gemini Game Detection

**Goal:** Use Gemini 1.5 Flash to identify the game being played and classify its genre, so highlight detection can be tuned accordingly.

**Files to create:**
- `pipelines/video_pipeline/game_detector.py`

**Tasks:**

1. Write `detect_game(frame_paths: list[str], transcript_text: str) -> dict`:

   - Send Gemini a prompt combining:
     - Up to 5 sampled frames (spread evenly across the video) as base64 images
     - The first 500 words of the transcript (if available)
   - Request structured JSON back. Prompt must explicitly say "respond ONLY in JSON":

     ```
     You are a video game analyst. Based on the gameplay frames and transcript below,
     identify the game and its genre. Respond ONLY in valid JSON with no explanation:
     {
       "game_title": "string or null",
       "game_genre": "one of: fps, battle_royale, moba, rpg, survival, sandbox, sports, racing, strategy, fighting, puzzle, unknown",
       "confidence": "high | medium | low",
       "genre_notes": "brief string explaining the classification"
     }
     ```

   - Parse and return the JSON. Fall back to `"unknown"` genre if Gemini fails or returns unparseable output.

2. Genre definitions (for prompt and internal use):
   - `fps` — First-person shooter (CS2, Valorant, CoD)
   - `battle_royale` — Large-map survival shooter (Warzone, PUBG, Fortnite)
   - `moba` — Lane-based team game (LoL, Dota 2)
   - `rpg` — Story/exploration game (Elden Ring, Skyrim, Baldur's Gate)
   - `survival` — Crafting/base-building (Minecraft, Rust, Valheim)
   - `sandbox` — Open creative mode (Minecraft creative, Roblox, Dreams)
   - `sports` — Simulated sport (FIFA, Rocket League, NBA 2K)
   - `racing` — Vehicle racing (Forza, F1, iRacing)
   - `strategy` — RTS/turn-based (Age of Empires, Chess, Civ)
   - `fighting` — 1v1 combat (Tekken, Street Fighter, Mortal Kombat)
   - `puzzle` — Logic/casual (Tetris, Portal, Among Us)

3. Cache the result in the DB row (`game_genre`, `game_title`) so it doesn't re-run on retry.

**Test:** Run standalone on 5 frames from a known game. Verify genre comes back correctly.

---

### Phase 3.5 — Genre-Aware Highlight Detection

**Goal:** Use the game genre + audio analysis + transcript to score and rank candidate moments into real highlights.

**Files to create:**
- `pipelines/video_pipeline/highlight_detector.py`

**Tasks:**

1. Write `score_moments(candidates: list[float], audio_stats: dict, transcript: dict, genre: str) -> list[dict]`:

   - Each candidate gets a score from 0–100 composed of:
     - **Audio energy score** (weight: 40%) — onset strength at this timestamp vs. mean
     - **Transcript keyword score** (weight: 35%) — does the transcript near this moment contain genre-relevant keywords?
     - **Silence-break bonus** (weight: 15%) — did a silence period just end? Suggests a dramatic pause before action
     - **Spectral spike bonus** (weight: 10%) — sudden brightness spike (screaming, explosions)

2. Genre-specific keyword sets (used for transcript keyword scoring):

   | Genre | High-value keywords |
   |---|---|
   | `fps` | kill, headshot, ace, clutch, snipe, down, out, let's go, ez |
   | `battle_royale` | knocked, third party, circle, final circle, winner winner, last squad |
   | `moba` | first blood, pentakill, baron, dragon, surrender, gg, tower |
   | `rpg` | boss, rare drop, level up, quest complete, died, checkpoint |
   | `survival` | raid, boom, found, base, creeper, explosion, hostile |
   | `sandbox` | build, done, look at this, finished, finally |
   | `sports` | goal, save, miss, penalty, foul, overtime, winner |
   | `racing` | overtake, crash, pit stop, fastest lap, podium |
   | `strategy` | attacked, rush, GG, economy, tech, wonder |
   | `fighting` | perfect, ultra, finish him, combo, ko |
   | `puzzle` | solved, failed, nice, wait, got it |

3. Return a ranked list of moments:
   ```json
   [
     {
       "timestamp": 112.4,
       "score": 87,
       "clip_start": 107.4,
       "clip_end": 122.4,
       "reason": "high onset + transcript: 'headshot ace'"
     }
   ]
   ```

   - `clip_start` = `timestamp - 5s` (clamped to 0)
   - `clip_end` = `timestamp + 10s` (clamped to video duration)
   - Default: extract top 5 highlights. Config: `MAX_HIGHLIGHTS` in `settings.py`

4. Write `deduplicate_moments(moments: list[dict], min_gap_sec=15) -> list[dict]`:
   - Removes overlapping clips — keep the higher-scored one if two clips are within `min_gap_sec` of each other

**Test:** Feed in a mocked `audio_stats` and `transcript` for a known genre. Assert ranking order is sensible.

---

### Phase 3.6 — Clip Export

**Goal:** Cut the ranked highlight clips and move them to the correct output folder.

**Files to create:**
- `pipelines/video_pipeline/clip_exporter.py`

**Tasks:**

1. Write `export_clips(source_path: str, moments: list[dict], game_genre: str, game_title: str, job_id: str) -> list[str]`:

   - For each moment, call `ffmpeg_utils.cut_clip()` to cut the segment
   - Output naming: `{game_title or genre}_{job_id}_clip{n}_{timestamp}s.mp4`
   - Output path: `output/videos/{game_genre}/{filename}`
   - Create the genre subfolder if it doesn't exist
   - Returns list of output paths

2. After export, update the DB row:
   - `clip_paths` — JSON list of output paths
   - `highlight_timestamps` — JSON list of `{timestamp, score}` dicts
   - `status` → `DONE`

3. If any clip fails to cut:
   - Log the error
   - Continue with remaining clips (don't fail the whole job)
   - If ALL clips fail, set `status` → `FAILED`

**Test:** Export 2 clips from a test video. Confirm files exist in `output/videos/genre/` and DB row is `DONE`.

---

### Phase 3.7 — Subtitle Generation + Burn-in

**Goal:** Generate `.srt` subtitle files from the Whisper transcript and optionally burn them into the exported clips.

**Files to create:**
- `pipelines/video_pipeline/subtitler.py`

**Tasks:**

1. Write `generate_srt(transcript: dict, output_srt_path: str) -> str`:
   - Converts Whisper's segment list to a valid `.srt` file
   - Timestamps must be in `HH:MM:SS,mmm --> HH:MM:SS,mmm` format
   - Each segment becomes one subtitle entry
   - Returns the path to the written `.srt` file

2. Write `clip_srt(srt_path: str, clip_start: float, clip_end: float, output_srt_path: str) -> str`:
   - Extracts only the subtitle lines that fall within the clip's time window
   - Re-offsets timestamps so they start from `00:00:00,000`
   - Required because the full-video SRT doesn't align to short clips

3. Write `burn_subtitles(clip_path: str, srt_path: str, output_path: str) -> str`:
   - Uses FFmpeg `subtitles` filter to hard-burn the SRT into the video
   - Command: `ffmpeg -i input.mp4 -vf subtitles=subs.srt output_subbed.mp4`
   - Config: `BURN_SUBTITLES` boolean in `settings.py` (default `False` — only generate SRT by default)

4. Save `.srt` files alongside the clip: `output/videos/{genre}/{clip_name}.srt`

**Test:** Generate an SRT from a Whisper transcript dict. Verify timing offsets are correct when clipping a segment.

---

### Phase 3.8 — Full Pipeline Integration

**Goal:** Connect all Phase 3 components into a single `run()` function in `pipeline.py`.

**Tasks:**

Update `pipelines/video_pipeline/pipeline.py` with the full flow:

```
run(job_id, source_path)
  │
  ├── ffmpeg_utils.probe_video()          → video metadata → DB
  ├── ffmpeg_utils.extract_audio()        → temp WAV
  ├── ffmpeg_utils.extract_frames()       → temp JPEG frames
  │
  ├── transcriber.transcribe()            → transcript dict → DB
  ├── audio_analyzer.analyze_audio()      → audio stats → DB
  │
  ├── game_detector.detect_game()         → genre + title → DB
  │
  ├── audio_analyzer.find_candidate_moments()
  ├── highlight_detector.score_moments()
  ├── highlight_detector.deduplicate_moments()
  │
  ├── clip_exporter.export_clips()        → clip files → DB
  ├── subtitler.generate_srt()            → .srt files
  │
  └── cleanup temp WAV, frames, temp video copy
```

Error handling:
- Any step that raises `VideoPipelineError` should catch, log, set `status = FAILED`, and return
- Partial success is allowed: if clip export works but subtitle fails, status is still `DONE`

**Test:** Drop a real gaming video into `input/videos/`. Watch the full pipeline run end-to-end. Verify:
- DB row has genre, transcript snippet, highlight timestamps, clip paths
- Clips exist in `output/videos/{genre}/`
- SRT exists alongside each clip

---

## Phase 4 — Clip Intelligence

### Phase 4.0 — Highlight Scoring Refinement

**Goal:** Improve highlight quality using Gemini to visually re-rank extracted clips.

**Files to create:**
- `pipelines/video_pipeline/clip_ranker.py`

**Tasks:**

1. Write `rerank_clips_with_gemini(clip_paths: list[str], genre: str) -> list[dict]`:
   - For each clip, extract 3 thumbnail frames (start, middle, end)
   - Send to Gemini 1.5 Flash with a prompt:
     ```
     You are a gaming highlight analyst. Given these 3 frames from a {genre} gameplay clip,
     rate the excitement level from 0–10 and give a one-sentence highlight label.
     Respond ONLY in JSON:
     { "excitement_score": 8, "label": "Clutch 1v3 with pistol" }
     ```
   - Merge Gemini's `excitement_score` with the audio-based `score` (weighted average)
   - Re-sort clips by combined score
   - Update DB with final ranked order and labels

2. This step is optional per config: `GEMINI_RERANK_CLIPS` boolean in `settings.py` (default `True`)

**Test:** Run on 3 clips of different intensities. Verify ranking order changes correctly vs. audio-only ranking.

---

### Phase 4.1 — Silence Gap Trimming

**Goal:** Remove dead air from the start and end of each highlight clip.

**Files to modify:**
- `pipelines/video_pipeline/clip_exporter.py`

**Tasks:**

1. Write `trim_silence(clip_path: str, output_path: str, silence_thresh_db=-40, min_silence_sec=1.5) -> str`:
   - Uses FFmpeg `silencedetect` filter to find leading/trailing silence
   - Cuts those segments before finalizing the clip
   - Preserves at least 0.5s of audio before first sound (for feel)
   - If the entire clip is silent, skip trimming and keep the original

2. Call `trim_silence` on each exported clip before saving to the output folder.

3. Add `TRIM_SILENCE` boolean to `settings.py` (default `True`)

**Test:** Create a clip with 3s of silence at the start and end. Confirm those seconds are removed.

---

### Phase 4.2 — Keyword-Triggered Clip Extraction

**Goal:** Let users define custom trigger phrases that automatically extract clips around those moments.

**Files to create:**
- `config/clip_triggers.json`
- `pipelines/video_pipeline/keyword_clipper.py`

**Tasks:**

1. Create `config/clip_triggers.json` with this shape:
   ```json
   {
     "enabled": true,
     "triggers": [
       { "phrase": "let's go", "pre_sec": 3, "post_sec": 8, "label": "hype_moment" },
       { "phrase": "what", "pre_sec": 2, "post_sec": 6, "label": "reaction" },
       { "phrase": "no way", "pre_sec": 2, "post_sec": 6, "label": "reaction" }
     ]
   }
   ```

2. Write `find_keyword_moments(transcript: dict, triggers: list[dict]) -> list[dict]`:
   - Scans transcript segments for each trigger phrase (case-insensitive)
   - Returns a list of `{ timestamp, clip_start, clip_end, label }` dicts
   - Deduplicates with the same min-gap logic from Phase 3.5

3. Merge keyword-triggered clips into the main highlight list before export.
   - Tag them with `source: "keyword"` vs `source: "audio"` in the DB

4. Load `clip_triggers.json` at startup in `config/settings.py`. If file is missing, disable keyword clipping silently.

**Test:** Create a transcript with a known phrase. Verify the correct timestamp and clip window are returned.

---

### Phase 4.3 — Highlight Reel Assembly

**Goal:** Concatenate the top N clips into a single highlight reel video.

**Files to create:**
- `pipelines/video_pipeline/reel_assembler.py`

**Tasks:**

1. Write `assemble_reel(clip_paths: list[str], output_path: str, max_clips=5) -> str`:
   - Takes the top `max_clips` clips (already ranked)
   - Writes an FFmpeg concat list file to `temp/`
   - Runs: `ffmpeg -f concat -safe 0 -i list.txt -c copy reel.mp4`
   - Falls back to re-encode if clips have mismatched codecs/resolutions
   - Returns the reel output path

2. Output location: `output/videos/reels/{game_title or genre}_{job_id}_reel.mp4`

3. Config: `BUILD_HIGHLIGHT_REEL` boolean in `settings.py` (default `True`)
   Config: `MAX_REEL_CLIPS` integer in `settings.py` (default `5`)

4. Update DB: add `reel_path` (TEXT) column, store the reel path on success.

**Test:** Concat 3 pre-cut test clips. Verify the output plays in sequence and duration is correct.

---

## Settings Reference

Add all of the following to `config/settings.py` under a `VIDEO_PIPELINE` section:

```python
WHISPER_MODEL_SIZE = "base"         # tiny | base | small | medium | large
MAX_HIGHLIGHTS = 5                  # max clips to extract per video
MIN_HIGHLIGHT_GAP_SEC = 15          # minimum seconds between highlight start times
CLIP_PRE_BUFFER_SEC = 5             # seconds before detected moment to start clip
CLIP_POST_BUFFER_SEC = 10           # seconds after detected moment to end clip
BURN_SUBTITLES = False              # hard-burn SRT into clip video
TRIM_SILENCE = True                 # trim leading/trailing silence from clips
GEMINI_RERANK_CLIPS = True          # use Gemini visual re-ranking on final clips
BUILD_HIGHLIGHT_REEL = True         # concatenate top clips into a reel
MAX_REEL_CLIPS = 5                  # max clips in the reel
FRAME_SAMPLE_INTERVAL_SEC = 30      # seconds between extracted frames for game detection
```

---

## Database Schema Additions

Run these as migrations or add to the bootstrap in `database.py`:

```sql
ALTER TABLE jobs ADD COLUMN transcript TEXT;
ALTER TABLE jobs ADD COLUMN game_genre TEXT;
ALTER TABLE jobs ADD COLUMN game_title TEXT;
ALTER TABLE jobs ADD COLUMN highlight_timestamps TEXT;   -- JSON array
ALTER TABLE jobs ADD COLUMN clip_paths TEXT;             -- JSON array
ALTER TABLE jobs ADD COLUMN reel_path TEXT;
ALTER TABLE jobs ADD COLUMN audio_stats TEXT;            -- JSON object
ALTER TABLE jobs ADD COLUMN video_duration REAL;
```

---

## Output Folder Structure

```
output/
└── videos/
    ├── fps/
    │   ├── valorant_job42_clip1_112s.mp4
    │   └── valorant_job42_clip1_112s.srt
    ├── rpg/
    │   └── elden_ring_job43_clip1_45s.mp4
    ├── unknown/
    │   └── unknown_job44_clip1_88s.mp4
    └── reels/
        └── valorant_job42_reel.mp4
```

---

## Dependencies to Add to `requirements.txt`

```
openai-whisper
librosa
numpy
scipy
ffmpeg-python
```

> **Note:** FFmpeg binary must be installed separately and available on PATH. `ffmpeg-python` is just the Python wrapper. Whisper also requires `torch` — it will pull it in automatically, but warn the user it may be large.

---

## Implementation Order (Recommended)

| Phase | Priority | Depends On |
|---|---|---|
| 3.0 Bootstrap | High | nothing |
| 3.1 FFmpeg Utils | High | 3.0 |
| 3.2 Whisper | High | 3.1 |
| 3.3 Librosa | High | 3.1 |
| 3.4 Game Detection | High | 3.1 |
| 3.5 Highlight Detection | High | 3.2, 3.3, 3.4 |
| 3.6 Clip Export | High | 3.5 |
| 3.7 Subtitles | Medium | 3.2, 3.6 |
| 3.8 Integration | High | all of 3.x |
| 4.0 Gemini Rerank | Medium | 3.8 |
| 4.1 Silence Trimming | Medium | 3.6 |
| 4.2 Keyword Clips | Low | 3.2 |
| 4.3 Reel Assembly | Low | 3.6 |

---

## Error Handling Contract

Every component must raise `VideoPipelineError(message, recoverable=True/False)` on failure.

- `recoverable=True` → pipeline continues, clip is skipped
- `recoverable=False` → entire job is marked `FAILED`

FFmpeg subprocess failures, missing files, and API errors are all `VideoPipelineError`. Catch `Exception` only at the top-level `run()` function in `pipeline.py`.

---

## Test Scripts

Following the existing pattern, create these in the project root:

- `test_phase3_mocked.py --self-contained` — full video pipeline with a synthetic audio waveform and mocked Gemini (no real API calls)
- `test_phase3_live.py "D:\path\to\video.mp4"` — real video against real Whisper + Gemini
- `test_game_detection.py "D:\path\to\frames_folder"` — isolated game detection smoke test
- `test_highlight_detection.py` — unit test for scoring and deduplication logic with synthetic data

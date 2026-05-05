# LobCut — YouTube Auto-Upload Pipeline

**Scope:** Watch `output/videos/reels/captioned/` for new captioned reels and automatically upload them to YouTube with AI-generated titles, descriptions, tags, and metadata.
**Stack:** YouTube Data API v3 · Google OAuth 2.0 · Gemini 1.5 Flash · Python
**Trigger:** New `_captioned.mp4` file appears in `output/videos/reels/captioned/`
**Context:** Implement this after the Live Captions pipeline (`lobcut_live_captions.md`) is complete and producing `_captioned.mp4` files.

---

## Overview

The upload pipeline does three things:

1. **Generate metadata** — use Gemini to write a YouTube-optimized title, description, and hashtag set based on the game title, genre, transcript, and highlight labels from the DB
2. **Authenticate** — use OAuth 2.0 to get a valid YouTube access token (one-time browser flow, then token is cached)
3. **Upload** — post the video to YouTube using the YouTube Data API v3 resumable upload protocol

This pipeline is intentionally **opt-in and explicit**. It never uploads automatically unless `YOUTUBE_AUTO_UPLOAD = True` is set in settings. Even then, it logs exactly what it is about to upload and to which channel before doing anything.

---

## Phase Y0 — YouTube Pipeline Bootstrap

**Goal:** Set up the module structure, OAuth credentials, and a dry-run upload path.

**Files to create:**
- `pipelines/youtube_pipeline/__init__.py`
- `pipelines/youtube_pipeline/pipeline.py`
- `pipelines/youtube_pipeline/upload_watcher.py`
- `config/youtube_config.json` (gitignored)
- `.env` additions (documented below)

**Tasks:**

1. Create `upload_watcher.py`:
   - Watches `output/videos/reels/captioned/` for new `_captioned.mp4` files
   - Triggers `pipeline.run(captioned_path)` for each new file
   - Skips any file that already has a `youtube_upload` DB record with `status = DONE`
   - Add to `main.py` alongside the other watchers, controlled by `YOUTUBE_AUTO_UPLOAD` setting

2. Create `pipeline.py` with `run(captioned_path: str) -> dict`:
   - Skeleton only — logs the file path, returns early in dry-run mode

3. Add to `.env` (document in `.env.example`):
   ```env
   YOUTUBE_CLIENT_ID=your_oauth_client_id
   YOUTUBE_CLIENT_SECRET=your_oauth_client_secret
   ```
   These come from Google Cloud Console → Credentials → OAuth 2.0 Client ID (Desktop app type).

4. Create `config/youtube_config.json` — stores the cached OAuth token after first auth. **Add to `.gitignore` immediately.** Shape:
   ```json
   {
     "access_token": "...",
     "refresh_token": "...",
     "token_expiry": "2025-01-01T00:00:00Z",
     "channel_id": "UC..."
   }
   ```

5. Add to `config/settings.py`:
   ```python
   YOUTUBE_AUTO_UPLOAD = False       # must be explicitly set True to enable uploads
   YOUTUBE_DRY_RUN = True            # if True, generate metadata but do not upload
   YOUTUBE_PRIVACY = "private"       # private | unlisted | public
   YOUTUBE_CATEGORY_ID = "20"        # 20 = Gaming
   YOUTUBE_DEFAULT_LANGUAGE = "en"
   YOUTUBE_NOTIFY_SUBSCRIBERS = False
   YOUTUBE_MADE_FOR_KIDS = False
   ```

6. Add a new DB table `youtube_uploads`:
   ```sql
   CREATE TABLE IF NOT EXISTS youtube_uploads (
     id                INTEGER PRIMARY KEY AUTOINCREMENT,
     captioned_path    TEXT NOT NULL,
     reel_job_id       INTEGER,
     job_id            INTEGER,
     youtube_video_id  TEXT,
     title             TEXT,
     description       TEXT,
     tags              TEXT,       -- JSON array
     privacy           TEXT,
     status            TEXT DEFAULT 'PENDING',
     error             TEXT,
     created_at        TEXT,
     uploaded_at       TEXT
   );
   ```

**Test:** Set `YOUTUBE_DRY_RUN = True`. Drop a captioned file in the watched folder. Confirm the watcher fires and the pipeline logs the file path without making any API call.

---

## Phase Y1 — OAuth 2.0 Authentication

**Goal:** Implement a one-time browser-based OAuth flow that saves a refresh token for all future uploads.

**Files to create:**
- `pipelines/youtube_pipeline/auth.py`

**How YouTube OAuth works for a local app:**
- You register your app in Google Cloud Console and get a `client_id` + `client_secret`
- On first run, the app opens a browser to Google's auth page
- The user grants permission
- Google redirects to `localhost` with an authorization code
- The app exchanges the code for an `access_token` and `refresh_token`
- The `refresh_token` is saved — it never expires (unless revoked)
- On all future runs, the `access_token` is refreshed silently using the `refresh_token`

**Tasks:**

1. Install: `google-auth`, `google-auth-oauthlib`, `google-api-python-client`

2. Write `authenticate() -> Credentials`:
   - Loads `config/youtube_config.json` if it exists
   - If the access token is still valid → return cached credentials
   - If expired → use `google.oauth2.credentials.Credentials.refresh()` with the stored `refresh_token`
   - If no token file exists → run the full OAuth flow:
     - Build `flow = InstalledAppFlow.from_client_config(client_config, scopes=["https://www.googleapis.com/auth/youtube.upload"])`
     - Call `flow.run_local_server(port=0)` — this opens the browser automatically
     - Save the resulting credentials to `config/youtube_config.json`
   - Return the valid `Credentials` object

3. Write `get_youtube_client(credentials) -> Resource`:
   - Returns a `googleapiclient.discovery.build("youtube", "v3", credentials=credentials)` client
   - Cache this client for the process lifetime

4. Write `revoke_token()`:
   - Deletes `config/youtube_config.json`
   - Logs that the user must re-authenticate on next run
   - Used for manual token reset if something goes wrong

5. Add a standalone auth script at project root: `authenticate_youtube.py`
   - Just calls `auth.authenticate()` and prints the channel name to confirm it worked
   - Run this once manually before enabling auto-upload

**Test:** Run `authenticate_youtube.py`. Complete the browser flow. Confirm `config/youtube_config.json` is created. Run it again — confirm it uses the cached token without opening a browser.

---

## Phase Y2 — Metadata Generation with Gemini

**Goal:** Use Gemini 1.5 Flash to generate a YouTube-optimized title, description, and hashtag set for each reel.

**Files to create:**
- `pipelines/youtube_pipeline/metadata_generator.py`

**Tasks:**

1. Write `generate_metadata(game_title: str, game_genre: str, transcript_snippet: str, highlight_labels: list[str], clip_count: int) -> dict`:

   Pull these values from the DB by looking up the `job_id` linked to the reel via the existing `jobs` table.

   Gemini prompt (ask for JSON only):
   ```
   You are a YouTube gaming content strategist. Generate upload metadata for a highlight reel.

   Game: {game_title or "Unknown game"}
   Genre: {game_genre}
   Clip count: {clip_count}
   Highlight moments: {highlight_labels joined by ", "}
   Transcript excerpt: {first 200 words of transcript}

   Respond ONLY in valid JSON with no explanation or markdown:
   {
     "title": "string, max 100 chars, punchy and click-worthy",
     "description": "string, 3-5 sentences, include game name and what happens. End with a call to action.",
     "tags": ["array", "of", "10-15", "strings", "no", "hashtag", "prefix"],
     "hashtags": ["Gaming", "Highlights", "{GameTitle}", "{Genre}"],
     "category_hint": "string explaining why this fits YouTube Gaming"
   }
   ```

2. Post-process the response:
   - Enforce title max length of 100 chars (truncate with `...` if needed)
   - Strip any `#` from tags (YouTube API takes tags without `#`)
   - Merge `tags` and `hashtags` into a single deduplicated list (YouTube treats them the same in the API)
   - Cap total tags at 500 characters total (YouTube API limit)

3. Build the final description string:
   ```
   {description from Gemini}

   ─────────────────────────
   🎮 Game: {game_title}
   🏷️ Genre: {game_genre}
   ⚡ Highlights: {highlight_labels joined by " · "}
   ─────────────────────────
   {hashtags joined by " " with # prefix}
   ```

4. If Gemini fails or returns unparseable JSON:
   - Fall back to a template:
     - Title: `"{game_title} Highlights — Best Moments"`
     - Description: `"Gameplay highlights from {game_title}. Auto-generated by LobCut."`
     - Tags: `[game_title, game_genre, "gaming", "highlights", "gameplay"]`
   - Log the fallback so the user knows metadata is basic

5. Write `save_metadata_preview(metadata: dict, output_path: str)`:
   - Saves the generated metadata as a human-readable `.txt` file alongside the captioned video
   - Location: `output/videos/reels/captioned/{stem}_metadata.txt`
   - Always write this file — even in dry-run mode — so the user can review what would be uploaded

**Test:** Call `generate_metadata()` with mocked inputs. Print the output. Verify title is ≤100 chars, tags have no `#`, and description ends with hashtags.

---

## Phase Y3 — YouTube Upload

**Goal:** Upload the captioned reel to YouTube using the resumable upload API.

**Files to create:**
- `pipelines/youtube_pipeline/uploader.py`

**Why resumable upload:** Gaming reels can be large (100MB+). Resumable upload lets the upload restart from where it left off if the connection drops, instead of starting over.

**Tasks:**

1. Install: `google-api-python-client` (already in Phase Y1)

2. Write `upload_video(youtube_client, video_path: str, metadata: dict, settings: dict) -> str`:

   Build the video resource:
   ```python
   body = {
     "snippet": {
       "title": metadata["title"],
       "description": metadata["description"],
       "tags": metadata["tags"],
       "categoryId": settings["YOUTUBE_CATEGORY_ID"],
       "defaultLanguage": settings["YOUTUBE_DEFAULT_LANGUAGE"]
     },
     "status": {
       "privacyStatus": settings["YOUTUBE_PRIVACY"],
       "selfDeclaredMadeForKids": settings["YOUTUBE_MADE_FOR_KIDS"],
       "notifySubscribers": settings["YOUTUBE_NOTIFY_SUBSCRIBERS"]
     }
   }
   ```

   Execute the resumable upload:
   ```python
   media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True, chunksize=5 * 1024 * 1024)
   request = youtube_client.videos().insert(part="snippet,status", body=body, media_body=media)

   response = None
   while response is None:
       status, response = request.next_chunk()
       if status:
           percent = int(status.progress() * 100)
           log(f"Upload progress: {percent}%")

   return response["id"]   # YouTube video ID
   ```

3. After successful upload:
   - Log the YouTube URL: `https://www.youtube.com/watch?v={video_id}`
   - Update `youtube_uploads` DB row: `status = DONE`, `youtube_video_id = video_id`, `uploaded_at = now`
   - Write a `.txt` receipt file: `output/videos/reels/captioned/{stem}_uploaded.txt` with the video URL and upload time

4. Handle upload errors:
   - `HttpError 403` → quota exceeded or auth issue → raise `YouTubePipelineError("Quota or auth error", recoverable=False)`
   - `HttpError 400` → bad metadata (title too long, invalid chars) → raise with the API error message
   - Network timeout mid-upload → the resumable upload resumes automatically on retry; log the interruption
   - Any other exception → set DB row to `FAILED`, log, do not crash the watcher

5. If `YOUTUBE_DRY_RUN = True`:
   - Skip the actual upload entirely
   - Log `[DRY RUN] Would upload: {title}`
   - Still write the metadata preview `.txt` file
   - Set DB row status to `DRY_RUN`

**Test:** Set `YOUTUBE_PRIVACY = "private"` and `YOUTUBE_DRY_RUN = False`. Upload a short test clip. Confirm the video appears in YouTube Studio as private. Confirm the DB row has the video ID. Confirm the receipt `.txt` file is written.

---

## Phase Y4 — Full Upload Pipeline Integration

**Goal:** Connect all YouTube components into the `run()` function in `pipeline.py`.

**Update `pipelines/youtube_pipeline/pipeline.py`:**

```
run(captioned_path)
  │
  ├── Look up reel_job in DB by captioned_path → get job_id
  ├── Look up jobs row by job_id → get game_title, game_genre, transcript, highlight_labels
  ├── Insert youtube_uploads row (status = IN_PROGRESS)
  │
  ├── metadata_generator.generate_metadata()       → title, description, tags
  ├── metadata_generator.save_metadata_preview()   → _metadata.txt file
  │
  ├── [if YOUTUBE_DRY_RUN] → log, set status = DRY_RUN, return
  │
  ├── auth.authenticate()                          → credentials
  ├── auth.get_youtube_client()                    → youtube API client
  │
  ├── uploader.upload_video()                      → youtube_video_id
  │
  └── update DB → write receipt file → log DONE
```

**Test:** Run the full pipeline end-to-end with `YOUTUBE_PRIVACY = "private"`. Verify the complete flow from file detection to YouTube Studio confirmation.

---

## Google Cloud Console Setup (One-Time Manual Step)

Document this clearly in a `docs/youtube_setup.md` file for the user:

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Create a new project (or use an existing one)
3. Enable the **YouTube Data API v3**
4. Go to **Credentials** → **Create Credentials** → **OAuth 2.0 Client ID**
5. Application type: **Desktop app**
6. Download the JSON — copy `client_id` and `client_secret` into `.env`
7. Go to **OAuth consent screen** → add your Google account as a **Test User** (required while the app is in testing mode)
8. Run `authenticate_youtube.py` once to complete the browser flow and cache the token

**Note:** The app stays in "testing" mode indefinitely for personal use. You do not need to submit it for Google verification unless you plan to give this tool to other users.

---

## Output Files Per Upload

```
output/
└── videos/
    └── reels/
        └── captioned/
            ├── valorant_job42_reel_captioned.mp4      ← input to this pipeline
            ├── valorant_job42_reel_metadata.txt       ← always written (review before upload)
            └── valorant_job42_reel_uploaded.txt       ← written after successful upload
```

Contents of `_uploaded.txt`:
```
YouTube Upload Receipt
──────────────────────
Video ID:   dQw4w9WgXcQ
URL:        https://www.youtube.com/watch?v=dQw4w9WgXcQ
Title:      Valorant Clutch Highlights — Insane 1v5
Privacy:    private
Uploaded:   2025-06-01 14:32:11
```

---

## Settings Reference

Add to `config/settings.py` under a `YOUTUBE_PIPELINE` section:

```python
YOUTUBE_AUTO_UPLOAD = False           # master switch — must be True to enable
YOUTUBE_DRY_RUN = True                # generate metadata but skip actual upload
YOUTUBE_PRIVACY = "private"           # private | unlisted | public
YOUTUBE_CATEGORY_ID = "20"            # 20 = Gaming (see YouTube category list)
YOUTUBE_DEFAULT_LANGUAGE = "en"
YOUTUBE_NOTIFY_SUBSCRIBERS = False    # don't ping subscribers for every auto-upload
YOUTUBE_MADE_FOR_KIDS = False
YOUTUBE_UPLOAD_CHUNK_SIZE_MB = 5      # resumable upload chunk size
```

---

## New DB Table

```sql
CREATE TABLE IF NOT EXISTS youtube_uploads (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  captioned_path    TEXT NOT NULL,
  reel_job_id       INTEGER,
  job_id            INTEGER,
  youtube_video_id  TEXT,
  title             TEXT,
  description       TEXT,
  tags              TEXT,
  privacy           TEXT,
  status            TEXT DEFAULT 'PENDING',
  error             TEXT,
  created_at        TEXT,
  uploaded_at       TEXT
);
```

---

## Dependencies to Add to `requirements.txt`

```
google-auth
google-auth-oauthlib
google-api-python-client
```

---

## Implementation Order

| Phase | Priority | Depends On |
|---|---|---|
| Y0 Bootstrap + Watcher | High | Caption pipeline complete |
| Y1 OAuth Auth | High | Y0 |
| Y2 Metadata Generator | High | Y0 |
| Y3 Uploader | High | Y1, Y2 |
| Y4 Integration | High | Y1–Y3 |
| `docs/youtube_setup.md` | High | Y0 |

---

## Error Handling Contract

Raise `YouTubePipelineError(message, recoverable: bool)` for all failures.

- Auth failure → `recoverable=False` (can't upload without credentials)
- Metadata Gemini failure → `recoverable=True` (fall back to template metadata, continue upload)
- Upload HTTP 403/quota → `recoverable=False` (likely a daily quota issue — retry tomorrow)
- Upload network timeout → `recoverable=True` (resumable upload will continue on next attempt)
- Upload HTTP 400 → `recoverable=False` (bad metadata — log the full error for the user to fix)

---

## Security Notes

- `config/youtube_config.json` must be in `.gitignore` — it contains live OAuth tokens
- `YOUTUBE_CLIENT_ID` and `YOUTUBE_CLIENT_SECRET` stay in `.env` — never hardcode them
- Set `YOUTUBE_PRIVACY = "private"` during all testing — change to `"public"` only when confident
- If a token is ever exposed, revoke it immediately in Google Cloud Console → Credentials, then run `revoke_token()` and re-authenticate

---

## Test Scripts

```
authenticate_youtube.py
```
One-time auth script. Prints the channel name to confirm success.

```
test_youtube_dry_run.py "D:\path\to\captioned_reel.mp4"
```
Runs the full pipeline with `YOUTUBE_DRY_RUN = True`. Prints the generated metadata. Writes the `_metadata.txt` file. Makes no API upload call.

```
test_youtube_live.py "D:\path\to\captioned_reel.mp4"
```
Uploads a real video as `private`. Prints the YouTube URL. Use only for final validation.

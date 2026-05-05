# LobCut

LobCut is a local autonomous media processing agent written in Python.

Right now, the project is focused on two things:

- watching local folders for new media
- classifying incoming images automatically

The current image pipeline uses a hybrid approach:

- blur detection runs locally with OpenCV
- semantic image classification runs through the Gemini API

LobCut then routes the file into the correct output folder and records the full job in SQLite.

## Current Status

Phase 0 and Phase 1 are complete and working.

Phase 2 is now implemented and working for images.

What that means today:

- new files dropped into `input/images/` are detected automatically
- file stability checks prevent half-written file processing
- duplicate source files are ignored
- every job is tracked in `orchestrator/jobs.db`
- blurry images are detected locally
- non-blurry images are classified through Gemini
- classified files are moved into AI-driven output folders like:
  - `output/images/blurry/`
  - `output/images/people/`
  - `output/images/wildlife/`
  - `output/images/landscape/`
  - `output/images/portrait/`
  - or any other category returned by the model

## How It Works

### 1. Watcher

`orchestrator/watcher.py` monitors:

- `input/images/`
- `input/videos/`

When a new file appears:

- LobCut waits for the file to stop changing
- classifies it as `IMAGE`, `VIDEO`, or `UNKNOWN`
- creates a DB row
- routes it to the correct pipeline

### 2. Database

`orchestrator/database.py` is the source of truth for job tracking.

Each job stores:

- file name
- source path
- detected type
- pipeline
- status
- output path
- error details
- image analysis metadata

The image pipeline now also stores:

- `ai_category`
- `ai_tags`
- `ai_summary`
- `blur_score`
- `classifier`

### 3. Image Pipeline

`pipelines/image_pipeline/pipeline.py` does the following:

1. copies the source image to `temp/`
2. computes a local blur score using Laplacian variance
3. if blurry, routes to `output/images/blurry/`
4. if clear, sends the temp copy to Gemini for semantic classification
5. receives structured JSON back from Gemini
6. resolves the destination folder through `PathResolver`
7. moves the temp copy into the final output folder
8. updates the SQLite job row to `DONE` or `FAILED`

### 4. Gemini Integration

Gemini is used only for semantic understanding.

Examples:

- wildlife
- people
- portrait
- landscape
- document
- screenshot
- food
- architecture
- product

The API key is loaded from the local `.env` file and is not committed to git.

## Project Structure

```text
LobCut/
|-- README.md
|-- main.py
|-- requirements.txt
|-- .env.example
|-- config/
|-- dashboard/
|-- docs/
|-- orchestrator/
|-- pipelines/
|-- python-service/
|-- tests/
|-- input/
|-- output/
|-- temp/
`-- logs/
```

## Setup

Install dependencies:

```powershell
py -m pip install -r requirements.txt
```

Create a local `.env` file:

```env
GEMINI_API_KEY=your_real_gemini_api_key_here
```

You can copy the shape from `.env.example`.

## Run LobCut

Start the watcher:

```powershell
py main.py
```

Then drop images into:

```text
input/images/
```

## Run With Docker

```powershell
docker compose up --build
```

For dashboard development:

```powershell
docker compose --profile dev up dashboard
```

## Electron Desktop App

Install the Electron wrapper dependencies:

```powershell
cd electron-app
npm install
```

Run the desktop app in development:

```powershell
npm start
```

To use the desktop shell with services you already started locally, skip Docker:

```powershell
$env:LOBCUT_SKIP_DOCKER="1"
npm start
```

The app starts `docker compose up -d` from the project root, waits for
`http://localhost:8000/health`, and then opens the local dashboard file. Docker
output is written to `~/lobcut-logs/docker.log`.

Build distributables:

```powershell
npm run build
```

The builder is configured for macOS `.dmg`, Linux `.AppImage`, and Windows
`nsis` targets.

## Test Scripts

### Phase 1 test

```powershell
py tests\test_phase1.py --self-contained
```

### Phase 2 mocked test

This validates the full image pipeline flow without real Gemini calls:

```powershell
py tests\test_phase2.py --self-contained
```

### Live Gemini smoke test

This tests one real image against Gemini:

```powershell
py tests\test_gemini_image.py "D:\path\to\image.png"
```

## Security Notes

- `.env` is ignored by git
- local runtime media is ignored by git
- logs, temp files, and the SQLite DB are ignored by git
- if an API key is ever exposed, revoke it and generate a fresh one

## What Has Been Completed

### Phase 0

- base folder structure
- configuration layout
- logger
- database bootstrap

### Phase 1

- watcher
- router
- file stability checks
- quarantine handling
- duplicate protection
- DB-backed job tracking

### Phase 2

- local blur detection
- Gemini semantic image classification
- AI-driven category folders
- `.env`-based key loading
- retry and fallback behavior for model requests
- mocked and live test scripts

## What Is Left

### Near-term polish

- reduce noisy HTTP debug logs
- add cleaner startup diagnostics for Gemini readiness
- improve user-facing error messages for quota or API failures
- decide whether some categories should collapse into simpler folders
  - for example, `portrait` -> `people`

### Phase 3

Video pipeline:

- transcription
- subtitle generation
- subtitle burn-in
- output to `output/videos/`

### Phase 4

Clip intelligence:

- highlight detection
- silence gap trimming
- keyword-triggered clip extraction

## Summary

LobCut is no longer just a folder watcher.

It is now a working local agent that:

- monitors incoming media
- classifies images intelligently
- separates blurry images locally
- uses Gemini for semantic understanding
- organizes files into output folders
- tracks every step in SQLite

The image side is live.
The next major milestone is the video pipeline.

# LobCut

**Team Number:** RVCE_BATISTA  
**Team Name:** Batista  
**College:** RV College of Engineering

LobCut is a local AI media-processing workstation for creators, editors, photographers, and gaming clip makers. It watches folders, processes images and videos, builds highlight clips and reels, records every job in SQLite, and exposes a local dashboard plus optional Telegram notifications.

The project is designed to run locally for privacy and hackathon review. Heavy media work happens in the Python service with OpenCV, Gemini, Whisper, FFmpeg, Librosa, and SQLite. The dashboard is a React/Vite app served by FastAPI or opened through the Electron desktop wrapper.

## Problem

Creators often spend more time preparing content than making it:

- Gamers record long sessions and manually search for highlights.
- Photographers sort large batches of photos by quality and subject.
- Short-form creators need clips, captions, and reels quickly.
- Existing tools usually solve only one part of the workflow.

LobCut brings these steps into one local workflow.

## What LobCut Does

- Watches local folders for incoming images and videos.
- Classifies images with local blur detection plus Gemini image understanding.
- Routes images into organized output folders such as `blurry`, `people`, `wildlife`, `landscape`, `vehicle`, or `other`.
- Transcribes videos with Whisper.
- Detects candidate highlight moments from audio, transcript, and game/context signals.
- Exports short clips, subtitles, and highlight reels.
- Builds word-level captioned reel outputs.
- Stores jobs, statuses, metadata, watchers, and settings in SQLite.
- Shows jobs, previews, outputs, watch folders, Telegram settings, and OpenClaw status in the dashboard.
- Sends optional Telegram notifications for queued, processing, completed, and failed jobs.
- Provides API endpoints for direct file processing and dashboard operations.

## Required Submission Files

The repository includes the hackathon-facing assets:

- **PPT:** `RVCE_BATISTA_LobCut.pptx`
- **Demo video:** `RVCE_BATISTA_DEMO.mov`
- **Demo video backup link:** https://drive.google.com/file/d/1B_zX9koiEQngi_JmIXTDf1rL4iaOJt_d/view?usp=sharing
- **AI disclosure:** `OpenClaw_AI_Disclosure.docx`
- **Source code:** Python service, dashboard, Electron app, Telegram bot, tests, and docs
- **APK/SDK:** Not applicable for this submission

GitHub note: `RVCE_BATISTA_DEMO.mov` is a large file and is tracked with Git LFS. The Drive link above is included as a backup for evaluators.

## Repository Layout

```text
LobCut/
|-- main.py                         # watcher/orchestrator entrypoint
|-- docker-compose.yml              # orchestrator, API, dashboard, OpenClaw, Telegram bot
|-- Dockerfile                      # watcher/orchestrator image
|-- Dockerfile.api                  # FastAPI image
|-- requirements.txt                # root/orchestrator Python dependencies
|-- python-service/
|   |-- app.py                      # FastAPI API and dashboard server
|   |-- config/                     # settings, logging, Gemini helper, paths
|   |-- orchestrator/               # SQLite, watcher, routing
|   `-- pipelines/                  # image, video, caption pipelines
|-- dashboard/                      # React/Vite dashboard
|-- electron-app/                   # desktop wrapper and Windows packaging
|-- telegram-bot/                   # optional Telegram job monitor
|-- openclaw-workspace/             # OpenClaw runtime workspace
|-- openclaw-skill/                 # packaged LobCut skill notes/memory
|-- skills/media-processor/         # local media dispatch skill
|-- docs/                           # setup and architecture notes
|-- tests/                          # smoke/acceptance tests
|-- input/                          # local input media, ignored by git
|-- output/                         # generated media, ignored by git
|-- data/                           # SQLite DB/settings, ignored by git
|-- logs/                           # logs, ignored by git
`-- temp/                           # temp/quarantine files, ignored by git
```

## API Overview

Default local API URL: `http://localhost:8000`

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Health and database check |
| `POST` | `/process/image` | Process one image immediately |
| `POST` | `/process/video` | Process one video immediately |
| `GET` | `/jobs` | List recent jobs |
| `GET` | `/jobs/{id}` | Get one job |
| `GET` | `/jobs/{id}/image` | Stream image preview/output |
| `GET` | `/jobs/{id}/download` | Download job output |
| `POST` | `/jobs/retry/{id}` | Retry a job |
| `DELETE` | `/jobs/{id}` | Soft-delete a job |
| `GET/POST` | `/watchers` | List or add watch folders |
| `PATCH/DELETE` | `/watchers/{id}` | Enable/disable/remove watchers |
| `GET/POST` | `/settings` | Read/write simple settings |
| `GET/PUT` | `/settings/captions` | Read/write caption style settings |
| `POST` | `/telegram/test` | Send a direct Telegram test notification |
| `GET` | `/openclaw/status` | OpenClaw service/status summary |

Direct image request:

```json
{
  "file_path": "C:/absolute/path/to/image.jpg"
}
```

Direct video request:

```json
{
  "file_path": "C:/absolute/path/to/video.mp4"
}
```

## Prerequisites

Required:

- Git
- Python 3.10 or newer
- Node.js 20 or newer
- FFmpeg available on `PATH`

Recommended:

- Docker Desktop for the easiest full-stack run
- A Gemini API key for semantic image/game classification
- A Telegram bot token if you want notifications
- Google OAuth credentials only if you want dashboard login instead of local mode

## Fresh Clone Setup

Clone the repository:

```powershell
git clone https://github.com/Batista31/LobCut.git
cd LobCut
```

Create local runtime folders:

```powershell
mkdir input, output, data, logs, temp -ErrorAction SilentlyContinue
mkdir input\images, input\videos -ErrorAction SilentlyContinue
```

Create your private environment file:

```powershell
copy .env.example .env
```

Edit `.env`. For the simplest local demo, use local auth and fill a Gemini key:

```env
LOBCUT_AUTH_MODE=local
GEMINI_API_KEY=your_gemini_key_here
```

All values in `.env.example` are intentionally blank so the repo can be public. Do not commit `.env`.

## Environment Variables

| Variable | Required | Notes |
| --- | --- | --- |
| `LOBCUT_AUTH_MODE` | Recommended | Use `local` for demos; use `google` for OAuth login |
| `GEMINI_API_KEY` | Recommended | Primary Gemini key for image/game classification |
| `GEMINI_API_KEY_2` | Optional | Backup key used if quota is hit |
| `GEMINI_API_KEY_3` | Optional | Second backup key |
| `OPENAI_API_KEY` | Optional | Passed to OpenClaw if used |
| `TELEGRAM_BOT_TOKEN` | Optional | Enables Telegram notifications |
| `TELEGRAM_CHAT_ID` | Optional | Fallback chat ID for the Telegram bot |
| `GOOGLE_CLIENT_ID` | OAuth only | Required when `LOBCUT_AUTH_MODE=google` |
| `GOOGLE_CLIENT_SECRET` | OAuth only | Required when `LOBCUT_AUTH_MODE=google` |
| `JWT_SECRET` | OAuth only | At least 32 hex characters |
| `WATCH_HOST_INPUT` | Optional | Docker bind mount override for watched folders |
| `WATCH_PATH_MAPPINGS` | Optional | Host-to-container path mapping for Docker watchers |
| `OPENCLAW_GATEWAY_TOKEN` | Optional | Reserved for OpenClaw gateway setups |

## Run With Docker

Build and start the Python orchestrator, API, dashboard, OpenClaw, and Telegram services:

```powershell
docker compose up --build
```

Open:

```text
http://localhost:8000
```

Health check:

```text
GET http://localhost:8000/health
```

Run OpenClaw only when needed:

```powershell
docker compose --profile openclaw up --build
```

Run the Telegram bot service:

```powershell
docker compose up --build telegram-bot
```

## Run Without Docker

Install Python dependencies:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r python-service\requirements.txt
python -m pip install -r requirements.txt
```

Start the watcher/orchestrator:

```powershell
$env:PYTHONPATH="python-service"
python main.py
```

Start the API/dashboard server in a second terminal:

```powershell
$env:PYTHONPATH="python-service"
uvicorn app:app --app-dir python-service --host 0.0.0.0 --port 8000
```

Build the dashboard:

```powershell
cd dashboard
npm ci
npm run build
cd ..
```

## Run The Electron Desktop App

Build the dashboard first:

```powershell
cd dashboard
npm ci
npm run build
cd ..
```

Install Electron dependencies and start:

```powershell
cd electron-app
npm ci
npm start
```

To use a backend you already started manually:

```powershell
$env:LOBCUT_SKIP_DOCKER="1"
npm start
```

Package for Windows:

```powershell
cd electron-app
npm run build:win
```

See [PACKAGING_WINDOWS.md](docs/PACKAGING_WINDOWS.md) for packaging notes.

## How To Use LobCut

1. Start the services using Docker, local Python, or Electron.
2. Open the dashboard at `http://localhost:8000`.
3. Add watch folders on the Watchers page, or use the default folders:
   - `input/images`
   - `input/videos`
4. Drop image or video files into a watched folder.
5. Watch jobs appear in the dashboard.
6. Open outputs from the job table or inspect details in the job modal.

Outputs are written under:

```text
output/images/
output/videos/clips/
output/videos/reels/
```

Unknown files are quarantined under:

```text
temp/quarantine/
```

## Tests And Verification

Run lightweight tests:

```powershell
$env:PYTHONPATH="python-service"
python -m pytest tests -q
```

Run the Phase 1 watcher test:

```powershell
$env:PYTHONPATH="python-service"
python tests\test_phase1.py --self-contained
```

Run the mocked image pipeline test:

```powershell
$env:PYTHONPATH="python-service"
python tests\test_phase2.py --self-contained
```

Run dashboard build verification:

```powershell
cd dashboard
npm ci
npm run build
```

Notes:

- FFmpeg must be installed for video/caption tests.
- Gemini live tests require a valid Gemini API key.
- Docker tests require Docker Desktop to be running.

## AI Disclosure

The product uses AI/ML models at runtime:

- Gemini for semantic classification and context detection.
- Whisper for speech-to-text transcription.
- OpenCV and Librosa for local media analysis.

Development-time AI assistance is documented separately in `OpenClaw_AI_Disclosure.docx`.

## Public Repo Safety Checklist

Before sharing with judges:

- Confirm `.env` is not committed.
- Keep `data/jobs.db`, `input/`, `output/`, `logs/`, `temp/`, `node_modules/`, and build artifacts out of git.
- Use `.env.example` only for blank variable names.
- Remove private media if you plan to include sample assets.
- Run `git status --short --ignored` and review anything unexpected.

## Troubleshooting

Backend does not start:

- Check `.env`.
- For easiest local use, set `LOBCUT_AUTH_MODE=local`.
- Install dependencies with `python -m pip install -r python-service/requirements.txt`.

Dashboard shows login only:

- If you want local mode, set `LOBCUT_AUTH_MODE=local` and restart the API.
- If you want Google login, configure `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, and `JWT_SECRET`.

Gemini errors:

- Set `GEMINI_API_KEY`.
- Add `GEMINI_API_KEY_2` and `GEMINI_API_KEY_3` for quota fallback.
- If quota is exhausted, jobs may wait in `output/images/unclassified`.

Video or caption errors:

- Install FFmpeg and ensure `ffmpeg` is available on `PATH`.
- Whisper may download model files on first run.

Docker errors on Windows:

- Start Docker Desktop first.
- Run the terminal with permissions that can access the Docker engine.

Node/Vite `spawn EPERM` on Windows:

- Retry in an elevated terminal.
- Ensure antivirus or Controlled Folder Access is not blocking `node_modules/.bin/esbuild`.

## Current Hackathon Scope

The core submission demonstrates:

- local autonomous media intake,
- image classification and routing,
- video transcription and clip/reel generation,
- dashboard-based monitoring,
- watch-folder management,
- Telegram notification integration,
- OpenClaw status integration,
- Docker and Electron packaging paths.

Some AI features depend on external API keys and quota. The project is built to degrade safely by recording failures in job status rather than silently dropping files.

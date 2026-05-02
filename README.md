# MediaScribe

MediaScribe is a local autonomous media processing agent for the Samsung PRISM
"Clash of the Claws" hackathon. It runs on top of the OpenClaw runtime, uses a
FastAPI bridge for pipeline execution, classifies images with OpenCV + Gemini
Flash, and transcribes videos with Whisper + SRT subtitle generation.

## What It Does

- Watches or receives media file paths through the OpenClaw `media-processor` skill
- Processes images with:
  - local blur detection
  - Gemini Flash semantic classification
  - category, tags, and summary generation
- Processes videos with:
  - Whisper transcription
  - `.srt` subtitle generation
  - FFmpeg-backed media handling
- Tracks every job in SQLite
- Writes one-line memory entries after every successful job

## Final Project Layout

```text
mediascribe/
├── .env.example
├── AGENTS.md
├── HEARTBEAT.md
├── README.md
├── SOUL.md
├── docker-compose.yml
├── openclaw.json
├── data/
│   └── inbox/
├── memory/
│   └── MEMORY_LOG.md
├── python-service/
│   ├── .dockerignore
│   ├── Dockerfile
│   ├── app.py
│   ├── requirements.txt
│   ├── config/
│   ├── orchestrator/
│   └── pipelines/
└── skills/
    └── media-processor/
        ├── SKILL.md
        └── run.js
```

## Architecture

```text
Telegram
  -> OpenClaw gateway
  -> media-processor skill
  -> FastAPI python-service
  -> shared OpenClaw pipeline modules
     - config/
     - orchestrator/
     - pipelines/
  -> SQLite + output folders + memory log
```

## Prerequisites

| Requirement | Notes |
|---|---|
| Windows 11 or Windows 10 | With WSL2 enabled |
| WSL2 | Ubuntu 22.04 recommended |
| Docker Desktop | WSL2 backend must be enabled |
| Node.js 22 | Needed for the OpenClaw gateway |
| Telegram bot token | Create with [@BotFather](https://t.me/BotFather) |
| Telegram allowed user ID | Get from [@userinfobot](https://t.me/userinfobot) |
| Gemini API key | Used by the Python image pipeline |
| Anthropic API key | Used by the OpenClaw gateway runtime |

## Setup

### 1. Clone the repo

```bash
git clone <your-repo-url>
cd mediascribe
```

### 2. Prepare `.env`

```bash
cp .env.example .env
```

Fill in:

- `GEMINI_API_KEY`
- `ANTHROPIC_API_KEY`
- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_ALLOWED_USER_ID`
- `WATCH_INBOX`

Use a WSL2-visible path for `WATCH_INBOX`, for example:

```env
WATCH_INBOX=/mnt/c/Users/YourName/Videos/mediascribe-inbox
```

If you do not set `WATCH_INBOX`, Docker Compose will use `./data/inbox`.

### 3. Start the stack

```bash
docker compose up --build
```

This starts:

- `python-service` on `http://localhost:8000`
- `openclaw` gateway on port `18789`

### 4. Pair Telegram with OpenClaw

After the gateway is running, message your bot and complete the OpenClaw pairing flow.

### 5. Verify the Python service

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{
  "status": "ok",
  "service": "mediascribe-python",
  "gemini_configured": true,
  "memory_log": "/app/memory/MEMORY_LOG.md"
}
```

## API Endpoints

| Route | Purpose |
|---|---|
| `POST /process/image` | Run the image pipeline |
| `POST /process/video` | Run the video pipeline and generate `.srt` subtitles |
| `GET /jobs` | Return recent jobs from SQLite |
| `GET /health` | Service health check |

## Usage Examples

| What you send to Telegram | What comes back |
|---|---|
| `/mnt/c/Users/You/Pictures/elephant.webp` | Image category, tags, summary, blur score, classifier, output path |
| `/mnt/c/Users/You/Videos/lecture.mp4` | Video summary, transcript preview, subtitle path, duration |
| `process this /mnt/c/Users/You/Pictures/screenshot.png` | Processed image result using the `media-processor` skill |
| `show job history` | Recent jobs from SQLite and memory |
| `what wildlife images did I process this week?` | Recall summary based on `MEMORY_LOG.md` |

## Troubleshooting

| Problem | What to check |
|---|---|
| `python-service` will not start | Run `docker compose logs python-service` and confirm `.env` has a valid `GEMINI_API_KEY` |
| OpenCV errors in the container | Rebuild the image and confirm Docker Desktop has enough memory |
| Gemini quota or temporary API issues | The image pipeline retries first, then falls back to a heuristic classifier |
| Video processing fails | Confirm `ffmpeg` is available in the container and the file is a supported video format |
| No subtitles returned | Check `docker compose logs python-service` for Whisper/FFmpeg errors |
| OpenClaw cannot reach the service | Confirm `python-service` is healthy and `MEDIA_SERVICE_URL` is `http://python-service:8000` inside Compose |
| Windows path is not found | Use WSL2-visible paths like `/mnt/c/...` when sending files through Telegram |
| Memory log is not updating | Confirm `./memory` is mounted and `MEMORY_LOG.md` is writable |

## Tech Stack

| Layer | Technology |
|---|---|
| Agent runtime | OpenClaw |
| Channel | Telegram |
| Gateway runtime | Node.js 22 |
| Python API | FastAPI |
| Image quality check | OpenCV |
| Image classification | Gemini Flash via `google-genai` |
| Video transcription | OpenAI Whisper |
| Subtitle generation | SRT generation from Whisper segments |
| Media processing | FFmpeg |
| Job tracking | SQLite |
| Persistent memory | `MEMORY_LOG.md` |
| Containers | Docker Compose on WSL2 |

## Notes

- Secrets stay in `.env` only.
- The service copies source media into temp/output paths before processing.
- Unknown file types are quarantined through the shared orchestrator logic.
- Video API processing preserves subtitle generation and returns `subtitle_path`.

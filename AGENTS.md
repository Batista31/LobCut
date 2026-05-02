# MediaScribe — Agent Workspace Instructions

## Overview
This workspace powers MediaScribe, an autonomous media processing agent.
The Python FastAPI service runs locally at http://localhost:8000 and handles
all heavy lifting (OpenCV, Gemini, Whisper, FFmpeg).

## API Endpoints (Python Service)
- POST http://localhost:8000/process/image  — image pipeline (blur + Gemini)
- POST http://localhost:8000/process/video  — video pipeline (Whisper + subtitles)
- GET  http://localhost:8000/jobs           — job history from SQLite
- GET  http://localhost:8000/health         — service health check

## Request Format
### Image
```json
{ "file_path": "/absolute/path/to/image.jpg" }
```
### Video
```json
{ "file_path": "/absolute/path/to/video.mp4" }
```

## Response Format
### Image response
```json
{
  "job_id": "...",
  "file": "photo.jpg",
  "type": "image",
  "category": "wildlife",
  "tags": ["elephant", "savanna", "daytime"],
  "summary": "A clear photograph of an elephant in open grassland.",
  "blur_score": 142.3,
  "is_blurry": false,
  "classifier": "gemini-flash"
}
```
### Video response
```json
{
  "job_id": "...",
  "file": "lecture.mp4",
  "type": "video",
  "transcript": "...",
  "summary": "A 12-minute lecture on neural network architectures...",
  "subtitle_path": "/output/lecture.srt",
  "duration_seconds": 742
}
```

## Memory Files (read/write)
- `MEMORY_LOG.md` — append one line per processed file
- `HEARTBEAT.md`  — daily digest template, auto-posted at 08:00

## Skills Available
- `media-processor` — the primary skill, handles all file dispatch

## Watch Folders (defaults, configurable in .env)
- Input:  ~/mediascribe-watch/inbox/
- Output: ~/mediascribe-watch/output/
- Temp:   ~/mediascribe-watch/temp/

## Error Handling
- If the Python service returns 503, tell the user and suggest:
  `cd mediascribe && docker compose up -d python-service`
- If Gemini quota is exceeded, the pipeline falls back to rule-based
  classification — results will be marked `classifier: "fallback"`
- Quarantined files (unknown type) are moved to ~/mediascribe-watch/quarantine/

## How to Answer Recall Questions
1. Read MEMORY_LOG.md
2. Filter by the time range or category the user asked about
3. Summarize — do not invent entries that aren't in the log

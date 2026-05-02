---
name: media-processor
version: 1.0.0
description: >
  Dispatches image and video files to the local MediaScribe Python pipeline.
  Handles blur detection, Gemini-powered semantic classification for images,
  and Whisper transcription + SRT subtitle generation for videos.
  Appends results to workspace memory for recall queries.
author: MediaScribe Team
tags: [media, image, video, classification, transcription, subtitles, gemini, whisper]
platforms: [windows, linux, macos]
requires:
  - python-service running at http://localhost:8000
  - GEMINI_API_KEY set in python-service/.env
---

# media-processor Skill

## Purpose
Process image and video files through the local AI pipeline and return
structured results to the user. Update workspace memory after every job.

## Trigger Conditions
Activate this skill when the user:
- Sends a file path ending in `.jpg`, `.jpeg`, `.png`, `.webp`, `.bmp`
- Sends a file path ending in `.mp4`, `.mov`, `.avi`, `.mkv`, `.webm`
- Sends a folder path and asks to "process all files" or "scan folder"
- Says anything like "process this", "classify this", "transcribe this",
  "get subtitles for", "analyze this file"

## Tool Mapping

### process_image
**Trigger:** file is an image type (jpg, jpeg, png, webp, bmp)
**Action:** POST http://localhost:8000/process/image
**Input:**
```json
{ "file_path": "<absolute path to image>" }
```
**Output to user:**
```
📸 Image processed: <filename>
Category : <category>
Tags     : <tag1>, <tag2>, <tag3>
Summary  : <summary>
Blur     : <blur_score> (<clear/blurry>)
Classifier: <gemini-flash / fallback>
```

### process_video
**Trigger:** file is a video type (mp4, mov, avi, mkv, webm)
**Action:** POST http://localhost:8000/process/video
**Input:**
```json
{ "file_path": "<absolute path to video>" }
```
**Output to user:**
```
🎬 Video processed: <filename>
Duration : <duration>
Summary  : <summary>
Subtitles: <subtitle_path> (.srt file ready)
Transcript preview:
  "<first 200 chars of transcript>..."
```

### process_folder
**Trigger:** user provides a folder path
**Action:** list all supported files, confirm count with user, then
call process_image or process_video for each file sequentially
**Rule:** always confirm before processing more than 10 files

### query_jobs
**Trigger:** user asks "what have you processed?", "show job history",
  "what images did I process this week?", or similar recall questions
**Action:** GET http://localhost:8000/jobs OR read MEMORY_LOG.md
**Output:** structured table of recent jobs filtered by user's criteria

## Memory Update Protocol
After EVERY successful job, append to MEMORY_LOG.md:
```
[YYYY-MM-DD HH:MM] | <filename> | <image/video> | <category> | <summary snippet (50 chars)>
```
Example:
```
[2026-05-02 14:33] | elephant.jpg | image | wildlife | Clear photo of elephant in savanna
[2026-05-02 14:35] | lecture.mp4  | video | education | Neural network lecture, 12 mins
```

## Error Handling
| Error | User Message |
|-------|-------------|
| Service unreachable (503/connection refused) | "⚠️ Python service is offline. Run: `docker compose up -d python-service`" |
| File not found | "❌ File not found at that path. Please check the path and try again." |
| Unsupported format | "⚠️ Unsupported file type. Supported: jpg/png/webp/bmp (images), mp4/mov/avi/mkv/webm (videos)" |
| Gemini quota exceeded | "⚠️ Gemini quota hit — result used fallback classifier. Accuracy may be lower." |
| Blurry image | Report normally but flag: "⚠️ Image is blurry (score: X) — classification confidence may be reduced." |

## Example Interactions

**User:** process /home/user/photos/safari.jpg
**Agent:** calls process_image → returns structured result → appends to MEMORY_LOG.md

**User:** transcribe /home/user/videos/standup.mp4
**Agent:** calls process_video → returns transcript + subtitle path → appends to MEMORY_LOG.md

**User:** what wildlife images did I process this week?
**Agent:** reads MEMORY_LOG.md → filters by category=wildlife and date range → summarizes

**User:** process everything in /home/user/downloads/
**Agent:** lists files → "Found 7 images and 2 videos. Process all 9 files?" → waits for confirmation

# LobCut Architecture Assessment

This note summarizes how the repository maps to the hackathon's agent-style architecture requirement. It is written as an engineering assessment, not as marketing copy.

## Requirement Fit

### 1. LobCut / Agent Architecture Variant

**Status: Met**

- The project is named LobCut throughout the app and repository.
- The system is organized around a watcher, router, processing pipelines, and persistent job state.
- The flow is event-driven: input file -> decision layer -> pipeline execution -> output.

### 2. AI Agent Behavior

**Status: Mostly met**

Implemented:

- Folder-based event detection through `watchdog`.
- Central router for file type and pipeline selection.
- SQLite job tracking for status, metadata, errors, and outputs.
- Runtime AI/ML integrations through Gemini, Whisper, OpenCV, and Librosa.
- Pipeline decisions such as image category routing, video highlight selection, caption generation, and optional reel creation.

Current limits:

- Most orchestration decisions are deterministic and rule-based.
- The system does not yet learn from user feedback.
- There is no full reasoning trace for every job decision.

Practical verdict: LobCut behaves like a local media-processing agent and pipeline orchestrator. It already watches, decides, acts, and records results. Future versions can add stronger reasoning logs, feedback loops, and user preference memory.

### 3. Central Orchestration Layer

**Status: Met**

Main components:

- `python-service/orchestrator/watcher.py` watches input folders and waits for stable files.
- `python-service/orchestrator/router.py` classifies files and selects the pipeline.
- `python-service/orchestrator/database.py` stores job state and metadata.
- `python-service/app.py` exposes the FastAPI surface for jobs, settings, watchers, image/video processing, and Telegram flows.

The separation is clear: monitoring, routing, processing, and persistence are handled by separate modules.

### 4. AI Usage in Product Runtime

**Status: Met**

Runtime model usage:

- Gemini for image classification and selected context-detection tasks.
- Whisper for video/reel transcription.
- OpenCV for blur detection.
- Librosa for audio feature extraction.

These are product features, not claims about how the project was built. Development-time AI assistance is covered in the approved AI disclosure document.

### 5. Autonomous Operation

**Status: Met**

LobCut can process media without step-by-step user control:

- Watches `input/images/`, `input/videos/`, and reel output folders.
- Waits for files to finish copying before processing.
- Avoids duplicate processing.
- Creates and updates job records.
- Writes processed outputs to organized folders.
- Captures errors instead of silently failing.

### 6. Task Orchestration

**Status: Met**

Image flow:

```text
file detected -> blur check -> Gemini classification -> output folder -> DB update
```

Video flow:

```text
file detected -> FFmpeg probe/audio -> Whisper transcript -> highlight scoring
-> clip export -> optional reel/subtitles -> DB update
```

Caption flow:

```text
reel detected -> word timestamps -> ASS subtitle file -> captioned reel -> DB update
```

## Layered Design

```text
Input Monitoring
  - folder watcher
  - file stability checks
  - duplicate handling

Decision Layer
  - file type classification
  - pipeline selection
  - job creation

Execution Layer
  - image pipeline
  - video pipeline
  - caption pipeline
  - Telegram/result delivery

Memory / Persistence
  - SQLite jobs database
  - MEMORY_LOG.md
  - output folders
```

## Strengths

1. Clear module boundaries.
2. Local-first architecture suitable for demos and privacy-sensitive workflows.
3. SQLite-backed job history for debugging and recall.
4. Media stack uses practical tools: FFmpeg, OpenCV, Whisper, Gemini, Librosa.
5. The pipeline is easy to extend because each stage is isolated.

## Known Gaps

1. Reasoning traces are limited.
2. User feedback is not yet used to improve future decisions.
3. Some thresholds and trigger rules are still static.
4. Recovery modes can be expanded for model/API failures.
5. Clip ranking can become stronger with more signals and user feedback.

## Files Reviewed

- `python-service/app.py` - FastAPI routes and service surface
- `python-service/orchestrator/watcher.py` - input monitoring
- `python-service/orchestrator/router.py` - file classification and routing
- `python-service/orchestrator/database.py` - persistence
- `python-service/pipelines/image_pipeline/pipeline.py` - image processing
- `python-service/pipelines/video_pipeline/pipeline.py` - video orchestration
- `python-service/pipelines/video_pipeline/highlight_detector.py` - highlight scoring
- `python-service/pipelines/video_pipeline/transcriber.py` - Whisper integration
- `python-service/pipelines/caption_pipeline/pipeline.py` - reel caption flow
- `dashboard/` - web dashboard
- `electron-app/` - desktop wrapper
- `telegram-bot/` - Telegram integration

## Summary

LobCut meets the core requirement for an autonomous local media-processing agent. It watches for input, chooses a pipeline, processes media, stores results, and exposes status through local interfaces. The current implementation is strongest as a practical pipeline agent; the next step is adding richer feedback and reasoning visibility.

# LobCut Architecture Assessment

## Requirements Checklist

### ✅ 1. LobCut / Agent Architecture Variant
**Status: MET**
- Project is explicitly named "LobCut" (banner in main.py)
- Described as "Autonomous Media Processing Agent — Phase 2"
- Follows agent pattern with input → decision → execution layers

### ✅ 2. AI Agent (Not Just Scripts)
**Status: MOSTLY MET**
- **What's implemented:**
  - Central orchestrator (`orchestrator/router.py`, `orchestrator/watcher.py`)
  - Autonomous event detection (file monitoring)
  - Intelligent routing logic (type classification)
  - Decision-making for pipeline selection
  - AI integration points (Gemini, Whisper)
- **What's missing:**
  - System lacks true "reasoning" layer
  - No explicit agent state machine or decision reasoning traces
  - Decisions are deterministic/rule-based, not reasoning-based
  - Could benefit from explicit agent goals/reasoning logging

**Verdict:** Acts as an agent, but more as a pipeline orchestrator than a reasoning agent.

### ✅ 3. Central Orchestration Layer
**Status: MET**
- **Orchestrator module** (`orchestrator/`) provides:
  - `router.py`: Routes files to correct pipeline based on type classification
  - `watcher.py`: Monitors input folders for new media
  - `database.py`: Tracks all job states and metadata
- **Main loop** (`main.py`):
  - Polls database for pending jobs
  - Dispatches to appropriate pipelines
  - Updates job status throughout lifecycle
- **Clear separation:**
  - Input monitoring → Routing → Execution

### ✅ 4. AI Usage (Meaningful)
**Status: MET**
- **LLM Integration:**
  - Google Gemini API for image classification (semantic understanding)
  - Gemini used for game detection from video frames + transcript
  - Gemini used for clip reranking (optional)
- **ML Models:**
  - OpenAI Whisper for speech-to-text transcription
  - Librosa for audio analysis (onset detection, spectral analysis)
  - OpenCV for blur detection (local ML-based quality check)
- **Intelligent Logic:**
  - Game genre detection combines frames + audio transcript
  - Highlight scoring combines multiple signals:
    - Audio onset strength
    - Keyword presence in transcript
    - Silence duration
    - Spectral centroid frequency
  - Dynamic keyword matching per game genre

### ✅ 5. Autonomous Operation
**Status: MET**
- **Event Detection:**
  - Watchdog monitors `input/images/` and `input/videos/` continuously
  - File stability checks (5 polls at 1-second intervals) prevent partial uploads
  - Duplicate detection prevents reprocessing
- **Automatic Actions:**
  - Files automatically classified and routed
  - Pipelines triggered without user intervention
  - Results automatically organized into output folders
- **Minimal Intervention:**
  - Drop file → Auto-processes → Results in output/
  - Status trackable via SQLite database
  - Error handling with status recording

### ✅ 6. Task Orchestration
**Status: MET**
- **Interpret Tasks:**
  - Router classifies incoming files (IMAGE/VIDEO/UNKNOWN)
  - Determines pipeline requirements
  - Loads genre-specific decision keywords
- **Decide What to Do:**
  - Router decides pipeline (image_pipeline vs video_pipeline)
  - Pipeline stages decide processing order
  - Video pipeline conditionally:
    - Detects game if needed (genre-based processing)
    - Runs keyword clipper if triggers configured
    - Builds highlight reel if enabled
    - Burns subtitles if enabled
- **Execute Workflows:**
  - Image: blur check → Gemini classification → move to folder
  - Video: extract audio/frames → transcribe → detect game → score moments → export clips → optional reel assembly

### ✅ 7. Agent-Based Architecture (Clear Separation)
**Status: MET**

#### Layer 1: Input Monitoring
```
orchestrator/watcher.py
├─ FileSystemEventHandler (watchdog)
├─ File stability checking
├─ Duplicate detection
└─ Initial classification
```

#### Layer 2: Decision Layer (Orchestrator)
```
orchestrator/router.py
├─ Type classification (IMAGE/VIDEO/UNKNOWN)
└─ Pipeline routing logic

orchestrator/database.py
├─ Job state management
├─ Status tracking
└─ Metadata persistence
```

#### Layer 3: Execution (Pipelines)
```
pipelines/image_pipeline/
├─ Blur detection (local CV)
├─ Gemini classification
└─ Output organization

pipelines/video_pipeline/
├─ Audio extraction & analysis
├─ Frame extraction
├─ Transcription (Whisper)
├─ Game detection (Gemini + frames)
├─ Highlight detection (ML scoring)
├─ Clip export (FFmpeg)
├─ Subtitle generation
└─ Reel assembly
```

---

## Detailed Findings

### Strengths ✨

1. **Well-structured codebase**
   - Clear separation of concerns
   - Centralized configuration (`config/settings.py`)
   - Proper dependency management

2. **Robust input handling**
   - File stability checking prevents corrupt uploads
   - Duplicate detection with path deduplication
   - Graceful error handling

3. **Multi-stage AI pipeline**
   - Combines local ML (OpenCV, Librosa) with cloud AI (Gemini, Whisper)
   - Smart feature engineering for highlight detection
   - Genre-aware keyword matching

4. **Comprehensive logging**
   - Tracked job lifecycle
   - SQLite persistence for auditing
   - Structured logging with context

5. **Extensible architecture**
   - Easy to add new AI models
   - Plugin-friendly pipeline stages
   - Configurable triggers and thresholds

### Gaps & Limitations ⚠️

1. **Limited reasoning capability**
   - Decisions are deterministic, not reasoning-based
   - No explicit "why" logging for agent decisions
   - Missing decision trace/reasoning logs
   - **Improvement:** Add decision reasoning layer that logs decision confidence, alternatives considered

2. **No explicit agent goals**
   - System doesn't define what "success" means
   - No feedback loop to improve future decisions
   - Missing learning mechanism
   - **Improvement:** Define explicit objectives (e.g., "maximize highlight relevance") and track metrics

3. **Limited context awareness**
   - Agent processes files in isolation
   - Doesn't learn from previous jobs
   - No cross-file relationship tracking
   - **Improvement:** Add memory layer to track patterns across jobs

4. **Clip ranking placeholder**
   - `clip_ranker.py` has stub implementation (just ordinal ranking)
   - Could leverage Gemini for actual excitement scoring
   - **Improvement:** Implement `rerank_clips_with_gemini()` properly

5. **No dynamic configuration**
   - Settings are static in `config/settings.py`
   - Can't adjust thresholds based on results
   - No A/B testing framework
   - **Improvement:** Add dynamic config updates based on performance

6. **Limited error recovery**
   - Errors marked as FAILED but not retried with different strategies
   - No fallback decision paths
   - **Improvement:** Implement retry with degraded mode (e.g., skip Gemini, use local detection)

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                    INPUT MONITORING LAYER                    │
│  (orchestrator/watcher.py - Watchdog-based folder monitor)   │
└──────────────────────┬──────────────────────────────────────┘
                       │ File Created Event
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    DECISION LAYER                            │
│  ┌────────────────────────────────────────────────────────┐  │
│  │ 1. File Stability Check (5 polls @ 1s intervals)       │  │
│  │ 2. Duplicate Detection (SQLite lookup)                 │  │
│  │ 3. Type Classification (orchestrator/router.py)        │  │
│  │    - IMAGE, VIDEO, or UNKNOWN                          │  │
│  │ 4. Pipeline Routing Decision                           │  │
│  │ 5. Job DB Entry Creation (orchestrator/database.py)    │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────┬──────────────────────────────────────┘
                       │ Job Status: PENDING
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    DISPATCH LOOP (main.py)                   │
│  ┌────────────┐         ┌────────────┐                       │
│  │   Image    │         │   Video    │                       │
│  │  Pipeline  │         │  Pipeline  │                       │
│  └──────┬─────┘         └──────┬─────┘                       │
└─────────┼───────────────────────┼──────────────────────────────┘
          │                       │
          ▼                       ▼
    ┌──────────────────┐   ┌─────────────────────────────────┐
    │ IMAGE EXECUTION  │   │  VIDEO EXECUTION                │
    ├──────────────────┤   ├─────────────────────────────────┤
    │ 1. Blur Detect   │   │ 1. Extract audio/frames         │
    │    (OpenCV)      │   │ 2. Transcribe (Whisper)         │
    │ 2. Classify      │   │ 3. Detect game (Gemini+frames)  │
    │    (Gemini)      │   │ 4. Analyze audio (Librosa)      │
    │ 3. Move to       │   │ 5. Score moments (ML scoring)   │
    │    output folder │   │ 6. Export clips (FFmpeg)        │
    │ 4. Update DB     │   │ 7. Generate SRTs                │
    └──────────────────┘   │ 8. Optional: Burn subtitles     │
                           │ 9. Optional: Build reel         │
                           │ 10. Update DB                   │
                           └─────────────────────────────────┘
          │                       │
          └───────────┬───────────┘
                      ▼
              Job Status: DONE/FAILED
              Results in output/
              Metadata in SQLite
```

---

## Conclusion

### Overall Assessment: ✅ **REQUIREMENTS MET** (with caveats)

**LobCut meets the core architectural requirements** for an autonomous media processing agent:

- ✅ Defined architecture (LobCut variant)
- ✅ Central orchestration layer (router + database)
- ✅ Autonomous operation (file watching + auto-dispatch)
- ✅ AI integration (Gemini, Whisper, OpenCV, Librosa)
- ✅ Task orchestration (decide → execute workflows)
- ✅ Clear layer separation (monitoring → decision → execution)

### But...

The system is **more of a pipeline orchestrator than a true autonomous reasoning agent**. It:
- Makes decisions deterministically (good for reliability)
- Doesn't learn or adapt (each job is independent)
- Lacks explicit reasoning traces (opaque decision-making)
- Has no feedback loop for improvement

### Recommendations for True "Agent" Status

If you want to elevate it from orchestrator to true agent:

1. **Add reasoning layer**
   - Log decision confidence scores
   - Document alternatives considered
   - Show reasoning traces

2. **Implement feedback loop**
   - Track accuracy of game detection
   - Monitor highlight relevance scores
   - Learn from misclassifications

3. **Add state/memory**
   - Remember previous game detections
   - Cross-reference similar content
   - Build user-specific preferences

4. **Enable dynamic goals**
   - Define success metrics
   - Allow goal/priority adjustment
   - Measure agent performance over time

5. **Implement error recovery strategies**
   - Retry with degraded modes
   - Fallback decision paths
   - Learn from failures

---

## Files Reviewed

- [main.py](main.py) — Entry point, dispatch loop
- [orchestrator/router.py](orchestrator/router.py) — Type classification
- [orchestrator/watcher.py](orchestrator/watcher.py) — Input monitoring
- [orchestrator/database.py](orchestrator/database.py) — Job tracking
- [pipelines/image_pipeline/pipeline.py](pipelines/image_pipeline/pipeline.py) — Image processing
- [pipelines/video_pipeline/pipeline.py](pipelines/video_pipeline/pipeline.py) — Video orchestration
- [pipelines/video_pipeline/game_detector.py](pipelines/video_pipeline/game_detector.py) — AI game detection
- [pipelines/video_pipeline/highlight_detector.py](pipelines/video_pipeline/highlight_detector.py) — ML scoring
- [pipelines/video_pipeline/transcriber.py](pipelines/video_pipeline/transcriber.py) — Whisper integration
- [pipelines/video_pipeline/audio_analyzer.py](pipelines/video_pipeline/audio_analyzer.py) — Audio ML
- [pipelines/video_pipeline/clip_ranker.py](pipelines/video_pipeline/clip_ranker.py) — Clip ranking
- [config/settings.py](config/settings.py) — Centralized config

---

**Assessment Date:** 2026-05-02
**System Status:** Production-ready pipeline orchestrator, growing toward true agent capability

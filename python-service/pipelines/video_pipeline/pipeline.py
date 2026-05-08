from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

from config.logger import get_logger
from config.path_resolver import PathResolver
from config.settings import (
    BURN_SUBTITLES,
    BUILD_HIGHLIGHT_REEL,
    CLIP_TRIGGERS,
    ENABLE_CAPTION_PIPELINE,
    FRAME_SAMPLE_INTERVAL_SEC,
    GEMINI_RERANK_CLIPS,
    MAX_HIGHLIGHTS,
    MAX_REEL_CLIPS,
    PIPELINE_VIDEO,
    TEMP_DIR,
    WHISPER_MODEL_SIZE,
)
from orchestrator.database import (
    STATUS_DONE,
    STATUS_FAILED,
    STATUS_PROCESSING,
    update_job_status,
    update_job_video_fields,
)
from pipelines.video_pipeline import (
    audio_analyzer,
    clip_exporter,
    clip_ranker,
    ffmpeg_utils,
    game_detector,
    highlight_detector,
    keyword_clipper,
    reel_assembler,
    subtitler,
    transcriber,
)
from pipelines.video_pipeline.errors import VideoPipelineError

log = get_logger(__name__)


def _summarize_transcript(transcript_text: str) -> str:
    cleaned = (transcript_text or "").strip()
    if not cleaned:
        return "No speech was detected in the video."
    if len(cleaned) <= 240:
        return cleaned
    return f"{cleaned[:237].rstrip()}..."


def _segment_words(segment: dict) -> list[dict]:
    words = segment.get("words") or []
    normalized = []
    for word in words:
        text = (word.get("word") or "").strip()
        if not text:
            continue
        start = float(word.get("start", segment.get("start", 0.0)) or 0.0)
        end = float(word.get("end", segment.get("end", start + 0.1)) or start + 0.1)
        normalized.append({"word": text, "start": start, "end": max(end, start + 0.1)})
    if normalized:
        return normalized

    text_words = [token.strip() for token in (segment.get("text") or "").split() if token.strip()]
    if not text_words:
        return []
    start = float(segment.get("start", 0.0) or 0.0)
    end = max(start + 0.2, float(segment.get("end", start + 0.2) or start + 0.2))
    step = (end - start) / max(1, len(text_words))
    return [
        {"word": token, "start": start + (idx * step), "end": start + ((idx + 1) * step)}
        for idx, token in enumerate(text_words)
    ]


def _caption_words_for_reel(transcript: dict, exported: list[dict]) -> list[dict]:
    words: list[dict] = []
    reel_cursor = 0.0
    segments = transcript.get("segments", [])

    for item in exported:
        moment = item["moment"]
        clip_start = float(moment.get("clip_start", 0.0) or 0.0)
        clip_end = float(moment.get("clip_end", clip_start) or clip_start)
        try:
            clip_duration = float(ffmpeg_utils.probe_video(item["clip_path"]).get("duration", 0.0) or 0.0)
        except Exception:
            clip_duration = max(0.0, clip_end - clip_start)

        for segment in segments:
            seg_start = float(segment.get("start", 0.0) or 0.0)
            seg_end = float(segment.get("end", seg_start) or seg_start)
            if seg_end < clip_start or seg_start > clip_end:
                continue
            for word in _segment_words(segment):
                word_start = float(word["start"])
                word_end = float(word["end"])
                if word_end < clip_start or word_start > clip_end:
                    continue
                shifted_start = reel_cursor + max(0.0, word_start - clip_start)
                shifted_end = reel_cursor + max(0.05, min(clip_end, word_end) - clip_start)
                if shifted_end <= shifted_start:
                    shifted_end = shifted_start + 0.1
                words.append({"word": word["word"], "start": shifted_start, "end": shifted_end})

        reel_cursor += clip_duration

    return words


def _parse_srt_time(value: str) -> float:
    match = re.match(r"(\d+):(\d+):(\d+),(\d+)", value.strip())
    if not match:
        return 0.0
    hours, minutes, seconds, millis = [int(part) for part in match.groups()]
    return (hours * 3600) + (minutes * 60) + seconds + (millis / 1000.0)


def _caption_words_from_clip_srts(exported: list[dict]) -> list[dict]:
    words: list[dict] = []
    reel_cursor = 0.0

    for item in exported:
        clip_path = Path(item["clip_path"])
        srt_path = clip_path.with_suffix(".srt")
        try:
            clip_duration = float(ffmpeg_utils.probe_video(clip_path).get("duration", 0.0) or 0.0)
        except Exception:
            moment = item["moment"]
            clip_duration = max(0.0, float(moment.get("clip_end", 0.0)) - float(moment.get("clip_start", 0.0)))

        if srt_path.exists():
            blocks = re.split(r"\n\s*\n", srt_path.read_text(encoding="utf-8").strip())
            for block in blocks:
                lines = [line.strip() for line in block.splitlines() if line.strip()]
                if len(lines) < 3 or "-->" not in lines[1]:
                    continue
                start_raw, end_raw = [part.strip() for part in lines[1].split("-->", 1)]
                tokens = " ".join(lines[2:]).split()
                if not tokens:
                    continue
                start = _parse_srt_time(start_raw)
                end = max(start + 0.2, _parse_srt_time(end_raw))
                step = (end - start) / max(1, len(tokens))
                for idx, token in enumerate(tokens):
                    words.append(
                        {
                            "word": token,
                            "start": reel_cursor + start + (idx * step),
                            "end": reel_cursor + start + ((idx + 1) * step),
                        }
                    )

        reel_cursor += clip_duration

    return words


def process_api_job(job_id, source_path) -> dict:
    source = Path(source_path)
    temp_video = None
    temp_wav = None

    try:
        update_job_status(int(job_id), STATUS_PROCESSING)
        temp_video = PathResolver.temp_copy(source)
        shutil.copy2(str(source), str(temp_video))
        log.info("[VIDEO][API] Processing job #%s | %s", job_id, source.name)

        probe = ffmpeg_utils.probe_video(temp_video)
        temp_wav = TEMP_DIR / f"{source.stem}_{job_id}.wav"
        ffmpeg_utils.extract_audio(temp_video, temp_wav)

        transcript = transcriber.transcribe(temp_wav, model_size=WHISPER_MODEL_SIZE)
        summary = _summarize_transcript(transcript.get("full_text", ""))

        output_video_path = PathResolver.output_for_pipeline(PIPELINE_VIDEO, source)
        output_video_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(temp_video), str(output_video_path))

        subtitle_path = Path(output_video_path).with_suffix(".srt")
        subtitler.generate_srt(transcript, str(subtitle_path))

        update_job_video_fields(
            job_id=int(job_id),
            transcript=transcript.get("full_text", ""),
            video_duration=probe.get("duration", 0.0),
        )
        update_job_status(
            int(job_id),
            STATUS_DONE,
            output_path=output_video_path,
            srt_path=subtitle_path,
        )

        return {
            "output_path": str(output_video_path),
            "subtitle_path": str(subtitle_path),
            "transcript": transcript.get("full_text", ""),
            "summary": summary,
            "duration_seconds": probe.get("duration", 0.0),
        }
    except VideoPipelineError as exc:
        log.exception("[VIDEO][API] Pipeline error for job #%s: %s", job_id, exc)
        update_job_status(int(job_id), STATUS_FAILED, error_message=str(exc))
        raise
    except Exception as exc:
        log.exception("[VIDEO][API] Unexpected failure for job #%s: %s", job_id, exc)
        update_job_status(int(job_id), STATUS_FAILED, error_message=str(exc))
        raise
    finally:
        for path in (temp_wav, temp_video):
            if path and Path(path).exists():
                try:
                    Path(path).unlink()
                except OSError:
                    pass


def run(job_id, source_path):
    source = Path(source_path)
    base_name = source.stem
    temp_video = None
    temp_wav = None
    frames_dir = None
    try:
        update_job_status(int(job_id), STATUS_PROCESSING)
        temp_video = PathResolver.temp_copy(source)
        shutil.copy2(str(source), str(temp_video))
        log.info("[VIDEO] Processing job #%s | %s", job_id, source.name)

        probe = ffmpeg_utils.probe_video(temp_video)
        update_job_video_fields(job_id=int(job_id), video_duration=probe.get("duration", 0.0))

        temp_wav = TEMP_DIR / f"{source.stem}_{job_id}.wav"
        ffmpeg_utils.extract_audio(temp_video, temp_wav)
        frames_dir = TEMP_DIR / f"frames_{job_id}"
        frame_paths = ffmpeg_utils.extract_frames(temp_video, frames_dir, interval_seconds=FRAME_SAMPLE_INTERVAL_SEC)

        transcript = transcriber.transcribe(temp_wav, model_size=WHISPER_MODEL_SIZE)
        update_job_video_fields(job_id=int(job_id), transcript=transcript.get("full_text", ""))

        audio_stats = audio_analyzer.analyze_audio(temp_wav)
        update_job_video_fields(job_id=int(job_id), audio_stats=json.dumps(audio_stats))

        game = game_detector.detect_game(frame_paths, transcript.get("full_text", ""))
        game_genre = game.get("game_genre") or "unknown"
        game_title = game.get("game_title")
        update_job_video_fields(job_id=int(job_id), game_genre=game_genre, game_title=game_title)

        candidates = audio_analyzer.find_candidate_moments(audio_stats, top_n=20)
        scored = highlight_detector.score_moments(candidates, audio_stats, transcript, game_genre)
        moments = highlight_detector.deduplicate_moments(scored)[:MAX_HIGHLIGHTS]

        if CLIP_TRIGGERS.get("enabled"):
            keyword_moments = keyword_clipper.find_keyword_moments(
                transcript,
                CLIP_TRIGGERS.get("triggers", []),
                audio_stats.get("duration_sec", 0.0),
            )
            moments = highlight_detector.deduplicate_moments(moments + keyword_moments)

        if not moments:
            fallback_end = min(float(audio_stats.get("duration_sec", 0.0) or probe.get("duration", 0.0) or 30.0), 30.0)
            fallback_end = max(0.1, fallback_end)
            moments = [
                {
                    "timestamp": fallback_end / 2,
                    "score": 1,
                    "clip_start": 0.0,
                    "clip_end": fallback_end,
                    "reason": "fallback starter clip",
                    "source": "fallback",
                }
            ]

        exported = clip_exporter.export_clips(
            str(temp_video),
            moments,
            game_genre,
            game_title,
            str(job_id),
            base_name=base_name,
        )
        if not exported:
            raise VideoPipelineError("All clips failed to export", recoverable=False)
        clip_paths = [item["clip_path"] for item in exported]
        exported_moments = [item["moment"] for item in exported]

        if GEMINI_RERANK_CLIPS:
            _ = clip_ranker.rerank_clips_with_gemini(clip_paths, game_genre)

        # Generate SRTs alongside clips
        for item in exported:
            clip_path = item["clip_path"]
            moment = item["moment"]
            clip_file = Path(clip_path)
            clip_srt = clip_file.with_suffix(".srt")
            subtitler.clip_srt(transcript, float(moment["clip_start"]), float(moment["clip_end"]), str(clip_srt))
            if BURN_SUBTITLES:
                burned = clip_file.with_name(f"{clip_file.stem}_subbed{clip_file.suffix}")
                try:
                    subtitler.burn_subtitles(str(clip_file), str(clip_srt), str(burned))
                    burned.replace(clip_file)
                except Exception:
                    log.warning("[VIDEO] Failed to burn subtitles for %s", clip_file.name)

        reel_path = None
        captioned_reel_path = None
        if BUILD_HIGHLIGHT_REEL:
            reel_name = f"{base_name}_reel1.mp4"
            reel_target = PathResolver.reels_dir() / reel_name
            try:
                reel_path = reel_assembler.assemble_reel(clip_paths, str(reel_target), max_clips=MAX_REEL_CLIPS)
            except VideoPipelineError:
                reel_path = None
            if reel_path and ENABLE_CAPTION_PIPELINE:
                try:
                    from pipelines.caption_pipeline.pipeline import run as run_caption_pipeline

                    caption_words = _caption_words_for_reel(transcript, exported[:MAX_REEL_CLIPS])
                    if not caption_words:
                        caption_words = _caption_words_from_clip_srts(exported[:MAX_REEL_CLIPS])
                    captioned_reel_path = run_caption_pipeline(reel_path, words=caption_words)
                except Exception as exc:
                    log.warning("[VIDEO] Failed to caption reel %s: %s", reel_path, exc)
                if not captioned_reel_path:
                    raise VideoPipelineError(
                        f"Captioned reel was not created for {Path(reel_path).name}",
                        recoverable=True,
                    )

        final_output_path = Path(captioned_reel_path or reel_path or clip_paths[0])

        update_job_video_fields(
            job_id=int(job_id),
            transcript=transcript.get("full_text", ""),
            video_duration=probe.get("duration", 0.0),
            clip_paths=json.dumps(clip_paths),
            highlight_timestamps=json.dumps(
                [
                    {"timestamp": m["timestamp"], "score": m["score"], "source": m.get("source", "audio")}
                    for m in exported_moments
                ]
            ),
            reel_path=str(captioned_reel_path or reel_path) if (captioned_reel_path or reel_path) else None,
        )
        update_job_status(int(job_id), STATUS_DONE, output_path=final_output_path)
    except VideoPipelineError as exc:
        log.exception("[VIDEO] Pipeline error for job #%s: %s", job_id, exc)
        update_job_status(int(job_id), STATUS_FAILED, error_message=str(exc))
    except Exception as exc:
        log.exception("[VIDEO] Unexpected failure for job #%s: %s", job_id, exc)
        update_job_status(int(job_id), STATUS_FAILED, error_message=str(exc))
    finally:
        for path in (temp_wav, temp_video):
            if path and Path(path).exists():
                try:
                    Path(path).unlink()
                except OSError:
                    pass
        if frames_dir and Path(frames_dir).exists():
            shutil.rmtree(frames_dir, ignore_errors=True)

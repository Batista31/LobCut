from __future__ import annotations

from pathlib import Path

from config.logger import get_logger
from orchestrator.database import insert_reel_job, update_reel_job
from pipelines.caption_pipeline import ass_builder, caption_burner, caption_transcriber
from pipelines.caption_pipeline.errors import CaptionPipelineError
from pipelines.video_pipeline.ffmpeg_utils import probe_video

log = get_logger(__name__)


def run(reel_path: str, words: list[dict] | None = None) -> str | None:
    reel = Path(reel_path)
    if not reel.exists():
        raise CaptionPipelineError(f"Reel not found: {reel}", recoverable=False)
    reel_job_id = insert_reel_job(reel, status="IN_PROGRESS")

    ass_path = None
    try:
        caption_words = words if words is not None else caption_transcriber.transcribe_for_captions(str(reel))
        if not caption_words:
            update_reel_job(reel_job_id, status="DONE", word_count=0)
            log.info("[CAPTION] No speech detected for %s", reel.name)
            return None

        meta = probe_video(reel)
        ass_content = ass_builder.build_ass(caption_words, int(meta.get("width", 1920)), int(meta.get("height", 1080)), {})
        ass_path = str(reel.with_suffix(".ass"))
        ass_builder.save_ass(ass_content, ass_path)

        captioned_dir = reel.parent / "captioned"
        captioned_path = captioned_dir / f"{reel.stem}_captioned.mp4"
        output = caption_burner.burn_captions(str(reel), ass_path, str(captioned_path))
        update_reel_job(
            reel_job_id,
            status="DONE",
            captioned_path=Path(output),
            word_count=len(caption_words),
        )
        log.info("[CAPTION] DONE %s -> %s", reel.name, output)
        return output
    except CaptionPipelineError as exc:
        update_reel_job(reel_job_id, status="FAILED", error=str(exc))
        log.exception("[CAPTION] FAILED %s", reel.name)
        return None
    except Exception as exc:
        update_reel_job(reel_job_id, status="FAILED", error=str(exc))
        log.exception("[CAPTION] FAILED %s", reel.name)
        return None
    finally:
        if ass_path:
            try:
                Path(ass_path).unlink(missing_ok=True)
            except OSError:
                pass

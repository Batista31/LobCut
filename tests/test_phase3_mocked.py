"""
Mocked smoke test for video pipeline orchestration.
Usage:
  py test_phase3_mocked.py
"""

from pathlib import Path
from unittest.mock import patch

from orchestrator.database import init_db
from pipelines.video_pipeline.pipeline import run


def main():
    init_db()
    sample = Path("input/videos/sample_test.mp4")
    sample.parent.mkdir(parents=True, exist_ok=True)
    if not sample.exists():
        sample.write_bytes(b"not-a-real-video")

    with patch("pipelines.video_pipeline.ffmpeg_utils.probe_video", return_value={"duration": 60.0}), patch(
        "pipelines.video_pipeline.ffmpeg_utils.extract_audio",
        return_value="temp/sample.wav",
    ), patch(
        "pipelines.video_pipeline.ffmpeg_utils.extract_frames",
        return_value=[],
    ), patch(
        "pipelines.video_pipeline.transcriber.transcribe",
        return_value={"full_text": "let's go headshot", "language": "en", "segments": [{"start": 5.0, "end": 7.0, "text": "let's go"}]},
    ), patch(
        "pipelines.video_pipeline.audio_analyzer.analyze_audio",
        return_value={"duration_sec": 60.0, "onset_timeline": [[5.0, 3.0]], "spectral_timeline": [[5.0, 4500]], "silence_periods": []},
    ), patch(
        "pipelines.video_pipeline.game_detector.detect_game",
        return_value={"game_title": "valorant", "game_genre": "fps"},
    ), patch(
        "pipelines.video_pipeline.clip_exporter.export_clips",
        return_value=["output/videos/fps/valorant_1_clip1_5s.mp4"],
    ), patch(
        "pipelines.video_pipeline.reel_assembler.assemble_reel",
        return_value="output/videos/reels/valorant_1_reel.mp4",
    ):
        run(1, str(sample))
    print("Phase 3 mocked pipeline smoke completed.")


if __name__ == "__main__":
    main()

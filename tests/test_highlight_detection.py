from pipelines.video_pipeline.highlight_detector import deduplicate_moments, score_moments


def test_scoring_and_dedup():
    audio_stats = {
        "duration_sec": 180.0,
        "onset_timeline": [[10.0, 0.5], [20.0, 2.2], [30.0, 1.8]],
        "spectral_timeline": [[10.0, 1000], [20.0, 4200], [30.0, 1800]],
        "silence_periods": [[16.0, 19.0]],
    }
    transcript = {
        "segments": [
            {"start": 19.0, "end": 23.0, "text": "what a headshot clutch let's go"},
            {"start": 28.0, "end": 31.0, "text": "nice play"},
        ]
    }
    moments = score_moments([20.0, 30.0], audio_stats, transcript, "fps")
    deduped = deduplicate_moments(moments, min_gap_sec=5)
    assert deduped
    assert deduped[0]["timestamp"] == 20.0

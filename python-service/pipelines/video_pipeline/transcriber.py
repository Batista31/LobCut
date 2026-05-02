from pipelines.video_pipeline.errors import VideoPipelineError

_model_cache = {}


def transcribe(wav_path, model_size="base", word_timestamps=True) -> dict:
    try:
        import whisper
    except ImportError as exc:
        raise VideoPipelineError("openai-whisper is not installed", recoverable=False) from exc

    if model_size not in _model_cache:
        _model_cache[model_size] = whisper.load_model(model_size)
    model = _model_cache[model_size]
    result = model.transcribe(str(wav_path), word_timestamps=word_timestamps)
    text = (result.get("text") or "").strip()
    segments = result.get("segments") or []
    return {
        "full_text": text,
        "language": result.get("language", "unknown"),
        "segments": [
            {
                "start": float(s.get("start", 0.0)),
                "end": float(s.get("end", 0.0)),
                "text": s.get("text", "").strip(),
                "words": s.get("words", []),
            }
            for s in segments
        ],
    }

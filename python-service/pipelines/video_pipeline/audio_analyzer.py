from __future__ import annotations

import math

from pipelines.video_pipeline.errors import VideoPipelineError


def analyze_audio(wav_path) -> dict:
    try:
        import librosa
        import numpy as np
    except ImportError as exc:
        raise VideoPipelineError("librosa/numpy are not installed", recoverable=False) from exc

    y, sr = librosa.load(str(wav_path), sr=16000, mono=True)
    if y.size == 0:
        return {
            "duration_sec": 0.0,
            "mean_rms": 0.0,
            "rms_timeline": [],
            "energy_spikes": [],
            "silence_periods": [],
            "onset_timeline": [],
            "spectral_timeline": [],
        }

    hop = max(1, int(sr * 0.5))
    rms = librosa.feature.rms(y=y, hop_length=hop)[0]
    onset = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
    centroid = librosa.feature.spectral_centroid(y=y, sr=sr, hop_length=hop)[0]
    times = librosa.frames_to_time(range(len(rms)), sr=sr, hop_length=hop)

    mean_rms = float(rms.mean()) if len(rms) else 0.0
    onset_mean = float(onset.mean()) if len(onset) else 0.0
    onset_std = float(onset.std()) if len(onset) else 0.0
    onset_threshold = onset_mean + 2 * onset_std

    energy_spikes = [float(t) for t, o in zip(times, onset) if o > onset_threshold]
    silence_threshold = max(mean_rms * 0.4, 0.005)
    silence_periods = []
    start = None
    for t, v in zip(times, rms):
        if v < silence_threshold and start is None:
            start = float(t)
        elif v >= silence_threshold and start is not None:
            if float(t) - start >= 2.0:
                silence_periods.append([start, float(t)])
            start = None
    if start is not None and len(times):
        end = float(times[-1])
        if end - start >= 2.0:
            silence_periods.append([start, end])

    return {
        "duration_sec": float(librosa.get_duration(y=y, sr=sr)),
        "mean_rms": mean_rms,
        "rms_timeline": [[float(t), float(v)] for t, v in zip(times, rms)],
        "energy_spikes": energy_spikes,
        "silence_periods": silence_periods,
        "onset_timeline": [[float(t), float(v)] for t, v in zip(times, onset)],
        "spectral_timeline": [[float(t), float(v)] for t, v in zip(times, centroid)],
    }


def find_candidate_moments(audio_stats: dict, top_n=20, min_gap=10) -> list[float]:
    ranked = sorted(audio_stats.get("onset_timeline", []), key=lambda x: x[1], reverse=True)
    selected = []
    for ts, _score in ranked:
        if all(abs(float(ts) - s) >= min_gap for s in selected):
            selected.append(float(ts))
        if len(selected) >= top_n:
            break
    return sorted(selected)

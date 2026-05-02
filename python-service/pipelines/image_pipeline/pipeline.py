"""
pipelines/image_pipeline/pipeline.py
Phase 2 image processing pipeline for OpenClaw.
"""

from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path

from config.logger import get_logger
from config.path_resolver import PathResolver
from config.settings import (
    BLUR_LAPLACIAN_THRESHOLD,
    DEFAULT_IMAGE_CATEGORY,
    GEMINI_API_KEY_ENV_VAR,
    GEMINI_BASE_CATEGORIES,
    GEMINI_IMAGE_MODEL,
    GEMINI_FALLBACK_MODELS,
    GEMINI_MAX_RETRIES_PER_MODEL,
    GEMINI_RETRY_DELAY_SECONDS,
    TEMP_DIR,
)
from orchestrator.database import (
    STATUS_DONE,
    STATUS_FAILED,
    update_job_analysis,
    update_job_status,
)

log = get_logger(__name__)

_gemini_client = None
_dotenv_loaded = False


def _fallback_classification(source: Path, error: Exception) -> dict:
    name = source.stem.lower()
    category = DEFAULT_IMAGE_CATEGORY
    tags = ["classification_fallback"]
    summary = "Gemini classification was unavailable, so a fallback category was used."

    if "screenshot" in name:
        category = "screenshot"
        tags.append("screen_capture")
        summary = "Gemini classification was unavailable; filename suggests this is a screenshot."
    elif any(token in name for token in ("portrait", "selfie", "person", "people")):
        category = "people"
        tags.append("filename_hint_people")
        summary = "Gemini classification was unavailable; filename suggests people are the main subject."

    log.warning(
        "[IMAGE] Falling back to heuristic classification for %s after Gemini failure: %s",
        source.name,
        error,
    )
    return {
        "primary_category": category,
        "secondary_tags": tags,
        "contains_people": category in {"people", "portrait"},
        "summary": summary,
        "confidence": 0.0,
    }


def _copy_to_temp(source: Path) -> Path:
    temp_copy = PathResolver.temp_copy(source)
    shutil.copy2(str(source), str(temp_copy))
    log.debug("Copied to temp: %s -> %s", source, temp_copy)
    return temp_copy


def _get_cv2():
    try:
        import cv2
    except ImportError as exc:
        raise RuntimeError(
            "opencv-python is required for blur detection but is not installed."
        ) from exc
    return cv2


def _load_dotenv_if_present() -> None:
    global _dotenv_loaded

    if _dotenv_loaded:
        return

    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    if not env_path.exists():
        _dotenv_loaded = True
        return

    dotenv_loaded = False
    try:
        from dotenv import load_dotenv

        load_dotenv(dotenv_path=env_path, override=True)
        dotenv_loaded = True
    except ImportError:
        dotenv_loaded = False

    if not dotenv_loaded:
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                os.environ[key] = value

    log.debug("Loaded environment variables from %s", env_path)

    _dotenv_loaded = True


def _get_gemini_client():
    global _gemini_client

    if _gemini_client is not None:
        return _gemini_client

    try:
        from google import genai
    except ImportError as exc:
        raise RuntimeError(
            "google-genai is required for Gemini image classification but is not installed."
        ) from exc

    _load_dotenv_if_present()
    api_key = os.getenv(GEMINI_API_KEY_ENV_VAR)
    if not api_key:
        raise RuntimeError(
            f"{GEMINI_API_KEY_ENV_VAR} is not set. Configure the Gemini API key before starting OpenClaw."
        )

    _gemini_client = genai.Client(api_key=api_key)
    return _gemini_client


def _laplacian_variance(image_path: Path) -> float:
    cv2 = _get_cv2()
    image = cv2.imread(str(image_path))
    if image is None:
        raise RuntimeError(f"Could not read image: {image_path}")

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    variance = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    log.debug("Blur score for %s: %.4f", image_path.name, variance)
    return variance


def _is_blurry(score: float) -> bool:
    return score < BLUR_LAPLACIAN_THRESHOLD


def _classify_with_gemini(image_path: Path) -> dict:
    client = _get_gemini_client()
    try:
        from google.genai import errors as genai_errors
    except ImportError:
        genai_errors = None

    prompt = (
        "Classify this image for an autonomous media organizer. "
        "Choose the best dominant category from the allowed list, add concise secondary tags, "
        "state whether people are visible, and include a one-sentence summary. "
        "Use the most visually important subject, not vague mood words. "
        "Prefer 'people' or 'portrait' when humans are the main subject, "
        "'screenshot' for screen captures, 'document' for paper/text documents, and 'other' only as fallback."
    )
    schema = {
        "type": "object",
        "properties": {
            "primary_category": {
                "type": "string",
                "enum": list(GEMINI_BASE_CATEGORIES),
            },
            "secondary_tags": {
                "type": "array",
                "items": {"type": "string"},
            },
            "contains_people": {
                "type": "boolean",
            },
            "summary": {
                "type": "string",
            },
            "confidence": {
                "type": "number",
            },
        },
        "required": [
            "primary_category",
            "secondary_tags",
            "contains_people",
            "summary",
            "confidence",
        ],
        "additionalProperties": False,
    }

    uploaded_file = client.files.upload(file=str(image_path))
    try:
        response = None
        last_error = None
        models_to_try = []
        for model_name in GEMINI_FALLBACK_MODELS:
            if model_name not in models_to_try:
                models_to_try.append(model_name)
        if GEMINI_IMAGE_MODEL not in models_to_try:
            models_to_try.insert(0, GEMINI_IMAGE_MODEL)

        for model_name in models_to_try:
            for attempt in range(1, GEMINI_MAX_RETRIES_PER_MODEL + 1):
                try:
                    log.info(
                        "[IMAGE] Gemini classify attempt %d/%d using %s for %s",
                        attempt,
                        GEMINI_MAX_RETRIES_PER_MODEL,
                        model_name,
                        image_path.name,
                    )
                    response = client.models.generate_content(
                        model=model_name,
                        contents=[uploaded_file, prompt],
                        config={
                            "response_mime_type": "application/json",
                            "response_json_schema": schema,
                            "temperature": 0.1,
                        },
                    )
                    last_error = None
                    break
                except Exception as exc:
                    last_error = exc
                    status_code = getattr(exc, "status_code", None)
                    is_retryable = status_code in {429, 500, 503}
                    if genai_errors is not None and isinstance(exc, getattr(genai_errors, "ServerError", tuple())):
                        is_retryable = True

                    log.warning(
                        "[IMAGE] Gemini request failed for %s with model %s on attempt %d/%d: %s",
                        image_path.name,
                        model_name,
                        attempt,
                        GEMINI_MAX_RETRIES_PER_MODEL,
                        exc,
                    )
                    if not is_retryable or attempt == GEMINI_MAX_RETRIES_PER_MODEL:
                        break
                    time.sleep(GEMINI_RETRY_DELAY_SECONDS * attempt)

            if response is not None:
                break

        if response is None:
            raise RuntimeError(f"Gemini classification failed after retries: {last_error}")
    finally:
        try:
            client.files.delete(name=uploaded_file.name)
        except Exception:
            log.warning("Could not delete uploaded Gemini file for %s", image_path.name)

    parsed = json.loads(response.text)
    category = str(parsed.get("primary_category", DEFAULT_IMAGE_CATEGORY)).strip().lower()
    if category not in GEMINI_BASE_CATEGORIES:
        category = DEFAULT_IMAGE_CATEGORY

    secondary_tags = []
    for tag in parsed.get("secondary_tags", []):
        clean_tag = str(tag).strip().lower()
        if clean_tag:
            secondary_tags.append(clean_tag)

    return {
        "primary_category": category,
        "secondary_tags": secondary_tags,
        "contains_people": bool(parsed.get("contains_people", False)),
        "summary": str(parsed.get("summary", "")).strip() or f"Classified as {category}.",
        "confidence": float(parsed.get("confidence", 0.0)),
    }


def _resolve_destination(source: Path, blurry: bool, category: str) -> Path:
    if blurry:
        return PathResolver.blurry(source)
    return PathResolver.category(source, category)


def process_job(job) -> None:
    job_id = int(job["id"])
    source = Path(job["source_path"])
    temp_copy = None

    try:
        log.info("[IMAGE] Processing Job #%d | %s", job_id, source.name)

        temp_copy = _copy_to_temp(source)
        blur_score = _laplacian_variance(temp_copy)
        blurry = _is_blurry(blur_score)

        if blurry:
            ai_result = {
                "primary_category": "blurry",
                "secondary_tags": ["low_sharpness"],
                "contains_people": False,
                "summary": "Image routed to blurry because the focus score is below threshold.",
                "confidence": 1.0,
            }
        else:
            try:
                ai_result = _classify_with_gemini(temp_copy)
            except Exception as exc:
                ai_result = _fallback_classification(source, exc)

        category = ai_result["primary_category"]
        destination = _resolve_destination(source, blurry, category)

        shutil.move(str(temp_copy), str(destination))
        update_job_analysis(
            job_id,
            ai_category=category,
            ai_tags=json.dumps(ai_result["secondary_tags"]),
            ai_summary=ai_result["summary"],
            blur_score=blur_score,
            classifier="local_blur+gemini" if not ai_result["secondary_tags"] or "classification_fallback" not in ai_result["secondary_tags"] else "local_blur+fallback",
        )
        update_job_status(job_id, STATUS_DONE, output_path=destination)

        log.info(
            "[IMAGE] DONE | Job #%d | %s -> %s | blur=%.4f | category=%s",
            job_id,
            source.name,
            destination,
            blur_score,
            category,
        )
    except Exception as exc:
        log.exception("[IMAGE] FAILED | Job #%d | %s", job_id, source.name)
        update_job_status(job_id, STATUS_FAILED, error_message=str(exc))
    finally:
        if temp_copy and temp_copy.exists() and temp_copy.parent == TEMP_DIR:
            try:
                temp_copy.unlink()
            except OSError:
                log.warning("Could not remove temp copy: %s", temp_copy)

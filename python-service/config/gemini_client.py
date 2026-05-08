from __future__ import annotations

import os
from pathlib import Path
from typing import Any


_dotenv_loaded = False
_current_key_index = 0


def _load_dotenv_if_present() -> None:
    global _dotenv_loaded
    if _dotenv_loaded:
        return

    env_path = Path(__file__).resolve().parents[2] / ".env"
    if env_path.exists():
        try:
            from dotenv import load_dotenv

            load_dotenv(dotenv_path=env_path, override=False)
        except ImportError:
            for raw_line in env_path.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))

    _dotenv_loaded = True


def _keys() -> list[str]:
    _load_dotenv_if_present()
    return [
        key
        for key in (
            os.environ.get("GEMINI_API_KEY"),
            os.environ.get("GEMINI_API_KEY_2"),
            os.environ.get("GEMINI_API_KEY_3"),
        )
        if key
    ]


def configured_key_count() -> int:
    return len(_keys())


def _is_quota_error(exc: Exception) -> bool:
    message = str(exc).lower()
    status_code = getattr(exc, "status_code", None)
    return status_code == 429 or "429" in message or "quota" in message or "resource_exhausted" in message


def generate_with_fallback(
    prompt: str | None = None,
    model_name: str = "gemini-2.0-flash",
    *,
    contents: list[Any] | None = None,
    config: dict[str, Any] | None = None,
    file_path: str | None = None,
    mime_type: str | None = None,
) -> str:
    global _current_key_index

    try:
        from google import genai
    except ImportError as exc:
        raise RuntimeError(
            "google-genai is required for Gemini features. Install project dependencies with "
            "`python -m pip install -r python-service/requirements.txt`."
        ) from exc

    keys = _keys()
    if not keys:
        raise RuntimeError("GEMINI_API_KEY is not set. Configure at least one Gemini API key.")

    last_error: Exception | None = None
    for attempt in range(len(keys)):
        idx = (_current_key_index + attempt) % len(keys)
        client = genai.Client(api_key=keys[idx])
        uploaded_file = None
        try:
            request_contents = list(contents or [])
            if prompt is not None and not request_contents:
                request_contents.append(prompt)
            if file_path:
                upload_config = {"mime_type": mime_type} if mime_type else None
                uploaded_file = client.files.upload(file=file_path, config=upload_config)
                request_contents.insert(0, uploaded_file)

            response = client.models.generate_content(
                model=model_name,
                contents=request_contents,
                config=config,
            )
            _current_key_index = idx
            return response.text
        except Exception as exc:
            last_error = exc
            if _is_quota_error(exc):
                print(f"[Gemini] Key {idx + 1} quota hit, rotating...")
                _current_key_index = (idx + 1) % len(keys)
                continue
            raise
        finally:
            if uploaded_file is not None:
                try:
                    client.files.delete(name=uploaded_file.name)
                except Exception:
                    pass

    raise RuntimeError(f"All Gemini API keys quota exceeded: {last_error}")

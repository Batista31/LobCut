from __future__ import annotations

import importlib.util
from pathlib import Path

_IMPL_PATH = Path(__file__).resolve().parents[1] / "python-service" / "config" / "gemini_client.py"
_SPEC = importlib.util.spec_from_file_location("_lobcut_gemini_client", _IMPL_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f"Could not load Gemini client from {_IMPL_PATH}")

_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

configured_key_count = _MODULE.configured_key_count
generate_with_fallback = _MODULE.generate_with_fallback

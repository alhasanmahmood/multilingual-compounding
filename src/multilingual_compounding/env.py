from __future__ import annotations

import os
from pathlib import Path


def load_env_file(path: Path) -> None:
    """Minimal .env loader so the evaluation pipeline does not depend on external config helpers."""
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if not os.environ.get(key):
            os.environ[key] = value

    had_native_openai_key = bool(os.environ.get("OPENAI_API_KEY"))

    # The existing repo uses OpenRouter-prefixed variables. Mirror them into the
    # OpenAI-compatible names expected by the evaluation pipeline and BFCL OpenAI handler.
    if not os.environ.get("OPENAI_API_KEY") and os.environ.get("OPENROUTER_API_KEY"):
        os.environ["OPENAI_API_KEY"] = os.environ["OPENROUTER_API_KEY"]
    if (
        not os.environ.get("OPENAI_BASE_URL")
        and not had_native_openai_key
        and os.environ.get("OPENROUTER_BASE_URL")
    ):
        os.environ["OPENAI_BASE_URL"] = os.environ["OPENROUTER_BASE_URL"]

from __future__ import annotations

import os

LANGUAGES = [
    ("EN", "English"),
    ("AR", "Arabic"),
    ("TR", "Turkish"),
    ("ZH", "Chinese"),
    ("HI", "Hindi"),
    ("JA", "Japanese"),
    ("ES", "Spanish"),
    ("SW", "Swahili"),
]
LANGUAGE_CODES = [code for code, _name in LANGUAGES]

PILOT_TEST_CATEGORIES = [
    "multi_turn_base",
    "multi_turn_miss_func",
    "multi_turn_miss_param",
    "multi_turn_long_context",
]


def _normalize_openrouter_model_name(model_name: str) -> str:
    normalized = model_name.strip()
    if normalized.startswith("openrouter/"):
        normalized = normalized.removeprefix("openrouter/")
    if normalized.startswith("openai/"):
        normalized = normalized.removeprefix("openai/")
    return normalized


PILOT_MODELS = {
    "gpt4o": {
        "registry_name": "gpt-4o-2024-08-06-FC",
        "model_name": "gpt-4o-2024-08-06",
        "provider": "openai_compatible",
        "handler": "responses",
        "required_env": "OPENAI_API_KEY",
    },
    "gpt4o_openai": {
        "registry_name": "gpt-4o-2024-08-06-FC",
        "model_name": "gpt-4o-2024-08-06",
        "provider": "openai_completions",
        "handler": "completions",
        "required_env": "OPENAI_API_KEY",
    },
    "gpt54": {
        "registry_name": "gpt-5.4-FC",
        "model_name": "gpt-5.4",
        "provider": "openai_compatible",
        "handler": "completions",
        "required_env": "OPENAI_API_KEY",
    },
    "gpt41": {
        "registry_name": "openai/gpt-4.1-FC",
        "model_name": "openai/gpt-4.1",
        "provider": "openai_compatible",
        "handler": "completions",
        "required_env": "OPENAI_API_KEY",
    },
    "gpt41_openai": {
        "registry_name": "gpt-4.1-FC",
        "model_name": "gpt-4.1",
        "provider": "openai_completions",
        "handler": "completions",
        "required_env": "OPENAI_API_KEY",
    },
    "claude_sonnet46": {
        "registry_name": "anthropic/claude-sonnet-4.6-FC",
        "model_name": "anthropic/claude-sonnet-4.6",
        "provider": "openai_compatible",
        "handler": "completions",
        "required_env": "OPENAI_API_KEY",
    },
    "claude_opus41": {
        "registry_name": "anthropic/claude-opus-4.1-FC",
        "model_name": "anthropic/claude-opus-4.1",
        "provider": "openai_compatible",
        "handler": "completions",
        "required_env": "OPENAI_API_KEY",
    },
    "gemini": {
        "registry_name": "google/gemini-3-flash-preview-FC",
        "model_name": "google/gemini-3-flash-preview",
        "provider": "openai_compatible",
        "handler": "completions",
        "required_env": "OPENAI_API_KEY",
    },
    "gemini25_pro_preview": {
        "registry_name": "google/gemini-2.5-pro-preview-FC",
        "model_name": "google/gemini-2.5-pro-preview",
        "provider": "openai_compatible",
        "handler": "completions",
        "required_env": "OPENAI_API_KEY",
    },
    "llama33_70b": {
        "registry_name": "meta-llama/llama-3.3-70b-instruct-FC",
        "model_name": "meta-llama/llama-3.3-70b-instruct",
        "provider": "openai_compatible",
        "handler": "completions",
        "required_env": "OPENAI_API_KEY",
    },
    "qwen35_35b": {
        "registry_name": "qwen/qwen3.5-35b-a3b-FC",
        "model_name": "qwen/qwen3.5-35b-a3b",
        "provider": "openai_compatible",
        "handler": "completions",
        "required_env": "OPENAI_API_KEY",
    },
    "mistral_nemo": {
        "registry_name": "mistralai/mistral-nemo-FC",
        "model_name": "mistralai/mistral-nemo",
        "provider": "openai_compatible",
        "handler": "completions",
        "required_env": "OPENAI_API_KEY",
    },
}

DEFAULT_PILOT_MODEL_KEYS = ["gpt4o", "gemini"]

_MODEL_TOKENS_TO_KEYS: dict[str, str] = {}
for model_key, model_info in PILOT_MODELS.items():
    tokens = {
        model_key,
        model_info["model_name"],
        _normalize_openrouter_model_name(model_info["model_name"]),
        f"openrouter/{model_info['model_name']}",
    }
    for token in tokens:
        _MODEL_TOKENS_TO_KEYS.setdefault(token, model_key)


def supported_model_keys() -> list[str]:
    return list(PILOT_MODELS.keys())


def resolve_model_keys(model_tokens: list[str]) -> list[str]:
    resolved: list[str] = []
    seen: set[str] = set()
    for token in model_tokens:
        normalized = _normalize_openrouter_model_name(token)
        model_key = _MODEL_TOKENS_TO_KEYS.get(token) or _MODEL_TOKENS_TO_KEYS.get(normalized)
        if model_key is None:
            supported = ", ".join(supported_model_keys())
            raise ValueError(f"Unsupported model '{token}'. Supported keys: {supported}")
        if model_key not in seen:
            resolved.append(model_key)
            seen.add(model_key)
    return resolved


def env_backbone_pool_model_keys(env_value: str | None = None) -> list[str]:
    raw_value = env_value if env_value is not None else os.getenv("OPENROUTER_LLM_BACKBONES", "")
    if not raw_value.strip():
        return list(DEFAULT_PILOT_MODEL_KEYS)
    return resolve_model_keys(
        [token.strip() for token in raw_value.split(",") if token.strip()]
    )


def resolve_language_codes(language_codes: list[str] | None) -> list[str]:
    if not language_codes:
        return list(LANGUAGE_CODES)

    resolved: list[str] = []
    seen: set[str] = set()
    valid_codes = set(LANGUAGE_CODES)
    for code in language_codes:
        normalized = code.upper()
        if normalized not in valid_codes:
            supported = ", ".join(LANGUAGE_CODES)
            raise ValueError(f"Unsupported language '{code}'. Supported codes: {supported}")
        if normalized not in seen:
            resolved.append(normalized)
            seen.add(normalized)
    return resolved


def language_pairs(language_codes: list[str] | None = None) -> list[tuple[str, str]]:
    allowed = set(resolve_language_codes(language_codes))
    return [(code, name) for code, name in LANGUAGES if code in allowed]


BFCL_COMMIT = "6ea57973c7a6097fd7c5915698c54c17c5b1b6c8"
DEFAULT_TRANSLATION_MODEL = "gpt-4o-2024-08-06"
DEFAULT_TEMPERATURE = 0.001
DEFAULT_RUN_LABELS = ["seed0"]

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

import requests

from .settings import DEFAULT_TRANSLATION_MODEL


FILE_PATTERN = re.compile(r"\b[\w.-]+\.[A-Za-z0-9]{1,8}\b")
TAG_PATTERN = re.compile(r"[@#][A-Za-z0-9_]+")
CODE_PATTERN = re.compile(r"\b[A-Z]{2,}[0-9]+\b")
NUMBER_PATTERN = re.compile(r"\b\d+(?:\.\d+)?\b")
QUOTED_PATTERN = re.compile(r"'([^']+)'|\"([^\"]+)\"")


@dataclass
class LocalizationArtifact:
    task_id: str
    language_code: str
    language_name: str
    localized_turns: list[str]
    backtranslated_turns: list[str]
    anchor_literals: list[str]
    preserved_literals: list[str]
    missing_literals: list[str]
    backtranslation_similarity: float
    invariance_pass: bool
    machine_fidelity_rating: int


class OpenAICompatibleTranslator:
    def __init__(self, model: str | None = None):
        self.model = model or os.getenv("TRANSLATION_MODEL") or DEFAULT_TRANSLATION_MODEL
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self.api_key = os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY must be set for localization.")

    def _chat_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        last_error: Exception | None = None
        for attempt in range(3):
            try:
                response = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "temperature": 0,
                        "response_format": {"type": "json_object"},
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                    },
                    timeout=120,
                )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
                return json.loads(content)
            except Exception as exc:  # network / provider errors
                last_error = exc
                if attempt == 2:
                    raise
                time.sleep(2 * (attempt + 1))
        assert last_error is not None
        raise last_error

    def translate_turns(self, turns: list[str], target_language: str) -> list[str]:
        payload = self._chat_json(
            system_prompt=(
                "You translate user-facing benchmark queries. Preserve filenames, "
                "quoted strings, usernames, hashtags, IDs, passwords, units, and "
                "other literal tokens exactly unless translating them would change "
                "task meaning. Return JSON with key 'translations' containing a list "
                "with one translated string per input turn in the same order."
            ),
            user_prompt=(
                f"Translate the following user turns into {target_language}.\n\n"
                f"Turns:\n{json.dumps(turns, ensure_ascii=False)}"
            ),
        )
        return [text.strip() for text in payload["translations"]]

    def backtranslate_turns(self, turns: list[str], source_language: str) -> list[str]:
        payload = self._chat_json(
            system_prompt=(
                "You back-translate benchmark queries into English. Preserve literal "
                "tokens exactly. Return JSON with key 'translations' containing a list "
                "with one English string per input turn in the same order."
            ),
            user_prompt=(
                f"Back-translate the following {source_language} turns into English.\n\n"
                f"Turns:\n{json.dumps(turns, ensure_ascii=False)}"
            ),
        )
        return [text.strip() for text in payload["translations"]]


def extract_anchor_literals(*texts: str) -> list[str]:
    anchors: list[str] = []
    for text in texts:
        for pattern in (FILE_PATTERN, TAG_PATTERN, CODE_PATTERN, NUMBER_PATTERN):
            anchors.extend(pattern.findall(text))
        for left, right in QUOTED_PATTERN.findall(text):
            anchors.append(left or right)
    seen = set()
    ordered = []
    for anchor in anchors:
        anchor = str(anchor).strip()
        if anchor and any(ch.isalnum() for ch in anchor) and anchor not in seen:
            seen.add(anchor)
            ordered.append(anchor)
    return ordered


def extract_literals_from_ground_truth(ground_truth: list[list[str]]) -> list[str]:
    return extract_anchor_literals(*[call for turn in ground_truth for call in turn])


def compute_similarity(original_turns: list[str], backtranslated_turns: list[str]) -> float:
    original_text = "\n".join(original_turns).casefold()
    backtranslated_text = "\n".join(backtranslated_turns).casefold()
    return SequenceMatcher(a=original_text, b=backtranslated_text).ratio()


def literal_in_text(literal: str, text: str) -> bool:
    return literal.casefold() in text.casefold()


def build_localization_artifact(
    task_id: str,
    language_code: str,
    language_name: str,
    original_turns: list[str],
    localized_turns: list[str],
    backtranslated_turns: list[str],
    ground_truth: list[list[str]],
) -> LocalizationArtifact:
    anchors = extract_anchor_literals(*original_turns)
    anchors.extend(extract_literals_from_ground_truth(ground_truth))
    anchors = list(dict.fromkeys(anchors))
    localized_blob = "\n".join(localized_turns)
    backtranslated_blob = "\n".join(backtranslated_turns)
    preserved = [
        anchor
        for anchor in anchors
        if literal_in_text(anchor, localized_blob) or literal_in_text(anchor, backtranslated_blob)
    ]
    missing = [anchor for anchor in anchors if anchor not in preserved]
    similarity = compute_similarity(original_turns, backtranslated_turns)
    anchor_ratio = (len(preserved) / len(anchors)) if anchors else 1.0
    fidelity = max(1, min(5, round(1 + 4 * ((similarity + anchor_ratio) / 2))))
    return LocalizationArtifact(
        task_id=task_id,
        language_code=language_code,
        language_name=language_name,
        localized_turns=localized_turns,
        backtranslated_turns=backtranslated_turns,
        anchor_literals=anchors,
        preserved_literals=preserved,
        missing_literals=missing,
        backtranslation_similarity=similarity,
        invariance_pass=not missing,
        machine_fidelity_rating=fidelity,
    )

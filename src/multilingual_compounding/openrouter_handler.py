from __future__ import annotations

import json
import os
import sys
import time
from typing import Any

import requests

from .paths import VENDOR_ROOT

vendor_path = str(VENDOR_ROOT)
if vendor_path not in sys.path:
    sys.path.insert(0, vendor_path)

from bfcl_eval.model_handler.api_inference.openai_completion import (
    OpenAICompletionsHandler,
)


class OpenRouterChatCompletionsHandler(OpenAICompletionsHandler):
    """OpenAI-compatible handler backed by raw OpenRouter chat completions."""

    def __init__(
        self,
        model_name,
        temperature,
        registry_name,
        is_fc_model,
        seed: int | None = None,
        **kwargs,
    ) -> None:
        super().__init__(
            model_name=model_name,
            temperature=temperature,
            registry_name=registry_name,
            is_fc_model=is_fc_model,
            **kwargs,
        )
        self.seed = seed
        self.api_key = os.getenv("OPENAI_API_KEY") or os.getenv("OPENROUTER_API_KEY")
        self.base_url = (
            os.getenv("OPENAI_BASE_URL")
            or os.getenv("OPENROUTER_BASE_URL")
            or "https://openrouter.ai/api/v1"
        ).rstrip("/")
        if not self.api_key:
            raise ValueError("OpenRouter/OpenAI-compatible API key is required.")

    def generate_with_backoff(self, **kwargs):
        if self.seed is not None:
            kwargs.setdefault("seed", self.seed)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        last_error: Exception | None = None
        for attempt in range(4):
            try:
                start_time = time.time()
                response = requests.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=kwargs,
                    timeout=180,
                )
                end_time = time.time()
                response.raise_for_status()
                return response.json(), end_time - start_time
            except Exception as exc:
                last_error = exc
                if attempt == 3:
                    raise
                time.sleep(2 * (attempt + 1))
        assert last_error is not None
        raise last_error

    def _parse_query_response_FC(self, api_response: Any) -> dict:
        if "choices" not in api_response:
            if "output" in api_response:
                model_responses = []
                tool_call_ids = []
                for item in api_response.get("output", []):
                    if item.get("type") == "function_call":
                        model_responses.append(
                            {item["name"]: item.get("arguments", "{}")}
                        )
                        tool_call_ids.append(
                            item.get("call_id") or item.get("id") or ""
                        )
                if not model_responses:
                    model_responses = api_response.get("output_text") or str(api_response)
                    tool_call_ids = []
                return {
                    "model_responses": model_responses,
                    "model_responses_message_for_chat_history": {
                        "role": "assistant",
                        "content": (
                            model_responses if isinstance(model_responses, str) else None
                        ),
                    },
                    "tool_call_ids": [call_id for call_id in tool_call_ids if call_id],
                    "input_token": api_response.get("usage", {}).get("input_tokens", 0),
                    "output_token": api_response.get("usage", {}).get("output_tokens", 0),
                }

            error = api_response.get("error")
            if isinstance(error, dict):
                error_message = error.get("message") or str(error)
            elif error is not None:
                error_message = str(error)
            else:
                error_message = str(api_response)

            return {
                "model_responses": error_message,
                "model_responses_message_for_chat_history": {
                    "role": "assistant",
                    "content": error_message,
                },
                "tool_call_ids": [],
                "input_token": api_response.get("usage", {}).get("prompt_tokens", 0),
                "output_token": api_response.get("usage", {}).get("completion_tokens", 0),
            }

        message = api_response["choices"][0]["message"]
        tool_calls = message.get("tool_calls") or []
        if tool_calls:
            model_responses = [
                {
                    tool_call["function"]["name"]: tool_call["function"]["arguments"]
                }
                for tool_call in tool_calls
            ]
            tool_call_ids = [tool_call["id"] for tool_call in tool_calls]
        else:
            model_responses = message.get("content")
            tool_call_ids = []

        assistant_message = {
            "role": "assistant",
            "content": message.get("content"),
        }
        if tool_calls:
            assistant_message["tool_calls"] = tool_calls

        return {
            "model_responses": model_responses,
            "model_responses_message_for_chat_history": assistant_message,
            "tool_call_ids": tool_call_ids,
            "input_token": api_response.get("usage", {}).get("prompt_tokens", 0),
            "output_token": api_response.get("usage", {}).get("completion_tokens", 0),
        }

    def _parse_query_response_prompting(self, api_response: Any) -> dict:
        message = api_response["choices"][0]["message"]
        return {
            "model_responses": message.get("content"),
            "model_responses_message_for_chat_history": {
                "role": "assistant",
                "content": message.get("content"),
            },
            "input_token": api_response.get("usage", {}).get("prompt_tokens", 0),
            "output_token": api_response.get("usage", {}).get("completion_tokens", 0),
        }

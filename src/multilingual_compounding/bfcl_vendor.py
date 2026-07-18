from __future__ import annotations
# pyright: reportMissingImports=false

import copy
import sys
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .paths import VENDOR_ROOT
from .openrouter_handler import OpenRouterChatCompletionsHandler
from .settings import PILOT_MODELS


def ensure_bfcl_on_path() -> None:
    vendor_path = str(VENDOR_ROOT)
    if vendor_path not in sys.path:
        sys.path.insert(0, vendor_path)


ensure_bfcl_on_path()

from bfcl_eval.eval_checker.multi_turn_eval.multi_turn_checker import (  # noqa: E402
    multi_turn_checker,
    response_checker,
    state_checker,
)
from bfcl_eval.model_handler.api_inference.openai_completion import (  # noqa: E402
    OpenAICompletionsHandler,
)
from bfcl_eval.model_handler.api_inference.openai_response import (  # noqa: E402
    OpenAIResponsesHandler,
)
from bfcl_eval.eval_checker.multi_turn_eval.multi_turn_utils import (  # noqa: E402
    execute_multi_turn_func_call,
    is_empty_execute_response,
)
from bfcl_eval.utils import load_dataset_entry, load_ground_truth_entry  # noqa: E402


@dataclass
class BFCLTask:
    category: str
    prompt_entry: dict[str, Any]
    ground_truth: list[list[str]]


@dataclass
class StepReplayCase:
    task_id: str
    execution_task_id: str
    category: str
    turn_index: int
    step_index: int
    current_turn_message: str
    prefix_calls: list[str]
    gold_call: str
    prefix_execution_results: list[str]
    prompt_entry: dict[str, Any]


def build_handler(model_key: str, temperature: float, seed: int | None = None):
    model_info = PILOT_MODELS[model_key]
    if model_info["provider"] == "openai_compatible":
        return OpenRouterChatCompletionsHandler(
            model_name=model_info["model_name"],
            temperature=temperature,
            registry_name=model_info["registry_name"],
            is_fc_model=True,
            seed=seed,
        )

    if model_info["provider"] == "openai_responses":
        return OpenAIResponsesHandler(
            model_name=model_info["model_name"],
            temperature=temperature,
            registry_name=model_info["registry_name"],
            is_fc_model=True,
        )

    if model_info["provider"] == "openai_completions":
        return OpenAICompletionsHandler(
            model_name=model_info["model_name"],
            temperature=temperature,
            registry_name=model_info["registry_name"],
            is_fc_model=True,
        )

    if model_info["provider"] == "google":
        from bfcl_eval.model_handler.api_inference.gemini import GeminiHandler  # noqa: E402

        return GeminiHandler(
            model_name=model_info["model_name"],
            temperature=temperature,
            registry_name=model_info["registry_name"],
            is_fc_model=True,
        )

    raise ValueError(f"Unsupported model provider: {model_info['provider']}")


def load_bfcl_multiturn_tasks(categories: list[str]) -> list[BFCLTask]:
    tasks: list[BFCLTask] = []
    for category in categories:
        prompts = load_dataset_entry(category, include_language_specific_hint=False)
        ground_truths = load_ground_truth_entry(category)
        ground_truth_map = {entry["id"]: entry["ground_truth"] for entry in ground_truths}
        for prompt_entry in prompts:
            tasks.append(
                BFCLTask(
                    category=category,
                    prompt_entry=prompt_entry,
                    ground_truth=ground_truth_map[prompt_entry["id"]],
                )
            )
    return tasks


def evaluate_multi_turn_entry(
    handler,
    prompt_entry: dict[str, Any],
    ground_truth: list[list[str]],
    model_result: list[list[Any]],
    model_name: str,
    test_category: str,
) -> dict[str, Any]:
    working_prompt = copy.deepcopy(prompt_entry)
    if "function" in working_prompt:
        del working_prompt["function"]

    if not isinstance(model_result, list):
        return {
            "valid": False,
            "error_type": "multi_turn:inference_error",
            "error_message": "Model did not return a multi-turn response list.",
        }

    if len(model_result) != len(ground_truth):
        return {
            "valid": False,
            "error_type": "multi_turn:force_terminated",
            "error_message": (
                f"Turn count mismatch: got {len(model_result)} model turns vs "
                f"{len(ground_truth)} gold turns."
            ),
        }

    decoded_turns: list[list[list[str]]] = []
    for single_turn_model_result_list in model_result:
        decoded_single_turn = []
        for model_result_item in single_turn_model_result_list:
            try:
                decoded_result = handler.decode_execute(
                    model_result_item, has_tool_call_tag=False
                )
                if is_empty_execute_response(decoded_result):
                    continue
                decoded_single_turn.append(decoded_result)
            except Exception:
                continue
        decoded_turns.append(decoded_single_turn)

    accuracy = multi_turn_checker(
        decoded_turns,
        ground_truth,
        copy.deepcopy(prompt_entry),
        test_category,
        model_name,
    )
    if not accuracy["valid"]:
        return {
            "valid": False,
            "error_type": accuracy.get("error_type", "multi_turn:unknown"),
            "error_message": accuracy.get("error_message", "BFCL multi-turn check failed."),
            "details": accuracy.get("details", {}),
            "decoded_result": decoded_turns,
        }
    return {"valid": True, "decoded_result": decoded_turns}


def build_step_replay_cases(
    task: BFCLTask,
    execution_task_id_prefix: str | None = None,
) -> list[StepReplayCase]:
    cases: list[StepReplayCase] = []
    prefix_calls: list[str] = []
    execution_task_id_prefix = execution_task_id_prefix or task.prompt_entry["id"]
    for turn_index, gold_turn in enumerate(task.ground_truth):
        current_turn_messages = task.prompt_entry["question"][turn_index]
        current_user_messages = [
            message["content"]
            for message in current_turn_messages
            if message["role"] == "user"
        ]
        current_turn_message = "\n".join(current_user_messages)
        for step_index, gold_call in enumerate(gold_turn):
            execution_task_id = (
                f"{execution_task_id_prefix}_turn{turn_index}_step{step_index}"
            )
            execution_results, _ = execute_multi_turn_func_call(
                prefix_calls,
                deepcopy(task.prompt_entry["initial_config"]),
                deepcopy(task.prompt_entry["involved_classes"]),
                "gold_prefix",
                execution_task_id,
                long_context=(
                    "long_context" in task.category or "composite" in task.category
                ),
                is_evaL_run=True,
            )
            cases.append(
                StepReplayCase(
                    task_id=task.prompt_entry["id"],
                    execution_task_id=execution_task_id,
                    category=task.category,
                    turn_index=turn_index,
                    step_index=step_index,
                    current_turn_message=current_turn_message,
                    prefix_calls=list(prefix_calls),
                    gold_call=gold_call,
                    prefix_execution_results=list(execution_results),
                    prompt_entry=task.prompt_entry,
                )
            )
            prefix_calls.append(gold_call)
    return cases


def evaluate_step_replay(
    replay_case: StepReplayCase,
    candidate_call: str | None,
) -> dict[str, Any]:
    if not candidate_call:
        return {"valid": False, "error_type": "replay:no_call"}

    long_context = (
        "long_context" in replay_case.category or "composite" in replay_case.category
    )
    candidate_execution, candidate_instances = execute_multi_turn_func_call(
        replay_case.prefix_calls + [candidate_call],
        deepcopy(replay_case.prompt_entry["initial_config"]),
        deepcopy(replay_case.prompt_entry["involved_classes"]),
        "candidate_replay",
        replay_case.execution_task_id,
        long_context=long_context,
        is_evaL_run=True,
    )
    gold_execution, gold_instances = execute_multi_turn_func_call(
        replay_case.prefix_calls + [replay_case.gold_call],
        deepcopy(replay_case.prompt_entry["initial_config"]),
        deepcopy(replay_case.prompt_entry["involved_classes"]),
        "gold_replay",
        replay_case.execution_task_id,
        long_context=long_context,
        is_evaL_run=True,
    )

    state_check = state_checker(candidate_instances, gold_instances)
    if not state_check["valid"]:
        return {
            "valid": False,
            "error_type": state_check.get("error_type", "replay:state_mismatch"),
            "details": state_check.get("details", {}),
        }

    response_check = response_checker(candidate_execution, gold_execution[-1:], 0)
    if not response_check["valid"]:
        return {
            "valid": False,
            "error_type": response_check.get(
                "error_type", "replay:execution_response_mismatch"
            ),
            "details": response_check.get("details", {}),
        }

    return {"valid": True}

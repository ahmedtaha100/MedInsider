import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from medinsider.agents import build_agent as create_agent
from medinsider.fhir.logger import FHIRActionLogger
from medinsider.fhir.state import FHIRPatientEpisodeState
from medinsider.fhir.tools import FHIRToolEnvironment


def _build_agent_system_prompt(base_prompt: str, env: FHIRToolEnvironment, min_calls: int) -> str:
    return base_prompt + "\n\n" + env.action_contract(min_calls)


def _compact_observation(
    result: dict[str, Any],
    tool_calls: int,
    min_calls: int,
    max_calls: int,
) -> dict[str, Any]:
    observation: dict[str, Any] = {
        "ok": bool(result.get("ok", False)),
        "tool": str(result.get("tool", "")),
        "tool_calls_used": tool_calls,
        "minimum_tool_calls_required": min_calls,
        "minimum_tool_calls_remaining": max(0, min_calls - tool_calls),
        "max_tool_calls": max_calls,
    }
    if "error" in result:
        observation["error"] = result["error"]
    if "schema_hint" in result:
        observation["schema_hint"] = result["schema_hint"]
    if result.get("param_normalizations"):
        observation["param_normalizations"] = result["param_normalizations"]
    if "normalized_params" in result:
        observation["normalized_params"] = result["normalized_params"]

    data = result.get("data")
    if isinstance(data, dict):
        compact_data = deepcopy(data)
        compact_data.pop("fhir_bundle", None)
        observation["data"] = compact_data
    elif data is not None:
        observation["data"] = data
    return observation


class FHIRScenarioRunner:
    def __init__(
        self,
        action_logger: FHIRActionLogger,
        min_calls: int = 6,
        max_calls: int = 20,
        context_window_pairs: int = 8,
    ):
        self.action_logger = action_logger
        self.min_calls = min_calls
        self.max_calls = max_calls
        self.context_window_pairs = context_window_pairs

    def build_environment(
        self,
        state: FHIRPatientEpisodeState,
        scenario: dict[str, Any],
    ) -> FHIRToolEnvironment:
        return FHIRToolEnvironment(state)

    def load_scenario(self, scenario_path: str) -> dict[str, Any]:
        with Path(scenario_path).open("r", encoding="utf-8") as f:
            return json.load(f)

    def build_agent(self, agent_type: str, scenario: dict[str, Any]):
        if agent_type == "scripted":
            return create_agent(agent_type=agent_type, scripted_actions=scenario.get("scripted_actions", []))
        if agent_type == "openai":
            return create_agent(
                agent_type=agent_type,
                model=scenario.get("openai_model", "gpt-5.4-2026-03-05"),
            )
        if agent_type == "claude":
            return create_agent(
                agent_type=agent_type,
                model=scenario.get("claude_model", "claude-sonnet-4-6"),
                max_tokens=scenario.get("claude_max_tokens", 1024),
            )
        if agent_type == "gemini":
            return create_agent(
                agent_type=agent_type,
                model=scenario.get("gemini_model", "gemini-2.5-pro"),
                max_output_tokens=scenario.get("gemini_max_output_tokens", 1024),
            )
        if agent_type == "openweight":
            model = str(scenario.get("openweight_model", "")).strip()
            if not model:
                raise ValueError("openweight_model is required for agent_type='openweight'")
            return create_agent(
                agent_type=agent_type,
                model=model,
                base_url=scenario.get("openweight_base_url", "http://localhost:8000/v1"),
                max_tokens=scenario.get("openweight_max_tokens", 1024),
                api_key=scenario.get("openweight_api_key", ""),
            )
        return create_agent(agent_type=agent_type)

    def run(self, scenario_path: str, agent_type: str = "scripted") -> dict[str, Any]:
        scenario = self.load_scenario(scenario_path)
        return self.run_loaded_scenario(scenario, agent_type=agent_type)

    def run_loaded_scenario(
        self,
        scenario: dict[str, Any],
        agent_type: str = "scripted",
        agent: Any | None = None,
    ) -> dict[str, Any]:
        episode_id = scenario["episode_id"]
        self.action_logger.reset(episode_id)
        patient_payload = scenario["patient_state"]
        system_prompt = scenario["system_prompt"]
        scenario_min = scenario.get("episode_length_min", self.min_calls)
        scenario_max = scenario.get("episode_length_max", self.max_calls)
        min_calls = max(self.min_calls, scenario_min)
        max_calls = min(self.max_calls, scenario_max)

        if min_calls > max_calls:
            raise ValueError(
                f"invalid_episode_constraints:effective_min={min_calls}_max={max_calls}"
                f"_runner=({self.min_calls},{self.max_calls})"
                f"_scenario=({scenario_min},{scenario_max})"
            )

        state = FHIRPatientEpisodeState.from_payload(episode_id, patient_payload)
        env = self.build_environment(state, scenario)
        agent = agent or self.build_agent(agent_type, scenario)
        reset = getattr(agent, "reset", None)
        if callable(reset):
            reset()
        agent_system_prompt = _build_agent_system_prompt(system_prompt, env, min_calls)

        messages: list[dict[str, str]] = [
            {
                "role": "user",
                "content": (
                    f"Begin episode for patient {state.patient_id}. "
                    "Respond with exactly one JSON action object. "
                    f"Finish is invalid before {min_calls} non-finish tool calls."
                ),
            }
        ]
        tool_calls = 0
        agent_error = ""
        termination_reason = "max_calls"

        while tool_calls < max_calls:
            try:
                action = agent.next_action(agent_system_prompt, messages, env.tool_names())
            except (json.JSONDecodeError, ValueError, RuntimeError, TypeError) as exc:
                agent_error = f"agent_action_error:{type(exc).__name__}:{exc}"
                termination_reason = "agent_error"
                self.action_logger.log(
                    episode_id=episode_id,
                    tool_name="__agent__",
                    params={},
                    result={
                        "ok": False,
                        "tool": "__agent__",
                        "error": agent_error,
                    },
                )
                break

            if not isinstance(action, dict):
                agent_error = f"agent_action_error:invalid_action_type:{type(action).__name__}"
                termination_reason = "agent_error"
                self.action_logger.log(
                    episode_id=episode_id,
                    tool_name="__agent__",
                    params={},
                    result={
                        "ok": False,
                        "tool": "__agent__",
                        "error": agent_error,
                    },
                )
                break

            action_name = action.get("action", "")
            params = action.get("params", {})

            if action_name == "finish":
                termination_reason = "finish"
                self.action_logger.log(
                    episode_id=episode_id,
                    tool_name="finish",
                    params={},
                    result={
                        "ok": True,
                        "tool": "finish",
                    },
                )
                break

            try:
                result = env.dispatch(action_name, params)
            except Exception as exc:
                result = {
                    "ok": False,
                    "tool": action_name,
                    "error": f"dispatch_error:{type(exc).__name__}:{exc}",
                }
            tool_calls += 1
            params_for_log = result.get("normalized_params", params)
            self.action_logger.log(
                episode_id=episode_id,
                tool_name=action_name,
                params=params_for_log,
                result=result,
            )

            messages.append(
                {
                    "role": "assistant",
                    "content": json.dumps({"action": action_name, "params": params_for_log}),
                }
            )
            messages.append(
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "observation": _compact_observation(
                                result=result,
                                tool_calls=tool_calls,
                                min_calls=min_calls,
                                max_calls=max_calls,
                            )
                        }
                    ),
                }
            )
            if self.context_window_pairs <= 0:
                messages = [messages[0]]
            else:
                max_messages = 1 + (self.context_window_pairs * 2)
                if len(messages) > max_messages:
                    messages = [messages[0]] + messages[-(self.context_window_pairs * 2) :]

        if tool_calls < min_calls:
            message = f"episode_tool_call_constraint_violation:{tool_calls}:expected_{min_calls}_to_{max_calls}"
            if agent_error:
                message = f"{message}:caused_by:{agent_error}"
            raise ValueError(message)

        summary = {
            "episode_id": episode_id,
            "scenario_family": scenario.get("scenario_family", ""),
            "condition": scenario.get("condition", ""),
            "tool_calls": tool_calls,
            "termination_reason": termination_reason,
            "log_path": str(self.action_logger._path),
            "final_chart": state.chart_snapshot(),
            "final_fhir_bundle": state.to_fhir_bundle(),
        }
        if agent_error:
            summary["agent_error"] = agent_error
        return summary

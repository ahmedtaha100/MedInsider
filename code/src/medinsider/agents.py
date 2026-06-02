from typing import Any

from medinsider.api_wrappers import ClaudeClient, GeminiClient, LocalInferenceClient, OpenAIClient


def _require_compatible_model(model: Any, agent_type: str) -> str:
    if not isinstance(model, str) or not model.strip():
        raise ValueError(f"{agent_type}_model is required for agent_type='{agent_type}'")
    return model.strip()


def _require_base_url(base_url: Any, agent_type: str) -> str:
    if not isinstance(base_url, str) or not base_url.strip():
        raise ValueError(f"{agent_type}_base_url is required for agent_type='{agent_type}'")
    return base_url.strip()


class ScriptedAgent:
    def __init__(self, scripted_actions: list[dict[str, Any]]):
        self.scripted_actions = scripted_actions
        self.index = 0

    def reset(self) -> None:
        self.index = 0

    def next_action(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        tool_names: list[str],
    ) -> dict[str, Any]:
        if self.index >= len(self.scripted_actions):
            return {"action": "finish", "params": {}}
        action = self.scripted_actions[self.index]
        self.index += 1
        return action


class OpenAIAgent:
    def __init__(self, model: str = "gpt-5.4-2026-03-05", request_timeout: int | float = 60):
        self.client = OpenAIClient(model=model, request_timeout=request_timeout)

    def complete_json(self, system_prompt: str, prompt: str) -> dict[str, Any]:
        return self.client.complete_json(system_prompt, prompt)

    def next_action(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        tool_names: list[str],
    ) -> dict[str, Any]:
        return self.client.next_action(system_prompt, messages, tool_names)


class ClaudeAgent:
    def __init__(self, model: str = "claude-sonnet-4-6", max_tokens: int = 1024, request_timeout: int | float = 60):
        self.client = ClaudeClient(model=model, max_tokens=max_tokens, request_timeout=request_timeout)

    def complete_json(self, system_prompt: str, prompt: str) -> dict[str, Any]:
        return self.client.complete_json(system_prompt, prompt)

    def next_action(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        tool_names: list[str],
    ) -> dict[str, Any]:
        return self.client.next_action(system_prompt, messages, tool_names)


class GeminiAgent:
    def __init__(
        self,
        model: str = "gemini-2.5-pro",
        max_output_tokens: int = 1024,
        request_timeout: int | float = 60,
    ):
        self.client = GeminiClient(
            model=model,
            max_output_tokens=max_output_tokens,
            request_timeout=request_timeout,
        )

    def complete_json(self, system_prompt: str, prompt: str) -> dict[str, Any]:
        return self.client.complete_json(system_prompt, prompt)

    def next_action(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        tool_names: list[str],
    ) -> dict[str, Any]:
        return self.client.next_action(system_prompt, messages, tool_names)


class LocalInferenceAgent:
    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:8000/v1",
        max_tokens: int = 1024,
        temperature: int | float = 0,
        thinking: dict[str, Any] | None = None,
        api_key: str = "",
        request_timeout: int | float = 60,
    ):
        self.client = LocalInferenceClient(
            model=model,
            base_url=base_url,
            max_tokens=max_tokens,
            temperature=temperature,
            thinking=thinking,
            api_key=api_key,
            request_timeout=request_timeout,
        )

    def complete_json(self, system_prompt: str, prompt: str) -> dict[str, Any]:
        return self.client.complete_json(system_prompt, prompt)

    def next_action(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        tool_names: list[str],
    ) -> dict[str, Any]:
        return self.client.next_action(system_prompt, messages, tool_names)


def build_agent(
    agent_type: str | None = None,
    *,
    type: str | None = None,
    **kwargs: Any,
):
    resolved_type = agent_type or type
    if resolved_type is None:
        raise TypeError("build_agent requires agent_type or type")
    if resolved_type == "scripted":
        return ScriptedAgent(kwargs.get("scripted_actions", []))
    if resolved_type == "openai":
        return OpenAIAgent(
            model=kwargs.get("model", "gpt-5.4-2026-03-05"),
            request_timeout=kwargs.get("request_timeout", 60),
        )
    if resolved_type == "claude":
        return ClaudeAgent(
            model=kwargs.get("model", "claude-sonnet-4-6"),
            max_tokens=kwargs.get("max_tokens", 1024),
            request_timeout=kwargs.get("request_timeout", 60),
        )
    if resolved_type == "gemini":
        return GeminiAgent(
            model=kwargs.get("model", "gemini-2.5-pro"),
            max_output_tokens=kwargs.get("max_output_tokens", 1024),
            request_timeout=kwargs.get("request_timeout", 60),
        )
    if resolved_type == "openweight":
        return LocalInferenceAgent(
            model=_require_compatible_model(kwargs.get("model"), resolved_type),
            base_url=kwargs.get("base_url", "http://localhost:8000/v1"),
            max_tokens=kwargs.get("max_tokens", 1024),
            temperature=kwargs.get("temperature", 0),
            thinking=kwargs.get("thinking"),
            api_key=kwargs.get("api_key", ""),
            request_timeout=kwargs.get("request_timeout", 60),
        )
    if resolved_type == "openai_compatible":
        return LocalInferenceAgent(
            model=_require_compatible_model(kwargs.get("model"), resolved_type),
            base_url=_require_base_url(kwargs.get("base_url"), resolved_type),
            max_tokens=kwargs.get("max_tokens", 1024),
            temperature=kwargs.get("temperature", 0),
            thinking=kwargs.get("thinking"),
            api_key=kwargs.get("api_key", ""),
            request_timeout=kwargs.get("request_timeout", 60),
        )
    raise ValueError(f"unsupported_agent:{resolved_type}")

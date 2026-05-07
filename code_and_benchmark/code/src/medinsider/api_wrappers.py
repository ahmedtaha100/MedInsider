import json
import os
import socket
import urllib.error
import urllib.request
from typing import Any

MAX_JSON_OBJECT_CANDIDATES = 16


def _empty_usage() -> dict[str, int]:
    return {
        "input_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
    }


def _merge_usage(current: dict[str, int], update: dict[str, int] | None) -> dict[str, int]:
    merged = dict(current)
    if not update:
        return merged
    for key in ("input_tokens", "output_tokens", "total_tokens"):
        merged[key] = int(merged.get(key, 0)) + int(update.get(key, 0) or 0)
    return merged


def _openai_usage(body: dict[str, Any]) -> dict[str, int] | None:
    usage = body.get("usage")
    if not isinstance(usage, dict):
        return None
    prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
    completion_tokens = int(usage.get("completion_tokens", 0) or 0)
    total_tokens = int(usage.get("total_tokens", prompt_tokens + completion_tokens) or 0)
    return {
        "input_tokens": prompt_tokens,
        "output_tokens": completion_tokens,
        "total_tokens": total_tokens,
    }


def _claude_usage(body: dict[str, Any]) -> dict[str, int] | None:
    usage = body.get("usage")
    if not isinstance(usage, dict):
        return None
    input_tokens = int(usage.get("input_tokens", 0) or 0)
    output_tokens = int(usage.get("output_tokens", 0) or 0)
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
    }


def _gemini_usage(body: dict[str, Any]) -> dict[str, int] | None:
    usage = body.get("usageMetadata")
    if not isinstance(usage, dict):
        return None
    input_tokens = int(usage.get("promptTokenCount", 0) or 0)
    output_tokens = int(usage.get("candidatesTokenCount", 0) or 0)
    total_tokens = int(usage.get("totalTokenCount", input_tokens + output_tokens) or 0)
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }


def _local_usage(body: dict[str, Any]) -> dict[str, int] | None:
    return _openai_usage(body)


def _claude_temperature_deprecation_error(detail: str) -> bool:
    error_type = ""
    message = detail
    try:
        payload = json.loads(detail)
    except json.JSONDecodeError:
        payload = None
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, dict):
            error_type = str(error.get("type", "") or "").lower()
            message = str(error.get("message", "") or message)
    normalized_message = message.lower()
    return (
        error_type == "invalid_request_error"
        and "temperature" in normalized_message
        and "deprecat" in normalized_message
    )


def _extract_gemini_text(body: dict[str, Any]) -> str:
    try:
        candidates = body["candidates"]
        if not candidates:
            block_reason = body.get("promptFeedback", {}).get("blockReason", "empty_candidates")
            raise KeyError(f"candidates:{block_reason}")
        candidate = candidates[0]
        parts = candidate["content"]["parts"]
        content = "".join(part.get("text", "") for part in parts).strip()
        if not content:
            raise KeyError(f"content:{candidate.get('finishReason', 'empty_text')}")
        return content
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"gemini_unexpected_response:{exc}") from exc


def _is_json_fence_marker(line: str) -> bool:
    marker = line.strip().lower()
    if not marker.startswith("```"):
        return False
    suffix = marker[3:].strip()
    return suffix in {"", "json"}


def _strip_code_fences(text: str) -> tuple[str, str]:
    stripped = text.strip()
    if not stripped.startswith("```"):
        return text, "direct"
    lines = stripped.splitlines()
    if len(lines) < 3 or lines[-1].strip() != "```":
        return text, "direct"
    first = lines[0]
    if not _is_json_fence_marker(first):
        return text, "direct"
    inner = "\n".join(lines[1:-1]).strip()
    return inner, "fenced_json"


def _remove_code_fence_lines(text: str) -> tuple[str, bool]:
    filtered: list[str] = []
    removed = False
    for line in text.splitlines():
        marker = line.strip()
        if marker == "```" or _is_json_fence_marker(marker):
            removed = True
            continue
        filtered.append(line)
    return "\n".join(filtered).strip(), removed


def _extract_json_object_candidates(text: str) -> list[str]:
    candidates: list[str] = []
    start: int | None = None
    depth = 0
    in_string = False
    escaped = False

    for index, char in enumerate(text):
        if start is None:
            if char == "{":
                start = index
                depth = 1
                in_string = False
                escaped = False
            continue

        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                candidates.append(text[start : index + 1])
                start = None
                if len(candidates) >= MAX_JSON_OBJECT_CANDIDATES:
                    break

    return candidates


def _parse_json_text(text: str) -> tuple[Any, str]:
    stripped = text.strip()
    if not stripped:
        raise json.JSONDecodeError("Expecting value", text, 0)
    try:
        return json.loads(stripped), "direct"
    except json.JSONDecodeError as original_error:
        fenced_text, fenced_mode = _strip_code_fences(stripped)
        if fenced_mode != "direct":
            try:
                return json.loads(fenced_text), fenced_mode
            except json.JSONDecodeError:
                stripped = fenced_text

        sanitized_text, removed_fences = _remove_code_fence_lines(stripped)
        if removed_fences:
            try:
                return json.loads(sanitized_text), "fence_line_repair"
            except json.JSONDecodeError:
                stripped = sanitized_text

        candidates = _extract_json_object_candidates(stripped)
        parsed_candidates: list[Any] = []
        for candidate in candidates:
            try:
                parsed_candidates.append(json.loads(candidate))
            except json.JSONDecodeError:
                continue
        if len(parsed_candidates) == 1:
            return parsed_candidates[0], "extracted_json"
        if len(parsed_candidates) > 1:
            first = parsed_candidates[0]
            if all(candidate == first for candidate in parsed_candidates[1:]):
                return first, "duplicate_json"
        raise original_error


def _action_json_instruction(tool_names: list[str]) -> str:
    return (
        "Return exactly one JSON object with keys action and params. "
        "Do not use markdown, code fences, prose, comments, or duplicate JSON objects. "
        "Allowed actions: " + ",".join(tool_names) + ",finish"
    )


class OpenAIClient:
    def __init__(self, model: str = "gpt-5.4-2026-03-05", request_timeout: int | float = 60):
        self.model = model
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        self.request_timeout = request_timeout
        self.resolved_model = model
        self.last_usage = _empty_usage()
        self.total_usage = _empty_usage()
        self.last_parse_mode = "direct"
        self.parse_repair_count = 0

    def complete_json(
        self,
        system_prompt: str,
        prompt: str,
    ) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("openai_auth_error:OPENAI_API_KEY is not set")
        payload = {
            "model": self.model,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
        }
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.request_timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")[:300]
            raise RuntimeError(f"openai_http_error:{exc.code}:{detail}") from exc
        except (TimeoutError, socket.timeout) as exc:
            raise RuntimeError(f"openai_timeout:{exc}") from exc
        except urllib.error.URLError as exc:
            if "timed out" in str(exc.reason).lower():
                raise RuntimeError(f"openai_timeout:{exc.reason}") from exc
            raise RuntimeError(f"openai_network_error:{exc.reason}") from exc
        self.resolved_model = str(body.get("model", self.model))
        self.last_usage = _openai_usage(body) or _empty_usage()
        self.total_usage = _merge_usage(self.total_usage, self.last_usage)
        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"openai_unexpected_response:{exc}") from exc
        parsed, parse_mode = _parse_json_text(content)
        self.last_parse_mode = parse_mode
        if parse_mode != "direct":
            self.parse_repair_count += 1
        return parsed

    def next_action(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        tool_names: list[str],
    ) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("openai_auth_error:OPENAI_API_KEY is not set")
        instruction = {
            "role": "system",
            "content": system_prompt + "\n" + _action_json_instruction(tool_names),
        }
        payload = {
            "model": self.model,
            "response_format": {"type": "json_object"},
            "messages": [instruction] + messages,
            "temperature": 0,
        }
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.request_timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")[:300]
            raise RuntimeError(f"openai_http_error:{exc.code}:{detail}") from exc
        except (TimeoutError, socket.timeout) as exc:
            raise RuntimeError(f"openai_timeout:{exc}") from exc
        except urllib.error.URLError as exc:
            if "timed out" in str(exc.reason).lower():
                raise RuntimeError(f"openai_timeout:{exc.reason}") from exc
            raise RuntimeError(f"openai_network_error:{exc.reason}") from exc
        self.resolved_model = str(body.get("model", self.model))
        self.last_usage = _openai_usage(body) or _empty_usage()
        self.total_usage = _merge_usage(self.total_usage, self.last_usage)
        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise RuntimeError(f"openai_unexpected_response:{exc}") from exc
        parsed, parse_mode = _parse_json_text(content)
        self.last_parse_mode = parse_mode
        if parse_mode != "direct":
            self.parse_repair_count += 1
        return parsed


class ClaudeClient:
    def __init__(self, model: str = "claude-sonnet-4-6", max_tokens: int = 1024, request_timeout: int | float = 60):
        self.model = model
        self.max_tokens = max_tokens
        self.api_key = os.getenv("ANTHROPIC_API_KEY", "")
        self.request_timeout = request_timeout
        self.resolved_model = model
        self.last_usage = _empty_usage()
        self.total_usage = _empty_usage()
        self.last_parse_mode = "direct"
        self.parse_repair_count = 0

    def _send_messages_request(self, payload: dict[str, Any]) -> dict[str, Any]:
        request_headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }
        for attempt in range(2):
            req = urllib.request.Request(
                "https://api.anthropic.com/v1/messages",
                data=json.dumps(payload).encode("utf-8"),
                headers=request_headers,
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=self.request_timeout) as resp:
                    return json.loads(resp.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                full_detail = exc.read().decode("utf-8", errors="ignore")
                if attempt == 0 and "temperature" in payload and _claude_temperature_deprecation_error(full_detail):
                    payload = dict(payload)
                    payload.pop("temperature", None)
                    continue
                detail = full_detail[:300]
                raise RuntimeError(f"claude_http_error:{exc.code}:{detail}") from exc
            except (TimeoutError, socket.timeout) as exc:
                raise RuntimeError(f"claude_timeout:{exc}") from exc
            except urllib.error.URLError as exc:
                if "timed out" in str(exc.reason).lower():
                    raise RuntimeError(f"claude_timeout:{exc.reason}") from exc
                raise RuntimeError(f"claude_network_error:{exc.reason}") from exc

    def complete_json(
        self,
        system_prompt: str,
        prompt: str,
    ) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("claude_auth_error:ANTHROPIC_API_KEY is not set")
        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": 0,
            "system": system_prompt,
            "messages": [{"role": "user", "content": prompt}],
        }
        body = self._send_messages_request(payload)
        self.resolved_model = str(body.get("model", self.model))
        self.last_usage = _claude_usage(body) or _empty_usage()
        self.total_usage = _merge_usage(self.total_usage, self.last_usage)
        text_chunks = [chunk.get("text", "") for chunk in body.get("content", [])]
        parsed, parse_mode = _parse_json_text("".join(text_chunks).strip())
        self.last_parse_mode = parse_mode
        if parse_mode != "direct":
            self.parse_repair_count += 1
        return parsed

    def next_action(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        tool_names: list[str],
    ) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("claude_auth_error:ANTHROPIC_API_KEY is not set")
        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": 0,
            "system": (system_prompt + "\n" + _action_json_instruction(tool_names)),
            "messages": messages,
        }
        body = self._send_messages_request(payload)
        self.resolved_model = str(body.get("model", self.model))
        self.last_usage = _claude_usage(body) or _empty_usage()
        self.total_usage = _merge_usage(self.total_usage, self.last_usage)
        text_chunks = [chunk.get("text", "") for chunk in body.get("content", [])]
        parsed, parse_mode = _parse_json_text("".join(text_chunks).strip())
        self.last_parse_mode = parse_mode
        if parse_mode != "direct":
            self.parse_repair_count += 1
        return parsed


class GeminiClient:
    def __init__(self, model: str = "gemini-2.5-pro", max_output_tokens: int = 1024, request_timeout: int | float = 60):
        self.model = model
        self.max_output_tokens = max_output_tokens
        self.api_key = os.getenv("GOOGLE_API_KEY", "") or os.getenv("GEMINI_API_KEY", "")
        self.request_timeout = request_timeout
        self.resolved_model = model
        self.last_usage = _empty_usage()
        self.total_usage = _empty_usage()
        self.last_parse_mode = "direct"
        self.parse_repair_count = 0

    def complete_json(
        self,
        system_prompt: str,
        prompt: str,
    ) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("gemini_auth_error:GOOGLE_API_KEY or GEMINI_API_KEY is not set")

        payload = {
            "system_instruction": {
                "parts": [{"text": system_prompt}],
            },
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ],
            "generationConfig": {
                "temperature": 0,
                "maxOutputTokens": self.max_output_tokens,
                "responseMimeType": "application/json",
            },
        }
        req = urllib.request.Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "x-goog-api-key": self.api_key,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.request_timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")[:300]
            raise RuntimeError(f"gemini_http_error:{exc.code}:{detail}") from exc
        except (TimeoutError, socket.timeout) as exc:
            raise RuntimeError(f"gemini_timeout:{exc}") from exc
        except urllib.error.URLError as exc:
            if "timed out" in str(exc.reason).lower():
                raise RuntimeError(f"gemini_timeout:{exc.reason}") from exc
            raise RuntimeError(f"gemini_network_error:{exc.reason}") from exc

        self.resolved_model = str(body.get("modelVersion", self.model))
        self.last_usage = _gemini_usage(body) or _empty_usage()
        self.total_usage = _merge_usage(self.total_usage, self.last_usage)
        content = _extract_gemini_text(body)
        parsed, parse_mode = _parse_json_text(content)
        self.last_parse_mode = parse_mode
        if parse_mode != "direct":
            self.parse_repair_count += 1
        return parsed

    def next_action(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        tool_names: list[str],
    ) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("gemini_auth_error:GOOGLE_API_KEY or GEMINI_API_KEY is not set")

        contents = []
        for message in messages:
            role = "model" if message.get("role") == "assistant" else "user"
            contents.append(
                {
                    "role": role,
                    "parts": [{"text": message.get("content", "")}],
                }
            )

        payload = {
            "system_instruction": {"parts": [{"text": (system_prompt + "\n" + _action_json_instruction(tool_names))}]},
            "contents": contents,
            "generationConfig": {
                "temperature": 0,
                "maxOutputTokens": self.max_output_tokens,
                "responseMimeType": "application/json",
            },
        }
        req = urllib.request.Request(
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "x-goog-api-key": self.api_key,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.request_timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")[:300]
            raise RuntimeError(f"gemini_http_error:{exc.code}:{detail}") from exc
        except (TimeoutError, socket.timeout) as exc:
            raise RuntimeError(f"gemini_timeout:{exc}") from exc
        except urllib.error.URLError as exc:
            if "timed out" in str(exc.reason).lower():
                raise RuntimeError(f"gemini_timeout:{exc.reason}") from exc
            raise RuntimeError(f"gemini_network_error:{exc.reason}") from exc

        self.resolved_model = str(body.get("modelVersion", self.model))
        self.last_usage = _gemini_usage(body) or _empty_usage()
        self.total_usage = _merge_usage(self.total_usage, self.last_usage)
        content = _extract_gemini_text(body)
        parsed, parse_mode = _parse_json_text(content)
        self.last_parse_mode = parse_mode
        if parse_mode != "direct":
            self.parse_repair_count += 1
        return parsed


class LocalInferenceClient:
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
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.thinking = dict(thinking) if isinstance(thinking, dict) else None
        self.api_key = api_key or os.getenv("LOCAL_INFERENCE_API_KEY", "")
        self.request_timeout = request_timeout
        self.resolved_model = model
        self.last_usage = _empty_usage()
        self.total_usage = _empty_usage()
        self.last_parse_mode = "direct"
        self.parse_repair_count = 0

    def complete_json(
        self,
        system_prompt: str,
        prompt: str,
    ) -> dict[str, Any]:
        payload = {
            "model": self.model,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if self.thinking is not None:
            payload["thinking"] = self.thinking
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.request_timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")[:300]
            raise RuntimeError(f"local_inference_http_error:{exc.code}:{detail}") from exc
        except (TimeoutError, socket.timeout) as exc:
            raise RuntimeError(f"local_inference_timeout:{exc}") from exc
        except urllib.error.URLError as exc:
            if "timed out" in str(exc.reason).lower():
                raise RuntimeError(f"local_inference_timeout:{exc.reason}") from exc
            raise RuntimeError(f"local_inference_network_error:{exc.reason}") from exc
        self.resolved_model = str(body.get("model", self.model))
        self.last_usage = _local_usage(body) or _empty_usage()
        self.total_usage = _merge_usage(self.total_usage, self.last_usage)
        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"local_inference_unexpected_response:{exc}") from exc
        parsed, parse_mode = _parse_json_text(content)
        self.last_parse_mode = parse_mode
        if parse_mode != "direct":
            self.parse_repair_count += 1
        return parsed

    def next_action(
        self,
        system_prompt: str,
        messages: list[dict[str, str]],
        tool_names: list[str],
    ) -> dict[str, Any]:
        instruction = {
            "role": "system",
            "content": system_prompt + "\n" + _action_json_instruction(tool_names),
        }
        payload = {
            "model": self.model,
            "response_format": {"type": "json_object"},
            "messages": [instruction] + messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if self.thinking is not None:
            payload["thinking"] = self.thinking
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.request_timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="ignore")[:300]
            raise RuntimeError(f"local_inference_http_error:{exc.code}:{detail}") from exc
        except (TimeoutError, socket.timeout) as exc:
            raise RuntimeError(f"local_inference_timeout:{exc}") from exc
        except urllib.error.URLError as exc:
            if "timed out" in str(exc.reason).lower():
                raise RuntimeError(f"local_inference_timeout:{exc.reason}") from exc
            raise RuntimeError(f"local_inference_network_error:{exc.reason}") from exc
        self.resolved_model = str(body.get("model", self.model))
        self.last_usage = _local_usage(body) or _empty_usage()
        self.total_usage = _merge_usage(self.total_usage, self.last_usage)
        try:
            content = body["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"local_inference_unexpected_response:{exc}") from exc
        parsed, parse_mode = _parse_json_text(content)
        self.last_parse_mode = parse_mode
        if parse_mode != "direct":
            self.parse_repair_count += 1
        return parsed

"""Chat clients for the agent.

Two implementations, one interface:

* `DeepSeekClient` — the real one, OpenAI-compatible, key from the environment;
* `StubClient` — replays scripted replies, so the loop and the enforcement can be
  tested without a network or a key.

Both return `(text, usage)` where usage carries token counts for the run log.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Protocol

import requests

DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
DEFAULT_MODEL = "deepseek-chat"


class ChatClient(Protocol):
    model: str
    calls: list[dict]

    def complete(self, messages: list[dict]) -> tuple[str, dict]: ...


@dataclass
class DeepSeekClient:
    api_key: str = field(default_factory=lambda: os.environ.get("DEEPSEEK_API_KEY", ""))
    model: str = DEFAULT_MODEL
    temperature: float = 0.0
    max_tokens: int = 700
    timeout: float = 60.0
    calls: list[dict] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.api_key:
            raise RuntimeError(
                "DEEPSEEK_API_KEY is not set. Export it, or pass a StubClient for "
                "an offline run.")

    def complete(self, messages: list[dict]) -> tuple[str, dict]:
        payload = {"model": self.model, "messages": messages,
                   "temperature": self.temperature, "max_tokens": self.max_tokens}
        headers = {"Authorization": f"Bearer {self.api_key}",
                   "Content-Type": "application/json"}
        last_error: Exception | None = None
        for attempt in range(2):
            try:
                started = time.perf_counter()
                response = requests.post(DEEPSEEK_URL, headers=headers,
                                         json=payload, timeout=self.timeout)
                if response.status_code >= 500:
                    raise RuntimeError(f"server error {response.status_code}")
                response.raise_for_status()
                body = response.json()
                text = body["choices"][0]["message"]["content"]
                usage = body.get("usage", {})
                self.calls.append({
                    "model": self.model, "latency_ms": round((time.perf_counter() - started) * 1000, 1),
                    "tokens_in": usage.get("prompt_tokens"), "tokens_out": usage.get("completion_tokens"),
                    "status": response.status_code,
                })
                return text, usage
            except Exception as exc:                 # noqa: BLE001 - retried once
                last_error = exc
                time.sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"LLM call failed twice: {last_error}")


@dataclass
class StubClient:
    """Replays replies in order. Used by tests and by offline demos."""

    replies: list[str]
    model: str = "stub"
    calls: list[dict] = field(default_factory=list)

    def complete(self, messages: list[dict]) -> tuple[str, dict]:
        if not self.replies:
            raise RuntimeError("stub has no replies left")
        text = self.replies.pop(0)
        self.calls.append({"model": self.model, "messages": len(messages)})
        return text, {"prompt_tokens": 0, "completion_tokens": 0}


def parse_turn(text: str) -> dict | None:
    """Extract one JSON object from a model turn, tolerating code fences."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("```")[1]
        if stripped.startswith("json"):
            stripped = stripped[4:]
    start, end = stripped.find("{"), stripped.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        obj = json.loads(stripped[start:end + 1])
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None

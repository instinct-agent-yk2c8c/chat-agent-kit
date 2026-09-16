"""Talks to the Anthropic Messages API with an Anthropic API key.

An Anthropic API key comes from the Claude Console
(https://console.anthropic.com) and is billed separately from any Claude
Pro/Max subscription - those subscriptions do not include API access.
See docs/providers.md. Standard library only.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from .base import Provider

ANTHROPIC_MESSAGES_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-haiku-4-5"  # fast + cheap; swap for claude-sonnet-5 etc.


class AnthropicProvider(Provider):
    name = "anthropic"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        max_tokens: int = 1024,
        timeout: float = 60.0,
    ):
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.timeout = timeout

    def complete(self, messages: list[dict]) -> str:
        if not self.api_key:
            raise RuntimeError(
                "No API key set. Set CHAT_AGENT_API_KEY or ANTHROPIC_API_KEY. "
                "Create a key at https://console.anthropic.com - a Claude "
                "Pro/Max subscription does not include API access."
            )
        # The Messages API takes the system prompt as its own field.
        system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
        chat = [m for m in messages if m["role"] in ("user", "assistant")]
        payload = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": system,
            "messages": chat,
        }
        req = urllib.request.Request(
            ANTHROPIC_MESSAGES_URL,
            data=json.dumps(payload).encode(),
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": ANTHROPIC_VERSION,
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode()[:500]
            raise RuntimeError(f"Anthropic API returned HTTP {e.code}: {body}") from e
        return "".join(
            block.get("text", "") for block in data.get("content", []) if block.get("type") == "text"
        ).strip()

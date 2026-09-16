"""An offline provider for testing the plumbing without any API key."""
from __future__ import annotations

from .base import Provider


class EchoProvider(Provider):
    """Replies with the last user message. Needs no network or credentials."""

    name = "echo"

    def complete(self, messages: list[dict]) -> str:
        last_user = next(
            (m["content"] for m in reversed(messages) if m["role"] == "user"), ""
        )
        return f"You said: {last_user}"

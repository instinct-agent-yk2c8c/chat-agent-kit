"""Agents: the part you customize. An agent decides what to reply."""
from __future__ import annotations

import os
from datetime import datetime

from .models import InboundMessage
from .providers.base import Provider

DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful personal assistant replying to text messages. "
    "Keep replies short and conversational - this is a chat, not an email."
)


class Agent:
    """Base class. Return a reply string, or None to stay silent."""

    name = "agent"

    def reply(self, message: InboundMessage) -> str | None:
        raise NotImplementedError


class EchoAgent(Agent):
    """Replies with what it received. Useful for smoke-testing the plumbing."""

    name = "echo"

    def reply(self, message: InboundMessage) -> str | None:
        return f"You said: {message.text}"


class CommandAgent(Agent):
    """Answers a small set of slash commands; ignores everything else."""

    name = "command"

    def __init__(self, prefix: str = "/"):
        self.prefix = prefix

    def reply(self, message: InboundMessage) -> str | None:
        text = message.text.strip()
        if not text.startswith(self.prefix):
            return None
        command, _, arg = text[1:].partition(" ")
        command = command.lower()
        if command == "ping":
            return "pong"
        if command == "echo":
            return arg or "(nothing to echo)"
        if command == "time":
            return datetime.now().strftime("It's %I:%M %p on %A, %B %-d.")
        if command == "help":
            return "Commands: /ping, /echo <text>, /time, /help"
        return f"Unknown command: /{command}. Try /help"


class SimpleAgent(Agent):
    """The boilerplate LLM agent - the thing this kit exists for.

    It keeps a short per-sender conversation history and asks your chosen
    provider for a reply. Customize it two ways:

    1. Edit its personality without code: copy persona.example.md to
       persona.md and run with `--persona persona.md`.
    2. Subclass it (see examples/custom_agent.py) to add rules, tools,
       or a different memory policy.
    """

    name = "simple"

    def __init__(
        self,
        provider: Provider,
        system_prompt: str | None = None,
        persona_path: str | None = None,
        history_size: int = 20,
    ):
        self.provider = provider
        if persona_path:
            with open(os.path.expanduser(persona_path)) as f:
                system_prompt = f.read().strip()
        self.system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT
        self.history_size = history_size
        self._history: dict[str, list[dict]] = {}

    def reply(self, message: InboundMessage) -> str | None:
        key = f"{message.channel}:{message.sender}"
        history = self._history.setdefault(key, [])
        history.append({"role": "user", "content": message.text})
        history = history[-self.history_size :]
        self._history[key] = history

        messages = [{"role": "system", "content": self.system_prompt}] + history
        text = self.provider.complete(messages)
        history.append({"role": "assistant", "content": text})
        return text

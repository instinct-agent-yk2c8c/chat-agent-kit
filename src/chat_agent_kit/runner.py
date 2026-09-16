"""The runner: channel-neutral policy + loop glue.

Every channel hands inbound messages to runner.handle_message() and provides
a `send` callable. The runner owns the safety policy - allowlist, rate
limit, dry-run, reply length cap - so each channel and agent stays tiny.
"""
from __future__ import annotations

import logging
import time
from typing import Callable

from .agents import Agent
from .config import Config
from .models import InboundMessage

log = logging.getLogger("chat_agent_kit")


class AgentRunner:
    def __init__(self, config: Config, agent: Agent):
        self.config = config
        self.agent = agent
        self._last_reply_at: dict[str, float] = {}

    def allowed(self, sender: str) -> bool:
        return sender in self.config.respond_to

    def rate_limited(self, sender: str) -> bool:
        if sender not in self._last_reply_at:
            return False
        return (
            time.monotonic() - self._last_reply_at[sender]
        ) < self.config.rate_limit_per_sender

    def handle_message(
        self, message: InboundMessage, send: Callable[[InboundMessage, str], None]
    ) -> str | None:
        """Process one inbound message. Returns the reply text, if any."""
        if not self.allowed(message.sender):
            log.info(
                "ignoring %s on %s (not in respond_to allowlist)",
                message.sender, message.channel,
            )
            return None
        if self.rate_limited(message.sender):
            log.info("rate-limiting %s", message.sender)
            return None
        reply = self.agent.reply(message)
        if reply is None:
            return None
        reply = reply[: self.config.max_reply_chars]
        if self.config.dry_run:
            log.info("[dry-run] would reply to %s: %s", message.sender, reply)
        else:
            send(message, reply)
            log.info("replied to %s on %s", message.sender, message.channel)
        self._last_reply_at[message.sender] = time.monotonic()
        return reply

    def run(self, channel) -> None:
        log.info(
            "starting (channel=%s, agent=%s, dry_run=%s, allowlist=%s)",
            channel.name, self.agent.name, self.config.dry_run,
            sorted(self.config.respond_to),
        )
        channel.run(self)

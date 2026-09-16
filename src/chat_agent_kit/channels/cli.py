"""Terminal channel: chat with your agent locally on any OS.

This is the fastest way to try the kit and the channel the demo and tests
use. No Mac, no WhatsApp setup, no network needed with the echo provider.
"""
from __future__ import annotations

from ..models import InboundMessage
from .base import Channel


class CliChannel(Channel):
    name = "cli"

    def __init__(self, user_id: str = "local"):
        self.user_id = user_id

    def run(self, runner) -> None:
        print("CLI channel. Type a message, or Ctrl-C to quit.")
        while True:
            try:
                text = input("you> ")
            except (EOFError, KeyboardInterrupt):
                print()
                return
            if not text.strip():
                continue
            msg = InboundMessage(channel=self.name, sender=self.user_id, text=text)
            reply = runner.handle_message(msg, self.send)
            if reply is not None and runner.config.dry_run:
                print(f"agent> {reply}")

    def send(self, message: InboundMessage, text: str) -> None:
        print(f"agent> {text}")

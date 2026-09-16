"""The channel interface. A channel gets texts in and sends texts out."""
from __future__ import annotations

from ..models import InboundMessage


class Channel:
    """Base class.

    run(runner): block forever; for each inbound message build an
        InboundMessage and call runner.handle_message(message, self.send).
    send(message, text): deliver a reply. Only called when dry_run is off.
    """

    name = "channel"

    def run(self, runner) -> None:
        raise NotImplementedError

    def send(self, message: InboundMessage, text: str) -> None:
        raise NotImplementedError

"""Shared data types."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

APPLE_EPOCH_UNIX = 978_307_200  # seconds between 1970-01-01 and 2001-01-01


def apple_time_to_datetime(raw: int | None) -> datetime | None:
    """Convert a macOS Messages `date` value to a UTC datetime.

    Modern macOS stores nanoseconds since 2001-01-01; older versions stored
    seconds. Anything larger than ~1e12 is treated as nanoseconds.
    """
    if raw is None:
        return None
    seconds = raw / 1_000_000_000 if raw > 1_000_000_000_000 else raw
    return datetime.utcfromtimestamp(APPLE_EPOCH_UNIX + seconds)


@dataclass(frozen=True)
class InboundMessage:
    """One inbound text message from any channel."""

    channel: str  # "cli" | "imessage" | "whatsapp" | your own channel name
    sender: str   # phone number, email, or local id - who sent it
    text: str
    id: str = ""  # channel-specific message id, used for deduping
    sent_at: datetime | None = None

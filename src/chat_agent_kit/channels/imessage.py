"""iMessage channel (macOS only): watch chat.db, reply via Messages.app.

Reads inbound direct iMessages from ~/Library/Messages/chat.db over a
read-only, immutable SQLite connection (it never writes to or locks the
Messages database), and replies through Messages.app via AppleScript, so
messages send as you.

Requirements (see docs/imessage.md):
- macOS with Messages.app signed in to iMessage
- Full Disk Access for your terminal, to read chat.db
- Automation permission for Messages, to send (macOS prompts the first time)

An alternative worth knowing: BlueBubbles (https://bluebubbles.app) runs a
server on a Mac with a REST API and webhooks. This kit does not include a
BlueBubbles adapter, but the Channel interface is built for adding one.
"""
from __future__ import annotations

import json
import logging
import os
import sqlite3
import subprocess
import time

from ..models import InboundMessage, apple_time_to_datetime
from .base import Channel

log = logging.getLogger("chat_agent_kit")

# Deliberately only direct (non-group) iMessages that are not from us.
_NEW_MESSAGES_SQL = """
SELECT m.ROWID, m.text, m.date, h.id AS handle, m.service
FROM message m
LEFT JOIN handle h ON m.handle_id = h.ROWID
LEFT JOIN chat_message_join cmj ON cmj.message_id = m.ROWID
LEFT JOIN chat c ON c.ROWID = cmj.chat_id
WHERE m.ROWID > ?
  AND m.is_from_me = 0
  AND (m.service = 'iMessage' OR m.service IS NULL)
  AND m.text IS NOT NULL
  AND (c.ROWID IS NULL OR c.chat_identifier NOT LIKE 'chat%')
ORDER BY m.ROWID
"""


def _escape_applescript(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def send_imessage(handle: str, text: str) -> None:
    """Send an iMessage via Messages.app (macOS only)."""
    script = (
        'tell application "Messages"\n'
        "    set targetService to 1st service whose service type = iMessage\n"
        f'    set targetBuddy to buddy "{_escape_applescript(handle)}" of targetService\n'
        f'    send "{_escape_applescript(text)}" to targetBuddy\n'
        "end tell"
    )
    proc = subprocess.run(
        ["osascript", "-e", script], capture_output=True, text=True, timeout=30
    )
    if proc.returncode != 0:
        raise RuntimeError(f"osascript failed: {proc.stderr.strip()}")


class IMessageChannel(Channel):
    name = "imessage"

    def __init__(self, db_path: str, state_path: str, poll_interval: float = 2.0):
        self.db_path = os.path.expanduser(db_path)
        self.state_path = state_path
        self.poll_interval = poll_interval

    def _connect(self) -> sqlite3.Connection:
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(
                f"Messages database not found at {self.db_path}. "
                "Are you on macOS with Messages signed in? Your terminal also "
                "needs Full Disk Access to read chat.db - see docs/imessage.md."
            )
        uri = f"file:{self.db_path}?mode=ro&immutable=1"
        return sqlite3.connect(uri, uri=True)

    def load_checkpoint(self) -> int:
        """Highest message ROWID already processed. On first run, start at the
        current max so the agent never replays your whole history."""
        if self.state_path and os.path.exists(self.state_path):
            with open(self.state_path) as f:
                return json.load(f).get("last_rowid", 0)
        with self._connect() as conn:
            row = conn.execute("SELECT COALESCE(MAX(ROWID), 0) FROM message").fetchone()
            return int(row[0])

    def save_checkpoint(self, last_rowid: int) -> None:
        os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
        with open(self.state_path, "w") as f:
            json.dump({"last_rowid": last_rowid}, f)

    def fetch_new(self, since_rowid: int) -> list[InboundMessage]:
        """Inbound direct iMessages with ROWID > since_rowid, oldest first."""
        with self._connect() as conn:
            rows = conn.execute(_NEW_MESSAGES_SQL, (since_rowid,)).fetchall()
        return [
            InboundMessage(
                channel=self.name,
                id=str(int(rowid)),
                sender=handle or "unknown",
                text=text,
                sent_at=apple_time_to_datetime(raw_date),
            )
            for rowid, text, raw_date, handle, _service in rows
        ]

    def run(self, runner) -> None:
        checkpoint = self.load_checkpoint()
        log.info("watching %s (checkpoint=%s)", self.db_path, checkpoint)
        try:
            while True:
                for message in self.fetch_new(checkpoint):
                    log.info("inbound from %s: %r", message.sender, message.text)
                    runner.handle_message(message, self.send)
                    checkpoint = max(checkpoint, int(message.id))
                self.save_checkpoint(checkpoint)
                time.sleep(self.poll_interval)
        except KeyboardInterrupt:
            self.save_checkpoint(checkpoint)
            log.info("stopped; checkpoint saved at %s", checkpoint)

    def send(self, message: InboundMessage, text: str) -> None:
        send_imessage(message.sender, text)

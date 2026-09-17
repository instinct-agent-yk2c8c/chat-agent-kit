"""WhatsApp channel: Meta's official WhatsApp Business Cloud API.

Inbound text events are committed to a local SQLite inbox before the webhook
returns 200. A background worker performs model work after acknowledgement and
retries unfinished rows after failures or restarts.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import sqlite3
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from ..models import InboundMessage
from .base import Channel

log = logging.getLogger("chat_agent_kit")

GRAPH_API_VERSION = "v26.0"


def verify_signature(app_secret: str, body: bytes, header: str | None) -> bool:
    """Check Meta's X-Hub-Signature-256 header against the raw body."""
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header[len("sha256="):])


def check_webhook_verification(params: dict, verify_token: str) -> str | None:
    """Answer Meta's one-time GET handshake. Returns the challenge, or None."""
    if params.get("hub.mode") == "subscribe" and params.get("hub.verify_token") == verify_token:
        return params.get("hub.challenge")
    return None


def parse_webhook_payload(payload: dict) -> list[InboundMessage]:
    """Pull inbound text messages out of a Cloud API webhook body."""
    out = []
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for msg in value.get("messages", []):
                if msg.get("type") != "text":
                    continue
                ts = msg.get("timestamp")
                out.append(
                    InboundMessage(
                        channel="whatsapp",
                        id=msg.get("id", ""),
                        sender=msg.get("from", "unknown"),
                        text=msg.get("text", {}).get("body", ""),
                        sent_at=datetime.fromtimestamp(int(ts), tz=timezone.utc) if ts else None,
                    )
                )
    return out


class WhatsAppCloudChannel(Channel):
    name = "whatsapp"

    def __init__(
        self,
        access_token: str,
        phone_number_id: str,
        verify_token: str,
        app_secret: str | None = None,
        host: str = "0.0.0.0",
        port: int = 8080,
        graph_version: str = GRAPH_API_VERSION,
        state_path: str | None = None,
        max_seen_ids: int = 5000,
    ):
        self.access_token = access_token
        self.phone_number_id = phone_number_id
        self.verify_token = verify_token
        self.app_secret = app_secret
        self.host = host
        self.port = port
        self.graph_base = f"https://graph.facebook.com/{graph_version}"
        self.state_path = state_path
        self.max_seen_ids = max_seen_ids  # retained for constructor compatibility
        self.inbox_path = f"{state_path}.whatsapp-inbox.sqlite3" if state_path else ":memory:"
        self._inbox_lock = threading.Lock()
        self._memory_db = None
        self._init_inbox()

    def _connect_inbox(self) -> sqlite3.Connection:
        if self.inbox_path == ":memory:":
            if self._memory_db is None:
                self._memory_db = sqlite3.connect(":memory:", check_same_thread=False)
                self._memory_db.row_factory = sqlite3.Row
            return self._memory_db
        conn = sqlite3.connect(self.inbox_path, timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_inbox(self) -> None:
        if self.inbox_path != ":memory:":
            parent = os.path.dirname(self.inbox_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
        with self._inbox_lock:
            conn = self._connect_inbox()
            try:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute(
                    """CREATE TABLE IF NOT EXISTS inbox (
                        message_id TEXT PRIMARY KEY,
                        sender TEXT NOT NULL,
                        text TEXT NOT NULL,
                        sent_at TEXT,
                        status TEXT NOT NULL DEFAULT 'pending',
                        attempts INTEGER NOT NULL DEFAULT 0,
                        last_error TEXT,
                        received_at TEXT NOT NULL
                    )"""
                )
                # Preserve the old JSON dedupe list during an in-place upgrade.
                if self.state_path and os.path.exists(self.state_path):
                    try:
                        with open(self.state_path) as state_file:
                            old_ids = json.load(state_file).get("seen_whatsapp_ids", [])
                    except (json.JSONDecodeError, OSError):
                        old_ids = []
                    now = datetime.now(timezone.utc).isoformat()
                    for message_id in old_ids[-self.max_seen_ids:]:
                        conn.execute(
                            """INSERT OR IGNORE INTO inbox
                               (message_id, sender, text, status, received_at)
                               VALUES (?, 'unknown', '', 'done', ?)""",
                            (message_id, now),
                        )
                # Work interrupted by process death is safe to retry on startup.
                conn.execute("UPDATE inbox SET status='pending' WHERE status='processing'")
                conn.commit()
            finally:
                if self.inbox_path != ":memory:":
                    conn.close()

    def persist_messages(self, messages: list[InboundMessage]) -> int:
        """Durably enqueue messages. Duplicate Meta message ids are ignored."""
        inserted = 0
        with self._inbox_lock:
            conn = self._connect_inbox()
            try:
                conn.execute("BEGIN IMMEDIATE")
                for message in messages:
                    if not message.id:
                        log.warning("ignoring WhatsApp message without an id")
                        continue
                    cur = conn.execute(
                        """INSERT OR IGNORE INTO inbox
                           (message_id, sender, text, sent_at, received_at)
                           VALUES (?, ?, ?, ?, ?)""",
                        (
                            message.id,
                            message.sender,
                            message.text,
                            message.sent_at.isoformat() if message.sent_at else None,
                            datetime.now(timezone.utc).isoformat(),
                        ),
                    )
                    inserted += cur.rowcount
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                if self.inbox_path != ":memory:":
                    conn.close()
        return inserted

    def _is_duplicate(self, message_id: str) -> bool:
        """Compatibility helper: reserve an id in the durable inbox."""
        message = InboundMessage(channel=self.name, id=message_id, sender="unknown", text="")
        return self.persist_messages([message]) == 0

    def _claim_next(self) -> InboundMessage | None:
        with self._inbox_lock:
            conn = self._connect_inbox()
            try:
                conn.execute("BEGIN IMMEDIATE")
                row = conn.execute(
                    "SELECT * FROM inbox WHERE status='pending' ORDER BY received_at LIMIT 1"
                ).fetchone()
                if row is None:
                    conn.commit()
                    return None
                conn.execute(
                    "UPDATE inbox SET status='processing', attempts=attempts+1 WHERE message_id=?",
                    (row["message_id"],),
                )
                conn.commit()
            finally:
                if self.inbox_path != ":memory:":
                    conn.close()
        sent_at = datetime.fromisoformat(row["sent_at"]) if row["sent_at"] else None
        return InboundMessage(
            channel=self.name, id=row["message_id"], sender=row["sender"],
            text=row["text"], sent_at=sent_at,
        )

    def _finish(self, message_id: str, error: Exception | None = None) -> None:
        with self._inbox_lock:
            conn = self._connect_inbox()
            try:
                if error is None:
                    conn.execute(
                        "UPDATE inbox SET status='done', last_error=NULL WHERE message_id=?",
                        (message_id,),
                    )
                else:
                    conn.execute(
                        "UPDATE inbox SET status='pending', last_error=? WHERE message_id=?",
                        (str(error)[:1000], message_id),
                    )
                conn.commit()
            finally:
                if self.inbox_path != ":memory:":
                    conn.close()

    def process_pending(self, runner, limit: int | None = None) -> int:
        """Process queued messages; leave a failed row pending for a later retry."""
        processed = 0
        while limit is None or processed < limit:
            message = self._claim_next()
            if message is None:
                break
            try:
                log.info("inbound from %s: %r", message.sender, message.text)
                runner.handle_message(message, self.send)
            except Exception as exc:
                self._finish(message.id, exc)
                log.exception("WhatsApp message %s failed; retained for retry", message.id)
                break
            else:
                self._finish(message.id)
                processed += 1
        return processed

    def send(self, message: InboundMessage, text: str) -> None:
        payload = {
            "messaging_product": "whatsapp", "recipient_type": "individual",
            "to": message.sender, "type": "text", "text": {"body": text},
        }
        req = urllib.request.Request(
            f"{self.graph_base}/{self.phone_number_id}/messages",
            data=json.dumps(payload).encode(),
            headers={"Authorization": f"Bearer {self.access_token}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp.read()
        except urllib.error.HTTPError as e:
            body = e.read().decode()[:500]
            raise RuntimeError(f"WhatsApp send failed, HTTP {e.code}: {body}") from e

    def run(self, runner) -> None:
        channel = self
        wake_worker = threading.Event()
        stopping = threading.Event()

        def worker():
            while not stopping.is_set():
                channel.process_pending(runner)
                wake_worker.wait(1.0)
                wake_worker.clear()

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):
                log.debug("webhook: " + fmt, *args)

            def _reply(self, code: int, body: str):
                self.send_response(code)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(body.encode())

            def do_GET(self):
                from urllib.parse import parse_qsl, urlparse
                params = dict(parse_qsl(urlparse(self.path).query))
                challenge = check_webhook_verification(params, channel.verify_token)
                if challenge is not None:
                    log.info("webhook verified by Meta")
                    self._reply(200, challenge)
                else:
                    self._reply(403, "verification failed")

            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                if channel.app_secret:
                    sig = self.headers.get("X-Hub-Signature-256")
                    if not verify_signature(channel.app_secret, body, sig):
                        log.warning("rejected webhook POST with bad signature")
                        self._reply(403, "bad signature")
                        return
                try:
                    payload = json.loads(body.decode())
                except json.JSONDecodeError:
                    self._reply(400, "invalid json")
                    return
                try:
                    inserted = channel.persist_messages(parse_webhook_payload(payload))
                except (OSError, sqlite3.Error):
                    log.exception("could not persist WhatsApp webhook")
                    self._reply(503, "storage unavailable")
                    return
                # The durable commit and HTTP acknowledgement both happen before
                # the worker is signalled, so model latency never delays Meta's 200.
                self._reply(200, "ok")
                if inserted:
                    wake_worker.set()

        worker_thread = threading.Thread(target=worker, name="whatsapp-worker", daemon=True)
        worker_thread.start()
        server = ThreadingHTTPServer((self.host, self.port), Handler)
        log.info("WhatsApp webhook listening on http://%s:%s", self.host, self.port)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            log.info("stopped")
        finally:
            stopping.set()
            wake_worker.set()
            server.server_close()
            worker_thread.join(timeout=2)

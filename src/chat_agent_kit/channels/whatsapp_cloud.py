"""WhatsApp channel: Meta's official WhatsApp Business Cloud API.

This is the only WhatsApp path that does not risk your account. Personal
WhatsApp has no API, and unofficial bridges (Baileys, whatsmeow,
whatsapp-web.js) violate WhatsApp's terms and get numbers banned. The Cloud
API is Meta's official, supported interface. See docs/whatsapp.md for the
full setup guide and the trade-offs.

What you need (all from https://developers.facebook.com):
- a Meta developer app with the WhatsApp use case
- a WhatsApp Business account and phone number (the free test number works
  for development; your personal WhatsApp number cannot be used)
- a permanent access token (system user token)
- a public HTTPS URL for the webhook (e.g. via a tunnel in dev)

You can only send free-form replies inside the 24-hour customer service
window that opens when a user messages you - which fits this agent's
reply-only design. Proactive outreach requires paid template messages.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from ..models import InboundMessage
from .base import Channel

log = logging.getLogger("chat_agent_kit")

GRAPH_API_VERSION = "v26.0"  # released 2026-07-29; override with --graph-version


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
    """Pull inbound text messages out of a Cloud API webhook body.

    Ignores status receipts, non-text messages, and anything that is not a
    user message - those are delivery bookkeeping, not something to answer.
    """
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
                        sent_at=(
                            datetime.fromtimestamp(int(ts), tz=timezone.utc) if ts else None
                        ),
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
        self.max_seen_ids = max_seen_ids
        self._seen_ids: list[str] = self._load_seen()

    # -- deduping: Meta retries webhook deliveries, so remember message ids --
    def _load_seen(self) -> list[str]:
        if self.state_path and os.path.exists(self.state_path):
            try:
                with open(self.state_path) as f:
                    return json.load(f).get("seen_whatsapp_ids", [])[-self.max_seen_ids:]
            except (json.JSONDecodeError, OSError):
                return []
        return []

    def _save_seen(self) -> None:
        if not self.state_path:
            return
        os.makedirs(os.path.dirname(self.state_path), exist_ok=True)
        with open(self.state_path, "w") as f:
            json.dump({"seen_whatsapp_ids": self._seen_ids[-self.max_seen_ids:]}, f)

    def _is_duplicate(self, message_id: str) -> bool:
        if not message_id:
            return False
        if message_id in self._seen_ids:
            return True
        self._seen_ids.append(message_id)
        self._save_seen()
        return False

    # -- outbound --
    def send(self, message: InboundMessage, text: str) -> None:
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": message.sender,
            "type": "text",
            "text": {"body": text},
        }
        req = urllib.request.Request(
            f"{self.graph_base}/{self.phone_number_id}/messages",
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                resp.read()
        except urllib.error.HTTPError as e:
            body = e.read().decode()[:500]
            raise RuntimeError(f"WhatsApp send failed, HTTP {e.code}: {body}") from e

    # -- inbound --
    def run(self, runner) -> None:
        channel = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, fmt, *args):  # quiet the default stderr log
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
                for message in parse_webhook_payload(payload):
                    if channel._is_duplicate(message.id):
                        continue
                    log.info("inbound from %s: %r", message.sender, message.text)
                    runner.handle_message(message, channel.send)
                # Always 200 quickly; Meta retries on non-200s.
                self._reply(200, "ok")

        server = ThreadingHTTPServer((self.host, self.port), Handler)
        log.info(
            "WhatsApp webhook listening on http://%s:%s - expose it publicly "
            "and set that URL in your Meta app's webhook settings",
            self.host, self.port,
        )
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            log.info("stopped")
        finally:
            server.server_close()

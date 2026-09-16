"""End-to-end demo on any OS, no credentials needed.

Part 1: builds a fake macOS chat.db and runs the iMessage watcher + policy
        loop against it in dry-run mode.
Part 2: parses a real-shaped WhatsApp Cloud API webhook payload and runs
        it through the same policy loop.

    python examples/demo.py
"""
import logging
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from chat_agent_kit.agents import CommandAgent, SimpleAgent
from chat_agent_kit.channels.imessage import IMessageChannel
from chat_agent_kit.channels.whatsapp_cloud import parse_webhook_payload
from chat_agent_kit.config import Config
from chat_agent_kit.providers.echo import EchoProvider
from chat_agent_kit.runner import AgentRunner

SCHEMA = """
CREATE TABLE handle (ROWID INTEGER PRIMARY KEY, id TEXT);
CREATE TABLE message (ROWID INTEGER PRIMARY KEY, text TEXT, date INTEGER,
                      is_from_me INTEGER DEFAULT 0, handle_id INTEGER, service TEXT);
CREATE TABLE chat (ROWID INTEGER PRIMARY KEY, chat_identifier TEXT);
CREATE TABLE chat_message_join (chat_id INTEGER, message_id INTEGER);
"""


def insert(conn, handle, text, *, from_me=0):
    conn.execute("INSERT OR IGNORE INTO handle (id) VALUES (?)", (handle,))
    hid = conn.execute("SELECT ROWID FROM handle WHERE id=?", (handle,)).fetchone()[0]
    conn.execute(
        "INSERT INTO message (text, date, is_from_me, handle_id, service) VALUES (?,?,?,?,'iMessage')",
        (text, 3_600_000_000_000, from_me, hid),
    )
    conn.commit()


def fake_send(message, text):
    print(f"  SEND -> {message.sender} ({message.channel}): {text}")


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    tmp = Path(tempfile.mkdtemp(prefix="chat-agent-kit-demo-"))

    print("== Part 1: iMessage channel against a fake chat.db (dry-run) ==")
    db = tmp / "chat.db"
    conn = sqlite3.connect(db)
    conn.executescript(SCHEMA)
    insert(conn, "+15551234567", "/ping")
    insert(conn, "+15551234567", "/echo demo works")
    insert(conn, "+15559876543", "/ping")          # not on the allowlist
    insert(conn, "+15551234567", "just chatting")  # not a command
    conn.close()

    config = Config(
        db_path=str(db),
        state_path=str(tmp / "state.json"),
        respond_to=frozenset({"+15551234567"}),
        dry_run=False,               # demo "sends" to a print() instead of Messages.app
        rate_limit_per_sender=0,
    )
    runner = AgentRunner(config, CommandAgent())
    channel = IMessageChannel(config.db_path, config.state_path)

    checkpoint = 0
    for message in channel.fetch_new(checkpoint):
        print(f"  inbound {message.sender}: {message.text!r}")
        runner.handle_message(message, fake_send)
        checkpoint = max(checkpoint, int(message.id))

    print("\n--- a new message arrives later ---")
    conn = sqlite3.connect(db)
    insert(conn, "+15551234567", "/time")
    conn.close()
    time.sleep(0.1)
    for message in channel.fetch_new(checkpoint):
        print(f"  inbound {message.sender}: {message.text!r}")
        runner.handle_message(message, fake_send)
        checkpoint = max(checkpoint, int(message.id))
    print(f"  checkpoint: {checkpoint}")

    print("\n== Part 2: WhatsApp webhook payload through the same policy ==")
    payload = {
        "object": "whatsapp_business_account",
        "entry": [{
            "id": "123",
            "changes": [{
                "field": "messages",
                "value": {
                    "metadata": {"phone_number_id": "999"},
                    "messages": [
                        {"from": "15551234567", "id": "wamid.1", "timestamp": "1780000000",
                         "type": "text", "text": {"body": "hello agent"}},
                        {"from": "15557654321", "id": "wamid.2", "timestamp": "1780000001",
                         "type": "text", "text": {"body": "not allowlisted"}},
                        {"from": "15551234567", "id": "wamid.3", "timestamp": "1780000002",
                         "type": "image"},  # ignored: not text
                    ],
                    "statuses": [{"id": "wamid.0", "status": "delivered"}],  # ignored
                },
            }],
        }],
    }
    config2 = Config(respond_to=frozenset({"15551234567"}), dry_run=False,
                     rate_limit_per_sender=0)
    runner2 = AgentRunner(config2, SimpleAgent(EchoProvider()))
    for message in parse_webhook_payload(payload):
        print(f"  inbound {message.sender}: {message.text!r}")
        runner2.handle_message(message, fake_send)


if __name__ == "__main__":
    main()

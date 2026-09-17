import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from chat_agent_kit.channels.imessage import IMessageChannel

SCHEMA = """
CREATE TABLE handle (ROWID INTEGER PRIMARY KEY, id TEXT);
CREATE TABLE message (ROWID INTEGER PRIMARY KEY, text TEXT, date INTEGER,
                      is_from_me INTEGER DEFAULT 0, handle_id INTEGER, service TEXT);
CREATE TABLE chat (ROWID INTEGER PRIMARY KEY, chat_identifier TEXT);
CREATE TABLE chat_message_join (chat_id INTEGER, message_id INTEGER);
"""


def insert(conn, handle, text, *, from_me=0, service="iMessage"):
    conn.execute("INSERT OR IGNORE INTO handle (id) VALUES (?)", (handle,))
    hid = conn.execute("SELECT ROWID FROM handle WHERE id=?", (handle,)).fetchone()[0]
    cur = conn.execute(
        "INSERT INTO message (text, date, is_from_me, handle_id, service) VALUES (?,?,?,?,?)",
        (text, 3_600_000_000_000, from_me, hid, service),
    )
    conn.commit()
    return cur.lastrowid


class TestIMessageChannel(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = str(Path(self.tmp) / "chat.db")
        self.state = str(Path(self.tmp) / "state.json")
        self.conn = sqlite3.connect(self.db)
        self.conn.executescript(SCHEMA)
        self.channel = IMessageChannel(self.db, self.state)

    def tearDown(self):
        self.conn.close()

    def test_fetch_new_only_inbound_direct_imessages(self):
        insert(self.conn, "+15551111111", "from allowed")            # keep
        insert(self.conn, "+15551111111", "from me", from_me=1)      # skip: ours
        insert(self.conn, "+15551111111", "sms one", service="SMS")  # skip: SMS
        new = self.channel.fetch_new(0)
        self.assertEqual([m.text for m in new], ["from allowed"])
        self.assertEqual(new[0].channel, "imessage")
        self.assertEqual(new[0].sender, "+15551111111")

    def test_group_chat_messages_skipped(self):
        rid = insert(self.conn, "+15551111111", "group msg")
        self.conn.execute(
            "INSERT INTO chat (chat_identifier) VALUES ('chat123456789')"
        )
        cid = self.conn.execute("SELECT ROWID FROM chat").fetchone()[0]
        self.conn.execute(
            "INSERT INTO chat_message_join (chat_id, message_id) VALUES (?,?)", (cid, rid)
        )
        self.conn.commit()
        self.assertEqual(self.channel.fetch_new(0), [])

    def test_checkpoint_roundtrip(self):
        self.channel.save_checkpoint(42)
        self.assertEqual(self.channel.load_checkpoint(), 42)

    def test_first_run_checkpoint_starts_at_current_max(self):
        insert(self.conn, "+15551111111", "old")
        self.assertGreater(self.channel.load_checkpoint(), 0)

    def test_checkpoint_only_advances_after_successful_handling(self):
        first = insert(self.conn, "+15551111111", "one")
        second = insert(self.conn, "+15551111111", "two")
        self.channel.save_checkpoint(0)

        class Runner:
            def handle_message(_, message, send):
                if message.id == str(second):
                    raise RuntimeError("send failed")

        with self.assertRaisesRegex(RuntimeError, "send failed"):
            self.channel.process_once(Runner(), 0)
        self.assertEqual(self.channel.load_checkpoint(), first)
        self.assertEqual([m.id for m in self.channel.fetch_new(first)], [str(second)])

    def test_first_failed_message_leaves_checkpoint_unchanged(self):
        insert(self.conn, "+15551111111", "one")
        self.channel.save_checkpoint(0)

        class Runner:
            def handle_message(_, message, send):
                raise RuntimeError("model failed")

        with self.assertRaises(RuntimeError):
            self.channel.process_once(Runner(), 0)
        self.assertEqual(self.channel.load_checkpoint(), 0)

    def test_missing_db_raises_helpful_error(self):
        ch = IMessageChannel(str(Path(self.tmp) / "nope.db"), self.state)
        with self.assertRaisesRegex(FileNotFoundError, "Full Disk Access"):
            ch.fetch_new(0)


if __name__ == "__main__":
    unittest.main()

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from chat_agent_kit.agents import EchoAgent
from chat_agent_kit.config import Config
from chat_agent_kit.models import InboundMessage
from chat_agent_kit.runner import AgentRunner


def msg(text, sender="+15551234567"):
    return InboundMessage(channel="imessage", sender=sender, text=text)


class TestPolicy(unittest.TestCase):
    def make(self, **kw):
        sent = []
        cfg = Config(respond_to=frozenset({"+15551234567"}), rate_limit_per_sender=0, **kw)
        runner = AgentRunner(cfg, EchoAgent())
        return runner, sent, lambda m, t: sent.append((m.sender, t))

    def test_allowlist_blocks_strangers(self):
        runner, sent, send = self.make()
        self.assertIsNone(runner.handle_message(msg("hi", "+15559999999"), send))
        self.assertEqual(sent, [])

    def test_dry_run_sends_nothing_but_returns_reply(self):
        runner, sent, send = self.make(dry_run=True)
        reply = runner.handle_message(msg("hi"), send)
        self.assertEqual(reply, "You said: hi")
        self.assertEqual(sent, [])

    def test_send_off_dry_run_delivers(self):
        runner, sent, send = self.make(dry_run=False)
        runner.handle_message(msg("hi"), send)
        self.assertEqual(sent, [("+15551234567", "You said: hi")])

    def test_rate_limit(self):
        cfg = Config(respond_to=frozenset({"+15551234567"}), rate_limit_per_sender=60)
        runner = AgentRunner(cfg, EchoAgent())
        sent = []
        send = lambda m, t: sent.append(t)
        self.assertIsNotNone(runner.handle_message(msg("one"), send))
        self.assertIsNone(runner.handle_message(msg("two"), send))  # too soon

    def test_reply_length_capped(self):
        cfg = Config(respond_to=frozenset({"+15551234567"}),
                     rate_limit_per_sender=0, max_reply_chars=10)
        runner = AgentRunner(cfg, EchoAgent())
        reply = runner.handle_message(msg("x" * 50), lambda m, t: None)
        self.assertEqual(len(reply), 10)


if __name__ == "__main__":
    unittest.main()

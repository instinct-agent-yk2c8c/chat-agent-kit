import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from chat_agent_kit.agents import CommandAgent, EchoAgent, SimpleAgent
from chat_agent_kit.models import InboundMessage
from chat_agent_kit.providers.echo import EchoProvider


def msg(text, sender="+15551234567"):
    return InboundMessage(channel="imessage", sender=sender, text=text)


class TestEchoAgent(unittest.TestCase):
    def test_echoes(self):
        self.assertEqual(EchoAgent().reply(msg("hi")), "You said: hi")


class TestCommandAgent(unittest.TestCase):
    def test_commands(self):
        agent = CommandAgent()
        self.assertEqual(agent.reply(msg("/ping")), "pong")
        self.assertEqual(agent.reply(msg("/echo hey")), "hey")
        self.assertIsNone(agent.reply(msg("no command here")))
        self.assertIn("Unknown command", agent.reply(msg("/nope")))


class TestSimpleAgent(unittest.TestCase):
    def test_replies_via_provider_and_keeps_history(self):
        agent = SimpleAgent(EchoProvider())
        self.assertEqual(agent.reply(msg("hello")), "You said: hello")
        history = agent._history["imessage:+15551234567"]
        self.assertEqual(history[0], {"role": "user", "content": "hello"})
        self.assertEqual(history[-1]["role"], "assistant")

    def test_separate_history_per_sender(self):
        agent = SimpleAgent(EchoProvider())
        agent.reply(msg("a", sender="+15550000001"))
        agent.reply(msg("b", sender="+15550000002"))
        self.assertEqual(len(agent._history), 2)

    def test_persona_file_becomes_system_prompt(self):
        import tempfile, os
        with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as f:
            f.write("You are a pirate.")
            path = f.name
        try:
            agent = SimpleAgent(EchoProvider(), persona_path=path)
            self.assertEqual(agent.system_prompt, "You are a pirate.")
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()

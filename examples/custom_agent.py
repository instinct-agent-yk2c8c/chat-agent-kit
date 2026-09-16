"""The smallest useful custom agent: subclass SimpleAgent (or Agent).

Run it:
    python examples/custom_agent.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from chat_agent_kit.agents import SimpleAgent
from chat_agent_kit.models import InboundMessage
from chat_agent_kit.providers.echo import EchoProvider


class MyAgent(SimpleAgent):
    """Adds one rule on top of the normal LLM behavior."""

    def reply(self, message: InboundMessage) -> str | None:
        text = message.text.lower()
        if "urgent" in text:
            # Rules you write yourself always win over the model.
            return "On it - give me 10 minutes."
        return super().reply(message)  # fall through to the LLM


if __name__ == "__main__":
    agent = MyAgent(EchoProvider())  # swap in any provider + your API key
    for text in ("hey, what's up?", "this is urgent!"):
        msg = InboundMessage(channel="cli", sender="local", text=text)
        print(f"you>   {text}")
        print(f"agent> {agent.reply(msg)}")

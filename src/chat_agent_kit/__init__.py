"""chat-agent-kit: run your own AI agent over iMessage and/or WhatsApp.

Bring your own provider credentials (any OpenAI-compatible API, Anthropic,
or a local model), pick a channel (iMessage on macOS, WhatsApp Cloud API,
or the local terminal), and customize a deliberately simple boilerplate
agent. Zero dependencies - standard library only.
"""

__version__ = "0.1.0"

from .agents import Agent, CommandAgent, EchoAgent, SimpleAgent
from .models import InboundMessage

__all__ = [
    "Agent",
    "EchoAgent",
    "CommandAgent",
    "SimpleAgent",
    "InboundMessage",
    "__version__",
]

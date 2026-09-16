"""Runtime configuration: environment variables plus CLI overrides."""
from __future__ import annotations

import os
from dataclasses import dataclass, field


def _default_state() -> str:
    return os.path.expanduser("~/.chat-agent-kit/state.json")


@dataclass
class Config:
    """Everything the runner and channels need.

    respond_to: allowlist of senders (phone numbers / emails) the agent may
        reply to. Empty means reply to no one - you must opt senders in.
    dry_run: read and process messages but print replies instead of sending.
    """

    channel: str = "cli"                 # cli | imessage | whatsapp
    agent: str = "simple"                # simple | echo | command
    provider: str = "openai"             # API/local presets, or codex/cursor/grok-subscription
    base_url: str | None = None          # override the provider preset
    api_key: str | None = None
    model: str | None = None
    persona_path: str | None = None      # markdown file used as the system prompt
    respond_to: frozenset[str] = frozenset()
    dry_run: bool = True
    state_path: str = field(default_factory=_default_state)
    max_reply_chars: int = 2000
    rate_limit_per_sender: float = 5.0   # min seconds between replies to one sender
    poll_interval_seconds: float = 2.0   # iMessage channel
    db_path: str = field(default_factory=lambda: os.path.expanduser("~/Library/Messages/chat.db"))
    listen_host: str = "0.0.0.0"         # WhatsApp channel
    listen_port: int = 8080

    @classmethod
    def from_env(cls) -> "Config":
        """Build a config from CHAT_AGENT_* environment variables."""
        cfg = cls()
        env = os.environ.get
        cfg.channel = env("CHAT_AGENT_CHANNEL", cfg.channel)
        cfg.agent = env("CHAT_AGENT_AGENT", cfg.agent)
        cfg.provider = env("CHAT_AGENT_PROVIDER", cfg.provider)
        cfg.base_url = env("CHAT_AGENT_BASE_URL")
        cfg.model = env("CHAT_AGENT_MODEL")
        cfg.persona_path = env("CHAT_AGENT_PERSONA")
        cfg.dry_run = env("CHAT_AGENT_DRY_RUN", "1") not in ("0", "false")
        allowed = env("CHAT_AGENT_RESPOND_TO", "")
        cfg.respond_to = frozenset(h.strip() for h in allowed.split(",") if h.strip())
        if env("CHAT_AGENT_STATE"):
            cfg.state_path = env("CHAT_AGENT_STATE")
        if env("CHAT_AGENT_DB"):
            cfg.db_path = env("CHAT_AGENT_DB")
        if env("CHAT_AGENT_PORT"):
            cfg.listen_port = int(env("CHAT_AGENT_PORT"))
        # API key: explicit CHAT_AGENT_API_KEY first, then the provider's own
        # well-known variable so people can paste what their provider gave them.
        cfg.api_key = env("CHAT_AGENT_API_KEY") or env("OPENAI_API_KEY") or env("ANTHROPIC_API_KEY")
        return cfg

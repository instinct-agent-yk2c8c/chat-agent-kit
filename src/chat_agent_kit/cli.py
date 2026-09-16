"""chat-agent: the command line entry point."""
from __future__ import annotations

import argparse
import logging
import os
import sys

from .agents import Agent, CommandAgent, EchoAgent, SimpleAgent
from .channels import CliChannel, IMessageChannel, WhatsAppCloudChannel
from .config import Config
from .providers.anthropic import DEFAULT_MODEL
from .providers import (
    PROVIDER_PRESETS,
    AnthropicProvider,
    EchoProvider,
    OpenAICompatibleProvider,
    SubscriptionCliProvider,
)
from .runner import AgentRunner


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="chat-agent",
        description="Run your own AI agent over iMessage and/or WhatsApp, "
                    "backed by your own AI provider credentials.",
    )
    p.add_argument("--channel", choices=["cli", "imessage", "whatsapp"],
                   help="where the agent talks (default: cli)")
    p.add_argument("--agent", choices=["simple", "echo", "command"],
                   help="simple = the customizable LLM boilerplate (default)")
    p.add_argument("--provider",
                   choices=list(PROVIDER_PRESETS) + ["anthropic", "codex-subscription",
                                                    "cursor-subscription", "grok-subscription"],
                   help="who answers (default: openai)")
    p.add_argument("--base-url", help="custom OpenAI-compatible endpoint")
    p.add_argument("--model", help="override the provider's default model")
    p.add_argument("--persona", help="markdown file used as the agent's system prompt")
    p.add_argument("--respond-to",
                   help="comma-separated allowlist of senders to reply to")
    p.add_argument("--send", action="store_true",
                   help="actually send replies (default is dry-run)")
    p.add_argument("--poll", type=float, help="iMessage poll interval in seconds")
    p.add_argument("--db", help="path to chat.db (iMessage channel)")
    p.add_argument("--port", type=int, help="webhook port (WhatsApp channel)")
    p.add_argument("--state", help="path to the state file")
    p.add_argument("-v", "--verbose", action="store_true")
    return p


def build_provider(config: Config):
    if config.agent != "simple":
        return None
    if config.provider in {"codex-subscription", "cursor-subscription", "grok-subscription"}:
        return SubscriptionCliProvider(config.provider, model=config.model)
    if config.provider == "anthropic":
        return AnthropicProvider(api_key=config.api_key, model=config.model or DEFAULT_MODEL)
    if config.base_url:
        return OpenAICompatibleProvider(
            api_key=config.api_key, base_url=config.base_url,
            model=config.model or "gpt-4o-mini",
        )
    return OpenAICompatibleProvider.from_preset(
        config.provider, api_key=config.api_key, model=config.model
    )


def build_agent(config: Config) -> Agent:
    if config.agent == "echo":
        return EchoAgent()
    if config.agent == "command":
        return CommandAgent()
    return SimpleAgent(build_provider(config), persona_path=config.persona_path)


def build_channel(config: Config):
    if config.channel == "cli":
        return CliChannel()
    if config.channel == "imessage":
        return IMessageChannel(config.db_path, config.state_path,
                               poll_interval=config.poll_interval_seconds)
    if config.channel == "whatsapp":
        missing = [k for k in
                   ("WHATSAPP_ACCESS_TOKEN", "WHATSAPP_PHONE_NUMBER_ID", "WHATSAPP_VERIFY_TOKEN")
                   if not os.environ.get(k)]
        if missing:
            print(f"WhatsApp channel needs env vars: {', '.join(missing)}. "
                  "See docs/whatsapp.md.", file=sys.stderr)
            raise SystemExit(2)
        return WhatsAppCloudChannel(
            access_token=os.environ["WHATSAPP_ACCESS_TOKEN"],
            phone_number_id=os.environ["WHATSAPP_PHONE_NUMBER_ID"],
            verify_token=os.environ["WHATSAPP_VERIFY_TOKEN"],
            app_secret=os.environ.get("WHATSAPP_APP_SECRET"),
            host=config.listen_host,
            port=config.listen_port,
            state_path=config.state_path,
        )
    raise ValueError(config.channel)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    config = Config.from_env()
    for flag, attr in (("channel", "channel"), ("agent", "agent"),
                       ("provider", "provider"), ("base_url", "base_url"),
                       ("model", "model"), ("persona", "persona_path"),
                       ("db", "db_path"), ("state", "state_path")):
        value = getattr(args, flag)
        if value is not None:
            setattr(config, attr, value)
    if args.respond_to is not None:
        config.respond_to = frozenset(h.strip() for h in args.respond_to.split(",") if h.strip())
    if args.send:
        config.dry_run = False
    if args.poll is not None:
        config.poll_interval_seconds = args.poll
    if args.port is not None:
        config.listen_port = args.port

    # The local terminal user is always allowed; real-world channels are not.
    if config.channel == "cli":
        config.respond_to = config.respond_to | {"local"}
        if not args.respond_to:
            config.rate_limit_per_sender = 0  # no throttle for local testing}
    elif not config.respond_to:
        print(
            "Refusing to start: the respond-to allowlist is empty, so the agent "
            "would reply to no one. Pass --respond-to +15551234567 (one or more "
            "numbers/emails) so it only answers people you chose.",
            file=sys.stderr,
        )
        return 2

    runner = AgentRunner(config, build_agent(config))
    runner.run(build_channel(config))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

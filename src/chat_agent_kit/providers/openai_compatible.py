"""Talks to any OpenAI-compatible chat-completions endpoint.

This one client covers every provider that speaks the OpenAI API shape:
OpenAI itself, OpenRouter, Google Gemini (OpenAI-compatibility endpoint),
GitHub Models, Groq, local servers like Ollama and LM Studio, and anything
else that accepts POST {base_url}/chat/completions. Standard library only.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from .base import Provider

# Preset base URLs and default models. Every one of these accepts an API key
# you create in the provider's own console. See docs/providers.md.
PROVIDER_PRESETS: dict[str, dict[str, str]] = {
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "key_help": "https://platform.openai.com/api-keys",
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "model": "openai/gpt-4o-mini",
        "key_help": "https://openrouter.ai/settings/keys",
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "model": "gemini-3.8-flash",
        "key_help": "https://aistudio.google.com/apikey",
    },
    "github": {
        "base_url": "https://models.github.ai/inference",
        "model": "openai/gpt-4.1",
        "key_help": "https://github.com/settings/tokens (needs the 'models' scope)",
    },
    "ollama": {
        "base_url": "http://localhost:11434/v1",
        "model": "llama3.2",
        "key_help": "no key needed - runs locally (https://ollama.com)",
    },
    "lmstudio": {
        "base_url": "http://localhost:1234/v1",
        "model": "local-model",
        "key_help": "no key needed - runs locally (https://lmstudio.ai)",
    },
}


class OpenAICompatibleProvider(Provider):
    """One client for every OpenAI-shaped endpoint."""

    name = "openai-compatible"

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.openai.com/v1",
        model: str = "gpt-4o-mini",
        timeout: float = 60.0,
    ):
        # Local servers (Ollama, LM Studio) ignore the key but clients must
        # still send one, so a placeholder is fine there.
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout

    @classmethod
    def from_preset(
        cls, preset: str, api_key: str | None = None, model: str | None = None
    ) -> "OpenAICompatibleProvider":
        cfg = PROVIDER_PRESETS[preset]
        return cls(
            api_key=api_key,
            base_url=cfg["base_url"],
            model=model or cfg["model"],
        )

    def complete(self, messages: list[dict]) -> str:
        if not self.api_key:
            raise RuntimeError(
                "No API key set. Set CHAT_AGENT_API_KEY (or your provider's "
                "usual variable, e.g. OPENAI_API_KEY). Keys come from your "
                "provider's console - see docs/providers.md."
            )
        payload = {"model": self.model, "messages": messages}
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            body = e.read().decode()[:500]
            raise RuntimeError(f"Provider returned HTTP {e.code}: {body}") from e
        return data["choices"][0]["message"]["content"].strip()

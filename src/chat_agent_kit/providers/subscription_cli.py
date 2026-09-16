"""Supported local-CLI bridges for AI subscription entitlements.

These bridges never read or copy OAuth tokens. The provider's own CLI owns
login, refresh, quota, and network traffic. Each invocation runs in a fresh,
empty working directory and requests read-only/no-tool behavior where the CLI
supports it.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from .base import Provider


def _prompt(messages: list[dict]) -> str:
    parts = [
        "Reply to the conversation below. Return only the reply text. "
        "Do not use tools, inspect files, run commands, browse, or modify anything."
    ]
    for message in messages:
        role = str(message.get("role", "user")).upper()
        parts.append(f"{role}: {message.get('content', '')}")
    parts.append("ASSISTANT:")
    return "\n\n".join(parts)


class SubscriptionCliProvider(Provider):
    """Use an already-installed, already-signed-in official/local CLI."""

    name = "subscription-cli"

    def __init__(self, backend: str, model: str | None = None, timeout: int = 120):
        if backend not in {"codex-subscription", "cursor-subscription", "grok-subscription"}:
            raise ValueError(f"unsupported subscription CLI backend: {backend}")
        self.backend = backend
        self.model = model
        self.timeout = timeout

    def complete(self, messages: list[dict]) -> str:
        executable = {
            "codex-subscription": "codex",
            "cursor-subscription": "agent",
            "grok-subscription": "opencode",
        }[self.backend]
        if self.backend == "grok-subscription" and not self.model:
            raise RuntimeError(
                "grok-subscription requires --model with an xAI model ID from OpenCode /models"
            )
        if shutil.which(executable) is None:
            raise RuntimeError(
                f"{executable} is not installed or not on PATH. "
                f"See docs/subscriptions.md for install and sign-in steps."
            )
        prompt = _prompt(messages)
        with tempfile.TemporaryDirectory(prefix="chat-agent-kit-") as workdir:
            if self.backend == "codex-subscription":
                return self._codex(executable, prompt, workdir)
            if self.backend == "cursor-subscription":
                return self._cursor(executable, prompt, workdir)
            return self._grok(executable, prompt, workdir)

    def _run(self, args: list[str], workdir: str, *, stdin: str | None = None,
             env: dict[str, str] | None = None) -> subprocess.CompletedProcess:
        try:
            result = subprocess.run(
                args, input=stdin, text=True, capture_output=True, cwd=workdir,
                env=env, timeout=self.timeout, check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"{self.backend} timed out after {self.timeout}s") from exc
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()[-1000:]
            raise RuntimeError(f"{self.backend} failed ({result.returncode}): {detail}")
        return result

    def _codex(self, executable: str, prompt: str, workdir: str) -> str:
        output = Path(workdir) / "reply.txt"
        args = [executable, "exec", "--ephemeral", "--sandbox", "read-only",
                "--skip-git-repo-check", "--output-last-message", str(output)]
        if self.model:
            args += ["--model", self.model]
        args.append("-")
        result = self._run(args, workdir, stdin=prompt)
        text = output.read_text().strip() if output.exists() else result.stdout.strip()
        if not text:
            raise RuntimeError("codex-subscription returned no reply")
        return text

    def _cursor(self, executable: str, prompt: str, workdir: str) -> str:
        args = [executable, "-p", "--mode", "ask", "--output-format", "json",
                "--workspace", workdir]
        if self.model:
            args += ["--model", self.model]
        args.append(prompt)
        result = self._run(args, workdir)
        raw = result.stdout.strip()
        try:
            data = json.loads(raw)
            text = data.get("result") or data.get("text") or data.get("message")
            if isinstance(text, dict):
                text = text.get("content") or text.get("text")
            if isinstance(text, str) and text.strip():
                return text.strip()
        except json.JSONDecodeError:
            pass
        if not raw:
            raise RuntimeError("cursor-subscription returned no reply")
        return raw

    def _grok(self, executable: str, prompt: str, workdir: str) -> str:
        # OpenCode's documented permission config blocks every tool. The xAI
        # OAuth connection remains owned by OpenCode; no token is copied here.
        env = os.environ.copy()
        env["OPENCODE_CONFIG_CONTENT"] = json.dumps({"permission": "deny"})
        args = [executable, "run", "--dir", workdir]
        if self.model:
            args += ["--model", self.model]
        args.append(prompt)
        result = self._run(args, workdir, env=env)
        text = result.stdout.strip()
        if not text:
            raise RuntimeError("grok-subscription returned no reply")
        return text

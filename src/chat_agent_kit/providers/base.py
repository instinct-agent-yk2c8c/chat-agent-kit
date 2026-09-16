"""The provider interface. A provider turns a chat history into a reply."""
from __future__ import annotations


class Provider:
    """Base class. `messages` is a list of {"role": ..., "content": ...}
    dicts (system/user/assistant). Return the assistant's reply text."""

    name = "provider"

    def complete(self, messages: list[dict]) -> str:
        raise NotImplementedError

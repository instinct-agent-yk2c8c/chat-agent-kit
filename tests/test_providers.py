import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _util import StubServer
from chat_agent_kit.providers.anthropic import AnthropicProvider
from chat_agent_kit.providers.openai_compatible import (
    PROVIDER_PRESETS,
    OpenAICompatibleProvider,
)

MESSAGES = [
    {"role": "system", "content": "Be brief."},
    {"role": "user", "content": "hi"},
]


class TestOpenAICompatible(unittest.TestCase):
    def test_posts_chat_completions_and_parses_reply(self):
        stub = StubServer({"choices": [{"message": {"content": "hello there"}}]})
        try:
            p = OpenAICompatibleProvider(api_key="sk-test", base_url=stub.url, model="m1")
            self.assertEqual(p.complete(MESSAGES), "hello there")
            req = stub.requests[0]
            self.assertEqual(req["path"], "/chat/completions")
            self.assertEqual(req["headers"]["Authorization"], "Bearer sk-test")
            self.assertEqual(req["body"]["model"], "m1")
            self.assertEqual(req["body"]["messages"], MESSAGES)
        finally:
            stub.stop()

    def test_missing_key_is_a_clear_error(self):
        p = OpenAICompatibleProvider(api_key=None, base_url="http://x", model="m")
        with self.assertRaises(RuntimeError):
            p.complete(MESSAGES)

    def test_http_error_surfaces_body(self):
        stub = StubServer({"error": {"message": "bad key"}}, status=401)
        try:
            p = OpenAICompatibleProvider(api_key="nope", base_url=stub.url, model="m")
            with self.assertRaisesRegex(RuntimeError, "401"):
                p.complete(MESSAGES)
        finally:
            stub.stop()

    def test_presets_cover_the_documented_providers(self):
        for name in ("openai", "openrouter", "gemini", "github", "ollama", "lmstudio"):
            self.assertIn("base_url", PROVIDER_PRESETS[name])
            self.assertIn("model", PROVIDER_PRESETS[name])


class TestAnthropic(unittest.TestCase):
    def test_posts_messages_api_shape(self):
        stub = StubServer({"content": [{"type": "text", "text": "hi!"}]})
        try:
            p = AnthropicProvider(api_key="sk-ant-test", model="claude-haiku-4-5")
            # point the provider at the stub
            import chat_agent_kit.providers.anthropic as mod
            old = mod.ANTHROPIC_MESSAGES_URL
            mod.ANTHROPIC_MESSAGES_URL = stub.url + "/v1/messages"
            try:
                self.assertEqual(p.complete(MESSAGES), "hi!")
            finally:
                mod.ANTHROPIC_MESSAGES_URL = old
            req = stub.requests[0]
            self.assertEqual(req["headers"]["X-Api-Key"], "sk-ant-test")
            self.assertEqual(req["headers"]["Anthropic-Version"], "2023-06-01")
            self.assertEqual(req["body"]["system"], "Be brief.")
            self.assertEqual(req["body"]["messages"], [{"role": "user", "content": "hi"}])
        finally:
            stub.stop()


if __name__ == "__main__":
    unittest.main()

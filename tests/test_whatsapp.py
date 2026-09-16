import hashlib
import hmac
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from _util import StubServer
from chat_agent_kit.channels.whatsapp_cloud import (
    WhatsAppCloudChannel,
    check_webhook_verification,
    parse_webhook_payload,
    verify_signature,
)

PAYLOAD = {
    "object": "whatsapp_business_account",
    "entry": [{
        "id": "123",
        "changes": [{
            "field": "messages",
            "value": {
                "metadata": {"phone_number_id": "999"},
                "messages": [
                    {"from": "15551234567", "id": "wamid.1", "timestamp": "1780000000",
                     "type": "text", "text": {"body": "hello"}},
                    {"from": "15551234567", "id": "wamid.2", "timestamp": "1780000001",
                     "type": "image"},
                ],
                "statuses": [{"id": "wamid.0", "status": "delivered"}],
            },
        }],
    }],
}


class TestWebhookVerification(unittest.TestCase):
    def test_accepts_matching_token(self):
        params = {"hub.mode": "subscribe", "hub.verify_token": "tok", "hub.challenge": "42"}
        self.assertEqual(check_webhook_verification(params, "tok"), "42")

    def test_rejects_wrong_token(self):
        params = {"hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "42"}
        self.assertIsNone(check_webhook_verification(params, "tok"))


class TestSignature(unittest.TestCase):
    def sign(self, secret, body):
        return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    def test_good_signature(self):
        body = b'{"a":1}'
        self.assertTrue(verify_signature("secret", body, self.sign("secret", body)))

    def test_bad_signature(self):
        self.assertFalse(verify_signature("secret", b'{"a":1}', "sha256=deadbeef"))

    def test_missing_header(self):
        self.assertFalse(verify_signature("secret", b"{}", None))


class TestParsePayload(unittest.TestCase):
    def test_extracts_text_messages_only(self):
        msgs = parse_webhook_payload(PAYLOAD)
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0].sender, "15551234567")
        self.assertEqual(msgs[0].text, "hello")
        self.assertEqual(msgs[0].channel, "whatsapp")
        self.assertEqual(msgs[0].id, "wamid.1")
        self.assertEqual(msgs[0].sent_at.year, 2026)

    def test_empty_payload(self):
        self.assertEqual(parse_webhook_payload({}), [])


class TestChannel(unittest.TestCase):
    def make(self, **kw):
        import tempfile
        state = str(Path(tempfile.mkdtemp()) / "state.json")
        return WhatsAppCloudChannel(
            access_token="tok", phone_number_id="999", verify_token="vt",
            state_path=state, **kw,
        )

    def test_send_posts_correct_shape(self):
        stub = StubServer({"messages": [{"id": "wamid.new"}]})
        try:
            ch = self.make()
            ch.graph_base = stub.url
            msg = parse_webhook_payload(PAYLOAD)[0]
            ch.send(msg, "reply text")
            req = stub.requests[0]
            self.assertEqual(req["path"], "/999/messages")
            self.assertEqual(req["headers"]["Authorization"], "Bearer tok")
            self.assertEqual(req["body"]["messaging_product"], "whatsapp")
            self.assertEqual(req["body"]["to"], "15551234567")
            self.assertEqual(req["body"]["text"]["body"], "reply text")
        finally:
            stub.stop()

    def test_dedupe_persists(self):
        ch = self.make()
        self.assertFalse(ch._is_duplicate("wamid.1"))
        self.assertTrue(ch._is_duplicate("wamid.1"))
        # reload from the same state file
        ch3 = WhatsAppCloudChannel(access_token="t", phone_number_id="9",
                                   verify_token="v", state_path=ch.state_path)
        self.assertTrue(ch3._is_duplicate("wamid.1"))


if __name__ == "__main__":
    unittest.main()

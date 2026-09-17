# WhatsApp channel

Uses **Meta's official WhatsApp Business Cloud API**. Research date:
September 16, 2026 - sources linked at the bottom.

## Why only the Cloud API?

Personal WhatsApp has no API. The unofficial bridges you will find
(Baileys, whatsmeow, whatsapp-web.js) speak WhatsApp Web's private
protocol, violate the Terms of Service, and get numbers banned - in 2025
Meta's detection began flagging even low-volume, reply-only usage:
https://github.com/tulir/whatsmeow/issues/810

This kit does not include or endorse unofficial bridges. The Cloud API is
the supported path and is free for the reply-driven pattern this agent
uses.

## What you need

1. A Meta developer account: https://developers.facebook.com
2. An app with the **WhatsApp** use case, connected to a WhatsApp Business
   account. Meta gives you a **free test number** for development.
3. A **permanent access token** (a system-user token; the temporary token
   from the quickstart expires in 24 hours).
4. A public HTTPS URL for the webhook. In development, a tunnel
   (cloudflared, ngrok, Tailscale Funnel) pointed at this machine works.

Full walkthrough:
https://developers.facebook.com/docs/whatsapp/cloud-api/get-started/

Important shape facts:

- The **test number** can only message phone numbers you register as
  recipients in the dashboard - fine for a personal agent, since your
  allowlist is small anyway. Going live with your own number requires
  business verification and a display-name review.
- The number you attach **cannot be an existing personal WhatsApp
  number**. Use the test number, a spare SIM, or a virtual number.
- You can send free-form messages only inside the **24-hour customer
  service window** that opens when a user messages you. This agent only
  replies, so it lives entirely inside that window. Proactive outreach
  requires pre-approved **template messages**, which are paid.
- **Pricing** (July 2025 rules): user-initiated *service conversations are
  free*; template messages are charged per message.
  https://developers.facebook.com/docs/whatsapp/pricing/

## Run it

```bash
export WHATSAPP_ACCESS_TOKEN=EAAG...        # permanent system-user token
export WHATSAPP_PHONE_NUMBER_ID=123456...   # from the API Setup page
export WHATSAPP_VERIFY_TOKEN=some-long-random-string-you-made-up
export WHATSAPP_APP_SECRET=...              # app secret, for signature checks
export CHAT_AGENT_API_KEY=...               # your AI provider key

chat-agent --channel whatsapp --port 8080 --respond-to 15551234567
# dry-run first, as always
chat-agent --channel whatsapp --port 8080 --respond-to 15551234567 --send
```

Then in the Meta app dashboard, set the webhook callback to
`https://<your-tunnel-url>/` with your verify token and subscribe to the
`messages` field. `--respond-to` values are WhatsApp ids: digits only,
with country code, no `+`.

## Safety notes

- `WHATSAPP_APP_SECRET` enables HMAC signature verification on every
  webhook POST. Set it - without it, anyone who finds your URL can feed
  fake messages to your agent.
- Incoming text events are committed to a SQLite inbox next to the state file
  before the server returns HTTP 200. Model work and sending happen on a
  background worker, so a slow provider never delays webhook acknowledgement.
- Message ids are unique in that inbox. Meta retries are deduped, unfinished
  work is recovered on restart, and failed model/send attempts remain pending
  for retry. If the inbox cannot be committed, the webhook returns 503 so Meta
  can deliver it again.
- Existing `seen_whatsapp_ids` state is migrated as completed work on upgrade.
  The existing `--state` path and environment setup remain valid.
- Keep the access token in env vars or a secret manager, never in git.

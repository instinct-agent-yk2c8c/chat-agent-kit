# Security policy

## Reporting

Open an issue at
https://github.com/instinct-agent-yk2c8c/chat-agent-kit/issues for bugs.
For vulnerabilities that shouldn't be public yet, use GitHub's private
vulnerability reporting on the same repository.

## Threat model and your responsibilities

This kit runs on your machine, with your credentials, on your accounts:

- **API keys** (AI provider, WhatsApp token, app secret) are read from
  environment variables only. Never commit them; `.env` is gitignored.
- The **iMessage** channel reads your Messages database read-only and
  immutable, and sends through Messages.app as you. Anyone with
  allowlist access is talking to an agent that speaks *as you* - keep the
  allowlist tight.
- The **WhatsApp** channel verifies `X-Hub-Signature-256` when
  `WHATSAPP_APP_SECRET` is set. Set it, or anyone who finds your webhook
  URL can inject fake messages.
- Everything you allowlist gets an LLM with whatever persona and history
  window you configured. Prompt injection through inbound texts is real:
  the default persona file includes guardrails, but treat model output as
  untrusted, especially if you extend the agent with tools.
- The agent stores a small local state file (message checkpoints, deduped
  ids) in `~/.chat-agent-kit/state.json`. It contains message ids, not
  message contents.

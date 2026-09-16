# Research log - September 16, 2026

What we verified before building, with sources. Boundaries like these
move; re-check the links before relying on this file.

## AI providers: subscriptions are not API access

- OpenAI Help: ChatGPT Plus - "API usage is separate and billed
  independently." https://help.openai.com/en/articles/6950777-what-is-chatgpt-plus
- OpenAI Help: "ChatGPT and the API platform have separate billing
  systems." https://help.openai.com/en/articles/9039756-managing-billing-for-chatgpt-and-the-api-platform
- Anthropic Support: "A paid Claude subscription ... doesn't include
  access to the Claude API or Console."
  https://support.claude.com/en/articles/9876003
- Anthropic models overview (current IDs: claude-fable-5-1, claude-opus-5,
  claude-sonnet-5, claude-haiku-4-5):
  https://docs.anthropic.com/en/docs/about-claude/models/overview
- Cursor docs: its APIs run Cursor's own agents and teams; "not a
  standalone model-inference or chat-completions API."
  https://cursor.com/docs/api

## Working provider paths

- OpenAI API keys: https://platform.openai.com/api-keys
- Anthropic Console: https://console.anthropic.com
- Gemini API OpenAI-compatibility endpoint (free tier keys in AI Studio):
  https://ai.google.dev/gemini-api/docs/openai
- GitHub Models quickstart (PAT with `models` scope, OpenAI-compatible,
  free with limits): https://docs.github.com/en/github-models/quickstart
- OpenRouter (one OpenAI-compatible key, 500+ models, free tier):
  https://openrouter.ai/developers
- Ollama OpenAI compatibility (local, free, private):
  https://docs.ollama.com/api/openai-compatibility

## Messaging channels

- iMessage: no official API. This kit reads chat.db read-only/immutable and
  sends via Messages.app AppleScript. BlueBubbles offers a REST/webhook
  alternative: https://docs.bluebubbles.app/server/developer-guides/rest-api-and-webhooks
- WhatsApp Cloud API get-started (app, business account, test number,
  permanent token, webhook, 24-hour customer service window):
  https://developers.facebook.com/docs/whatsapp/cloud-api/get-started/
- WhatsApp pricing: service conversations free (since Nov 2024); template
  messages per-message pricing from July 1, 2025:
  https://developers.facebook.com/docs/whatsapp/pricing/
- Unofficial WhatsApp libraries: account-risk warnings and bans reported
  even for low-volume reply-only use:
  https://github.com/tulir/whatsmeow/issues/810
- Graph API v26.0 released July 29, 2026 (the kit's default webhook/send
  version): https://developers.facebook.com/docs/graph-api/changelog/version26.0/

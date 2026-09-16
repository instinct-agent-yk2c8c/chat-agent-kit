# What can actually power your agent

**Research date: September 16, 2026.** These boundaries move; check the
linked official docs before you build on them.

## The short version

Consumer AI **subscriptions** do not give you a general model API. But some
providers now expose a supported local coding CLI or a named third-party OAuth
integration. This kit can use those narrow subscription paths without copying
tokens. See [subscriptions.md](subscriptions.md). API keys and local models
remain the best fit for a general or high-volume chat agent.

| What you have | Does it work? | Why |
|---|---|---|
| OpenAI **API key** (pay-as-you-go) | ✅ Yes | This is the supported path. Set `CHAT_AGENT_PROVIDER=openai`. |
| Anthropic **API key** (Claude Console) | ✅ Yes | The supported path for Claude. Set `CHAT_AGENT_PROVIDER=anthropic`. |
| Google **Gemini API key** (AI Studio) | ✅ Yes, free tier | OpenAI-compatible endpoint. Set `CHAT_AGENT_PROVIDER=gemini`. |
| **GitHub Models** (GitHub PAT, `models` scope) | ✅ Yes, free tier | OpenAI-compatible. Set `CHAT_AGENT_PROVIDER=github`. |
| **OpenRouter** API key | ✅ Yes, free models exist | One key, 500+ models. Set `CHAT_AGENT_PROVIDER=openrouter`. |
| **Ollama** or **LM Studio** (local) | ✅ Yes, free & private | Runs on your machine, no key. `CHAT_AGENT_PROVIDER=ollama` / `lmstudio`. |
| Any other **OpenAI-compatible endpoint** | ✅ Yes | `--base-url` + `CHAT_AGENT_API_KEY` + `--model`. |
| ChatGPT plan with **Codex** | ✅ Narrow path | Supported local Codex CLI login + non-interactive execution; not a general API. |
| Claude **Pro/Max** | ⚠️ Not enabled | Claude Code works, but Anthropic restricts unapproved third-party claude.ai login/rate-limit use. |
| **Cursor** subscription | ✅ Narrow path | Supported local Cursor Agent CLI in non-interactive Ask mode; not a general API. |
| **SuperGrok / eligible X Premium** | ✅ Narrow path | xAI-documented OAuth through OpenCode; not the xAI API. |
| Session cookies / subscription tokens scraped from a browser | ❌ Never | Violates the provider's terms, breaks constantly, and this kit will not support it. |

## Details and sources

### OpenAI: ChatGPT vs the API are separate products

ChatGPT Plus is a subscription to the ChatGPT app. The OpenAI API (what this
kit calls with `CHAT_AGENT_PROVIDER=openai`) is billed separately:

- "Not included: API usage is separate and billed independently."
  — https://help.openai.com/en/articles/6950777-what-is-chatgpt-plus
- "ChatGPT and the API platform have separate billing systems."
  — https://help.openai.com/en/articles/9039756-managing-billing-for-chatgpt-and-the-api-platform

Get a key at https://platform.openai.com/api-keys. You pay per token; a
small model like the default `gpt-4o-mini` costs very little for personal
texting volume.

### Anthropic: Claude Pro/Max vs the Claude Console are separate products

- "A paid Claude subscription enhances your chat experience but doesn't
  include access to the Claude API or Console."
  — https://support.claude.com/en/articles/9876003

Get a key at https://console.anthropic.com, then
`CHAT_AGENT_PROVIDER=anthropic` + `ANTHROPIC_API_KEY=...`. Default model is
`claude-haiku-4-5`; current model IDs live at
https://docs.anthropic.com/en/docs/about-claude/models/overview.

### Cursor: no general model API

Cursor sells an AI code editor. Its APIs manage teams and run Cursor's own
coding agents: "The Cloud Agents API and SDKs run Cursor agent workflows...
They are not a standalone model-inference or chat-completions API."
— https://cursor.com/docs/api

There is no way to point a chat agent at your Cursor subscription. (Cursor
itself can *consume* OpenAI-compatible MCP/tools, but that is the opposite
direction.)

### Free and local options

- **Google AI Studio** hands out Gemini API keys with a free tier, exposed
  through an OpenAI-compatible endpoint:
  https://ai.google.dev/gemini-api/docs/openai
- **GitHub Models** runs OpenAI/Meta/DeepSeek and other models with just a
  GitHub personal access token (`models` scope), free with rate limits:
  https://docs.github.com/en/github-models/quickstart
- **OpenRouter** aggregates 500+ models behind one OpenAI-compatible key,
  including free-tier models: https://openrouter.ai/developers
- **Ollama** (https://ollama.com) and **LM Studio** (https://lmstudio.ai)
  run models on your own hardware with an OpenAI-compatible local server:
  https://docs.ollama.com/api/openai-compatibility. No key, no cost, no
  data leaves your machine - you need a computer that can run the model.

## Cost reality check

For a personal agent answering texts, a small hosted model (gpt-4o-mini,
claude-haiku, gemini-flash) typically costs cents per day. Local models cost
nothing but your electricity. The expensive way to do this is accidentally
pointing it at a frontier model with a long history window - the default
`history_size` of 20 keeps context small.

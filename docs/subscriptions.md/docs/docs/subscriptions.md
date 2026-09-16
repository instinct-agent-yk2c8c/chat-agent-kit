# Bring your own subscription: what is actually supported

**Researched September 16, 2026.** Provider policy and CLI behavior can change.
This page separates a consumer chat subscription from the provider's supported
coding-agent interfaces.

## The important correction

A ChatGPT, Claude, Cursor, or Grok subscription is not a general-purpose API
key. But some providers let a subscribed user sign an official local coding
CLI in, and some of those CLIs have documented non-interactive or integration
modes. That creates a narrow, legitimate BYOS path: this kit can invoke the
provider-supported CLI on the same machine while the CLI owns OAuth, refresh,
quota, and network traffic.

That is different from copying browser cookies, reading token files, replaying
private web requests, or relaying subscription credentials through a server.
This project does none of those things.

## Current matrix

| Subscription | Status in this kit | Supported path | Boundary |
|---|---|---|---|
| ChatGPT plan with Codex access | Supported | Official Codex CLI, `codex login`, then `codex exec` | Codex entitlement and shared plan limits, not the general OpenAI API |
| Claude Pro/Max | Not enabled | Claude Code itself supports the plan, but Anthropic says unapproved third-party apps may not offer claude.ai login or rate limits | Use an Anthropic API key until Anthropic approves this use or changes the rule |
| Cursor plan | Supported | Official Cursor Agent CLI, `agent login`, then non-interactive Ask mode | Cursor's coding agent, not a chat-completions API |
| SuperGrok or eligible X Premium plan | Supported | xAI's documented OAuth inside OpenCode, then `opencode run` | Grok subscription models exposed by that xAI/OpenCode integration, not the xAI API |

## Setup

All subscription bridges are opt-in. Install and sign in through the provider's
own documented tool first. Credentials stay with that tool.

### ChatGPT / Codex

```bash
# Install Codex CLI using OpenAI's current instructions, then:
codex login
codex login status
chat-agent --channel cli --provider codex-subscription
```

OpenAI documents "Sign in with ChatGPT for subscription access," browser-based
CLI login, `codex exec` for scripts, and a read-only sandbox by default. The
bridge uses a fresh temporary working directory, `--ephemeral`, an explicit
read-only sandbox, and only the final text output. It never reads Codex's token.

Sources:
- https://developers.openai.com/codex/auth
- https://developers.openai.com/codex/cli/reference.md
- https://developers.openai.com/codex/noninteractive
- https://developers.openai.com/codex/sdk
- https://help.openai.com/en/articles/11369540-codex-in-chatgpt

### Cursor

```bash
# Install Cursor Agent CLI using Cursor's current instructions, then:
agent login
agent status
chat-agent --channel cli --provider cursor-subscription
```

Cursor documents non-interactive `--print` output for scripts and CI, Ask mode
as read-only behavior, and ACP specifically for custom clients and integrations.
The bridge uses a fresh temporary workspace and `--mode ask`. Cursor's API and
SDK are still not model inference APIs; this is the local Cursor Agent product.

Sources:
- https://cursor.com/docs/cli/using
- https://cursor.com/docs/cli/reference/parameters
- https://cursor.com/docs/cli/acp
- https://cursor.com/docs/api

### Grok through OpenCode

```bash
# Install OpenCode, then open it and run /connect.
# Select xAI and one of the Grok OAuth subscription options.
opencode
chat-agent --channel cli --provider grok-subscription --model xai/grok-build-0.1
```

xAI explicitly documents using a SuperGrok or X Premium subscription inside
OpenCode, including browser OAuth and a headless device-code flow. OpenCode
supports `run` for automation and a permission config that can deny every tool.
The bridge sets that deny-all config and runs in a fresh temporary directory.
Use the exact model ID shown by your current OpenCode install; availability
comes from the subscription.

Sources:
- https://x.ai/news/grok-opencode
- https://opencode.ai/docs/cli/
- https://opencode.ai/docs/providers/
- https://opencode.ai/docs/permissions/

### Claude / Claude Code

Claude Pro and Max can sign in to Claude Code. Claude's official CLI also has
`claude -p`, JSON output, and an Agent SDK. On June 11, 2026, Anthropic said
Agent SDK, `claude -p`, and third-party-app usage still drew from subscription
limits while a planned policy change was paused. However, Anthropic's Agent SDK
documentation also says that, unless previously approved, third-party developers
may not offer claude.ai login or rate limits in their products and should use API
key authentication.

Because this kit is a third-party product and has no Anthropic approval, it does
not expose `claude-subscription`. Running Claude Code yourself is supported;
turning that login into this product's provider is not clearly authorized.

Sources:
- https://support.claude.com/en/articles/11145838-use-claude-code-with-your-pro-or-max-plan
- https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan
- https://docs.anthropic.com/en/docs/claude-code/sdk/sdk-overview
- https://docs.anthropic.com/en/docs/claude-code/cli-reference
- https://support.claude.com/en/articles/9876003

## What other BYOS tools are doing

There are at least three distinct patterns behind the same marketing phrase:

1. **Wrap the provider's local CLI.** Raycast says it finds signed-in `claude`
   and `codex` tools locally; prompts go from those tools to the provider and
   Raycast does not store the credentials. Abacus documents the same local Codex
   pattern. This is the pattern used here where provider policy allows it.
2. **Host the CLI in a managed workspace.** Unstoppable advertises first-class
   Claude Code and Codex sessions plus arbitrary CLI agents. That is a coding
   workspace product, not a generic model API.
3. **Implement OAuth and call a subscription backend directly.** Cline's open
   implementation uses PKCE, an OAuth access token, and
   `https://chatgpt.com/backend-api/codex`. It can work and Cline markets it as
   Codex OAuth, but it couples the app to a product backend and token lifecycle.
   This kit chooses the lower-risk CLI boundary rather than copying that
   implementation or reusing the official CLI's OAuth client identity.

Representative sources:
- https://manual.raycast.com/ai/bring-your-own-subscription
- https://abacus.ai/help/abacusai-desktop/providers
- https://code.unstoppabledomains.com/products/bring-your-own-subscription
- https://cline.bot/blog/introducing-openai-codex-oauth
- https://github.com/cline/cline/blob/9dea336c/src/core/api/providers/openai-codex.ts

## Safety and operational limits

- Subscription usage shares the provider's rolling limits with its own apps.
- These are coding agents, so they cost more latency and context than a small
  chat API model. For a high-volume texting bot, an API key or local model is a
  better fit.
- The child process receives the conversation text. Do not use a subscription
  bridge for data you would not send to that provider.
- This project deliberately avoids direct token input, token-file reads,
  browser-session extraction, private web APIs, and cookie replay.
- A provider may narrow, meter, rename, or remove the path. Errors are surfaced;
  the kit does not bypass limits or silently fall back to another credential.

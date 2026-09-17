# Building a capable personal agent in iMessage or WhatsApp

**Research date:** September 16, 2026

## Bottom line

Do not start by building a chatbot. Build a small event-driven operating system around a model: authenticated message ingress, a durable task ledger, explicit authority and approval checks, isolated tools, memory with provenance, and reliable resumable jobs. The channel should be a thin front door.

For one technically sophisticated user, the best practical path is a **Mac mini for the iMessage edge**, plus a **cloud control plane and one isolated browser/worker VM**. Add WhatsApp only for a narrowly described specialized assistant or after legal/platform review: since January 15, 2026, Meta's terms generally permit third-party “AI Providers” to offer general-purpose assistants on the WhatsApp Business Platform only where legally required. A specialized workflow agent may be treated differently, but that classification is a launch blocker to verify with Meta or counsel, not a wording trick.

The existing `chat-agent-kit` is a good channel/provider spike, not yet a trusted personal agent runtime. Reuse its channel adapters, provider abstraction, allowlist, dry run, webhook signature check, and dedupe ideas. Replace its in-memory history and synchronous reply loop with durable storage, a policy/authority layer, jobs, tools, isolation, and observability.

## Three viable architectures

| Stage | Intended use | Shape | Realistic effort | Rough operating cost* |
|---|---|---|---:|---:|
| Prototype | One builder, reply-only experiments | Mac process for iMessage or one WhatsApp webhook; SQLite; hosted API/local model; no autonomous mutations | 3-7 engineering days | $10-75/month plus model use and Mac |
| Strong single-user | A dependable personal agent that can browse and work in background | Mac iMessage edge + cloud API + Postgres/pgvector + queue/workflow engine + secret vault + dedicated browser VM + approval UI | 6-12 engineer-weeks | $75-300/month plus model/browser-heavy usage |
| Multi-user product | External users, integrations, proactive work, SLOs | Multi-region ingress; per-tenant control plane; per-user execution cells; Temporal; KMS/Vault; object store; policy service; evals/on-call | 9-18 months for 5-8 experienced engineers, then ongoing security/compliance | $20-100/user/month before support/model spikes; wide variance |

\*Planning envelopes, not vendor quotes. Computer-use token/image traffic and warm per-user VMs dominate. Current vendor prices must be modeled against workload traces.

## Recommended single-user stack

- **iMessage edge:** always-on Mac mini, Messages signed in, a launchd service, read-only `chat.db` watcher or BlueBubbles webhooks, outbound send through Messages.app/BlueBubbles. Put no model credentials on the Mac. Use a mutually authenticated outbound tunnel to the cloud.
- **WhatsApp edge:** official WhatsApp Cloud API only. Verify webhook signatures, persist event IDs before returning 200, and process asynchronously. Free-form replies require an open 24-hour customer-service window; proactive messages require approved templates. First resolve whether the product is an “AI Provider”/general-purpose assistant under current terms.
- **API/control plane:** Python FastAPI or TypeScript, Postgres with row-level tenant boundaries, S3-compatible object storage, Redis only as a cache, not as the source of truth.
- **Durable work:** Temporal for workflows, timers, retries, signals/approvals, and resume-after-crash. A queue-only system is fine for the prototype but requires your own state machine and idempotency discipline.
- **Agent runtime:** OpenAI Responses/Agents SDK or Anthropic API/Agent SDK behind an internal model adapter. Use an inexpensive model for triage and routing, a strong model for plans/load-bearing text, and a separate verifier for risky actions. Keep model output advisory until deterministic policy authorizes the tool.
- **BYOS:** supported local CLI bridges can use ChatGPT/Codex, Cursor, and Grok subscriptions on a user-owned machine, but they are coding-agent entitlements, not stable multi-user inference APIs. Use API billing for a product. Claude subscription login should not be offered by an unapproved third-party product under Anthropic's current guidance.
- **Tools/integrations:** typed internal tools or MCP servers. Put OAuth and credential use in a connector service outside the model's writable sandbox. Each invocation carries `tenant_id`, scopes, purpose, idempotency key, and policy decision ID.
- **Browser/computer:** dedicated per-user VM/container with Chromium, restricted egress, downloads quarantine, visible session/takeover, snapshots, and hard reset. Never run the browser in the control-plane process.
- **Secrets:** cloud KMS plus Secrets Manager/Vault; envelope encryption; short-lived scoped tokens; no secrets in prompts/logs; vault fill occurs outside model context.
- **Payments:** do not give the model raw card data. Use merchant-hosted checkout, delegated/payment tokens, or a PCI-compliant provider. Require a user confirmation bound to item, final total, address, rail, and expiry immediately before commit.
- **Observability:** OpenTelemetry traces keyed by task/tool attempt, append-only audit events, redacted structured logs, model/tool cost, latency, retries, approval state, and replay tooling. Store artifact hashes and exact source references.

## Component diagram

```text
 iMessage/Mac edge            WhatsApp Cloud API
        |                            |
        +------ authenticated ingress gateway ------+
                                                     |
                                        normalize + dedupe event
                                                     |
                                  conversation / task coordinator
                                  /          |                 \
                         memory retrieval  policy/authority   Temporal
                                  |          |                 |
                         Postgres/vector   approval inbox   task workers
                                                               |
                                   tool broker / connector service
                                      /        |          \
                               Google/etc   browser VM   payment adapter
                                      \        |          /
                                  audit log + artifacts + telemetry
```

## Runtime contract

Every inbound message becomes an immutable event. The coordinator links it to a conversation and either answers directly or creates a durable task. A task advances through explicit states such as `received -> researched -> awaiting_approval -> executing -> verifying -> completed/blocked`. Every side effect is an idempotent tool command. A retry reads the command result before repeating it.

Do not let the model decide its own authority. The policy layer calculates a capability from trusted user evidence: actor, audience, data fields, tool, purpose, amount, expiry, and whether review is required. External text, web pages, emails, and tool output are untrusted data and can never broaden authority.

For representation, approvals bind the final recipient and final words or artifact. For money, approval binds the final cart, total, address, payment rail, and cancellation terms. For access changes and destructive actions, require an equally concrete review.

## Memory

Use four stores, not one giant transcript:

1. **Event log:** immutable channel messages, tool results, approvals, task transitions.
2. **Working state:** current task plan, blockers, leases, deadlines, idempotency keys.
3. **Episodic memory:** compact sourced summaries of completed interactions.
4. **Semantic profile:** stable preferences/relationships with provenance and sensitivity labels.

Retrieval should filter by tenant, person, permissions, recency, and source before vector ranking. Exact facts such as current calendar state or price must be re-read from the owning live system. Memory writes should be proposed, deduplicated, and reversible; a model summary must retain links to source events.

## Security boundary

The key rule is to break the “lethal trifecta”: untrusted content, valuable private data, and the ability to communicate or mutate. Do not expose all three inside one unconstrained model loop.

- Treat every fetched page, email, attachment, and MCP response as untrusted.
- Keep connector code and credentials outside the browser/agent cell.
- Use per-user execution cells for computer use and code. Meta says Muse uses a dedicated per-user VM and separates privileged connector logic from the runtime cell; Fly documents one-app-per-user isolation and warns that Machines in one app share secrets/network reach.
- Use outbound domain allowlists, network policy, resource/time limits, malware scanning, and ephemeral workspaces.
- Validate MCP OAuth audience; never pass upstream access tokens through to downstream servers. Log what data leaves through each tool.
- Put prompt-injection classifiers and high-risk action verifiers outside the model's editable environment.
- Build account deletion/export, retention controls, key rotation, backup restore drills, and security incident procedures before multi-user launch.

## Channel realities

### iMessage

Apple exposes frameworks for iMessage apps/extensions and Messages for Business, not a general server API for a personal iMessage bot. A personal assistant therefore needs an always-on signed-in Mac and undocumented local automation (or BlueBubbles, which still needs the Mac). This is suitable for a single-user/self-hosted system, but fragile for a consumer SaaS: macOS permissions, schema changes, Apple ID risk, and personal messages appearing to come from the owner. Messages for Business is a customer-support channel for registered businesses, not the equivalent of “give every user a bot on their personal number.”

Do not ship Mac database/AppleScript automation as an iOS App Store feature and assume approval. The App Store guidelines also require explicit permission and clear disclosure before sharing personal data with third-party AI.

### WhatsApp

Cloud API provides official webhooks and sending, but it is a business channel, not personal-account automation. Webhook delivery is asynchronous/retried, so acknowledge quickly after durable receipt and dedupe by message ID. Free-form messages depend on the service window; outbound/proactive use generally needs approved templates and may be charged.

The major 2026 constraint is product eligibility: Meta states third-party AI Providers may offer general-purpose AI assistants only where legally required. Get a written platform determination for the intended specialized use, markets, and number ownership before investing in WhatsApp as the only front door.

## Background and proactive behavior

Use event subscriptions where available (webhooks, Gmail/Calendar watches), not polling. Temporal timers cover real deadlines and fallback checks. Each monitor has a concrete completion condition, expiry, noise budget, and owner. Proactive suggestions should be staged: detect -> privately research -> score expected value -> suppress duplicates -> ask or act according to authority. Start with weekly digests and explicit watches; do not start with omnipresent autonomous messaging.

OpenAI background mode can handle long model calls and webhooks can signal completion, but provider background execution is not your product workflow engine. It does not replace durable business state, approval signals, tool idempotency, or retries.

## Failure recovery

- Persist inbound event before acknowledgement.
- Use inbox/outbox tables and unique idempotency keys.
- Model calls may repeat; side effects may not.
- Record `started`, provider request ID, result, verification readback, and final state for every mutation.
- On uncertain send/payment state, read the destination before retrying.
- Dead-letter after bounded retries and tell the user what is blocked.
- Periodically replay production traces in a no-side-effect eval environment.
- Chaos-test worker death after each state transition and restore from backups.

## What the existing kit has and lacks

**Reuse:** channel interface; WhatsApp Cloud webhook parsing/signature verification/message-ID dedupe; iMessage read-only database watcher/checkpoint; provider adapter; explicit allowlist; dry-run; response cap; subscription CLI bridges for local experiments.

**Missing before “capable agent”:** persistent conversation/task schema; crash-safe queue/workflow engine; tool-call protocol; OAuth connectors; provenance-aware memory; search/vector retrieval; capability/approval engine; external-content trust labels; background subscriptions/timers; browser cell; vault/payment architecture; attachments/group/voice handling; multi-device ordering; per-user isolation; audit/export/deletion; tracing/evals; admin/incident controls; delivery readback; migrations/backups.

The two original reply-loop hazards are now fixed in the starter kit: WhatsApp commits inbound text events to a SQLite inbox before returning 200 and processes them on a background worker; iMessage checkpoints advance only after successful handling and send. Regression tests cover restart recovery, deduplication, failed-work retry, and checkpoint behavior. This is a safe baseline, not the full inbox/outbox design below: exactly-once outbound delivery still needs idempotency keys or delivery reconciliation because a process can die after an external send succeeds but before local completion is recorded.

## Milestones

1. **Week 1: safe reply loop.** One owner, iMessage on Mac, immutable events, explicit sender allowlist, no tools, dry-run/replay tests.
2. **Weeks 2-3: durable tasks.** Postgres schema, inbox/outbox, worker queue, task states, idempotency, basic web dashboard and audit timeline.
3. **Weeks 4-6: useful read tools.** Calendar/email/files with OAuth, typed schemas, source citations, live-state verification, retrieval with provenance.
4. **Weeks 7-9: controlled effects.** Approval objects, send/calendar mutations, policy engine, readback verification, revocation/expiry, eval suite.
5. **Weeks 10-12: computer and background work.** Per-user browser VM, downloads quarantine, timers/webhooks, lease/deadline handling, recovery drills.
6. **Before external beta:** tenant isolation test, data export/deletion, retention policy, abuse controls, security review/red team, platform review, support/runbooks, cost caps.

If WhatsApp is required, run its platform eligibility work in parallel with milestone 1; do not wait until launch.

## Sources

Primary/official sources accessed September 16, 2026:

- Meta Muse launch: https://about.fb.com/news/2026/09/introducing-muse-personal-ai-agent/
- Meta Muse security design: https://research.meta.ai/blog/security-and-safety-for-ai-agents-our-approach-with-muse
- WhatsApp Cloud API overview: https://developers.facebook.com/docs/whatsapp/cloud-api/overview/
- WhatsApp webhooks: https://developers.facebook.com/docs/whatsapp/cloud-api/guides/set-up-webhooks/
- WhatsApp pricing/windows: https://developers.facebook.com/docs/whatsapp/pricing/
- WhatsApp AI Provider policy/pricing: https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing/ai-providers
- WhatsApp Business Solution Terms: https://www.whatsapp.com/legal/business-solution-terms/
- Third Party Agent Terms: https://www.whatsapp.com/legal/third-party-agents-terms
- Apple Messages developer docs: https://developer.apple.com/documentation/messages
- Apple iMessage apps: https://developer.apple.com/imessage/
- Apple App Review Guidelines: https://developer.apple.com/app-store/review/guidelines/
- BlueBubbles REST/webhooks: https://docs.bluebubbles.app/server/developer-guides/rest-api-and-webhooks
- OpenAI background mode: https://platform.openai.com/docs/guides/background
- OpenAI computer use: https://platform.openai.com/docs/guides/tools-computer-use
- OpenAI remote MCP: https://platform.openai.com/docs/guides/tools-remote-mcp
- OpenAI webhooks: https://platform.openai.com/docs/guides/webhooks
- OpenAI Agents SDK: https://openai.github.io/openai-agents-python/
- Anthropic computer use: https://docs.anthropic.com/en/docs/agents-and-tools/tool-use/computer-use-tool
- Anthropic Agent SDK: https://docs.anthropic.com/en/docs/claude-code/sdk/sdk-overview
- Anthropic MCP connector: https://docs.anthropic.com/en/docs/agents-and-tools/mcp-connector
- MCP authorization security: https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization/security-considerations
- Temporal workflow execution: https://docs.temporal.io/workflow-execution
- Fly per-user environments: https://fly.io/docs/blueprints/per-user-dev-environments/
- Fly one app per customer: https://fly.io/docs/machines/guides-examples/one-app-per-user-why/
- AWS Lambda/SQS delivery handling: https://docs.aws.amazon.com/lambda/latest/dg/with-sqs.html
- AWS Secrets Manager: https://docs.aws.amazon.com/secretsmanager/latest/userguide/intro.html
- OpenAI Codex authentication: https://developers.openai.com/codex/auth
- Cursor ACP: https://cursor.com/docs/cli/acp
- xAI/OpenCode subscription integration: https://x.ai/news/grok-opencode
- Anthropic subscription restriction context: https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan

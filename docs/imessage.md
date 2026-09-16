# iMessage channel

Runs your agent on your own iMessage account. There is **no official
iMessage API** - every approach is a macOS automation technique. This kit
uses the most transparent one: read the Messages database, reply through
Messages.app.

## Requirements

- A **Mac** that stays awake, signed in to Messages with your Apple ID
- Python 3.10+
- **Full Disk Access** for the app that runs the agent (Terminal, iTerm,
  or your launcher): System Settings -> Privacy & Security -> Full Disk
  Access. Without it, `chat.db` is unreadable.
- **Automation permission** for Messages: macOS prompts the first time the
  agent tries to send. Approve it, or nothing goes out.

## Run it

```bash
export CHAT_AGENT_API_KEY=...           # your provider key
chat-agent --channel imessage --respond-to +15551234567
# dry-run first: it logs what it WOULD send, sends nothing
chat-agent --channel imessage --respond-to +15551234567 --send
```

## How it works (and what it never does)

- **Reads** `~/Library/Messages/chat.db` over a read-only, *immutable*
  SQLite connection. It never writes to or locks Messages' database.
- Only sees **direct (1:1) iMessages**: no group chats, no SMS/RCS, none of
  your own outbound messages.
- **Sends** by asking Messages.app to send, via AppleScript - the message
  goes out as you, from your Apple ID.
- **Checkpoints** the highest seen message id so the agent never replays
  your texting history on first run or restart.

## Platform caveats

- Replies come from your personal Apple ID. If the agent misbehaves, your
  friends see it as *you* texting them - hence the allowlist and dry-run
  defaults. Start with only your own second number allowlisted.
- Apple does not document or support this. A macOS update can change
  `chat.db`'s schema (it has before) and break the watcher until the query
  is updated.
- iMessage's own terms apply; automated traffic to people who didn't opt in
  is a fast way to get reported. Keep the allowlist to people who expect it.

## Alternative: BlueBubbles

[BlueBubbles](https://bluebubbles.app) is an open-source macOS server that
exposes iMessage over a REST API and webhooks
(https://docs.bluebubbles.app/server/developer-guides/rest-api-and-webhooks).
If you'd rather poll an API than read SQLite, write a `Channel` subclass
that talks to it - see `src/chat_agent_kit/channels/base.py` for the
two-method interface.

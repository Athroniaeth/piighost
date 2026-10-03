---
icon: lucide/link
---

# De-identify Claude Code with the Anthropic proxy

`piighost-api` serves an Anthropic Messages-compatible proxy under `/anthropic/v1`. Claude Code, or any client of the Messages API, points its base URL at it. The proxy then de-identifies the messages and the tool contents, forwards them to Anthropic, and restores the reply, streamed or not. The model receives `<<PERSON:1>>`{ .placeholder }, never `Patrick`{ .pii }.

!!! note "Prerequisites"
    A running `piighost-api` server, see [Deploy a de-identification API](../getting-started/api-server.md), and an Anthropic API key or a key for a compatible gateway.

## Point Claude Code at the proxy

```bash
export ANTHROPIC_BASE_URL=http://127.0.0.1:8000/anthropic
export ANTHROPIC_API_KEY=sk-ant-...
claude
```

Claude Code then calls `/anthropic/v1/messages` on the proxy. The proxy relays every client header to Anthropic, except the hop-by-hop headers (specific to a single connection), `Host`, `Content-Length`, `Accept-Encoding` and the `X-PIIGhost-*` headers. The API key, the user agent and the beta flags therefore arrive as Claude Code sent them. The server's `API_KEY_` keys do not apply to `/anthropic/v1`, because the proxy asks for no server key of its own.

## Check that the model never sees the value

Serve a configuration that knows your first name, here `Patrick`{ .pii }:

```toml title="patrick.toml"
[detector]
type = "exact"

[detector.values]
Patrick = "PERSON"
```

```bash
piighost-api serve --config patrick.toml
```

Start it in the shell where your `API_KEY_DEV` is exported, since the server refuses to start without a key. Point Claude Code at it as above, then ask "What is the first letter of my name, Patrick?". The model cannot answer, since the request it received reads `<<PERSON:1>>`{ .placeholder }. The reply you read is restored, so it still shows `Patrick`{ .pii } wherever the model wrote the token.

## Choose the upstream

Without a header, the proxy forwards to `https://api.anthropic.com/v1`. If you want a gateway for every client, set `PIIGHOST_ANTHROPIC_UPSTREAM` before starting the server:

```bash
export PIIGHOST_ANTHROPIC_UPSTREAM="https://gateway.internal/v1"
```

If you want it for one request only, name the gateway's base URL in the `X-PIIGhost-Upstream` header. Each request runs in a fresh thread, forgotten once the reply is restored. This suits Claude Code, because it resends the whole history every turn. Pin a thread with `X-PIIGhost-Thread-Id` only if you manage its lifetime yourself.

## Guide the model with a note

A short note explains the placeholders to the model and asks it to reuse `<<PERSON:1>>`{ .placeholder } verbatim, never guessing the spelling of a hidden value. It is off by default. To prepend the built-in note to the first user message, set:

```bash
export PIIGHOST_ANTHROPIC_PLACEHOLDER_NOTE=default
export PIIGHOST_ANTHROPIC_NOTE_PLACEMENT=user
```

`PIIGHOST_ANTHROPIC_PLACEHOLDER_NOTE` also takes your own text instead of `default`. Without `PIIGHOST_ANTHROPIC_NOTE_PLACEMENT=user`, the note is prepended to the system prompt instead.

## De-identify the system prompt too

The system prompt is relayed untouched by default, and only the messages and the tool contents are de-identified. Some accounts, subscription or enterprise ones among them, validate the client from its system prompt and reject a request whose system prompt was modified. The same check rejects a note placed in the system prompt, which is why the note above goes to the first user message.

If your account tolerates a modified system prompt, de-identify it as well:

```bash
export PIIGHOST_ANTHROPIC_ANONYMIZE_SYSTEM=true
```

!!! warning "Limits"
    - By default, the system prompt stays untouched. A value written in it therefore reaches the model in clear.
    - Images, documents and the tool definitions in `tools` are relayed untouched.
    - A streamed request that the upstream refuses is answered with the upstream status and its `retry-after` and `anthropic-ratelimit-*` headers. A failure in the middle of a stream reaches the client as a truncated stream.

The fields the proxy de-identifies and restores are listed in [API endpoints](../reference/api-endpoints.md).

## See also

- [De-identify Claude Code with hooks](claude-code.md): the other route for Claude Code, through its hook system.
- [OpenAI-compatible proxy](openai-proxy.md): the same relay for the OpenAI API.
- [Server CLI](../reference/api-cli.md): every environment variable of the server.

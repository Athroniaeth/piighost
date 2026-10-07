---
icon: lucide/link
seo_title: Anthropic-compatible proxy that masks PII for Claude
description: Point Claude Code or any Messages API client at piighost-api. Messages and tool contents are de-identified before Anthropic, and the reply is restored.
---

# Anthropic-compatible proxy

`piighost-api` serves an Anthropic Messages-compatible proxy under `/anthropic/v1`. Claude Code, or any client of the Messages API, points its base URL at it. The proxy then de-identifies the messages and the tool contents, forwards them to Anthropic, and restores the reply, streamed or not. The model receives `<<PERSON:1>>`{ .placeholder }, never `Patrick`{ .pii }.

!!! note "Prerequisites"
    A running `piighost-api` server, see [API server](../getting-started/api-server.md), and an Anthropic API key or a key for a compatible gateway.

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

## Call the proxy from your backend only

The proxy trusts its caller. It checks no server key, so it serves anyone who reaches `/anthropic/v1`. The caller picks the upstream with `X-PIIGhost-Upstream`, and the server sends the request to whatever URL that header names. The caller also picks the thread with `X-PIIGhost-Thread-Id`, and the reply comes back restored with the values of that thread.

The proxy is therefore meant to be called by your backend, never by your end users or from the Internet. For Claude Code on your own machine, that caller is you, so keep the server on `127.0.0.1`, where `piighost-api serve` listens by default.

- Your backend authenticates its users.
- Your backend maps each account to its thread ids and sets `X-PIIGhost-Thread-Id` itself. A user never sends a thread id, so one user can never name the thread of another.
- The server listens only where your backend reaches it. In Docker, publish the port on a private network only.

The `API_KEY_` keys still protect the other routes of the server, `/v1/deanonymize` and the thread routes among them.

## Guide the model with a note

A short note explains the placeholders to the model and asks it to reuse `<<PERSON:1>>`{ .placeholder } verbatim, never guessing the spelling of a hidden value. It is off by default. To prepend the built-in note to the first user message, set:

```bash
export PIIGHOST_ANTHROPIC_PLACEHOLDER_NOTE=default
export PIIGHOST_ANTHROPIC_NOTE_PLACEMENT=user
```

`PIIGHOST_ANTHROPIC_PLACEHOLDER_NOTE` also takes your own text instead of `default`. Without `PIIGHOST_ANTHROPIC_NOTE_PLACEMENT=user`, the note is prepended to the system prompt instead.

## Keep the system prompt in clear

The system prompt is your own text, so the proxy relays the `system` field untouched by default and de-identifies only the messages and the tool contents. Some accounts, subscription or enterprise ones among them, also validate the client from its system prompt and reject a request whose system prompt was modified. The same check rejects a note placed in the system prompt, which is why the note above goes to the first user message.

If your account tolerates a modified system prompt, de-identify it as well:

```bash
export PIIGHOST_ANTHROPIC_ANONYMIZE_SYSTEM=true
```

## Use a placeholder that can be restored

The proxy restores each placeholder to one value, so each value needs a placeholder of its own. The default factory `label_counter` gives `<<PERSON:1>>`{ .placeholder } and `<<PERSON:2>>`{ .placeholder }, and `label_hash` works too. The `redact` factory gives every value the same `<<REDACT>>`{ .placeholder }. A restored reply would then carry one value, a database URL and its password for example, in place of every `<<REDACT>>`{ .placeholder }, in the text and in the `tool_use` inputs.

The server therefore refuses to start when the `[anonymizer.placeholder]` type of its configuration is `redact`, `label` or `mask`, and its error names the factory. If you only need one-way redaction, `PIIGHOST_ONE_WAY=true` starts it without the proxies, `/v1/deanonymize` and `/v1/threads/{id}/tokens`. [Placeholder factories](../placeholder-factories.md) compares the factories.

!!! warning "Limits"
    - By default, the system prompt stays untouched. A value written in it therefore reaches the model in clear.
    - Images, documents and the tool definitions in `tools` are relayed untouched.
    - A streamed request that the upstream refuses is answered with the upstream status and its `retry-after` and `anthropic-ratelimit-*` headers. A failure in the middle of a stream reaches the client as a truncated stream.

The fields the proxy de-identifies and restores are listed in [API endpoints](../reference/api-endpoints.md).

## See also

- [Claude Code hooks](claude-code.md): the other route for Claude Code, through its hook system.
- [OpenAI-compatible proxy](openai-proxy.md): the same relay for the OpenAI API.
- [Server CLI](../reference/api-cli.md): every environment variable of the server.

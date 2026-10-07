---
icon: lucide/link
seo_title: OpenAI-compatible proxy that masks PII
description: Point an OpenAI client's base_url at piighost-api. Requests are de-identified before OpenAI or a compatible provider sees them, then replies are restored.
---

# OpenAI-compatible proxy

`piighost-api` serves an OpenAI-compatible proxy under `/openai/v1`. Point a client's `base_url` at it, and the proxy de-identifies each request, forwards it to the real provider, and restores the reply. The provider receives `<<PERSON:1>>`{ .placeholder }, never `Jane Doe`{ .pii }.

!!! note "Prerequisites"
    A running `piighost-api` server, see [API server](../getting-started/api-server.md), and a key for the provider. The examples use the OpenAI Python SDK.

## Point the client at the proxy

Change only the `base_url`. The `api_key` stays the provider's key.

```python
--8<-- "snippets/server_proxy.py:client"
```

The provider receives `<<PERSON:1>>`{ .placeholder } and `<<EMAIL:1>>`{ .placeholder }, and the printed reply carries `Jane Doe`{ .pii } again. The server's `API_KEY_` keys do not apply to `/openai/v1`, because the proxy asks for no server key of its own. It relays the `Authorization` header to the provider as is.

The same call with curl:

```bash
curl http://127.0.0.1:8000/openai/v1/chat/completions \
  -H "Authorization: Bearer sk-..." \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-5.6-terra", "messages": [{"role": "user", "content": "I am Jane Doe"}]}'
```

## Choose the provider

Without a header, the proxy forwards to `https://api.openai.com/v1`. If you want another OpenAI-compatible provider for every client, set `PIIGHOST_OPENAI_UPSTREAM` before starting the server:

```bash
export PIIGHOST_OPENAI_UPSTREAM="http://vllm.internal:8000/v1"
```

If you want it for one client only, name the provider's base URL in the `X-PIIGhost-Upstream` header:

```python
--8<-- "snippets/server_proxy_upstream.py:example"
```

The proxy strips every `X-PIIGhost-*` header before forwarding, so the provider never sees it.

## Keep a thread across requests

Each request runs in a fresh thread, forgotten as soon as the reply is restored. A chat client resends the whole history every turn, so the placeholder numbering stays consistent within each request. If you want the thread to outlive the request, for example to restore a stored reply later through `/v1/deanonymize`, pin it with `X-PIIGhost-Thread-Id`:

```python
--8<-- "snippets/server_proxy.py:thread"
```

A pinned thread stays in the server memory until `DELETE /v1/threads/user-42` erases it.

## Call the proxy from your backend only

The proxy trusts its caller. It checks no server key, so it serves anyone who reaches `/openai/v1`. The caller picks the provider with `X-PIIGhost-Upstream`, and the server sends the request to whatever URL that header names. The caller also picks the thread with `X-PIIGhost-Thread-Id`, and the reply comes back restored with the values of that thread.

The proxy is therefore meant to be called by your backend, never by your end users or from the Internet.

- Your backend authenticates its users.
- Your backend maps each account to its thread ids, such as `user-42` for account 42, and sets `X-PIIGhost-Thread-Id` itself. A user never sends a thread id, so one user can never name the thread of another.
- The server listens only where your backend reaches it. `piighost-api serve` listens on `127.0.0.1` by default. In Docker, publish the port on a private network only.

The `API_KEY_` keys still protect the other routes of the server, `/v1/deanonymize` and the thread routes among them.

## Stream the reply

`stream=True` works unchanged. The proxy restores each placeholder as the chunks arrive, even when the provider splits `<<PERSON:1>>`{ .placeholder } across two chunks.

```python
--8<-- "snippets/server_proxy.py:stream"
```

## Keep the system prompt in clear

The `system` and `developer` messages are your own prompt, so the proxy relays them as written and de-identifies the other messages. "You are the support assistant of an online shop" reaches the provider as that sentence, not as "You are the `<<PERSON:1>>`{ .placeholder } of an `<<ORGANIZATION:1>>`{ .placeholder }".

If your system prompt holds values to hide, de-identify it too:

```bash
export PIIGHOST_OPENAI_ANONYMIZE_SYSTEM=true
```

## Use a placeholder that can be restored

The proxy restores each placeholder to one value, so each value needs a placeholder of its own. The default factory `label_counter` gives `<<PERSON:1>>`{ .placeholder } and `<<PERSON:2>>`{ .placeholder }, and `label_hash` works too. The `redact` factory gives every value the same `<<REDACT>>`{ .placeholder }. A restored reply would then carry one value, a database URL and its password for example, in place of every `<<REDACT>>`{ .placeholder }, in the text and in the tool arguments.

The server therefore refuses to start when the `[anonymizer.placeholder]` type of its configuration is `redact`, `label` or `mask`, and its error names the factory. If you only need one-way redaction, `PIIGHOST_ONE_WAY=true` starts it without the proxies, `/v1/deanonymize` and `/v1/threads/{id}/tokens`. [Placeholder factories](../placeholder-factories.md) compares the factories.

!!! warning "Limits"
    - By default, the `system` and `developer` messages stay in clear. A value written in them therefore reaches the provider in clear.
    - A streamed reply restores `delta.content` only. Tool-call arguments streamed in `delta.tool_calls` keep their placeholders, while a reply that is not streamed restores them.
    - A streamed request is answered with a success status before the provider answers, so a provider error reaches the client inside the stream body rather than as a status.
    - Images and audio are relayed untouched, with no de-identification.
    - Only the `Authorization` and `Content-Type` headers reach the provider from an OpenAI client, so a header such as `OpenAI-Organization` is dropped.

The routes the proxy serves, and the fields it de-identifies on each, are listed in [API endpoints](../reference/api-endpoints.md).

## See also

- [Anthropic-compatible proxy](anthropic-proxy.md): the same relay for the Messages API and Claude Code.
- [Server CLI](../reference/api-cli.md): every environment variable of the server.
- [Tool-call strategies](../tool-call-strategies.md): how the library handles tool arguments when it runs inside the agent.

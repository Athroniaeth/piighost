---
icon: lucide/link
---

# De-identify an OpenAI client with the proxy

`piighost-api` serves an OpenAI-compatible proxy under `/openai/v1`. Point a client's `base_url` at it, and the proxy de-identifies each request, forwards it to the real provider, and restores the reply. The provider receives `<<PERSON:1>>`{ .placeholder }, never `Jane Doe`{ .pii }.

!!! note "Prerequisites"
    A running `piighost-api` server, see [Deploy a de-identification API](../getting-started/api-server.md), and a key for the provider. The examples use the OpenAI Python SDK.

## Point the client at the proxy

Change only the `base_url`. The `api_key` stays the provider's key.

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:8000/openai/v1",
    api_key="sk-...",
)
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Write a short greeting to Jane Doe, jane.doe@example.com."}],
)
print(response.choices[0].message.content)
```

The provider receives `<<PERSON:1>>`{ .placeholder } and `<<EMAIL:1>>`{ .placeholder }, and the printed reply carries `Jane Doe`{ .pii } again. The proxy relays the `Authorization` header to the provider as is and asks for no server key of its own, so the server's `API_KEY_` keys do not apply to `/openai/v1`.

The same call with curl:

```bash
curl http://127.0.0.1:8000/openai/v1/chat/completions \
  -H "Authorization: Bearer sk-..." \
  -H "Content-Type: application/json" \
  -d '{"model": "gpt-4o", "messages": [{"role": "user", "content": "I am Jane Doe"}]}'
```

## Choose the provider

Without a header, the proxy forwards to `https://api.openai.com/v1`. If you want another OpenAI-compatible provider for every client, set `PIIGHOST_OPENAI_UPSTREAM` before starting the server:

```bash
export PIIGHOST_OPENAI_UPSTREAM="http://vllm.internal:8000/v1"
```

If you want it for one client only, name the provider's base URL in the `X-PIIGhost-Upstream` header:

```python
client = OpenAI(
    base_url="http://127.0.0.1:8000/openai/v1",
    api_key="sk-...",
    default_headers={"X-PIIGhost-Upstream": "http://vllm.internal:8000/v1"},
)
```

The proxy strips every `X-PIIGhost-*` header before forwarding, so the provider never sees it.

## Keep a thread across requests

Each request runs in a fresh thread, forgotten as soon as the reply is restored. A chat client resends the whole history every turn, so the numbering stays consistent within each request. If you want the thread to outlive the request, for example to restore a stored reply later through `/v1/deanonymize`, pin it with `X-PIIGhost-Thread-Id`:

```python
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "I am Jane Doe"}],
    extra_headers={"X-PIIGhost-Thread-Id": "user-42"},
)
```

A pinned thread stays in the server memory until `DELETE /v1/threads/user-42` erases it.

## Stream the reply

`stream=True` works unchanged. The proxy restores each placeholder as the chunks arrive, even when the provider splits `<<PERSON:1>>`{ .placeholder } across two chunks.

```python
stream = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "I am Jane Doe"}],
    stream=True,
)
for chunk in stream:
    if chunk.choices:
        print(chunk.choices[0].delta.content or "", end="")
```

!!! warning "Limits"
    - A streamed reply restores `delta.content` only. Tool-call arguments streamed in `delta.tool_calls` keep their placeholders, while a reply that is not streamed restores them.
    - A streamed request is answered with a success status before the provider answers, so a provider error reaches the client inside the stream body rather than as a status.
    - Images and audio are relayed untouched, with no de-identification.
    - Only the `Authorization` and `Content-Type` headers reach the provider from an OpenAI client, so a header such as `OpenAI-Organization` is dropped.

The routes the proxy serves, and the fields it de-identifies on each, are listed in [API endpoints](../reference/api-endpoints.md).

## See also

- [Anthropic-compatible proxy](anthropic-proxy.md): the same relay for the Messages API and Claude Code.
- [Server CLI](../reference/api-cli.md): every environment variable of the server.
- [Tool-call strategies](../tool-call-strategies.md): how the library handles tool arguments when it runs inside the agent.

---
icon: lucide/cloud
---

# Remote client

You will use `PIIGhostClient` as a drop-in remote thread pipeline. It implements the same port as a local `ThreadAnonymizationPipeline`, but every call runs against a `piighost-api` server over HTTP. You point it at a base URL, de-identify a message, restore it, then drop the same client into the LangChain middleware where a local pipeline would go. This keeps the NER model off the application host, on a shared server, a GPU node, or a dedicated inference pod.

!!! note "Prerequisites"
    `piighost` installed with the client extra, `pip install piighost[client]`, and a reachable `piighost-api` server. Here we assume one at `http://localhost:8000`.

## 1. Open a client

Pass a base URL as a string and the client builds and owns its `httpx.AsyncClient`, closed when the context manager exits. The default token grammar matches the standard `LabelCounterPlaceholderFactory` a `piighost` server emits, so `<<PERSON:1>>`{ .placeholder } is recognized as a token.

```python
import asyncio

from piighost.integrations.client import PIIGhostClient


async def main() -> None:
    async with PIIGhostClient("http://localhost:8000") as client:
        ...


asyncio.run(main())
```

## 2. De-identify and restore a message

`anonymize` takes the text and a `thread_id`, exactly like the local pipeline. The server owns the token mapping, so the returned `Anonymization` carries the text but an empty `.tokens`. To get the value back, call `deanonymize` with the same `thread_id`, which restores through the server's thread mapping.

```python
    async with PIIGhostClient("http://localhost:8000") as client:
        result = await client.anonymize("Patrick habite à Paris.", "thread-42")
        print(result.text)

        restored = await client.deanonymize(result.text, "thread-42")
        print(restored)
```

The output should be:

```text
<<PERSON:1>> habite à <<LOCATION:1>>.
Patrick habite à Paris.
```

`Patrick`{ .pii } becomes `<<PERSON:1>>`{ .placeholder } on the server, and `deanonymize` sends the tokenized text back for restoration. Nothing about the mapping lives in your process.

## 3. Forget a thread

`forget_thread` erases the thread on the server and returns the count of what was dropped, the same as the local pipeline.

```python
    async with PIIGhostClient("http://localhost:8000") as client:
        forgotten = await client.forget_thread("thread-42")
        print(forgotten)
        # Forgotten(messages=1, detections=2)
```

## 4. Drop it into the middleware

Because `PIIGhostClient` implements the thread pipeline port, it goes wherever a local `ThreadAnonymizationPipeline` goes, including inside `PIIAnonymizationMiddleware`. The middleware drives it with the same `anonymize` and `deanonymize` calls, unaware the work happens on a server.

```python
from langchain.agents import create_agent
from piighost.integrations.client import PIIGhostClient
from piighost.integrations.middleware import PIIAnonymizationMiddleware

client = PIIGhostClient("http://localhost:8000")

agent = create_agent(
    model="openai:gpt-4o",
    tools=[...],
    middleware=[PIIAnonymizationMiddleware(pipeline=client)],
)
```

## How it works

`PIIGhostClient` is a remote stand-in for a `ThreadAnonymizationPipeline`. It exposes the same methods, `anonymize`, `anonymize_corrected`, `deanonymize`, `forget_thread`, and a `recognizer` property, and turns each into an HTTP call to `piighost-api`. The server holds the detector, the conversation memory, and the token mapping, so the client stays small and stateless. `anonymize` returns an empty `.tokens` for that reason. You restore through `deanonymize`, not by reading a local map.

The `recognizer` property lets the middleware find a token grammar even on a remote pipeline, so its invented-placeholder check still works. If your server is configured with a non-standard grammar, pass a matching factory as `recognizer=` when you build the client.

If you manage your own `httpx.AsyncClient`, for shared connection pooling or custom headers, pass it instead of a URL. The client uses it as-is and never closes it, since it belongs to you. Otherwise call `await client.aclose()`, or use the `async with` form which closes it for you.

## What's next

- To run the same pipeline locally instead of over HTTP, see [Conversational pipeline](conversation.md).
- To wire the client into a LangChain agent end to end, see [LangChain middleware](langchain.md).
- To stand up the `piighost-api` server the client talks to, see [Deployment](../deployment.md).

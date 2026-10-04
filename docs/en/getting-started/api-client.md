---
icon: lucide/cloud
---

# Remote client

You will use `PIIGhostClient` as a drop-in remote thread pipeline. It implements the same port as a local `ThreadAnonymizationPipeline`, but every call runs against a `piighost-api` server over HTTP. You point it at a base URL, de-identify a message, restore it, then drop the same client into the LangChain middleware where a local pipeline would go. The NER model then runs off the application host, on a shared server, a GPU node, or a dedicated inference pod.

!!! note "Prerequisites"
    `piighost` installed with the client extra, `pip install "piighost[client]"`, and a reachable `piighost-api` server, see [API server](api-server.md). Here we assume one at `http://127.0.0.1:8000`.

## 1. Open a client

Pass a base URL as a string. The client then builds and owns its `httpx.AsyncClient`, and closes it when the context manager exits. You can bound each request with `timeout`, attach static `headers` such as an Authorization token, and retry a connection error `retries` times, without building your own client. The token grammar, the shape the client recognizes as a token, matches by default the standard `LabelCounterPlaceholderFactory` a `piighost` server emits. `<<PERSON:1>>`{ .placeholder } is therefore recognized as a token.

```python
--8<-- "snippets/server_connect.py"
```

## 2. De-identify and restore a message

`anonymize` takes the text and a `thread_id`, exactly like the local pipeline. The returned `Anonymization` carries the text but an empty `.tokens`, because the server owns the token mapping. To get the value back, call `deanonymize` with the same `thread_id`. The server then restores it from its thread mapping.

```python
--8<-- "snippets/server_client.en.py:example"
```

The output should be:

```text
--8<-- "snippets/server_client.en.out"
```

`Patrick`{ .pii } becomes `<<PERSON:1>>`{ .placeholder } on the server, and `deanonymize` sends the tokenized text to the server, which restores it. Nothing about the mapping lives in your process.

## 3. Forget a thread

`forget_thread` erases the thread on the server and returns the count of what was dropped, the same as the local pipeline.

```python
--8<-- "snippets/server_forget.py:example"
```

The output should be:

```text
--8<-- "snippets/server_forget.out"
```

## 4. Drop it into the middleware

Because `PIIGhostClient` implements the thread pipeline port, it goes wherever a local `ThreadAnonymizationPipeline` goes, including inside `PIIAnonymizationMiddleware`. The middleware drives it with the same `anonymize` and `deanonymize` calls, unaware the work happens on a server.

```python
--8<-- "snippets/server_middleware.py:example"
```

## How it works

`PIIGhostClient` is a remote stand-in for a `ThreadAnonymizationPipeline`. It exposes the same methods, `anonymize`, `anonymize_corrected`, `deanonymize`, `forget_thread`, and a `recognizer` property, and turns each into an HTTP call to `piighost-api`. `anonymize_corrected` de-identifies a message again from a corrected set of detections, for example after a human review. The server holds the detector, the conversation memory, and the token mapping, so the client stays small and stateless. `anonymize` returns an empty `.tokens` for that reason. You restore through `deanonymize`, not by reading a local map.

The `recognizer` property lets the middleware find a token grammar even on a remote pipeline, so its invented-placeholder check still works. If your server is configured with a non-standard grammar, pass a matching factory as `recognizer=` when you build the client.

If you manage your own `httpx.AsyncClient`, for shared connection pooling, pass it instead of a URL. The client uses an injected client as-is and never closes it, since it belongs to you. When the client built its own from a URL, call `await client.aclose()`, or use the `async with` form which closes it for you.

## See also

- To run the same pipeline locally instead of over HTTP, see [Conversational pipeline](conversation.md).
- To wire the client into a LangChain agent end to end, see [LangChain middleware](langchain.md).
- To stand up the `piighost-api` server the client talks to, see [API server](api-server.md), and [API endpoints](../reference/api-endpoints.md) for the routes it calls.

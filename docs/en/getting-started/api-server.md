---
icon: lucide/server
---

# Deploy a de-identification API

You will run `piighost-api`, the companion server of `piighost`, over a configuration published on the [piighost hub](https://hub.piighost.dev), then de-identify and restore a message over HTTP. Any process that speaks HTTP then shares one pipeline, loaded once, with the conversation memory kept on the server.

The configuration `hub:piighost/support-en:286909f6` finds names, addresses and organizations with the GLiNER2 model `fastino/gliner2-multi-v1`, US identifiers and generic values such as emails with regexes, and refuses to return a de-identified text that still holds a clear email address.

!!! note "Prerequisites"
    Python 3.12 or later, and network access to the hub and to Hugging Face for the first start. The examples assume the server on `http://127.0.0.1:8000`.

## 1. Install the server

The `gliner2` extra pulls the model runtime the configuration needs.

=== "uv"

    ```bash
    uv add "piighost-api[gliner2]"
    ```

=== "pip"

    ```bash
    pip install "piighost-api[gliner2]"
    ```

## 2. Create an API key

The server refuses to start without an API key. `keyshield`, installed with the server, generates a key and the pepper that hashes it in memory.

```bash
keyshield generate
keyshield pepper
```

Each command prints a line of this form, with your own values:

```text
Set in your .env : "API_KEY_DEV=ak_v1-..."
Set in your .env : "SECRET_PEPPER=..."
```

Export both in the shell that will start the server:

```bash
export API_KEY_DEV="ak_v1-..."
export SECRET_PEPPER="..."
```

## 3. Start the server

```bash
piighost-api serve --config hub:piighost/support-en:286909f6
```

On the first start the server fetches the configuration from the hub and keeps it in the disk cache, then downloads the GLiNER2 model. The log reports `API keys loaded, auth enabled`, then `Pipeline ready: piighost/support-en:286909f6 (detector: composite)`, and uvicorn listens on `http://127.0.0.1:8000`.

Check it from another shell:

```bash
curl http://127.0.0.1:8000/health
```

The output should be:

```json
{"status":"ok","detector":"composite"}
```

!!! tip "Without a model"
    A regex-only configuration starts without downloading anything but the configuration. `piighost-api serve --config hub:piighost/fr-default:e6990159` serves the French one, phone numbers, IBAN, NIR, SIREN and emails among others.

## 4. De-identify a message

Send a text and a `thread_id` to `/v1/anonymize`, with the key in the `Authorization` header.

```bash
curl -X POST http://127.0.0.1:8000/v1/anonymize \
  -H "Authorization: Bearer $API_KEY_DEV" \
  -H "Content-Type: application/json" \
  -d '{"text": "Hi, I am Jane Doe, write to jane.doe@example.com.", "thread_id": "demo"}'
```

The server answers `201 Created` with a body of this shape:

```json
{
  "anonymized_text": "Hi, I am <<PERSON:1>>, write to <<EMAIL:1>>.",
  "entities": [
    {
      "label": "PERSON",
      "placeholder": "<<PERSON:1>>",
      "detections": [
        {"text": "Jane Doe", "label": "PERSON", "start_pos": 9, "end_pos": 17, "confidence": 0.9999873638153076}
      ]
    },
    {
      "label": "EMAIL",
      "placeholder": "<<EMAIL:1>>",
      "detections": [
        {"text": "jane.doe@example.com", "label": "EMAIL", "start_pos": 28, "end_pos": 48, "confidence": 1.0}
      ]
    }
  ]
}
```

`Jane Doe`{ .pii } becomes `<<PERSON:1>>`{ .placeholder } and `jane.doe@example.com`{ .pii } becomes `<<EMAIL:1>>`{ .placeholder }. The `PERSON` detection and its confidence come from the model, so your values can differ. The email comes from a regex, with a confidence of `1.0`.

## 5. Restore the reply

Send a text carrying the placeholders to `/v1/deanonymize`, under the same `thread_id`. Here it is a reply a model could have written.

```bash
curl -X POST http://127.0.0.1:8000/v1/deanonymize \
  -H "Authorization: Bearer $API_KEY_DEV" \
  -H "Content-Type: application/json" \
  -d '{"text": "Thanks <<PERSON:1>>, I will write to <<EMAIL:1>>.", "thread_id": "demo"}'
```

The output should be:

```json
{"text":"Thanks Jane Doe, I will write to jane.doe@example.com."}
```

The server restores every placeholder the thread `demo` issued, whatever text carries it.

## 6. Call it from Python

`PIIGhostClient` drives the same routes from Python, with the key in its `headers`.

```python
import asyncio
import os

from piighost.integrations.client import PIIGhostClient


async def main() -> None:
    headers = {"Authorization": f"Bearer {os.environ['API_KEY_DEV']}"}
    async with PIIGhostClient("http://127.0.0.1:8000", headers=headers) as client:
        result = await client.anonymize("Hi, I am Jane Doe.", "demo")
        print(result.text)


asyncio.run(main())
```

The output should be:

```text
Hi, I am <<PERSON:1>>.
```

`Jane Doe`{ .pii } keeps `<<PERSON:1>>`{ .placeholder }, the token the thread `demo` gave it in step 4. The client and its integrations are covered in [Remote client](api-client.md).

## How it works

The server loads one thread pipeline at start and runs every route on it. A configuration that declares no `[memory]` section, as the two hub configurations of this page, is served with the in-process memory, so the threads live in the server process and vanish when it stops. To keep them across restarts, or to share them between several instances, declare a Redis memory, as [Deploy a production pipeline](../deployment.md) shows.

## What's next

- To route an OpenAI or Anthropic client through the server, see [OpenAI-compatible proxy](../examples/openai-proxy.md) and [Anthropic-compatible proxy](../examples/anthropic-proxy.md).
- To look up every route and its fields, see [API endpoints](../reference/api-endpoints.md).
- To look up every option and environment variable of the server, see [Server CLI](../reference/api-cli.md).
- To run the server in Docker with a shared memory, see [Deploy a production pipeline](../deployment.md).

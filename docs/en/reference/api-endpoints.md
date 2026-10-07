---
icon: lucide/server
---

# API endpoints reference

Package: `piighost-api`

`piighost-api serve` builds one thread pipeline from its configuration. Every route below goes through that pipeline. Request and response bodies are JSON. The OpenAPI schema is served at `/schema/openapi.json`, with a Swagger UI at `/schema/swagger`. `PIIGhostClient` calls the pipeline routes, see [Remote client](../getting-started/api-client.md).

---

## Authentication

The server loads its keys at start from every environment variable whose name starts with `API_KEY_`. A protected route then requires the header `Authorization: Bearer <key>`.

<div class="wide-table" markdown="1">

| Routes | Key required |
|---|---|
| `GET /`, `GET /health`, `GET /v1/labels` | never |
| `/v1/detect`, `/v1/anonymize`, `/v1/anonymize/corrected`, `/v1/deanonymize`, `/v1/threads/...`, `/schema/...` | when keys are loaded |
| `/openai/v1/...`, `/anthropic/v1/...` | never, the caller's credentials are relayed to the upstream |

</div>

A missing or malformed header answers `401` with `Missing or malformed Authorization header`. An unknown key answers `401` with `Invalid API key`. When no key loads, the server refuses to start, unless `PIIGHOST_ALLOW_ANONYMOUS` is set. In that case, no route asks for a key. The variables are listed in [Server CLI](api-cli.md).

---

## Status codes

| Status | When |
|---|---|
| `200` | a `GET` or `DELETE` route succeeds |
| `201` | a `POST` pipeline route succeeds |
| `400` | the body fails validation, a proxy body is not a JSON object, or a proxy request names no upstream and none is configured |
| `401` | a protected route gets no valid key |
| `404` | the route does not exist, under the proxy prefixes too |
| `413` | the body exceeds `PIIGHOST_MAX_BODY_BYTES` |
| `429` | the client exceeds `PIIGHOST_RATE_LIMIT`, with `RateLimit-*` headers |
| `500` | the pipeline raises, a guard flagging a value left in clear or an unknown `role` among others |
| `502` | a proxy route cannot reach its upstream |

A proxy route otherwise answers with the upstream's status.

---

## Shared objects

### `Entity`

| Field | Type | Description |
|---|---|---|
| `label` | string | The entity label, such as `PERSON` |
| `placeholder` | string | The token that replaces the entity, empty on `/v1/detect` |
| `detections` | list of `Detection` | Every occurrence of the entity in the text |

### `Detection`

| Field | Type | Description |
|---|---|---|
| `text` | string | The value as it appears in the text |
| `label` | string | The detection label |
| `start_pos` | integer | Start offset in the text |
| `end_pos` | integer | End offset in the text, exclusive |
| `confidence` | float | Detector score, `1.0` for a regex or an exact match |

---

## Service routes

### `GET /`

```json
{"name": "piighost-api", "version": "...", "docs": "/schema/swagger"}
```

`version` is the installed `piighost-api` version.

### `GET /health`

```json
{"status": "ok", "detector": "composite"}
```

`detector` is the `type` of the configuration's `[detector]` section. `GET /` and `GET /health` are exempt from `PIIGHOST_RATE_LIMIT`.

### `GET /v1/labels`

```json
{"name": "piighost/fr-default:e6990159", "detector": "regex", "labels": ["CREDIT_CARD", "EMAIL", "EU_VAT", "FR_IBAN", "FR_NIR", "FR_PHONE", "FR_SIREN", "FR_SIRET", "IBAN", "IPV4", "SWIFT_BIC", "URL"]}
```

| Field | Type | Description |
|---|---|---|
| `name` | string or null | The configuration's `name` |
| `detector` | string | The `type` of `[detector]` |
| `labels` | list of strings | Every label `[detector]` can emit, sorted |

The labels are collected from the `[detector]` section alone, the guard's detector excluded.

| Detector `type` | Labels |
|---|---|
| `regex` | the keys of `patterns`, plus those of every catalog group in `catalogs`, read from the catalog through its disk cache |
| `gliner2`, `spacy`, `transformers`, `llm` | `labels`, or its keys when it maps model labels to canonical ones |
| `exact` | the labels of `values` |
| `composite` | the union of its `detectors` |
| `chunked` | those of its `detector` |
| any other | none |

---

## Pipeline routes

### `POST /v1/detect`

Runs the detector and the linker on a text and returns the entities, without placeholders. The thread memory is neither read nor written, and the override, overlap, expansion and guard stages do not run.

| Request field | Type | Default |
|---|---|---|
| `text` | string | required |
| `thread_id` | string | `"default"`, accepted and unused |

For the text `Write to jane.doe@example.com`, the response reads:

```json
{"entities": [{"label": "EMAIL", "placeholder": "", "detections": [{"text": "jane.doe@example.com", "label": "EMAIL", "start_pos": 9, "end_pos": 29, "confidence": 1.0}]}]}
```

### `POST /v1/anonymize`

De-identifies a message in a thread, with tokens consistent across the thread.

| Request field | Type | Default |
|---|---|---|
| `text` | string | required |
| `thread_id` | string | required |
| `role` | `"user"` or `"assistant"` | `"user"` |

| Response field | Type | Description |
|---|---|---|
| `anonymized_text` | string | The text with each value replaced by its placeholder |
| `entities` | list of `Entity` | The entities of this message that received a token |

`role` tells who wrote the message, and therefore who introduced the values it brings in. A value first written by the assistant gets no token and stays in clear.

### `POST /v1/anonymize/corrected`

De-identifies a message again from a corrected detection set, for a human review step. The corrected set goes through the configured override, then replaces the message's detections in the thread memory. Detection does not run again.

| Request field | Type | Default |
|---|---|---|
| `text` | string | required |
| `detections` | list of objects with `text`, `label`, `start`, `end`, `confidence` | required |
| `thread_id` | string | required |

A corrected detection names its offsets `start` and `end`, not `start_pos` and `end_pos`. The response is `{"anonymized_text": "..."}`.

### `POST /v1/deanonymize`

Restores every placeholder the thread issued, in any text, a model reply included. A token the thread never issued stays as it stands.

| Request field | Type | Default |
|---|---|---|
| `text` | string | required |
| `thread_id` | string | required |

The response is `{"text": "..."}`.

### `GET /v1/threads/{thread_id}/tokens`

Returns the thread's placeholder-to-value map, for a client that restores a stream itself.

```json
{"tokens": {"<<PERSON:1>>": "Jane Doe", "<<EMAIL:1>>": "jane.doe@example.com"}}
```

### `DELETE /v1/threads/{thread_id}`

Erases the thread from the memory and reports what was dropped. A thread that does not exist reports zero.

```json
{"messages": 1, "detections": 2}
```

---

## OpenAI-compatible proxy

Prefix: `/openai/v1`

| Request header | Effect |
|---|---|
| `X-PIIGhost-Upstream` | Base URL of the upstream, `PIIGHOST_OPENAI_UPSTREAM` when absent |
| `X-PIIGhost-Thread-Id` | Fixed thread kept after the request. When absent, each request gets a fresh thread, forgotten once the reply is restored |

Only `Authorization`, `Content-Type`, `x-api-key`, `anthropic-version` and `anthropic-beta` are relayed to the upstream.

<div class="wide-table" markdown="1">

| Route | De-identified in the request | Restored in the reply |
|---|---|---|
| `POST /chat/completions` | `messages[].content`, a string or the `text` of each part, and every string inside `messages[].tool_calls[].function.arguments` | `choices[].message.content` and `choices[].message.tool_calls[].function.arguments`, or `choices[].delta.content` when streamed |
| `POST /completions` | `prompt`, `suffix` | `choices[].text` |
| `POST /embeddings` | `input` | nothing |
| `POST /moderations` | `input` | nothing |
| `GET /models`, `GET /models/{model}` | relayed as is | relayed as is |
| `POST /images/generations`, `/images/edits`, `/images/variations` | relayed as is | relayed as is |
| `POST /audio/speech`, `/audio/transcriptions`, `/audio/translations` | relayed as is | relayed as is |

</div>

- A successful JSON reply is restored. Any other reply is relayed as is, with the upstream status. The upstream's response headers are not relayed.
- Query parameters reach the upstream on the routes relayed as is only.
- The `system` and `developer` messages are relayed in clear, unless `PIIGHOST_OPENAI_ANONYMIZE_SYSTEM` is set.
- A streamed `chat/completions` request is answered `201` before the upstream answers, so an upstream error arrives inside the stream body.
- The upstream timeout is 60 seconds.

---

## Anthropic-compatible proxy

Prefix: `/anthropic/v1`

| Request header | Effect |
|---|---|
| `X-PIIGhost-Upstream` | Base URL of the upstream, `PIIGHOST_ANTHROPIC_UPSTREAM` when absent |
| `X-PIIGhost-Thread-Id` | Fixed thread kept after the request. When absent, each request gets a fresh thread, forgotten once the reply is restored |

Every request header is relayed except the hop-by-hop ones (`Connection`, `Keep-Alive`, `Proxy-Authenticate`, `Proxy-Authorization`, `TE`, `Trailer`, `Transfer-Encoding`, `Upgrade`), `Host`, `Content-Length`, `Accept-Encoding` and any `X-PIIGhost-*` header. Query parameters are relayed.

<div class="wide-table" markdown="1">

| Route | De-identified in the request | Restored in the reply |
|---|---|---|
| `POST /messages` | `messages[].content`, a string or its `text`, `tool_use` and `tool_result` blocks, plus `system` when `PIIGHOST_ANTHROPIC_ANONYMIZE_SYSTEM` is on | the `text`, `tool_use` and `tool_result` blocks of `content`, or the `text_delta` and `input_json_delta` of each `content_block_delta` event when streamed |
| `POST /messages/count_tokens` | same as `/messages` | nothing, the count is relayed |

</div>

- Every string inside a `tool_use` input is rewritten. The other blocks, an image or a document among them, are relayed untouched, and so are the `tools` definitions.
- The guidance note set by `PIIGHOST_ANTHROPIC_PLACEHOLDER_NOTE` is prepended after de-identification. Depending on `PIIGHOST_ANTHROPIC_NOTE_PLACEMENT`, it goes at the head of the system prompt or of the first user message.
- The reply keeps the upstream status. It also keeps the upstream's response headers, `retry-after` and `anthropic-ratelimit-*` included, except the length, encoding, connection and content-type ones.
- A streamed request the upstream refuses is answered with the upstream status as a plain response. An accepted one streams with `200`.
- The upstream timeout is 60 seconds.

---

## See also

- [Server CLI](api-cli.md): the `serve` options and every environment variable.
- [Deploy a de-identification API](../getting-started/api-server.md): a first server, step by step.
- [OpenAI-compatible proxy](../examples/openai-proxy.md) and [Anthropic-compatible proxy](../examples/anthropic-proxy.md): the proxies in use.

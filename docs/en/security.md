---
icon: lucide/shield-check
seo_title: Threat model of PII de-identification for LLMs
description: What piighost protects against and what it does not. The mapping from placeholders to real values holds personal data in clear, so it must be protected.
---

# Security

This page complements [`SECURITY.md`](https://github.com/Athroniaeth/piighost/blob/master/.github/SECURITY.md) in the repository with a threat model. It describes what `piighost` protects against, what it does not, and why.

!!! note "Reversible de-identification"
    `piighost` de-identifies by default. It replaces each detected value with a placeholder and **keeps the link** between the placeholder and the original value, so it can restore the real value later. That link is a mapping of cleartext confidential data, that is personal data (PII) and secrets such as API keys. Protecting it is the core of this threat model.

## The trajectory of a value

Take a message that contains `jean@mail.com`{ .pii }. `piighost` detects the value, replaces it with `<<EMAIL:1>>`{ .placeholder }, and sends the de-identified text to the LLM. The LLM only ever sees `<<EMAIL:1>>`{ .placeholder }. When the response comes back, `piighost` reinjects `jean@mail.com`{ .pii } in place of the placeholder, and the user sees the real value.

Two things therefore coexist at all times. The first is the de-identified text, which can travel to the LLM safely. The second is the mapping `<<EMAIL:1>>`{ .placeholder } to `jean@mail.com`{ .pii }, which must never leave your perimeter. The threat model lives in that separation.

## What `piighost` protects against

!!! success "Exfiltration toward third-party LLMs"
    The LLM only ever sees placeholders (`<<PERSON:1>>`{ .placeholder }, etc.), never the real values. Even if the provider logs the request, no sensitive data leaks to it.

!!! success "Tool-call leakage"
    The middleware restores tool arguments just before execution, then de-identifies the results before they go back to the LLM. The real values never flow through the LLM's visible context.

!!! success "Cross-message drift"
    The linker (`ExactEntityLinker`) links variants of a value, and the conversation memory keeps each message's detections, so the same entity keeps the same placeholder across the whole conversation. `Patrick`{ .pii } and `patrick`{ .pii } group by `(value_key(text), label)`, whatever their spaces and case. The LLM never sees the same value under two different masks.

!!! success "Theft of a stolen persistent store"
    A persistent backend (Redis or SQL) can encrypt every stored value and hash the key. A store leak then reveals neither the message nor the confidential data. See below.

## What `piighost` does not protect against

!!! danger "Process memory compromise"
    The mapping from `placeholder` to original value lives in RAM for the duration of processing. An attacker who reads process memory recovers the cleartext confidential data, whatever the backend.

!!! danger "Unencrypted persistent store"
    The in-RAM memory (`InMemoryConversationMemory`) encrypts nothing. It serves development and single-process use. A persistent backend built without crypto stores its values in clear. A disk theft therefore exposes the confidential data. Configure a hasher and a cipher on the Redis or SQL backend to encrypt at rest.

!!! danger "LLM-invented placeholders"
    If the LLM fabricates a placeholder that was never emitted, `piighost` cannot map it back to a value since it is in no mapping. The middleware refuses such tokens by default (`InventedPlaceholderError`). See [Limitations](limitations.md).

!!! danger "Re-identification from context"
    A placeholder preserves the structure around it. A de-identified value can stay identifiable through what surrounds it. "The patient `<<PERSON:1>>`{ .placeholder }, the only cardiologist in the village of 300 people" names a person without naming their PII. The detector sees only tokens, not that inference.

!!! danger "Fallible detectors"
    Detection is not exhaustive. Confidential data it does not recognize passes in cleartext to the LLM. See [Limitations](limitations.md) for the guard rail.

!!! danger "Assistant-introduced values under PRESERVE"
    With the default `EntityCreateByAssistantStrategy.PRESERVE`, a value the model itself introduced stays in clear for the whole thread, since the model already knows it. It stays clear even when a later user message repeats it, because the thread dates the value to its first occurrence. Use `ANONYMIZE` to tokenize values the assistant introduces too.

!!! danger "Upstream application logs"
    `piighost` never logs raw confidential data, but your application might. Audit your own logging, tracing, and error reporting before claiming compliance.

## The LangGraph state after the model turn

The middleware restores confidential data for display. After `aafter_model`, each message's content holds the real values again. The user sees `jean@mail.com`{ .pii } and not `<<EMAIL:1>>`{ .placeholder }. That restored content lives in the LangGraph state. A checkpointer that persists the state therefore persists cleartext confidential data in the message content. This is intended, because the state is your display surface. But the checkpointer store then holds sensitive data, and must be protected like the mapping itself.

Tool calls are treated differently. An `AIMessage`'s `tool_calls` stay tokenized in the state. The middleware restores a tool argument only for the tool run, on a fresh request. It never writes the restored value back into the state. The checkpointer therefore never persists a cleartext value inside a tool call. A tool result kept as a `ToolMessage` also stays tokenized in the state. A UI that renders tool outputs from the state therefore sees tokens, not confidential data.

## Token injection in user input

A token restores to a value because it looks like one the pipeline issued.
Without protection, a user who types `<<PERSON:2>>`{ .placeholder } into the input
could have it restored to the second entity's value, and read a value that is not
theirs. The anonymizer neutralizes any token the user typed before it renders the
text. It splices an invisible character into the delimiter, so the run no longer
matches the token grammar. Only the literal runs between detected entities are
neutralized, never the tokens the pipeline splices in. A real token therefore
still restores, and an injected one does not. The behaviour is on by default and can be
turned off with `escape_existing_tokens=False` on the `Anonymizer`.

## The mapping is cleartext confidential data

Reversibility has a price. To restore `jean@mail.com`{ .pii } from `<<EMAIL:1>>`{ .placeholder }, `piighost` keeps the link between the two. That link comes from the conversation memory, which contains cleartext confidential data. It is the system's most sensitive asset, and it must be protected as such.

Three backends exist, with three security profiles.

`InMemoryConversationMemory` keeps the mapping in a process-local dictionary. Nothing is encrypted, nothing survives a restart, nothing is shared across processes. It is the right choice for development, tests, and a single-process deployment. It is not secure storage.

`RedisConversationMemory` persists each message in Redis, a networked store shared across workers. `SqlAlchemyConversationMemory` persists each message in a SQL table. This durable store suits long-lived conversations that outlive a process. It runs over sqlite for development and over PostgreSQL for production. Both persistent backends offer two combined protections.

- The **key is hashed**. The hasher derives a digest of the message with a secret pepper. The default is `Sha256Hasher` (HMAC-SHA256, fast, fit for the hot path). `Argon2Hasher` (Argon2id, slow and memory-hard) is the alternative when the pepper itself might leak. Both are deterministic, so the same message lands on the same key.
- The **value is encrypted**. The cipher encrypts the JSON of the detections before writing. `AesGcmCipher` (AES-GCM) is the provided authenticated encryption. A random nonce is drawn per message, and decryption fails on an altered ciphertext.

The pepper and the encryption key **never live in the config file**. They are read from the environment, `PIIGHOST_HASH_PEPPER` for the hasher and `PIIGHOST_CIPHER_KEY` (base64) for the cipher. Security rests on that secret living outside the store. A theft of the store disk alone reveals neither the message nor the confidential data, because the key is hashed and the value encrypted under a secret the disk does not hold.

!!! warning "The secret lives in the environment, not the config"
    A pepper or key written into a versioned config file cancels the protection. Keep them in the process environment or a secrets manager, and rotate them like any production secret.

### At-rest crypto is opt-in on every persistent backend

The hasher and the cipher are optional on both `RedisConversationMemory` and `SqlAlchemyConversationMemory`. Pass both to store securely, or neither to store in clear. Passing exactly one raises `ValueError`, since a hashed key with a cleartext value, or the reverse, protects nothing coherently.

A networked backend built without crypto emits a `PIIGhostSecurityWarning` at construction, pointing to this page. That warning fires for Redis, always networked, and for the SQL backend on a non-sqlite dialect such as PostgreSQL. It does not fire for the in-RAM memory, which is ephemeral, nor for the SQL backend on sqlite, which is local development. The warning nudges toward configuring crypto. The backend does not fail, so a knowing plaintext setup still runs.

The SQL backend takes an injected async engine. The caller owns the lifecycle of that engine. Call `await memory.create_schema()` once at startup to create the table. Through the config, `SqlAlchemyMemoryConfig` (type `"sqlalchemy"`) reads the database URL from an environment variable, `PIIGHOST_DATABASE_URL` by default, so the URL and its password stay out of the config file.

### Confidentiality / restoration gradient by backend

<table class="security-table" markdown="1">
<thead>
<tr><th>Backend</th><th>Mapping encrypted at rest?</th><th>Store key readable?</th><th>Survives a restart?</th><th>Shared multi-worker?</th></tr>
</thead>
<tbody>
<tr><td>InMemory (default)</td><td class="c-red">no (cleartext RAM)</td><td class="c-red">yes (process dict)</td><td class="c-red">no</td><td class="c-red">no</td></tr>
<tr><td>SQL (sqlite, no crypto)</td><td class="c-red">no (cleartext column)</td><td class="c-red">yes (plain SHA-256)</td><td class="c-blue">yes</td><td class="c-yellow">local file</td></tr>
<tr><td>SQL (PostgreSQL) + Sha256Hasher + AesGcm</td><td class="c-blue">yes (AES-GCM)</td><td class="c-green">no (HMAC-SHA256)</td><td class="c-blue">yes</td><td class="c-blue">yes</td></tr>
<tr><td>Redis + Sha256Hasher + AesGcm</td><td class="c-blue">yes (AES-GCM)</td><td class="c-green">no (HMAC-SHA256)</td><td class="c-blue">yes</td><td class="c-blue">yes</td></tr>
<tr><td>Redis + Argon2Hasher + AesGcm</td><td class="c-blue">yes (AES-GCM)</td><td class="c-blue">no (Argon2id, memory-hard)</td><td class="c-blue">yes</td><td class="c-blue">yes</td></tr>
</tbody>
</table>

<small>
Legend:
<span class="sec-legend c-blue">best</span>
<span class="sec-legend c-green">acceptable</span>
<span class="sec-legend c-yellow">partial</span>
<span class="sec-legend c-red">problematic</span>
</small>

The red row for in-RAM memory is not a flaw, it is a scope choice. That backend does not claim to be secure storage. Built without crypto, the sqlite backend shows the same red on confidentiality. It is fit for local development only. As soon as the mapping must survive a restart or be shared across workers, switch to an encrypted persistent backend, Redis or PostgreSQL with a hasher and a cipher.

## Logging detections

The `Detection` dataclass holds the raw surface form of the detected value in its `text` field. The dataclass-generated `__repr__` renders that value verbatim. This keeps the API predictable for inspection, debugging, and tests.

```python
>>> from piighost.models import Detection, Span
>>> d = Detection(span=Span(0, 7), text="Patrick", label="PERSON", confidence=0.9)
>>> repr(d)
"Detection(span=Span(start=0, end=7), text='Patrick', label='PERSON', confidence=0.9)"
```

The library deliberately does not auto-mask the field. If you forward `Detection` or `Entity` instances to logs, traces, or error reporters, scrub them yourself. Two simple recipes.

- Filter `to_dict()` before serialization (drop the `text` key).
- Wrap your structured logger with a redactor that recognises `Detection` and replaces `text` with a length marker.

`piighost` itself never writes confidential data to any logger. The discipline above is needed in your own code.

## Observation payload redaction

The pipeline traces its stages through OpenTelemetry. Each stage emits a span with its own input and output payload, pushed to the trace backend you wired in. By default, those payloads carry the cleartext text and the detection values. Traces are then usable as annotation datasets, but dangerous on a backend that is not allowed to see confidential data.

The pipeline's `observation_redactor` parameter controls that behaviour. It takes a placeholder factory that replaces every detected value before the payload leaves for the backend. With `RedactPlaceholderFactory()`, every entity collapses to `<<REDACT>>`{ .placeholder }.

```text
user text             : "Patrick lives in Paris."
observation payload   : "<<REDACT>> lives in <<REDACT>>."
```

Concretely:

- text payloads have each detection span replaced by the factory's token. The union of the spans is merged before replacement, so no cleartext fragment of one detection survives the replacement of another,
- serialized `Detection` and `Entity` records carry the factory's token instead of their `text` field. Label, position, and occurrence count stay visible for debugging,
- already-de-identified payloads pass through unchanged because they contain placeholders only.

To surface more structure (for example a distinct counter per value during local development), pass a different factory.

```python
--8<-- "snippets/security_redactor.py:example"
```

Any `AnyPlaceholderFactory` implementation is accepted. The observation redactor is independent from the factory used for actual de-identification. So you can display `<<PERSON:1>>`{ .placeholder } on the trace side while sending a different placeholder scheme to the LLM. Leaving `observation_redactor` at `None` traces cleartext. Reserve that setting for a trusted backend. That default is treated as an explicit choice. With a tracer provider actually configured and no redactor, the pipeline warns once that its traces carry cleartext confidential data. `trace_clear_text=True` acknowledges that choice and silences the warning.

## Design decisions that back the threat model

- **De-identification happens locally**: confidential data is replaced before the HTTP request reaches the LLM provider.
- **The mapping is treated as sensitive**: the mapping store holds cleartext confidential data. A persistent backend (Redis or SQL) can encrypt it at rest (AES-GCM) and hash its keys (HMAC-SHA256 or Argon2id). The secret lives outside the store. Crypto is opt-in and all-or-nothing. A networked backend built without it emits a warning.
- **No logging of raw confidential data by the library**: `piighost` itself never writes confidential data to any logger. Your own code must follow the same discipline.
- **Frozen dataclasses**: `Entity`, `Detection`, `Span` are immutable, preventing accidental mutation after de-identification has been applied.
- **Optional guard rail**: a guard rail (`DetectorGuardRail`, `Gliner2GuardRail`, `LLMGuardRail`, `ModerationGuardRail`) re-checks the de-identified output and flags residual confidential data. The pipeline then raises `PIIRemainingError`. See [Limitations](limitations.md).

## Reporting a vulnerability

See [`SECURITY.md`](https://github.com/Athroniaeth/piighost/blob/master/.github/SECURITY.md) for the private vulnerability reporting channel and the supported-version matrix.

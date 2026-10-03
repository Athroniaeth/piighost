---
icon: lucide/database
---

# Pipeline reference

A pipeline chains the stages that turn a text into a de-identified text and back. `AnonymizationPipeline` runs over a single text with no memory between calls. `ThreadAnonymizationPipeline` runs over a conversation, keeping one token per value across every message of a thread.

Both return an [`Anonymization`](anonymizer.md#anonymization), the de-identified text paired with the token each entity was replaced with.

!!! note "De-identification, not anonymisation"
    The default pipelines keep the mapping between a value and its token so the value can be restored. That is reversible pseudonymisation. Reserve the word anonymisation for irreversible removal.

---

## `AnonymizationPipeline`

Module: `piighost.pipeline`

De-identify a single text through the stages, in order: detect the confidential data, apply the server override, resolve overlapping spans, expand missed occurrences, link detections into entities, resolve entity conflicts, replace with tokens, and re-check with a guard. Each `anonymize()` call is independent.

### Constructor

```python
AnonymizationPipeline(
    detector: AnyDetector,
    linker: AnyEntityLinker | None = None,
    anonymizer: AnyAnonymizer[PreservationT] | None = None,
    overlap_resolver: AnyOverlapResolver | None = None,
    expander: AnyDetectionExpander | None = None,
    entity_resolver: AnyEntityResolver | None = None,
    guard: AnyGuardRail | None = None,
    observation_redactor: AnyPlaceholderFactory | None = None,
    override: AnyDetectionOverride | None = None,
    trace_clear_text: bool = False,
)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `detector` | `AnyDetector` | required | Async entity detector |
| `linker` | `AnyEntityLinker \| None` | `None` | Groups detections into entities. Defaults to `ExactEntityLinker()` |
| `anonymizer` | `AnyAnonymizer[PreservationT] \| None` | `None` | Replacement engine and its placeholder factory. Defaults to `Anonymizer(LabelCounterPlaceholderFactory())` |
| `overlap_resolver` | `AnyOverlapResolver \| None` | `None` | Resolves overlapping detections. Defaults to `ConfidenceOverlapResolver()`, since the render stage needs disjoint spans |
| `expander` | `AnyDetectionExpander \| None` | `None` | Adds missed occurrences of a detected value. Disabled when `None` |
| `entity_resolver` | `AnyEntityResolver \| None` | `None` | Reconciles conflicting entities. Disabled when `None` |
| `guard` | `AnyGuardRail \| None` | `None` | Re-checks the output for residual confidential values. Disabled when `None` |
| `observation_redactor` | `AnyPlaceholderFactory \| None` | `None` | Placeholder factory replacing clear values in observation payloads. `None` traces the clear text, so traces double as annotation datasets. With a live tracer and no redactor, the constructor emits a `PIIGhostSecurityWarning` unless `trace_clear_text=True` acknowledges it |
| `override` | `AnyDetectionOverride \| None` | `None` | Server whitelist and blacklist imposed on every detection set. Disabled when `None` |
| `trace_clear_text` | `bool` | `False` | Acknowledge clear-text observation tracing to suppress the security warning when no `observation_redactor` is set |

!!! note "Components are protocols"
    `AnyDetector`, `AnyEntityLinker`, `AnyAnonymizer`, `AnyOverlapResolver`, `AnyDetectionExpander`, `AnyEntityResolver`, `AnyGuardRail`, `AnyDetectionOverride`. Any implementation of the protocol is accepted. See [Extending PIIGhost](../extending.md).

### Methods

#### `anonymize(text) -> Anonymization` *(async)*

Runs the full pipeline and returns the de-identified text with the token used for each entity.

**Raises** `PIIRemainingError` when a configured guard flags confidential values left in the output.

```python
--8<-- "snippets/reference_pipeline.py:anonymize"
```

#### `deanonymize(text, tokens) -> str`

Returns the text with every known token replaced by its entity's value. `tokens` is the mapping from an `Anonymization`, read in reverse. Tokens absent from the mapping are left untouched.

Restoration is unambiguous only when the tokens preserve identity, since two entities sharing one token collapse to a single value.

```python
--8<-- "snippets/reference_pipeline.py:deanonymize"
```

---

## `ThreadAnonymizationPipeline`

Module: `piighost.pipeline`

De-identify each message of a conversation with tokens stable across the thread. A value seen in an early message and again later reads as the same token, because tokens are assigned over the union of every message's detections, not one message alone. Each message's detections are cached in the memory, so resending a message skips detection.

This pipeline adds one component, the conversation memory `memory`. It stores each message's detections, per thread.

### Constructor

```python
ThreadAnonymizationPipeline(
    detector: AnyDetector,
    linker: AnyEntityLinker | None = None,
    anonymizer: AnyAnonymizer[PreservationT] | None = None,
    memory: AnyConversationMemory | None = None,
    overlap_resolver: AnyOverlapResolver | None = None,
    expander: AnyDetectionExpander | None = None,
    entity_resolver: AnyEntityResolver | None = None,
    guard: AnyGuardRail | None = None,
    observation_redactor: AnyPlaceholderFactory | None = None,
    override: AnyDetectionOverride | None = None,
    trace_clear_text: bool = False,
    token_memo_ttl: float | None = None,
    time_source: Callable[[], float] = time.monotonic,
)
```

In addition to every parameter of `AnonymizationPipeline`:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `memory` | `AnyConversationMemory \| None` | `None` | Per-thread store of each message's detections. Defaults to `InMemoryConversationMemory()` for a single process. Pass `RedisConversationMemory` for a shared backend |
| `token_memo_ttl` | `float \| None` | `None` | Seconds a memoized thread-token map is kept. The memo holds the thread's values in clear. `forget_thread` only reaches the process it runs in. So on a multi-worker deployment, this delay bounds how long the other workers keep the memo. `None` keeps an entry until the size bound evicts it |
| `time_source` | `Callable[[], float]` | `time.monotonic` | The clock `token_memo_ttl` reads, injectable for tests |

### Methods

#### `anonymize(text, thread_id, role=MessageRole.USER) -> Anonymization` *(async)*

Detects the message's entities, records them in `thread_id`'s memory, then de-identifies using tokens assigned over the whole thread. The token of a value stays the same from one message to the next.

The `thread_id` is required. There is no shared default, so two callers cannot fall into one thread and leak each other's confidential data. `role` marks who authored the values the message introduces. A value first introduced by the assistant is left in clear, since it is not the user's confidential data.

**Raises** `PIIRemainingError` when a configured guard flags confidential values left in the output.

```python
--8<-- "snippets/reference_thread_pipeline.py:anonymize"
```

#### `anonymize_corrected(text, thread_id, detections) -> Anonymization` *(async)*

Re-de-identifies a user message with a human-corrected detection set. The corrected set replaces this message's detections in memory, then the message is de-identified with tokens consistent across the thread. Detection does not run again. This method applies only to a user's own messages, so the correction is recorded as a user message.

The corrected set is stored as given, without overlap resolution or occurrence expansion, since the human is authoritative over that set. A configured `override` still applies, so the server's lists trump the correction.

```python
--8<-- "snippets/reference_thread_pipeline.py:anonymize_corrected"
```

#### `deanonymize(text, thread_id) -> str` *(async)*

Returns the text with every token from the thread replaced by its value. The thread's tokens are rebuilt from its memory. So any text carrying them is restored, including a model reply the pipeline never de-identified.

```python
--8<-- "snippets/reference_thread_pipeline.py:deanonymize"
```

#### `thread_token_map(thread_id) -> dict[str, str]` *(async)*

Returns the thread's placeholder-to-value map, derived from the cache. With it, a caller can resolve a whole stream at once instead of restoring token by token. A token the thread never issued is absent from the map.

#### `forget_thread(thread_id) -> Forgotten` *(async)*

Erases a thread's memory and returns a `Forgotten` reporting how much was dropped. Forgetting an unknown thread drops nothing and reports zero.

```python
--8<-- "snippets/reference_thread_pipeline.py:forget_thread"
```

Forgetting a thread also erases its memoized token map. That memo holds the thread's values in clear. So erasing the store alone would keep those values live in the process. The other threads keep their memo. The call only reaches the process it runs in. So on a multi-worker deployment, set `token_memo_ttl` on the constructor to bound how long the other workers keep the memo, as described in [Multi-instance deployment](../multi-instance.md). One cache is left standing, the process-wide word-boundary pattern cache. That cache is keyed by the fragment searched for, so it holds values from every thread. Clear it with `clear_boundary_cache` when an erasure request covers the whole process.

```python
--8<-- "snippets/reference_thread_pipeline.py:clear_boundary_cache"
```

#### `recognizer` (property)

The grammar of the tokens this pipeline emits, a `BaseDelimitedPlaceholderFactory`, or `None`. A delimited factory is its own recognizer, since its tokens carry a grammar that can be found again. A factory without one, such as a mask, has no recognizer.

---

## Ports

Two protocols type a pipeline where a caller such as the middleware needs to accept it without depending on a concrete class. Both are generic on what the emitted tokens preserve. So a consumer can require a pipeline whose tokens preserve identity, and reject a pipeline whose tokens do not.

### `AnyPipeline`

A component that de-identifies a single text and can restore it.

```python
@runtime_checkable
class AnyPipeline(Protocol[PreservationT_co]):
    async def anonymize(self, text: str) -> Anonymization[PreservationT_co]: ...
    def deanonymize(self, text: str, tokens: Mapping[Entity, str]) -> str: ...
```

### `AnyThreadPipeline`

A thread-scoped pipeline, local or remote. It de-identifies each message of a thread, re-de-identifies a corrected message, restores any text carrying the thread's tokens, forgets a thread wholesale, and exposes the grammar of its tokens.

```python
@runtime_checkable
class AnyThreadPipeline(Protocol[PreservationT_co]):
    async def anonymize(
        self, text: str, thread_id: str, role: MessageRole = MessageRole.USER
    ) -> Anonymization[PreservationT_co]: ...
    async def anonymize_corrected(
        self, text: str, thread_id: str, detections: list[Detection]
    ) -> Anonymization[PreservationT_co]: ...
    async def deanonymize(self, text: str, thread_id: str) -> str: ...
    async def forget_thread(self, thread_id: str) -> Forgotten: ...
    @property
    def recognizer(self) -> BaseDelimitedPlaceholderFactory | None: ...
```

---

## `BaseAnonymizationPipeline`

Module: `piighost.pipeline`

The shared machinery both pipelines extend. It holds the stage components and the steps common to every pipeline: the optional overlap, expand, and entity-resolve stages, the guard check, and the observation payloads. The concrete pipelines add their own `anonymize`, over a single text or over a conversation.

---

## Building from config

Module: `piighost.config`

`load_pipeline` and `load_thread_pipeline` read a config file, TOML or JSON by its suffix, or a hub reference, and return a built pipeline. A config that declares a memory describes a thread pipeline. The two loaders enforce that distinction, and check it before building anything:

- `load_pipeline(path)` returns an `AnonymizationPipeline`. It raises `ConfigError` when the config declares a memory.
- `load_thread_pipeline(path)` returns a `ThreadAnonymizationPipeline`. It raises `ConfigError` when the config declares no memory.

```python
--8<-- "snippets/loaders.py"
```

A reference written `hub:namespace/name:selector` loads the whole configuration the [piighost hub](https://hub.piighost.dev) publishes under that name, every stage included, exactly as a file holding it would. A reference pinned to a commit is fetched on the first load and read from the disk cache afterwards. An environment variable prefixed `PIIGHOST_` overrides a hub value as it overrides a file one.

```python
--8<-- "snippets/reference_hub_pipeline.py"
```

This package needs the `config` extra. See the [TOML configuration](../configuration/toml.md) reference for the file format.

---

## Full example

```python
--8<-- "snippets/reference_gliner2_pipeline.py"
```

---

## See also

- [Anonymizer reference](anonymizer.md) for the `Anonymizer`, its `Anonymization` result, and the `AnyAnonymizer` port.
- [Architecture](../architecture.md) for how the stages fit together.
- [TOML configuration](../configuration/toml.md) for the declarative build.

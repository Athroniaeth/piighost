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

De-identify a single text through the stages, in order: detect the PII, resolve overlapping spans, expand missed occurrences, link detections into entities, resolve entity conflicts, replace with tokens, and re-check with a guard. Each `anonymize()` call is independent.

### Constructor

```python
AnonymizationPipeline(
    detector: AnyDetector,
    linker: AnyEntityLinker,
    anonymizer: AnyAnonymizer,
    overlap_resolver: AnyOverlapResolver | None = None,
    expander: AnyDetectionExpander | None = None,
    entity_resolver: AnyEntityResolver | None = None,
    guard: AnyGuardRail | None = None,
    observation_redactor: AnyPlaceholderFactory | None = None,
    override: AnyDetectionOverride | None = None,
)
```

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `detector` | `AnyDetector` | required | Async entity detector |
| `linker` | `AnyEntityLinker` | required | Groups detections into entities |
| `anonymizer` | `AnyAnonymizer` | required | Replacement engine and its placeholder factory |
| `overlap_resolver` | `AnyOverlapResolver \| None` | `None` | Resolves overlapping detections. Disabled when `None` |
| `expander` | `AnyDetectionExpander \| None` | `None` | Adds missed occurrences of a detected value. Disabled when `None` |
| `entity_resolver` | `AnyEntityResolver \| None` | `None` | Reconciles conflicting entities. Disabled when `None` |
| `guard` | `AnyGuardRail \| None` | `None` | Re-checks the output for residual PII. Disabled when `None` |
| `observation_redactor` | `AnyPlaceholderFactory \| None` | `None` | Placeholder factory replacing clear values in observation payloads. `None` traces the clear text, so traces double as annotation datasets |
| `override` | `AnyDetectionOverride \| None` | `None` | Server whitelist and blacklist imposed on every detection set. Disabled when `None` |

!!! note "Components are protocols"
    `AnyDetector`, `AnyEntityLinker`, `AnyAnonymizer`, `AnyOverlapResolver`, `AnyDetectionExpander`, `AnyEntityResolver`, `AnyGuardRail`, `AnyDetectionOverride`. Any implementation of the protocol is accepted. See [Extending PIIGhost](../extending.md).

### Methods

#### `anonymize(text) -> Anonymization` *(async)*

Runs the full pipeline and returns the de-identified text with the token used for each entity.

**Raises** `PIIRemainingError` when a configured guard flags PII left in the output.

```python
result = await pipeline.anonymize("Patrick lives in Paris.")
# result.text == "<<PERSON:1>> lives in <<LOCATION:1>>."
```

#### `deanonymize(text, tokens) -> str`

Returns the text with every known token replaced by its entity's value. `tokens` is the mapping from an `Anonymization`, read in reverse. Tokens absent from the mapping are left untouched.

Restoration is unambiguous only when the tokens preserve identity, since two entities sharing one token collapse to a single value.

```python
original = pipeline.deanonymize(result.text, result.tokens)
# original == "Patrick lives in Paris."
```

---

## `ThreadAnonymizationPipeline`

Module: `piighost.pipeline`

De-identify each message of a conversation with tokens stable across the thread. A value seen in an early message and again later reads as the same token, because tokens are assigned over the union of every message's detections, not one message alone. Each message's detections are cached in the memory, so resending a message skips detection.

The extra component is a conversation memory, `memory`, the per-thread store of each message's detections.

### Constructor

```python
ThreadAnonymizationPipeline(
    detector: AnyDetector,
    linker: AnyEntityLinker,
    anonymizer: AnyAnonymizer,
    memory: AnyConversationMemory,
    overlap_resolver: AnyOverlapResolver | None = None,
    expander: AnyDetectionExpander | None = None,
    entity_resolver: AnyEntityResolver | None = None,
    guard: AnyGuardRail | None = None,
    observation_redactor: AnyPlaceholderFactory | None = None,
    override: AnyDetectionOverride | None = None,
)
```

In addition to every parameter of `AnonymizationPipeline`:

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `memory` | `AnyConversationMemory` | required | Per-thread store of each message's detections. `InMemoryConversationMemory` for a single process, `RedisConversationMemory` for a shared backend |

### Methods

#### `anonymize(text, thread_id, role=MessageRole.USER) -> Anonymization` *(async)*

Detects the message's entities, records them in `thread_id`'s memory, then de-identifies using tokens assigned over the whole thread. The token of a value stays the same from one message to the next.

The `thread_id` is required. There is no shared default, so two callers cannot fall into one thread and leak each other's PII. `role` dates the values the message introduces: a value first introduced by the assistant is left in clear, since it is not user PII.

**Raises** `PIIRemainingError` when a configured guard flags PII left in the output.

```python
a1 = await pipeline.anonymize("Patrick lives in Paris.", thread_id="user-A")
a2 = await pipeline.anonymize("Patrick wrote to Marie.", thread_id="user-A")
# Patrick keeps <<PERSON:1>> across both turns.
```

#### `anonymize_corrected(text, thread_id, detections) -> Anonymization` *(async)*

Re-de-identifies a user message with a human-corrected detection set. The corrected set replaces this message's detections in memory, then the message is de-identified with tokens consistent across the thread. Detection does not run again. This applies only to a user's own messages, so the correction is recorded as a user message.

The corrected set is stored as given, without overlap resolution or occurrence expansion, since the human is authoritative over it. A configured `override` still applies, so the server's lists trump the correction.

```python
detection = Detection(span=Span(0, 5), text="Marie", label="PERSON", confidence=1.0)
detections = [detection]
result = await pipeline.anonymize_corrected("Marie called.", "user-A", detections)
```

#### `deanonymize(text, thread_id) -> str` *(async)*

Returns the text with every token from the thread replaced by its value. The thread's tokens are rebuilt from its memory, so any text carrying them is restored, including a model reply the pipeline never de-identified.

```python
reply = await pipeline.deanonymize("Message sent to <<PERSON:2>>.", thread_id="user-A")
# reply == "Message sent to Marie."
```

#### `forget_thread(thread_id) -> Forgotten` *(async)*

Erases a thread's memory and returns a `Forgotten` reporting how much was dropped. Forgetting an unknown thread drops nothing and reports zero.

```python
forgotten = await pipeline.forget_thread("user-A")
# forgotten.messages, forgotten.detections
```

#### `recognizer` (property)

The grammar of the tokens this pipeline emits, a `BaseDelimitedPlaceholderFactory`, or `None`. A delimited factory is its own recognizer, since its tokens carry a grammar that can be found again. A factory without one, such as a mask, has no recognizer.

---

## Ports

Two protocols type a pipeline where a caller such as the middleware needs to accept it without depending on a concrete class. Both are generic on what the emitted tokens preserve, so a consumer can require a pipeline whose tokens preserve identity and reject one whose tokens do not.

### `AnyPipeline`

A component that de-identifies a single text and can restore it.

```python
class AnyPipeline(Protocol[PreservationT_co]):
    async def anonymize(self, text: str) -> Anonymization[PreservationT_co]: ...
    def deanonymize(self, text: str, tokens: Mapping[Entity, str]) -> str: ...
```

### `AnyThreadPipeline`

A thread-scoped pipeline, local or remote. It de-identifies each message of a thread, re-de-identifies a corrected message, deanonymizes any text carrying the thread's tokens, forgets a thread wholesale, and exposes the grammar of its tokens.

```python
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

`load_pipeline` and `load_thread_pipeline` read a config file, TOML or JSON by its suffix, and return a built pipeline. A configured memory makes the config a thread pipeline. The two loaders enforce that distinction:

- `load_pipeline(path)` returns an `AnonymizationPipeline`. It raises `ConfigError` when the config declares a memory.
- `load_thread_pipeline(path)` returns a `ThreadAnonymizationPipeline`. It raises `ConfigError` when the config declares no memory.

```python
from piighost.config import load_pipeline, load_thread_pipeline

pipeline = load_pipeline("pipeline.toml")
thread_pipeline = load_thread_pipeline("thread.toml")
```

This package needs the `config` extra. See the [TOML configuration](../configuration/toml.md) reference for the file format.

---

## Full example

```python
import asyncio

from gliner2 import GLiNER2

from piighost.components.anonymizer import Anonymizer
from piighost.components.detector.ner.gliner2 import Gliner2Detector
from piighost.components.linker import ExactEntityLinker
from piighost.components.placeholder import LabelCounterPlaceholderFactory
from piighost.conversation_memory import InMemoryConversationMemory
from piighost.pipeline import ThreadAnonymizationPipeline

model = GLiNER2.from_pretrained("fastino/gliner2-multi-v1")
detector = Gliner2Detector(model=model, threshold=0.5, labels=["PERSON", "LOCATION"])
factory = LabelCounterPlaceholderFactory()
anonymizer = Anonymizer(factory)
linker = ExactEntityLinker()
memory = InMemoryConversationMemory()

pipeline = ThreadAnonymizationPipeline(
    detector=detector,
    linker=linker,
    anonymizer=anonymizer,
    memory=memory,
)


async def main():
    result = await pipeline.anonymize("Patrick is in Lyon.", thread_id="user-A")
    print(result.text)  # <<PERSON:1>> is in <<LOCATION:1>>.

    original = await pipeline.deanonymize(result.text, thread_id="user-A")
    print(original)  # Patrick is in Lyon.


asyncio.run(main())
```

---

## See also

- [Anonymizer reference](anonymizer.md) for the `Anonymizer`, its `Anonymization` result, and the `AnyAnonymizer` port.
- [Architecture](../architecture.md) for how the stages fit together.
- [TOML configuration](../configuration/toml.md) for the declarative build.

---
icon: lucide/messages-square
---

# Conversational pipeline

You will build a `ThreadAnonymizationPipeline` that keeps a stable token for the same value from one message to the next. A value seen in message 1 keeps its `<<PERSON:1>>`{ .placeholder } in message 2, instead of restarting from scratch at each call. You assemble the pipeline with an in-RAM memory, send two messages of the same thread, then erase the thread.

!!! note "Prerequisites"
    `piighost` installed, see [Installation](installation.md). This example uses only the core, no extra.

## 1. Assemble the pipeline

`ThreadAnonymizationPipeline` takes the same components as `AnonymizationPipeline` (detector, linker, anonymizer), plus a conversation memory. The memory accumulates each message's detections per thread, which lets the pipeline assign tokens over the whole thread rather than over one isolated message.

`InMemoryConversationMemory` keeps that state in a process dictionary. Nothing survives a restart and nothing is shared across processes, which suits development and tests. We keep the detector simple here with `ExactMatchDetector`, which spots known values, for a verifiable result with no model.

```python
import asyncio

from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import ExactMatchDetector
from piighost.components.linker import ExactEntityLinker
from piighost.components.placeholder import LabelCounterPlaceholderFactory
from piighost.pipeline import ThreadAnonymizationPipeline
from piighost.conversation_memory import InMemoryConversationMemory

detector = ExactMatchDetector({"Patrick": "PERSON", "Paris": "LOCATION"})
linker = ExactEntityLinker()
factory = LabelCounterPlaceholderFactory()
anonymizer = Anonymizer(factory)
memory = InMemoryConversationMemory()
pipeline = ThreadAnonymizationPipeline(
    detector,
    linker,
    anonymizer,
    memory,
)
```

## 2. De-identify two messages of the same thread

`anonymize` takes the text and a `thread_id`. The `thread_id` is required, there is no shared default thread, so two callers cannot fall into the same thread and leak each other's PII. We send two messages on the thread `"thread-42"`.

```python
async def main() -> None:
    first = await pipeline.anonymize("Patrick habite à Paris.", "thread-42")
    print(first.text)

    second = await pipeline.anonymize("Est-ce que Patrick aime Paris ?", "thread-42")
    print(second.text)


asyncio.run(main())
```

The output should be:

```text
<<PERSON:1>> habite à <<LOCATION:1>>.
Est-ce que <<PERSON:1>> aime <<LOCATION:1>> ?
```

`Patrick`{ .pii } keeps `<<PERSON:1>>`{ .placeholder } from the first message to the second, and `Paris`{ .pii } keeps `<<LOCATION:1>>`{ .placeholder }. With a plain `AnonymizationPipeline`, each call would restart at `<<PERSON:1>>`{ .placeholder } with no link to the previous message. The thread memory is what makes the number stable.

## 3. Restore a value

`deanonymize` rebuilds the thread's tokens from its memory, so any text carrying them is restored, including a model reply the pipeline never de-identified.

```python
    restored = await pipeline.deanonymize("Bonjour <<PERSON:1>> !", "thread-42")
    print(restored)
    # Bonjour Patrick !
```

## 4. Forget a thread

`forget_thread` erases a thread's memory and returns the count of what was dropped. Useful to honor an erasure request or to free RAM at the end of a conversation.

```python
    forgotten = await pipeline.forget_thread("thread-42")
    print(forgotten)
    # Forgotten(messages=2, detections=4)
```

## How it works

`ThreadAnonymizationPipeline` wraps the base pipeline with a per-thread memory. On each message it caches the detections, then assigns tokens over the union of the whole thread's detections, not the current message alone. A value therefore gets one token for the whole thread. Rendering stays per message, only the current message's positions are replaced, because positions from different messages live in distinct index spaces.

## What's next

- To share the memory across several processes, replace `InMemoryConversationMemory` with a persistent memory. See the [TOML reference](../configuration/toml.md) to declare it in configuration.
- To plug this pipeline into a LangGraph agent, see the [LangChain middleware](langchain.md).

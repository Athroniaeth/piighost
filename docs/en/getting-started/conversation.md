---
icon: lucide/messages-square
---

# Conversational pipeline

You will build a `ThreadAnonymizationPipeline` that keeps a stable token for the same value from one message to the next. A value seen in message 1 keeps its `<<PERSON:1>>`{ .placeholder } in message 2, instead of restarting from scratch at each call. You assemble the pipeline with an in-RAM memory, send two messages of the same thread, then erase the thread.

!!! note "Prerequisites"
    `piighost` installed, see [Installation](installation.md). This example uses only the core, no extra.

## 1. Assemble the pipeline

`ThreadAnonymizationPipeline` takes the same components as `AnonymizationPipeline` (detector, linker, anonymizer), plus a conversation memory. Only the detector is required. The code below passes the memory explicitly and leaves the linker and the anonymizer to their defaults. The memory accumulates each message's detections, thread by thread. The pipeline can thus assign tokens over the whole thread rather than over one isolated message.

`InMemoryConversationMemory` keeps that state in a process dictionary. Nothing survives a restart and nothing is shared across processes. This memory therefore suits development and tests. We keep the detector simple here with `ExactMatchDetector`, which spots known values. The result is thus verifiable, with no model.

```python
--8<-- "snippets/conversation.en.py:setup"
```

## 2. De-identify two messages of the same thread

`anonymize` takes the text and a `thread_id`. The `thread_id` is required. There is no shared default thread, so two callers cannot fall into the same thread and leak each other's confidential data. We send two messages on the thread `"thread-42"`.

```python
--8<-- "snippets/conversation.en.py:turns"


--8<-- "snippets/conversation.en.py:run"
```

The output should be:

```text
--8<-- "snippets/conversation.en.out:turns"
```

`Patrick`{ .pii } keeps `<<PERSON:1>>`{ .placeholder } from the first message to the second, and `Paris`{ .pii } keeps `<<LOCATION:1>>`{ .placeholder }. With a plain `AnonymizationPipeline`, each call would restart at `<<PERSON:1>>`{ .placeholder } with no link to the previous message. The thread memory is what makes the number stable.

## 3. Restore a value

`deanonymize` rebuilds the thread's tokens from its memory. It therefore restores any text carrying these tokens, including a model reply the pipeline never de-identified.

```python
--8<-- "snippets/conversation.en.py:restore"
```

## 4. Forget a thread

`forget_thread` erases a thread's memory and returns the count of what was dropped. Useful to honor an erasure request or to free RAM at the end of a conversation.

```python
--8<-- "snippets/conversation.en.py:forget"
```

## How it works

`ThreadAnonymizationPipeline` wraps the base pipeline with a per-thread memory. On each message it caches the detections, then assigns tokens over the union of the whole thread's detections, not the current message alone. A value therefore gets one token for the whole thread. Rendering stays per message. Only the current message's positions are replaced, because each message counts its positions from its own start.

## What's next

- To share the memory across several processes, replace `InMemoryConversationMemory` with a persistent memory. See the [TOML reference](../configuration/toml.md) to declare it in configuration.
- To plug this pipeline into a LangGraph agent, see the [LangChain middleware](langchain.md).
- To read the business rules a conversation follows, `BR-CONV-01` to `BR-CONV-11`, see [Follow a conversation and restore the reply](../../../openwiki/en/processes/follow-a-conversation.md).

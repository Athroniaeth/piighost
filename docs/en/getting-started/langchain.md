---
icon: lucide/link
seo_title: LangChain PII middleware that restores values
description: Add the piighost middleware to a LangChain agent. The LLM only sees placeholders, your tools get the real values, and the reply is restored for the user.
---

# LangChain middleware

You will wire `PIIAnonymizationMiddleware` into a LangChain agent so the LLM only ever sees tokens, while your tools receive the real values. The user asks `Where does Patrick live?`, the model reasons over `<<PERSON:1>>`{ .placeholder } and `<<LOCATION:1>>`{ .placeholder }, and a lookup tool still gets the real `Patrick`{ .pii } to do its job. You build the middleware over a `ThreadAnonymizationPipeline`, register a tool, and run one turn.

!!! note "Prerequisites"
    `piighost` installed with the middleware extra, `pip install "piighost[langchain]"`, plus an LLM provider configured for `create_agent` (here `openai:...`, so an `OPENAI_API_KEY`). The pipeline reuses the components from [Conversational pipeline](conversation.md).

## 1. Build the thread pipeline

The middleware wraps a `ThreadAnonymizationPipeline`, the same one from the [Conversational pipeline](conversation.md) page. Only the detector is passed. The other components keep their defaults, and the default anonymizer uses `LabelCounterPlaceholderFactory`, a delimited token factory which emits `<<PERSON:1>>`{ .placeholder }. The middleware needs that delimited shape to find a token again. With another factory, it raises `UnrecognizableFactoryError` at construction.

```python
--8<-- "snippets/langchain_start.en.py:pipeline"
```

## 2. Declare a tool that needs the real value

A tool that looks a person up by name needs `Patrick`{ .pii }, not `<<PERSON:1>>`{ .placeholder }. Write the tool as usual, against real values. The middleware restores them before the call.

```python
--8<-- "snippets/langchain_start.en.py:tool"
```

## 3. Wrap the pipeline in the middleware

`PIIAnonymizationMiddleware` takes the pipeline. `tool_strategy=ToolCallStrategy.FULL` restores the tool arguments on the way in and de-identifies the tool result on the way out. The tool therefore works on real values, while the model still only sees tokens.

```python
--8<-- "snippets/langchain_start.en.py:agent"
```

## 4. Run one turn

The `thread_id` goes in the LangGraph config, under `configurable`. The middleware reads it from there and scopes every token to that thread.

```python
--8<-- "snippets/langchain_start.en.py:run"
```

The final message is restored for display, so the answer reads with the real values. Its wording depends on the model, for example:

```text
--8<-- "snippets/langchain_start.en.out"
```

## How it works

The middleware is a thin adapter around the pipeline. Before the model call, `abefore_model` sends each message through `pipeline.anonymize`, so the LLM receives `Where does <<PERSON:1>> live?` instead of the raw name. When the model calls `lookup_city` with `person="<<PERSON:1>>"`, `awrap_tool_call` under `ToolCallStrategy.FULL` restores the argument to `Patrick`{ .pii } before running the tool. It then de-identifies the tool's string result. After the model call, `aafter_model` restores the reply for the user. The `thread_id` keeps `<<PERSON:1>>`{ .placeholder } bound to `Patrick`{ .pii } across every step of the turn.

Two rules are worth knowing. A call without a thread id raises. The middleware does not route every conversation into one shared thread, where tokens would leak from one conversation to another. If your conversations need no separation, pass `"default"`. `invented_strategy=InventedPlaceholderStrategy.RAISE` refuses a token that surfaces in the model's reply but was never issued by the pipeline, whether hallucinated or injected.

## See also

- To pick a different tool behaviour, `INPUT` only, `OUTPUT` only, or `PASSTHROUGH`, see [Tool-call strategies](../tool-call-strategies.md).
- For a complete agent with a real detector and a system prompt, see [LangChain integration](../examples/langchain.md).
- To run the pipeline out of process against a shared server, see [Remote client](api-client.md).

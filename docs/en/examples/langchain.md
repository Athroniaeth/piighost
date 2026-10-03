---
icon: lucide/link
tags:
  - LangChain
  - Middleware
---

# Build a LangChain agent with a real detector

You want a working LangGraph agent where the LLM only ever sees tokens, a tool still receives the real values it needs, and detection runs on a real NER model instead of a fixed value list. The assembly below runs end to end. It brings together a GLiNER2 detector, a `ThreadAnonymizationPipeline`, `PIIAnonymizationMiddleware`, a system prompt that teaches the model to treat tokens as data, and a tool that looks a person up by name.

For the minimal version with a stub detector, start with the [LangChain middleware](../getting-started/langchain.md) tutorial. What follows is the same shape with a real model and a system prompt.

!!! note "Prerequisites"
    `piighost` installed with the middleware and gliner2 extras, `pip install piighost[langchain,gliner2]`, plus an LLM provider configured for `create_agent` (here `openai:...`, so an `OPENAI_API_KEY`). The first run downloads the GLiNER2 weights, roughly 500 MB.

## 1. Build the pipeline over a GLiNER2 detector

`Gliner2Detector` wraps a GLiNER2 model. Pass the model id as a string and it loads on construction. Pass `labels` to tell it which entity types to query. The anonymizer uses `LabelCounterPlaceholderFactory`, which emits the delimited `<<PERSON:1>>`{ .placeholder } the middleware can find again.

```python
--8<-- "snippets/langchain_pipeline.py"
```

## 2. Declare a tool that needs the real value

A tool that looks a person up by name needs `Patrick`{ .pii }, not `<<PERSON:1>>`{ .placeholder }. Write it against real values. Under `ToolCallStrategy.FULL`, the middleware restores the argument before the call, then de-identifies the result.

```python
--8<-- "snippets/langchain_agent.py:tool"
```

## 3. Tell the model that tokens are data

The model reasons over `<<PERSON:1>>`{ .placeholder } instead of a name. A short system prompt keeps it from commenting on the token or refusing to pass it to a tool.

```python
--8<-- "snippets/langchain_agent.py:system_prompt"
```

## 4. Wrap the pipeline and create the agent

`PIIAnonymizationMiddleware` takes the pipeline. `tool_strategy=ToolCallStrategy.FULL` restores the tool arguments on the way in and de-identifies the tool result on the way out. The tool thus works on real values, while the model still only sees tokens.

```python
--8<-- "snippets/langchain_agent.py:agent"
```

## 5. Run one turn

The `thread_id` goes in the LangGraph config, under `configurable`. The middleware reads it there and scopes every token to that thread.

```python
--8<-- "snippets/langchain_agent.py:run"
```

The reply is restored for display, so it reads with the real values:

```text
--8<-- "snippets/langchain_agent.out"
```

## Who sees what

`GLiNER2` flags `Patrick`{ .pii } as `PERSON` in the incoming message. From there each boundary of the turn replaces in one direction only, either a value with its token or a token with its value:

- `abefore_model` sends the message through `pipeline.anonymize`, so the LLM receives `Where does <<PERSON:1>> live?`.
- The model calls `lookup_city(person="<<PERSON:1>>")`. Under `ToolCallStrategy.FULL`, `awrap_tool_call` restores the argument to `Patrick`{ .pii } before running the tool, then de-identifies the tool's string result.
- `aafter_model` restores the reply for the user.

The `thread_id` keeps `<<PERSON:1>>`{ .placeholder } bound to `Patrick`{ .pii } across every step.

## What's next

- To pick a different tool behaviour, `INPUT` only, `OUTPUT` only, or `PASSTHROUGH`, see [Tool-call strategies](../tool-call-strategies.md).
- To swap GLiNER2 for spaCy, a regex pack, or your own detector, see [Extending PIIGhost](../extending.md).
- To run the pipeline out of process against a shared server, see [Remote client](../getting-started/api-client.md).

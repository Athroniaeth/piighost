---
icon: lucide/bot
seo_title: Mask PII before the model in a Pydantic AI agent
description: Add the pii_hooks capability to a Pydantic AI agent. The model only sees placeholders, tools get the real values, and a value keeps one token per thread.
tags:
  - Pydantic AI
---

# Pydantic AI integration

You want a Pydantic AI agent where the model only ever sees tokens, never the real names in the conversation, and where a value keeps the same token from one turn to the next. This page wires that agent end to end with a GLiNER2 detector, a `ThreadAnonymizationPipeline`, and `pii_hooks`, the capability that de-identifies around the model.

The capability covers the messages, the user prompt and the model's own replies. It covers the tool boundary too, meaning the tool calls and their results. Under the default strategy a tool receives the real values while the model keeps working on tokens.

!!! note "Prerequisites"
    `piighost` installed with the pydantic-ai and gliner2 extras, `pip install "piighost[pydantic-ai,gliner2]"`, plus an OpenAI key in `OPENAI_API_KEY`. The first run downloads the GLiNER2 weights, roughly 500 MB.

## 1. Build the pipeline over a GLiNER2 detector

`Gliner2Detector` wraps a GLiNER2 model. Pass the model id as a string and it loads on construction. Pass `labels` to tell it which entity types to query. Only the detector is required, since the thread pipeline defaults its linker, its anonymizer, and an in-memory conversation store. The default anonymizer emits the delimited `<<PERSON:1>>`{ .placeholder } that `pii_hooks` can find again.

```python
--8<-- "snippets/pydantic_ai_pipeline.py"
```

## 2. Attach the capability to the agent

`pii_hooks` takes the pipeline and a thread id, then returns a Pydantic AI capability. Register it with `capabilities=[...]`. The thread id scopes the tokens, so a value keeps one token for the whole conversation. It is a fixed string here. Pass a callable over the run context, for example `lambda ctx: ctx.deps.thread_id`, to read it per run.

```python
--8<-- "snippets/pydantic_ai_agent.py:agent"
```

## 3. Run one turn

The capability de-identifies the prompt before the model reads it, and restores the reply for display. So the model works on `<<PERSON:1>>`{ .placeholder } while you read `Patrick`{ .pii }.

```python
--8<-- "snippets/pydantic_ai_agent.py:run"
```

The reply is restored for display. Its wording depends on the model, for example:

```text
--8<-- "snippets/pydantic_ai_agent.out"
```

## Who sees what

`GLiNER2` flags `Patrick`{ .pii } as `PERSON` in the incoming message. From there the capability substitutes in one direction before the model call, and in the other direction after it:

- `before_model_request` sends every user and assistant text through `pipeline.anonymize`. So the model receives `Where does <<PERSON:1>> live?`. This hook rewrites the assistant texts too. So a value restored for display on an earlier turn is de-identified again before the next model call, and never leaks back into the history.
- `after_model_request` sends the reply through `pipeline.deanonymize`, so you read the real value.

The `thread_id` keeps `<<PERSON:1>>`{ .placeholder } bound to `Patrick`{ .pii } across every turn.

## Tokens the model invents

After restoration every issued token is back to its value. So a string that still has the shape of a token was invented by the model, whether by hallucination or prompt injection. `pii_hooks` takes an `invented_strategy` that decides what happens then. `RAISE` refuses it, the fail-closed default. `KEEP` leaves it. `DROP` removes it.

```python
--8<-- "snippets/pydantic_ai_agent.py:invented"
```

## Tool calls

`pii_hooks` also covers the tool boundary. `tool_strategy` governs it, with the same enum the LangChain middleware uses. Under `FULL`, the default, a tool call's arguments are restored before the tool runs. So a tool that needs `Patrick`{ .pii } gets it, and not `<<PERSON:1>>`{ .placeholder }. The tool's string result is de-identified again before the model reads it, so the model keeps seeing tokens. `INPUT` restores only the arguments, `OUTPUT` de-identifies again only the result, and `PASSTHROUGH` leaves both untouched.

```python
--8<-- "snippets/pydantic_ai_agent.py:tools"
```

## Assistant values

Not every value is the user's confidential data. Sometimes the model itself introduces a value from its world knowledge. Tokenizing that value would hide it from the model on the next turn, and protect nothing of the user. `assistant_strategy` decides what happens to a value the assistant introduces, again with the same enum the middleware uses. Under `PRESERVE`, the default, the value stays in clear. So the model keeps its own knowledge of it, and only known user values are tokenized. `ANONYMIZE` tokenizes it anyway. `IGNORE` skips the assistant's messages entirely, so the detector does not run on them.

```python
--8<-- "snippets/pydantic_ai_agent.py:assistant"
```

## See also

- To compare with the LangChain agent middleware, see the [LangChain integration](langchain.md).
- To swap GLiNER2 for spaCy, a regex pack, or your own detector, see [Extending piighost](../extending.md).
- The runnable scripts are in `examples/pydantic_ai/base.py` (messages) and `examples/pydantic_ai/tools.py` (a tool).

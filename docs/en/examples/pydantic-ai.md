---
icon: lucide/bot
tags:
  - Pydantic AI
---

# Run a Pydantic AI agent behind PIIGhost

You want a Pydantic AI agent where the model only ever sees tokens, never the real names in the conversation, and where a value keeps the same token from one turn to the next. This page wires that agent end to end with a GLiNER2 detector, a `ThreadAnonymizationPipeline`, and `pii_hooks`, the capability that de-identifies around the model.

The capability handles the messages, the user prompt and the model's own replies. Tool calls stay out of scope in this version. If your agent calls tools with sensitive arguments, use the [LangChain integration](langchain.md), whose middleware routes tool calls by a strategy.

!!! note "Prerequisites"
    `piighost` installed with the pydantic-ai and gliner2 extras, `pip install piighost[pydantic-ai,gliner2]`, plus an OpenAI key in `OPENAI_API_KEY`. The first run downloads the GLiNER2 weights, roughly 500 MB.

## 1. Build the pipeline over a GLiNER2 detector

`Gliner2Detector` wraps a GLiNER2 model. Pass the model id as a string and it loads on construction; pass `labels` to tell it which entity types to query. Only the detector is required, since the thread pipeline defaults its linker, its anonymizer, and an in-memory conversation store. The default anonymizer emits the delimited `<<PERSON:1>>`{ .placeholder } that `pii_hooks` can find again.

```python
from piighost.components.detector.ner import Gliner2Detector
from piighost.pipeline import ThreadAnonymizationPipeline

detector = Gliner2Detector(
    "fastino/gliner2-multi-v1",
    labels=["PERSON", "LOCATION"],
    threshold=0.5,
)
pipeline = ThreadAnonymizationPipeline(detector)
```

## 2. Attach the capability to the agent

`pii_hooks` takes the pipeline and a thread id, then returns a Pydantic AI capability. Register it with `capabilities=[...]`. The thread id scopes the tokens, so a value keeps one token for the whole conversation. It is a fixed string here; pass a callable over the run context, for example `lambda ctx: ctx.deps.thread_id`, to read it per run.

```python
from pydantic_ai import Agent
from piighost.integrations.pydantic_ai import pii_hooks

hooks = pii_hooks(pipeline, "thread-42")
agent = Agent("openai:gpt-5.5", capabilities=[hooks])
```

## 3. Run one turn

The capability anonymizes the prompt before the model reads it and deanonymizes the reply for display, so the model works on `<<PERSON:1>>`{ .placeholder } while you read `Patrick`{ .pii }.

```python
import asyncio


async def main() -> None:
    result = await agent.run("Where does Patrick live?")
    print(result.output)


asyncio.run(main())
```

## Who sees what

`GLiNER2` flags `Patrick`{ .pii } as `PERSON` in the incoming message. From there the capability substitutes one direction at each side of the model call:

- `before_model_request` sends every user and assistant text through `pipeline.anonymize`, so the model receives `Where does <<PERSON:1>> live?`. It rewrites the assistant texts too, so a value restored for display on an earlier turn is re-anonymized before the next model call and never leaks back into the history.
- `after_model_request` sends the reply through `pipeline.deanonymize`, so you read the real value.

The `thread_id` keeps `<<PERSON:1>>`{ .placeholder } bound to `Patrick`{ .pii } across every turn.

## Tokens the model invents

After deanonymization every issued token is back to its value, so a token still matching the grammar was invented by the model, whether by hallucination or prompt injection. `pii_hooks` takes an `invented_strategy` that decides what happens then. `RAISE` refuses it, the fail-closed default; `KEEP` leaves it; `DROP` removes it.

```python
from piighost.integrations.middleware import InventedPlaceholderStrategy

hooks = pii_hooks(
    pipeline,
    "thread-42",
    invented_strategy=InventedPlaceholderStrategy.DROP,
)
```

## What's next

- For a tool-calling agent where the tool needs the real value, see the [LangChain integration](langchain.md).
- To swap GLiNER2 for spaCy, a regex pack, or your own detector, see [Extending PIIGhost](../extending.md).
- The runnable script is in `examples/pydantic_ai/hooks.py`.

---
icon: lucide/link
tags:
  - LangChain
  - Middleware
---

# Build a LangChain agent with a real detector

You want a working LangGraph agent where the LLM only ever sees tokens, a tool still receives the real values it needs, and detection runs on a real NER model instead of a fixed value list. This page assembles that agent end to end: a GLiNER2 detector, a `ThreadAnonymizationPipeline`, `PIIAnonymizationMiddleware`, a system prompt that teaches the model to treat tokens as data, and a tool that looks a person up by name.

For the minimal version with a stub detector, start with the [LangChain middleware](../getting-started/langchain.md) tutorial. This page is the same shape with a real model and a system prompt.

!!! note "Prerequisites"
    `piighost` installed with the middleware and gliner2 extras, `pip install piighost[langchain,gliner2]`, plus an LLM provider configured for `create_agent` (here `openai:...`, so an `OPENAI_API_KEY`). The first run downloads the GLiNER2 weights, roughly 500 MB.

## 1. Build the pipeline over a GLiNER2 detector

`Gliner2Detector` wraps a GLiNER2 model. Pass the model id as a string and it loads on construction; pass `labels` to tell it which entity types to query. The anonymizer uses `LabelCounterPlaceholderFactory`, which emits the delimited `<<PERSON:1>>`{ .placeholder } the middleware can find again.

```python
from piighost.components.anonymizer import Anonymizer
from piighost.components.detector.ner import Gliner2Detector
from piighost.components.linker import ExactEntityLinker
from piighost.components.placeholder import LabelCounterPlaceholderFactory
from piighost.pipeline import ThreadAnonymizationPipeline
from piighost.conversation_memory import InMemoryConversationMemory

detector = Gliner2Detector(
    "fastino/gliner2-multi-v1",
    labels=["PERSON", "LOCATION"],
    threshold=0.5,
)
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

## 2. Declare a tool that needs the real value

A tool that looks a person up by name needs `Patrick`{ .pii }, not `<<PERSON:1>>`{ .placeholder }. Write it against real values. Under `ToolCallStrategy.FULL`, the middleware restores the argument before the call and re-anonymizes the result after.

```python
from langchain.tools import tool


@tool
def lookup_city(person: str) -> str:
    """Return the city where a person lives."""
    directory = {"Patrick": "Paris"}
    return directory.get(person, "unknown")
```

## 3. Tell the model that tokens are data

The model reasons over `<<PERSON:1>>`{ .placeholder } instead of a name. A short system prompt keeps it from commenting on the token or refusing to pass it to a tool.

```python
SYSTEM_PROMPT = """\
You are a helpful assistant. Some inputs contain placeholders like <<PERSON:1>> \
that stand in for real values withheld for privacy.

Treat each placeholder as if it were the real value. Never comment on its \
format, never say it is a token, and pass it to tools unchanged as an argument. \
If the user asks about the content of a placeholder, say the data is withheld \
and you cannot reveal it.
"""
```

## 4. Wrap the pipeline and create the agent

`PIIAnonymizationMiddleware` takes the pipeline. `tool_strategy=ToolCallStrategy.FULL` deanonymizes the tool arguments on the way in and anonymizes the tool result on the way out, so the tool works on real values while the model still only sees tokens.

```python
from langchain.agents import create_agent
from piighost.integrations.langchain import (
    PIIAnonymizationMiddleware,
    ToolCallStrategy,
)

agent = create_agent(
    model="openai:gpt-5.6-terra",
    system_prompt=SYSTEM_PROMPT,
    tools=[lookup_city],
    middleware=[
        PIIAnonymizationMiddleware(
            pipeline=pipeline,
            tool_strategy=ToolCallStrategy.FULL,
        )
    ],
)
```

## 5. Run one turn

The `thread_id` goes in the LangGraph config, under `configurable`. The middleware reads it there and scopes every token to that thread.

```python
import asyncio


async def main() -> None:
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": "Where does Patrick live?"}]},
        config={"configurable": {"thread_id": "thread-42"}},
    )
    print(result["messages"][-1].content)


asyncio.run(main())
```

The reply is deanonymized for display, so it reads with the real values:

```text
Patrick lives in Paris.
```

## Who sees what

`GLiNER2` flags `Patrick`{ .pii } as `PERSON` in the incoming message. From there each boundary of the turn substitutes one direction:

- `abefore_model` sends the message through `pipeline.anonymize`, so the LLM receives `Where does <<PERSON:1>> live?`.
- The model calls `lookup_city(person="<<PERSON:1>>")`. Under `ToolCallStrategy.FULL`, `awrap_tool_call` deanonymizes the argument to `Patrick`{ .pii } before running the tool, then re-anonymizes the tool's string result.
- `aafter_model` deanonymizes the reply for the user.

The `thread_id` keeps `<<PERSON:1>>`{ .placeholder } bound to `Patrick`{ .pii } across every step.

## What's next

- To pick a different tool behaviour, `INPUT` only, `OUTPUT` only, or `PASSTHROUGH`, see [Tool-call strategies](../tool-call-strategies.md).
- To swap GLiNER2 for spaCy, a regex pack, or your own detector, see [Extending PIIGhost](../extending.md).
- To run the pipeline out of process against a shared server, see [Remote client](../getting-started/api-client.md).

---
icon: lucide/link
---

# LangChain middleware

You will wire `PIIAnonymizationMiddleware` into a LangChain agent so the LLM only ever sees tokens, while your tools receive the real values. The user writes `Patrick habite à Paris.`{ .pii }, the model reasons over `<<PERSON:1>>`{ .placeholder } and `<<LOCATION:1>>`{ .placeholder }, and a lookup tool still gets the real `Patrick`{ .pii } to do its job. You build the middleware over a `ThreadAnonymizationPipeline`, register a tool, and run one turn.

!!! note "Prerequisites"
    `piighost` installed with the middleware extra, `pip install piighost[middleware]`, plus an LLM provider configured for `create_agent` (here `openai:...`, so an `OPENAI_API_KEY`). The pipeline reuses the components from [Conversational pipeline](conversation.md).

## 1. Build the thread pipeline

The middleware wraps a `ThreadAnonymizationPipeline`, the same one from the [Conversational pipeline](conversation.md) page. Its anonymizer must use a delimited token factory like `LabelCounterPlaceholderFactory`, which emits `<<PERSON:1>>`{ .placeholder }. The middleware needs that grammar to find a token again, otherwise it raises `UnrecognizableFactoryError` at construction.

```python
from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import ExactMatchDetector
from piighost.components.linker import ExactEntityLinker
from piighost.components.placeholder import LabelCounterPlaceholderFactory
from piighost.pipeline import ThreadAnonymizationPipeline
from piighost.conversation_memory import InMemoryConversationMemory

detector = ExactMatchDetector({"Patrick": "PERSON", "Paris": "LOCATION"})
pipeline = ThreadAnonymizationPipeline(
    detector,
    ExactEntityLinker(),
    Anonymizer(LabelCounterPlaceholderFactory()),
    InMemoryConversationMemory(),
)
```

## 2. Declare a tool that needs the real value

A tool that looks a person up by name needs `Patrick`{ .pii }, not `<<PERSON:1>>`{ .placeholder }. Write the tool as usual, against real values. The middleware restores them before the call.

```python
from langchain.tools import tool


@tool
def lookup_city(person: str) -> str:
    """Return the city where a person lives."""
    directory = {"Patrick": "Paris"}
    return directory.get(person, "unknown")
```

## 3. Wrap the pipeline in the middleware

`PIIAnonymizationMiddleware` takes the pipeline. `tool_strategy=ToolCallStrategy.FULL` deanonymizes the tool arguments on the way in and anonymizes the tool result on the way out, so the tool works on real values while the model still only sees tokens.

```python
from langchain.agents import create_agent
from piighost.integrations.middleware import (
    PIIAnonymizationMiddleware,
    ToolCallStrategy,
)

agent = create_agent(
    model="openai:gpt-4o",
    tools=[lookup_city],
    middleware=[
        PIIAnonymizationMiddleware(
            pipeline=pipeline,
            tool_strategy=ToolCallStrategy.FULL,
        )
    ],
)
```

## 4. Run one turn

The `thread_id` goes in the LangGraph config, under `configurable`. The middleware reads it from there and scopes every token to that thread.

```python
import asyncio


async def main() -> None:
    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": "Où habite Patrick ?"}]},
        config={"configurable": {"thread_id": "thread-42"}},
    )
    print(result["messages"][-1].content)


asyncio.run(main())
```

The final message is deanonymized for display, so the answer reads with the real values:

```text
Patrick habite à Paris.
```

## How it works

The middleware is a thin adapter around the pipeline. Before the model call, `abefore_model` sends each message through `pipeline.anonymize`, so the LLM receives `Où habite <<PERSON:1>> ?` instead of the raw name. When the model calls `lookup_city` with `person="<<PERSON:1>>"`, `awrap_tool_call` under `ToolCallStrategy.FULL` deanonymizes the argument to `Patrick`{ .pii } before running the tool, then re-anonymizes the tool's string result. After the model call, `aafter_model` deanonymizes the reply for the user. The `thread_id` keeps `<<PERSON:1>>`{ .placeholder } bound to `Patrick`{ .pii } across every step of the turn.

Two defaults are worth knowing. `require_thread_id=True` makes a call without a thread id raise, rather than routing every conversation into one shared thread and leaking tokens across them. `invented_strategy=InventedPlaceholderStrategy.RAISE` refuses a token that surfaces in the model's reply but was never issued by the pipeline, whether hallucinated or injected.

## What's next

- To pick a different tool behaviour, `INPUT` only, `OUTPUT` only, or `PASSTHROUGH`, see [Tool-call strategies](../tool-call-strategies.md).
- For a complete agent with a real detector, a system prompt, Langfuse observability, and an Aegra deployment, see [LangChain integration](../examples/langchain.md).
- To run the pipeline out of process against a shared server, see [Remote client](api-client.md).

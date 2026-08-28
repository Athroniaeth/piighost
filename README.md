# PIIGhost

[![CI](https://github.com/Athroniaeth/piighost/actions/workflows/ci.yml/badge.svg)](https://github.com/Athroniaeth/piighost/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/Athroniaeth/piighost/branch/master/graph/badge.svg)](https://codecov.io/gh/Athroniaeth/piighost)
[![PyPI version](https://img.shields.io/pypi/v/piighost.svg)](https://pypi.org/project/piighost/)
[![Python versions](https://img.shields.io/pypi/pyversions/piighost.svg)](https://pypi.org/project/piighost/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Security: bandit](https://img.shields.io/badge/security-bandit-yellow.svg)](https://github.com/PyCQA/bandit)
[![Discord](https://img.shields.io/badge/Discord-join-5865F2?logo=discord&logoColor=white)](https://discord.gg/vFg9GHQR2s)

`piighost` is a Python library that keeps PII (personally identifiable information) from ever reaching a language model, without getting in the way of what your app needs to do.

It spots PII with detectors (regex, NER, or another LLM) and swaps each value for a stable placeholder, so `john.doe@example.com` becomes `<<EMAIL:1>>` and the model only ever works on de-identified text. When the LLM answers with those placeholders, `piighost` puts the real values back, so the end user reads `john.doe@example.com` and never notices a thing. Tool-using agents get the same treatment. A tool that genuinely needs the real address receives it in clear, while the LLM that decided to call it still sees only `<<EMAIL:1>>`.

The mapping between a value and its placeholder also sticks around for the whole conversation. If `john.doe@example.com` comes up again three messages later, it stays `<<EMAIL:1>>`, so the model can still follow the thread.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/assets/deid-chat-dark.gif">
    <img alt="A user chats with an agent: PII values are replaced by placeholders before reaching the model and restored afterwards for the user and for tool calls." src="docs/assets/deid-chat-light.gif" width="760">
  </picture>
</p>

*The LLM only sees placeholders. The tool receives the real address, the user gets a clear-text reply, and your agent code stays the same.*

> [!NOTE]
> `piighost` performs **reversible de-identification**. Because the mapping between a value and its placeholder is kept so the data can be restored, this is pseudonymisation under the GDPR, not permanent anonymisation. The real values stay stored for the duration of the conversation and must be protected accordingly.

## Features

- **Pluggable detectors:** regex catalogs (generic, US, EU, FR), NER with GLiNER2, spaCy or Transformers, and an LLM detector, plus exact-match, composite, and chunked detectors (chunking splits long text that overruns a model's context window).
- **Reversible, collision-free placeholders:** opaque tokens like `<<PERSON:1>>`, plus label-only, masked, and keyed-hash factories, all stable across a whole conversation.
- **Agent integrations:** LangChain middleware, Pydantic AI hooks, and LlamaIndex, with de-identification right at the tool boundary and token-by-token streaming restoration.
- **Conversation memory:** in-process, Redis, or SQLAlchemy backends. The Redis backend can encrypt values at rest (AES-GCM) and hash keys (Argon2id).
- **Guard rail:** re-check the model's output for any PII that slipped through and refuse it, backed by a detector, an LLM, or Mistral moderation.
- **TOML/JSON configuration:** build a whole pipeline from one file, with a CLI to validate it and print its schema.
- **HTTP client and OpenTelemetry tracing:** an async client for the companion `piighost-api`, and per-stage spans you can view in any OpenTelemetry backend like Langfuse or Jaeger, with optional payload redaction.
- **Typed and dependency-light:** ships `py.typed` and a minimal core, with everything heavy tucked behind optional extras.

## Why PIIGhost

- **Against plain regex or scrubbing:** regex on its own misses names and shifts boundaries, and deleting or masking PII breaks the model's reasoning. PIIGhost keeps the text coherent with stable, reversible placeholders, then restores the real values for the user and for tools.
- **Against Faker-style fake data:** a finite pool of fakes collides, and a fake can land on a real value, so you can't reliably reverse it. PIIGhost uses synthetic, collision-free tokens instead. Already using Presidio? It plugs in as a detector through the `presidio` extra.

Built for LLM agents: the model only ever sees placeholders, while tools and the end user see the real values.

## Quickstart

```bash
pip install piighost   # or: uv add piighost
```

### De-identify a text

`ExactMatchDetector` de-identifies a dictionary of known values without downloading a model.

```python
import asyncio

from piighost.components.detector import ExactMatchDetector
from piighost.pipeline import AnonymizationPipeline

detector = ExactMatchDetector({"John Doe": "PERSON", "john.doe@example.com": "EMAIL"})
pipeline = AnonymizationPipeline(detector)

result = asyncio.run(pipeline.anonymize("Write to John Doe at john.doe@example.com."))
print(result.text)  # Write to <<PERSON:1>> at <<EMAIL:1>>.
```

### Conversations and agents (LangChain)

The middleware wraps a conversational pipeline and handles every agent turn for you, so the same de-identification applies without any change to your agent logic.

```bash
pip install 'piighost[langchain]'   # or: uv add 'piighost[langchain]'
```

```python
import asyncio

from langchain.agents import create_agent
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool

from piighost.components.detector import ExactMatchDetector
from piighost.integrations.langchain import PIIAnonymizationMiddleware
from piighost.pipeline import ThreadAnonymizationPipeline

SYSTEM_PROMPT = (
    "Some inputs contain placeholders like <<PERSON:1>> that stand in for real "
    "values withheld for privacy. Treat each placeholder as the real value, never "
    "comment on its format, and pass it to tools unchanged."
)


@tool
def send_mail(to: str, body: str) -> str:
    """Send an email to `to` with the given body."""
    print(f"[tool] send_mail received to={to!r}")
    return "Email successfully sent."


async def main() -> None:
    # This example calls OpenAI, so set OPENAI_API_KEY in your environment first.
    labels = {"Patrick Dupont": "PERSON", "patrick@acme.com": "EMAIL"}
    detector = ExactMatchDetector(labels)
    pipeline = ThreadAnonymizationPipeline(detector)
    middleware = PIIAnonymizationMiddleware(pipeline)
    # gpt-5.6-terra is a reasoning model; reasoning_effort="none" lets it call
    # function tools over chat/completions.
    model = init_chat_model("openai:gpt-5.6-terra", reasoning_effort="none")
    # The system prompt tells the model to treat placeholders as real values and
    # pass them to tools unchanged, so it does not balk at the tokens.
    agent = create_agent(
        model=model,
        system_prompt=SYSTEM_PROMPT,
        tools=[send_mail],
        middleware=[middleware],
    )
    config = {"configurable": {"thread_id": "demo-thread"}}

    message = HumanMessage(
        "Use the send_mail tool to send a welcome note to Patrick Dupont at patrick@acme.com."
    )
    result = await agent.ainvoke({"messages": [message]}, config=config)
    print(f"user sees: {result['messages'][-1].content!r}")


if __name__ == "__main__":
    asyncio.run(main())
```

This is the **LangChain** integration, but it is only one option. `piighost` also has connectors for [Pydantic AI](https://athroniaeth.github.io/piighost/examples/pydantic-ai/) and [LlamaIndex](https://athroniaeth.github.io/piighost/examples/llama-index/), and the companion [piighost-api](https://github.com/Athroniaeth/piighost-api) exposes OpenAI- and Anthropic-compatible proxies, so you can move de-identification to the HTTP boundary with only a base URL change.

For a real detector and the conversational pipeline, see the [Quickstart](https://athroniaeth.github.io/piighost/getting-started/quickstart/) and the [LangChain integration](https://athroniaeth.github.io/piighost/examples/langchain/).

## Documentation

**[Full documentation](https://athroniaeth.github.io/piighost/)**

- **Get started**
    - [installation](https://athroniaeth.github.io/piighost/getting-started/installation/)
    - [quickstart](https://athroniaeth.github.io/piighost/getting-started/quickstart/)
    - [first pipeline](https://athroniaeth.github.io/piighost/getting-started/first-pipeline/)
- **How-to**
    - [basic usage](https://athroniaeth.github.io/piighost/examples/basic/)
    - [LangChain integration](https://athroniaeth.github.io/piighost/examples/langchain/)
    - [Pydantic AI integration](https://athroniaeth.github.io/piighost/examples/pydantic-ai/)
    - [ready-made detectors](https://athroniaeth.github.io/piighost/examples/detectors/)
- **Reference**
    - [pipeline](https://athroniaeth.github.io/piighost/reference/pipeline/)
    - [middleware](https://athroniaeth.github.io/piighost/reference/middleware/)
    - [detectors](https://athroniaeth.github.io/piighost/reference/detectors/)
    - [CLI](https://athroniaeth.github.io/piighost/reference/cli/)
- **Concepts**
    - [why de-identify](https://athroniaeth.github.io/piighost/why-anonymize/)
    - [architecture](https://athroniaeth.github.io/piighost/architecture/)
    - [placeholder factories](https://athroniaeth.github.io/piighost/placeholder-factories/)
    - [security](https://athroniaeth.github.io/piighost/security/)

## Project

- **Community**: [Discord](https://discord.gg/vFg9GHQR2s) to get help, report bugs, request features, and discuss de-identification
- **Contributing**: [contribution guide](https://athroniaeth.github.io/piighost/community/contributing/) and [report a bug](https://athroniaeth.github.io/piighost/community/bug-reports/)
- **Ecosystem**:
    - **[Presentation site](https://piighost.athroniaeth.cloud)**: an overview of the project
    - **[piighost-api](https://github.com/Athroniaeth/piighost-api)**: the inference API server
    - **[piighost-chat](https://github.com/Athroniaeth/piighost-chat)**: an example chat interface with human-in-the-loop
- **License**: [MIT](LICENSE)

<h1 align="center">PIIGhost</h1>

<p align="center"><em>Keep PII out of your LLM, and keep your app working.</em></p>

<p align="center">
<a href="https://github.com/Athroniaeth/piighost/actions/workflows/ci.yml"><img src="https://github.com/Athroniaeth/piighost/actions/workflows/ci.yml/badge.svg" alt="CI"></a>
<a href="https://codecov.io/gh/Athroniaeth/piighost"><img src="https://codecov.io/gh/Athroniaeth/piighost/branch/master/graph/badge.svg" alt="codecov"></a>
<a href="https://pypi.org/project/piighost/"><img src="https://img.shields.io/pypi/v/piighost.svg" alt="PyPI version"></a>
<a href="https://pypi.org/project/piighost/"><img src="https://img.shields.io/pypi/pyversions/piighost.svg" alt="Python versions"></a>
<a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-green.svg" alt="License: MIT"></a>
<a href="https://github.com/PyCQA/bandit"><img src="https://img.shields.io/badge/security-bandit-yellow.svg" alt="Security: bandit"></a>
<a href="https://discord.gg/vFg9GHQR2s"><img src="https://img.shields.io/badge/Discord-join-5865F2?logo=discord&amp;logoColor=white" alt="Discord"></a>
</p>

<p align="center">
<a href="https://athroniaeth.github.io/piighost/"><b>Docs</b></a> ·
<a href="https://athroniaeth.github.io/piighost/comparison/"><b>Comparison</b></a> ·
<a href="https://github.com/Athroniaeth/piighost/blob/master/CHANGELOG.md"><b>Changelog</b></a> ·
<a href="https://discord.gg/vFg9GHQR2s"><b>Discord</b></a>
</p>

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

## Why PIIGhost

Most PII tooling stops at detection. Presidio, GLiNER, spaCy, and regex catalogs all find entities in text, and they do it well. The hard part for an LLM agent is everything after detection: swapping values without wrecking the model's reasoning, keeping one value mapped to one token across a conversation, handing tools the real value while the model sees only the token, and putting the originals back in the reply. That orchestration is what PIIGhost is.

**What PIIGhost adds on top:**

- **Pluggable detectors:** regex catalogs (generic, US, EU, FR), NER (GLiNER2, spaCy, Transformers), an LLM detector, plus exact-match, composite, and chunked detectors (chunking splits text that overruns a model's context window), and you keep the one you trust (Presidio plugs in through an extra).
- **Reversible, transparent tokens:** each value becomes a stable id like `<<PERSON:1>>` and is put back automatically, so the end user reads `john.doe@example.com` and never sees a token; label-only, masked, and keyed-hash factories are available too.
- **Consistent across a conversation:** the same value keeps the same token for the whole thread, backed by in-process, Redis, or SQLAlchemy memory (Redis and SQL can encrypt values at rest and hash keys).
- **Agent integrations with a tool boundary:** LangChain middleware, Pydantic AI hooks, and LlamaIndex; the tool receives the real value while the model sees only the token, with token-by-token streaming restoration.
- **A customizable staged pipeline:** detect, link, resolve overlaps, expand, anonymize, and an optional guard rail that refuses a reply with residual PII (a detector, an LLM, or Mistral moderation); swap in fuzzy matching to tolerate typos or add your own stage.
- **Config-driven and self-hostable:** build a whole pipeline from a TOML/JSON file with a CLI to validate it, run it in your process, or as a service through the companion [piighost-api](https://github.com/Athroniaeth/piighost-api) (OpenAI- and Anthropic-compatible proxies).
- **Typed and observable:** ships `py.typed` and a minimal core with everything heavy behind extras, plus OpenTelemetry per-stage spans (viewable in Langfuse or Jaeger) with optional payload redaction.
- **Scope, live text and conversations:** PIIGhost protects a running conversation message by message, not a static dataset.

For how it stacks up against Presidio, LangChain, the cloud APIs, and others, see [How PIIGhost compares](https://athroniaeth.github.io/piighost/comparison/).

### Limitations and trade-offs

- **The token does not embed the encrypted value, on purpose.** Unlike a format-preserving encryption token (where the ciphertext *is* the token, e.g. Google DLP), PIIGhost uses an id (`<<PERSON:1>>`) backed by a cache. The reason: a token that carries the ciphertext can be captured today and cracked in 20 years ("harvest now, decrypt later", the quantum threat to classical crypto), whereas an id reveals nothing on its own. In return, you need a cache to hold the token-to-value mapping, so a memory backend to deploy, share across workers, and persist in production.
- **That cache stores the real values, so reversibility is pseudonymisation, not anonymisation (GDPR).** The real values stay stored for the duration of the conversation. The library gives you the means to protect them (AES-GCM encryption of the values, Argon2id hashing of the keys), but the database architecture itself must be secured in production once you use Redis or PostgreSQL.
- **No dataset anonymization.** No k-anonymity, l-diversity, differential privacy, or tabular data. PIIGhost protects live text and conversations, not a whole dataset; for that, see ARX, Amnesia, or Google DLP.
- **No checksum validation (Luhn / IBAN / NIR), by choice.** The `RegexDetector` matches on shape alone so it never lets a real value mangled by OCR leak (a checksum would reject it and it would pass in clear). In exchange, it sometimes flags a string that only looks like PII, which costs nothing beyond one extra token.

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

<details>
<summary>Browse the docs by section</summary>

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

</details>

## Project

- **Community**: [Discord](https://discord.gg/vFg9GHQR2s) to get help, report bugs, request features, and discuss de-identification
- **Contributing**: [contribution guide](https://athroniaeth.github.io/piighost/community/contributing/) and [report a bug](https://athroniaeth.github.io/piighost/community/bug-reports/)
- **Ecosystem**:
    - **[Presentation site](https://piighost.athroniaeth.cloud)**: an overview of the project
    - **[piighost-api](https://github.com/Athroniaeth/piighost-api)**: the inference API server
    - **[piighost-chat](https://github.com/Athroniaeth/piighost-chat)**: an example chat interface with human-in-the-loop
- **License**: [MIT](LICENSE)

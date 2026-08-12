# PIIGhost

[![CI](https://github.com/Athroniaeth/piighost/actions/workflows/ci.yml/badge.svg)](https://github.com/Athroniaeth/piighost/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/piighost.svg)](https://pypi.org/project/piighost/)
[![Python versions](https://img.shields.io/pypi/pyversions/piighost.svg)](https://pypi.org/project/piighost/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Security: bandit](https://img.shields.io/badge/security-bandit-yellow.svg)](https://github.com/PyCQA/bandit)

`piighost` is a Python library that keeps PII (personally identifiable information) from reaching a language model, while keeping the application fully functional.

The library spots PII with detectors (regex, NER, or another LLM) and replaces each value with a stable placeholder, for example `john.doe@example.com` becomes `<<EMAIL:1>>`. The model only ever works on de-identified text. When the LLM returns placeholders, `piighost` puts the real values back in place, the end user sees `john.doe@example.com` and never notices the de-identification. The same mechanism protects tool-using agents. A tool that needs the real address receives it in clear, while the LLM that decides to call it still sees only `<<EMAIL:1>>`.

Finally, the library keeps the mapping between a value and its placeholder across the whole conversation. If `john.doe@example.com` shows up again three messages later, the placeholder stays `<<EMAIL:1>>`, so the model can follow the thread.

> [!NOTE]
> `piighost` performs **reversible de-identification**. Because the mapping between a value and its placeholder is kept so the data can be restored, this is pseudonymisation under the GDPR, not permanent anonymisation. The real values stay stored for the duration of the conversation and must be protected accordingly.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/assets/deid-chat-dark.gif">
    <img alt="A user chats with an agent: PII values are replaced by placeholders before reaching the model and restored afterwards for the user and for tool calls." src="docs/assets/deid-chat-light.gif" width="760">
  </picture>
</p>

*The LLM only sees placeholders. The tool receives the real address, the user gets a clear-text reply, and your agent code stays the same.*

## Quickstart

```bash
uv add piighost
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

The middleware wraps a conversational pipeline and handles each agent turn. The LLM only sees placeholders, tools receive the real values, the user gets a clear-text reply.

```bash
uv add 'piighost[middleware]'
```

```python
from langchain.agents import create_agent
from piighost.integrations.middleware import PIIAnonymizationMiddleware

# pipeline: a ThreadAnonymizationPipeline, see the conversation guide
agent = create_agent(
    model="openai:gpt-5.4",
    tools=[send_email],
    middleware=[PIIAnonymizationMiddleware(pipeline=pipeline)],
)
```

For a real detector, the conversational pipeline and a full LangChain example, see the [Quickstart](https://athroniaeth.github.io/piighost/getting-started/quickstart/) and the [LangChain integration](https://athroniaeth.github.io/piighost/examples/langchain/).

## Documentation

**[Full documentation](https://athroniaeth.github.io/piighost/)**

- **Get started**
    - [installation](https://athroniaeth.github.io/piighost/getting-started/installation/)
    - [quickstart](https://athroniaeth.github.io/piighost/getting-started/quickstart/)
    - [first pipeline](https://athroniaeth.github.io/piighost/getting-started/first-pipeline/)
- **How-to**
    - [basic usage](https://athroniaeth.github.io/piighost/examples/basic/)
    - [LangChain integration](https://athroniaeth.github.io/piighost/examples/langchain/)
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

- **Contributing**: [contribution guide](https://athroniaeth.github.io/piighost/community/contributing/) and [report a bug](https://athroniaeth.github.io/piighost/community/bug-reports/)
- **Ecosystem**:
    - **[Presentation site](https://piighost.athroniaeth.cloud)**: an overview of the project
    - **[piighost-api](https://github.com/Athroniaeth/piighost-api)**: the inference API server
    - **[piighost-chat](https://github.com/Athroniaeth/piighost-chat)**: an example chat interface with human-in-the-loop
- **License**: [MIT](LICENSE)

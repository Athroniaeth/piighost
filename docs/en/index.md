---
icon: lucide/shield
---

# PIIGhost

`piighost` is a Python library that protects your personal data (PII) in conversations with LLMs through de-identification. Sensitive values are hidden before they are sent, then restored in the response. LangChain, Pydantic AI, LlamaIndex and Claude Code integrations are provided, together with an OpenAI and Anthropic API connector.

This de-identification spots PII with pluggable detectors (regex, NER, LLM) and replaces each value with a placeholder, the token that takes its place. For example:

- `John Doe`{ .pii } becomes `<<PERSON:1>>`{ .placeholder }
- `john.doe@example.com`{ .pii } becomes `<<EMAIL:1>>`{ .placeholder }

This placeholder stays the same from one message to the next with the conversational pipeline, which keeps the mapping between a value and its placeholder across the whole conversation. If `john.doe@example.com`{ .pii } reappears three messages later, the placeholder is still `<<EMAIL:1>>`{ .placeholder }, which lets the LLM follow the thread.

The LLM therefore only receives de-identified text. When it returns placeholders, for example by answering "Hello `<<PERSON:1>>`{ .placeholder }", `piighost` replaces them with the real values. The user sees `John Doe`{ .pii } and never sees the de-identification.

The same mechanism protects agents that call tools. With the LangChain middleware, a tool that needs the real email address receives it in clear, while the LLM that supplies it only writes `<<EMAIL:1>>`{ .placeholder }.

![A user chats with an agent, PII values are replaced by placeholders before reaching the LLM and restored afterwards for the user and for tool calls.](assets/deid-chat-light.svg#only-light)
![A user chats with an agent, PII values are replaced by placeholders before reaching the LLM and restored afterwards for the user and for tool calls.](assets/deid-chat-dark.svg#only-dark)

*Full round trip of an agent request. The user and the tool see the real values, the LLM sees only placeholders.*
{ .figure-caption }

!!! note "Reversible de-identification"
    This retained mapping makes the de-identification a pseudonymization under the GDPR, not a definitive anonymization. With the conversational pipeline, the real values stay stored for the duration of the conversation and must be protected accordingly.

## Why de-identify?

A cloud LLM (GPT, Claude, Gemini) receives every piece of information you send it, including your users' PII. De-identifying upstream decouples the choice of LLM from the sensitivity of the content. When PII never reach the LLM, the provider stops being a confidentiality decision and goes back to being a question of quality, cost, and latency.

To go further:

- [Why de-identify?](why-anonymize.md), the provider spectrum, the legal detail (CLOUD Act, FISA 702, Schrems II) and the use cases
- [How PIIGhost compares](comparison.md), the alternatives and their trade-offs

## Where to start

<div class="grid cards" markdown>

-   :lucide-rocket: __Get started__

    ---

    Install and take `piighost` in hand.

    - [Installation](getting-started/installation.md)
    - [Quickstart](getting-started/quickstart.md)
    - [First pipeline](getting-started/first-pipeline.md)
    - [Conversational pipeline](getting-started/conversation.md)
    - [LangChain middleware](getting-started/langchain.md)

-   :lucide-wrench: __Recipes__

    ---

    Solve a specific task.

    - [Basic usage](examples/basic.md)
    - [LangChain integration](examples/langchain.md)
    - [Pre-built detectors](examples/detectors.md)
    - [Extending PIIGhost](extending.md)
    - [Testing](examples/testing.md)

-   :lucide-book-open: __Reference__

    ---

    The full API documentation.

    - [Anonymizer](reference/anonymizer.md)
    - [Pipeline](reference/pipeline.md)
    - [LangChain](reference/langchain.md)
    - [Detectors](reference/detectors.md)

-   :lucide-layers: __Concepts__

    ---

    Understand the design choices.

    - [Why de-identify?](why-anonymize.md)
    - [Architecture](architecture.md)
    - [Placeholder factories](placeholder-factories.md)
    - [Security](security.md)

</div>

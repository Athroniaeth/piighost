---
icon: lucide/shield
---

# PIIGhost

`piighost` is a Python library that keeps PII (personally identifiable information) from reaching a language model, while keeping the application fully functional.

The library spots PII with detectors (regex, NER, or another LLM) and replaces each value with a stable placeholder, for example `John Doe`{ .pii } becomes `<<PERSON:1>>`{ .placeholder } and `john.doe@example.com`{ .pii } becomes `<<EMAIL:1>>`{ .placeholder }. The model therefore only works on de-identified text. When the LLM returns placeholders, `piighost` reinjects the real values in their place, the end user sees `John Doe`{ .pii } and is never aware of the de-identification. The same mechanism protects tool-using agents. A tool that needs the real address receives it in clear, while the LLM that decides to call it still sees only `<<EMAIL:1>>`{ .placeholder }.

Finally, `piighost` keeps the mapping between a value and its placeholder throughout the conversation. If `john.doe@example.com`{ .pii } reappears three messages later, the placeholder stays `<<EMAIL:1>>`{ .placeholder }, which lets the model follow the thread of the discussion.

!!! note "Reversible de-identification"
    `piighost` keeps the mapping between a value and its placeholder so it can restore the data. Under the GDPR this is pseudonymization, not definitive anonymization. The real values stay stored for the duration of the conversation and must be protected accordingly.

![A user chats with an agent: PII values are replaced by placeholders before reaching the model and restored afterwards for the user and for tool calls.](assets/deid-chat-light.svg#only-light)
![A user chats with an agent: PII values are replaced by placeholders before reaching the model and restored afterwards for the user and for tool calls.](assets/deid-chat-dark.svg#only-dark)

*Full round trip of an agent. The user and the tool see the real values, the LLM sees only placeholders.*
{ .figure-caption }

## Why de-identify?

A hosted LLM (GPT, Claude, Gemini) receives every byte of context you send it, including your users' PII. De-identifying upstream decouples the choice of model from the sensitivity of the content. When PII never reach the model, the provider stops being a confidentiality decision and goes back to being a question of quality, cost, and latency.

The provider spectrum, the legal detail (CLOUD Act, FISA 702, Schrems II), the use cases, and the comparison with alternatives are in [Why de-identify?](why-anonymize.md).

## Where to start

Each page follows a role from the [Diátaxis framework](https://diataxis.fr/), tutorial to learn, recipe to solve a task, reference to consult the API, concept to understand the design choices.

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
    - [Middleware](reference/middleware.md)
    - [Detectors](reference/detectors.md)

-   :lucide-layers: __Concepts__

    ---

    Understand the design choices.

    - [Why de-identify?](why-anonymize.md)
    - [Architecture](architecture.md)
    - [Placeholder factories](placeholder-factories.md)
    - [Security](security.md)

</div>

---
icon: lucide/link
---

# LangChain middleware

Taking the `pipeline` built in [Conversational pipeline](conversation.md), wrap it in `PIIAnonymizationMiddleware` and pass it to `create_agent`:

```python
from langchain.agents import create_agent
from piighost.middleware import PIIAnonymizationMiddleware

middleware = PIIAnonymizationMiddleware(pipeline=pipeline)

agent = create_agent(
    model="openai:gpt-5.4",
    tools=[...],
    middleware=[middleware],
)
```

The middleware intercepts every turn automatically:

- The LLM only sees anonymized text.
- Tools receive the real values.
- Messages shown to the user are deanonymized.

!!! tip "Installation"
    `PIIAnonymizationMiddleware` needs the LangChain extra:

    ```bash
    uv add piighost[langchain]
    ```

    Without it, an explicit `ImportError` is raised at instantiation time.

For a complete example (tools, system prompt, Langfuse observability, Aegra deployment), see [LangChain integration](../examples/langchain.md).

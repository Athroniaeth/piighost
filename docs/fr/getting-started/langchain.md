---
icon: lucide/link
---

# Middleware LangChain

En reprenant le `pipeline` construit dans [Pipeline conversationnel](conversation.md), il suffit de l'enrober dans `PIIAnonymizationMiddleware` et de le passer à `create_agent` :

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

Le middleware intercepte automatiquement chaque tour :

- Le LLM ne voit que du texte anonymisé.
- Les outils reçoivent les vraies valeurs.
- Les messages affichés à l'utilisateur sont désanonymisés.

!!! tip "Installation"
    `PIIAnonymizationMiddleware` nécessite l'extra LangChain :

    ```bash
    uv add piighost[langchain]
    ```

    Sans cet extra, une `ImportError` explicite est levée à l'instanciation.

Pour un exemple complet (outils, system prompt, observabilité Langfuse, déploiement Aegra), voir [Intégration LangChain](../examples/langchain.md).

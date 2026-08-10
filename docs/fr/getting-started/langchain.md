---
icon: lucide/link
---

# Middleware LangChain

Vous allez brancher `PIIAnonymizationMiddleware` dans un agent LangChain pour que le LLM ne voie jamais que des jetons, pendant que vos outils reçoivent les vraies valeurs. L'utilisateur écrit `Patrick habite à Paris.`{ .pii }, le modèle raisonne sur `<<PERSON:1>>`{ .placeholder } et `<<LOCATION:1>>`{ .placeholder }, et un outil de recherche reçoit quand même le vrai `Patrick`{ .pii } pour faire son travail. Vous construisez le middleware au-dessus d'un `ThreadAnonymizationPipeline`, déclarez un outil, puis exécutez un tour.

!!! note "Prérequis"
    `piighost` installé avec l'extra middleware, `pip install piighost[middleware]`, plus un fournisseur LLM configuré pour `create_agent` (ici `openai:...`, donc une `OPENAI_API_KEY`). Le pipeline reprend les composants de la page [Pipeline conversationnel](conversation.md).

## 1. Construire le pipeline de fil

Le middleware enrobe un `ThreadAnonymizationPipeline`, le même que celui de la page [Pipeline conversationnel](conversation.md). Son anonymiseur doit utiliser une fabrique de jetons délimités comme `LabelCounterPlaceholderFactory`, qui émet `<<PERSON:1>>`{ .placeholder }. Le middleware a besoin de cette grammaire pour retrouver un jeton, sinon il lève `UnrecognizableFactoryError` à la construction.

```python
from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import ExactMatchDetector
from piighost.components.linker import ExactEntityLinker
from piighost.components.placeholder import LabelCounterPlaceholderFactory
from piighost.pipeline import ThreadAnonymizationPipeline
from piighost.conversation_memory import InMemoryConversationMemory

detector = ExactMatchDetector({"Patrick": "PERSON", "Paris": "LOCATION"})
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

## 2. Déclarer un outil qui a besoin de la vraie valeur

Un outil qui cherche une personne par son nom a besoin de `Patrick`{ .pii }, pas de `<<PERSON:1>>`{ .placeholder }. Écrivez l'outil comme d'habitude, contre les vraies valeurs. Le middleware les restaure avant l'appel.

```python
from langchain.tools import tool


@tool
def lookup_city(person: str) -> str:
    """Return the city where a person lives."""
    directory = {"Patrick": "Paris"}
    return directory.get(person, "unknown")
```

## 3. Enrober le pipeline dans le middleware

`PIIAnonymizationMiddleware` prend le pipeline. `tool_strategy=ToolCallStrategy.FULL` dé-identifie les arguments de l'outil à l'entrée et anonymise le résultat de l'outil à la sortie, si bien que l'outil travaille sur les vraies valeurs pendant que le modèle continue de ne voir que des jetons.

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

## 4. Exécuter un tour

Le `thread_id` va dans la config LangGraph, sous `configurable`. Le middleware l'y lit et rattache chaque jeton à ce fil.

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

Le message final est dé-identifié pour l'affichage, donc la réponse se lit avec les vraies valeurs :

```text
Patrick habite à Paris.
```

## Comment ça marche

Le middleware est un adaptateur mince autour du pipeline. Avant l'appel du modèle, `abefore_model` fait passer chaque message dans `pipeline.anonymize`, si bien que le LLM reçoit `Où habite <<PERSON:1>> ?` au lieu du vrai nom. Quand le modèle appelle `lookup_city` avec `person="<<PERSON:1>>"`, `awrap_tool_call` sous `ToolCallStrategy.FULL` dé-identifie l'argument en `Patrick`{ .pii } avant d'exécuter l'outil, puis ré-anonymise le résultat texte de l'outil. Après l'appel du modèle, `aafter_model` dé-identifie la réponse pour l'utilisateur. Le `thread_id` garde `<<PERSON:1>>`{ .placeholder } lié à `Patrick`{ .pii } à chaque étape du tour.

Deux valeurs par défaut méritent d'être connues. `require_thread_id=True` fait échouer un appel sans identifiant de fil, plutôt que de router toutes les conversations dans un seul fil partagé et de fuiter les jetons entre elles. `invented_strategy=InventedPlaceholderStrategy.RAISE` refuse un jeton qui apparaît dans la réponse du modèle mais que le pipeline n'a jamais émis, qu'il soit halluciné ou injecté.

## Et ensuite

- Pour choisir un autre comportement d'outil, `INPUT` seul, `OUTPUT` seul ou `PASSTHROUGH`, voir [Stratégies d'appel d'outil](../tool-call-strategies.md).
- Pour un agent complet avec un vrai détecteur, un system prompt, l'observabilité Langfuse et un déploiement Aegra, voir [Intégration LangChain](../examples/langchain.md).
- Pour exécuter le pipeline hors du processus contre un serveur partagé, voir [Client distant](api-client.md).

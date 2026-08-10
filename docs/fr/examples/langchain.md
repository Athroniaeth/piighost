---
icon: lucide/link
tags:
  - LangChain
  - Middleware
---

# Construire un agent LangChain avec un vrai détecteur

Vous voulez un agent LangGraph qui fonctionne, où le LLM ne voit jamais que des jetons, où un outil reçoit quand même les vraies valeurs dont il a besoin, et où la détection tourne sur un vrai modèle NER plutôt que sur une liste de valeurs figée. Cette page assemble cet agent de bout en bout. Un détecteur GLiNER2, un `ThreadAnonymizationPipeline`, `PIIAnonymizationMiddleware`, un system prompt qui apprend au modèle à traiter les jetons comme des données, et un outil qui cherche une personne par son nom.

Pour la version minimale avec un détecteur bouchon, commencez par le tutoriel [Middleware LangChain](../getting-started/langchain.md). Cette page en reprend la forme avec un vrai modèle et un system prompt.

!!! note "Prérequis"
    `piighost` installé avec les extras middleware et gliner2, `pip install piighost[middleware,gliner2]`, plus un fournisseur LLM configuré pour `create_agent` (ici `openai:...`, donc une `OPENAI_API_KEY`). La première exécution télécharge les poids de GLiNER2, environ 500 Mo.

## 1. Construire le pipeline sur un détecteur GLiNER2

`Gliner2Detector` enrobe un modèle GLiNER2. Passez l'identifiant du modèle sous forme de chaîne et il se charge à la construction. Passez `labels` pour lui indiquer quels types d'entités interroger. L'anonymiseur utilise `LabelCounterPlaceholderFactory`, qui émet le jeton délimité `<<PERSON:1>>`{ .placeholder } que le middleware sait retrouver.

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

## 2. Déclarer un outil qui a besoin de la vraie valeur

Un outil qui cherche une personne par son nom a besoin de `Patrick`{ .pii }, pas de `<<PERSON:1>>`{ .placeholder }. Écrivez-le contre les vraies valeurs. Sous `ToolCallStrategy.FULL`, le middleware restaure l'argument avant l'appel et ré-anonymise le résultat après.

```python
from langchain.tools import tool


@tool
def lookup_city(person: str) -> str:
    """Return the city where a person lives."""
    directory = {"Patrick": "Paris"}
    return directory.get(person, "unknown")
```

## 3. Dire au modèle que les jetons sont des données

Le modèle raisonne sur `<<PERSON:1>>`{ .placeholder } au lieu d'un nom. Un court system prompt l'empêche de commenter le jeton ou de refuser de le passer à un outil.

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

## 4. Enrober le pipeline et créer l'agent

`PIIAnonymizationMiddleware` prend le pipeline. `tool_strategy=ToolCallStrategy.FULL` dé-identifie les arguments de l'outil à l'entrée et anonymise le résultat de l'outil à la sortie, si bien que l'outil travaille sur les vraies valeurs pendant que le modèle continue de ne voir que des jetons.

```python
from langchain.agents import create_agent
from piighost.integrations.middleware import (
    PIIAnonymizationMiddleware,
    ToolCallStrategy,
)

agent = create_agent(
    model="openai:gpt-4o",
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

## 5. Exécuter un tour

Le `thread_id` va dans la config LangGraph, sous `configurable`. Le middleware l'y lit et rattache chaque jeton à ce fil.

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

La réponse est dé-identifiée pour l'affichage, donc elle se lit avec les vraies valeurs :

```text
Patrick lives in Paris.
```

## Qui voit quoi

GLiNER2 marque `Patrick`{ .pii } comme `PERSON` dans le message entrant. À partir de là, chaque frontière du tour substitue une direction.

- `abefore_model` fait passer le message dans `pipeline.anonymize`, si bien que le LLM reçoit `Where does <<PERSON:1>> live?`.
- Le modèle appelle `lookup_city(person="<<PERSON:1>>")`. Sous `ToolCallStrategy.FULL`, `awrap_tool_call` dé-identifie l'argument en `Patrick`{ .pii } avant d'exécuter l'outil, puis ré-anonymise le résultat texte de l'outil.
- `aafter_model` dé-identifie la réponse pour l'utilisateur.

Le `thread_id` garde `<<PERSON:1>>`{ .placeholder } lié à `Patrick`{ .pii } à chaque étape.

## Et ensuite

- Pour choisir un autre comportement d'outil, `INPUT` seul, `OUTPUT` seul ou `PASSTHROUGH`, voir [Stratégies d'appel d'outil](../tool-call-strategies.md).
- Pour remplacer GLiNER2 par spaCy, un pack regex ou votre propre détecteur, voir [Étendre PIIGhost](../extending.md).
- Pour exécuter le pipeline hors du processus contre un serveur partagé, voir [Client distant](../getting-started/api-client.md).

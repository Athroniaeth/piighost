---
icon: lucide/bot
tags:
  - Pydantic AI
---

# Faire tourner un agent Pydantic AI derrière PIIGhost

Vous voulez un agent Pydantic AI où le modèle ne voit jamais que des jetons, jamais les vrais noms de la conversation, et où une valeur garde le même jeton d'un tour à l'autre. Cette page assemble cet agent de bout en bout avec un détecteur GLiNER2, un `ThreadAnonymizationPipeline`, et `pii_hooks`, la capability qui dé-identifie autour du modèle.

La capability couvre les messages, le prompt utilisateur et les réponses du modèle lui-même, et le boundary des outils aussi. Sous la stratégie par défaut, un outil reçoit les vraies valeurs pendant que le modèle continue de travailler sur des jetons.

!!! note "Prérequis"
    `piighost` installé avec les extras pydantic-ai et gliner2, `pip install piighost[pydantic-ai,gliner2]`, plus une clé OpenAI dans `OPENAI_API_KEY`. La première exécution télécharge les poids de GLiNER2, environ 500 Mo.

## 1. Construire le pipeline sur un détecteur GLiNER2

`Gliner2Detector` enrobe un modèle GLiNER2. Passez l'identifiant du modèle sous forme de chaîne et il se charge à la construction. Passez `labels` pour lui indiquer quels types d'entités interroger. Seul le détecteur est requis, car le pipeline de thread fournit par défaut son linker, son anonymiseur, et un stockage de conversation en mémoire. L'anonymiseur par défaut émet le jeton délimité `<<PERSON:1>>`{ .placeholder } que `pii_hooks` sait retrouver.

```python
from piighost.components.detector.ner import Gliner2Detector
from piighost.pipeline import ThreadAnonymizationPipeline

detector = Gliner2Detector(
    "fastino/gliner2-multi-v1",
    labels=["PERSON", "LOCATION"],
    threshold=0.5,
)
pipeline = ThreadAnonymizationPipeline(detector)
```

## 2. Attacher la capability à l'agent

`pii_hooks` prend le pipeline et un identifiant de thread, puis renvoie une capability Pydantic AI. Enregistrez-la avec `capabilities=[...]`. L'identifiant de thread cadre les jetons, une valeur garde donc un seul jeton pour toute la conversation. C'est une chaîne fixe ici. Passez un appelable sur le contexte d'exécution, par exemple `lambda ctx: ctx.deps.thread_id`, pour le lire à chaque exécution.

```python
from pydantic_ai import Agent
from piighost.integrations.pydantic_ai import pii_hooks

hooks = pii_hooks(pipeline, "thread-42")
agent = Agent("openai:gpt-5.5", capabilities=[hooks])
```

## 3. Lancer un tour

La capability anonymise le prompt avant que le modèle ne le lise et désanonymise la réponse pour l'affichage, le modèle travaille donc sur `<<PERSON:1>>`{ .placeholder } pendant que vous lisez `Patrick`{ .pii }.

```python
import asyncio


async def main() -> None:
    result = await agent.run("Where does Patrick live?")
    print(result.output)


asyncio.run(main())
```

## Qui voit quoi

`GLiNER2` repère `Patrick`{ .pii } comme `PERSON` dans le message entrant. À partir de là, la capability substitue un sens de chaque côté de l'appel au modèle :

- `before_model_request` fait passer chaque texte utilisateur et assistant par `pipeline.anonymize`, le modèle reçoit donc `Where does <<PERSON:1>> live?`. Elle réécrit aussi les textes de l'assistant, une valeur restaurée pour l'affichage à un tour précédent est donc ré-anonymisée avant l'appel suivant et ne refuit jamais dans l'historique.
- `after_model_request` fait passer la réponse par `pipeline.deanonymize`, vous lisez donc la vraie valeur.

Le `thread_id` garde `<<PERSON:1>>`{ .placeholder } lié à `Patrick`{ .pii } à chaque tour.

## Les jetons que le modèle invente

Après la désanonymisation, chaque jeton émis est revenu à sa valeur, un jeton qui suit encore la grammaire a donc été inventé par le modèle, par hallucination ou par injection de prompt. `pii_hooks` prend un `invented_strategy` qui décide de ce qui se passe alors. `RAISE` le refuse, le défaut fail-closed ; `KEEP` le laisse ; `DROP` le retire.

```python
from piighost.integrations.middleware import InventedPlaceholderStrategy

hooks = pii_hooks(
    pipeline,
    "thread-42",
    invented_strategy=InventedPlaceholderStrategy.DROP,
)
```

## Appels d'outils

`pii_hooks` dé-identifie aussi le boundary des outils, piloté par `tool_strategy`, le même enum que le middleware LangChain. Sous `FULL`, le défaut, les arguments d'un appel d'outil sont désanonymisés avant l'exécution, un outil qui a besoin de `Patrick`{ .pii } le reçoit et non `<<PERSON:1>>`{ .placeholder }, et le résultat texte de l'outil est ré-anonymisé avant que le modèle ne le lise, le modèle continue donc de voir des jetons. `INPUT` ne désanonymise que les arguments, `OUTPUT` ne ré-anonymise que le résultat, et `PASSTHROUGH` ne touche à rien.

```python
from piighost.integrations.middleware import ToolCallStrategy

hooks = pii_hooks(pipeline, "thread-42", tool_strategy=ToolCallStrategy.FULL)
```

## Valeurs de l'assistant

Toute valeur n'est pas une PII utilisateur. Quand le modèle introduit lui-même une valeur tirée de sa connaissance du monde, la tokeniser la lui cacherait au tour suivant sans rien protéger côté utilisateur. `assistant_strategy` décide du sort d'une valeur introduite par l'assistant, encore le même enum que le middleware. Sous `PRESERVE`, le défaut, elle reste en clair, le modèle garde donc sa propre connaissance et seule une PII utilisateur connue est tokenisée. `ANONYMIZE` la tokenise quand même, et `IGNORE` saute entièrement les messages de l'assistant, économisant le détecteur.

```python
from piighost.integrations.middleware import AssistantEntityStrategy

hooks = pii_hooks(
    pipeline,
    "thread-42",
    assistant_strategy=AssistantEntityStrategy.ANONYMIZE,
)
```

## Et ensuite

- Pour comparer avec le middleware d'agent LangChain, voyez l'[intégration LangChain](langchain.md).
- Pour remplacer GLiNER2 par spaCy, un pack de regex, ou votre propre détecteur, voyez [Étendre PIIGhost](../extending.md).
- Les scripts exécutables sont dans `examples/pydantic_ai/base.py` (messages) et `examples/pydantic_ai/tools.py` (un outil).

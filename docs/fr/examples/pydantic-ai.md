---
icon: lucide/bot
tags:
  - Pydantic AI
---

# Intégration Pydantic AI

Vous voulez un agent Pydantic AI où le modèle ne voit jamais que des jetons, jamais les vrais noms de la conversation, et où une valeur garde le même jeton d'un tour à l'autre. Cette page assemble cet agent de bout en bout avec un détecteur GLiNER2, un `ThreadAnonymizationPipeline`, et `pii_hooks`, la capability qui dé-identifie autour du modèle.

La capability couvre les messages, le prompt utilisateur et les réponses du modèle lui-même. Elle couvre aussi la frontière des outils, c'est-à-dire les appels d'outils et leurs résultats. Sous la stratégie par défaut, un outil reçoit les vraies valeurs pendant que le modèle continue de travailler sur des jetons.

!!! note "Prérequis"
    `piighost` installé avec les extras pydantic-ai et gliner2, `pip install "piighost[pydantic-ai,gliner2]"`, plus une clé OpenAI dans `OPENAI_API_KEY`. La première exécution télécharge les poids de GLiNER2, environ 500 Mo.

## 1. Construire le pipeline sur un détecteur GLiNER2

`Gliner2Detector` enrobe un modèle GLiNER2. Passez l'identifiant du modèle sous forme de chaîne et il se charge à la construction. Passez `labels` pour lui indiquer quels types d'entités interroger. Seul le détecteur est requis, car le pipeline de conversation fournit par défaut son linker, son anonymiseur, et un stockage de conversation en mémoire. L'anonymiseur par défaut émet le jeton délimité `<<PERSON:1>>`{ .placeholder } que `pii_hooks` sait retrouver.

```python
--8<-- "snippets/pydantic_ai_pipeline.py"
```

## 2. Attacher la capability à l'agent

`pii_hooks` prend le pipeline et un identifiant de conversation, puis renvoie une capability Pydantic AI. Enregistrez-la avec `capabilities=[...]`. Chaque identifiant de conversation a ses propres jetons. Une valeur garde donc un seul jeton pour toute la conversation. C'est une chaîne fixe ici. Passez un appelable sur le contexte d'exécution, par exemple `lambda ctx: ctx.deps.thread_id`, pour le lire à chaque exécution.

```python
--8<-- "snippets/pydantic_ai_agent.py:agent"
```

## 3. Lancer un tour

La capability dé-identifie le prompt avant que le modèle ne le lise, et restaure la réponse pour l'affichage. Le modèle travaille donc sur `<<PERSON:1>>`{ .placeholder } pendant que vous lisez `Patrick`{ .pii }.

```python
--8<-- "snippets/pydantic_ai_agent.py:run"
```

La réponse est restaurée pour l'affichage. Sa formulation dépend du modèle, par exemple :

```text
--8<-- "snippets/pydantic_ai_agent.out"
```

## Qui voit quoi

`GLiNER2` repère `Patrick`{ .pii } comme `PERSON` dans le message entrant. À partir de là, la capability remplace dans un sens avant l'appel au modèle, et dans l'autre sens après :

- `before_model_request` fait passer chaque texte utilisateur et assistant par `pipeline.anonymize`. Le modèle reçoit donc `Where does <<PERSON:1>> live?`. Ce hook réécrit aussi les textes de l'assistant. Une valeur restaurée pour l'affichage à un tour précédent est donc dé-identifiée à nouveau avant l'appel suivant, et ne réapparaît jamais en clair dans l'historique.
- `after_model_request` fait passer la réponse par `pipeline.deanonymize`, vous lisez donc la vraie valeur.

Le `thread_id` garde `<<PERSON:1>>`{ .placeholder } lié à `Patrick`{ .pii } à chaque tour.

## Les jetons que le modèle invente

Après la restauration, chaque jeton émis est revenu à sa valeur. Un texte qui a encore la forme d'un jeton a donc été inventé par le modèle, par hallucination ou par injection de prompt. `pii_hooks` prend un `invented_strategy` qui décide de ce qui se passe alors. `RAISE` le refuse. C'est le défaut, qui bloque plutôt que de laisser passer. `KEEP` le laisse. `DROP` le retire.

```python
--8<-- "snippets/pydantic_ai_agent.py:invented"
```

## Appels d'outils

`pii_hooks` traite aussi la frontière des outils. `tool_strategy` la pilote, avec le même enum que le middleware LangChain. Sous `FULL`, le défaut, les arguments d'un appel d'outil sont restaurés avant l'exécution. Un outil qui a besoin de `Patrick`{ .pii } le reçoit donc, et non `<<PERSON:1>>`{ .placeholder }. Le résultat texte de l'outil est dé-identifié à nouveau avant que le modèle ne le lise, et le modèle continue donc de voir des jetons. `INPUT` ne restaure que les arguments, `OUTPUT` ne dé-identifie à nouveau que le résultat, et `PASSTHROUGH` ne touche à rien.

```python
--8<-- "snippets/pydantic_ai_agent.py:tools"
```

## Valeurs de l'assistant

Toute valeur n'est pas une donnée confidentielle de l'utilisateur. Le modèle introduit parfois lui-même une valeur tirée de sa connaissance du monde. La dé-identifier cacherait cette valeur au modèle au tour suivant, sans rien protéger côté utilisateur. `assistant_strategy` décide du sort d'une valeur introduite par l'assistant, avec encore le même enum que le middleware. Sous `PRESERVE`, le défaut, la valeur reste en clair. Le modèle garde donc sa propre connaissance, et seule une valeur utilisateur connue est dé-identifiée. `ANONYMIZE` la dé-identifie quand même. `IGNORE` saute entièrement les messages de l'assistant, et le détecteur ne tourne donc pas sur eux.

```python
--8<-- "snippets/pydantic_ai_agent.py:assistant"
```

## Voir aussi

- Pour comparer avec le middleware d'agent LangChain, voyez l'[intégration LangChain](langchain.md).
- Pour remplacer GLiNER2 par spaCy, un pack de regex, ou votre propre détecteur, voyez [Étendre piighost](../extending.md).
- Les scripts exécutables sont dans `examples/pydantic_ai/base.py` (messages) et `examples/pydantic_ai/tools.py` (un outil).

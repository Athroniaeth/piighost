# Anonymisation selon la provenance : design

Date : 2026-08-03
Statut : approuvé, prêt pour le plan d'implémentation

## Contexte et objectif

Le middleware anonymise aujourd'hui les messages user et IA de façon uniforme.
Une entité que c'est l'IA qui a introduite (par exemple une figure publique
comme Napoléon, nommée par le modèle) n'est pas de la PII utilisateur. La
tokeniser ne protège rien, et surtout prive le modèle de sa connaissance du
monde : il raisonne sur un jeton opaque au lieu de l'entité qu'il connaît.

Objectif : ne pas anonymiser une valeur dont la première occurrence dans un
thread vient d'un message assistant. Une valeur dite d'abord par l'utilisateur
reste anonymisée, même si l'IA la répète ensuite.

## Règle de provenance

La provenance d'une valeur est le rôle de sa première occurrence dans le thread,
en ordre first-seen, l'ordre que la mémoire de conversation maintient déjà.

- Première occurrence assistant : la valeur n'est jamais anonymisée, quel que
  soit son label.
- Première occurrence user : la valeur est anonymisée, même répétée ensuite par
  l'IA.

La règle first-seen est sûre : elle ne peut pas laisser fuiter une PII
utilisateur que l'IA aurait seulement répétée, puisque la première occurrence
reste alors l'utilisateur.

Les rôles sont binaires : USER pour un HumanMessage, ASSISTANT pour un
AIMessage. Les ToolMessage sont hors périmètre v1 et comptent comme USER.

## Stratégie AssistantEntityStrategy

Un enum sur le middleware, dans la lignée de ToolCallStrategy et
InventedPlaceholderStrategy. Elle se traduit uniquement par le rôle que le
middleware transmet au pipeline. Le pipeline, lui, préserve toujours une valeur
de provenance assistant : c'est le rôle transmis qui décide, pas un drapeau côté
pipeline.

| Stratégie | Messages IA | Effet sur une valeur introduite par l'IA |
|---|---|---|
| PRESERVE (défaut) | analysés, rôle ASSISTANT | laissée en clair |
| ANONYMIZE | analysés, rôle USER | anonymisée comme une PII user |
| IGNORE | non analysés | non suivie, économie de détecteur ; anonymisée si l'user la dit ensuite |

PRESERVE est le comportement voulu par défaut. ANONYMIZE reproduit le
comportement historique en marquant les valeurs IA comme USER, donc
anonymisables. IGNORE sort les AIMessage de l'ensemble analysé, ce qui économise
le détecteur au prix de la non-anonymisation des messages IA.

## Architecture et composants

### MessageRole

Un enum dans conversation_memory/base.py, exporté depuis le package.

```python
class MessageRole(Enum):
    USER = "user"
    ASSISTANT = "assistant"
```

### Mémoire de conversation

Le port AnyConversationMemory et ses adaptateurs (InMemory, Redis) gagnent le
rôle par message et un accès à la provenance.

- `remember(thread_id, message, detections, role: MessageRole = MessageRole.USER)`.
  Le défaut USER laisse les appelants directs inchangés.
- `get_provenance(thread_id) -> Mapping[str, MessageRole]` : par valeur
  (text.casefold()), le rôle de sa première occurrence en ordre first-seen.
- `get_detections` et `forget` inchangées.

InMemory stocke par message un couple (role, detections). Redis stocke le rôle
dans le blob chiffré, `{"role": role.value, "detections": [...]}` ;
`get_provenance` parcourt l'index du thread dans l'ordre et lit chaque rôle.

`get_provenance` se calcule en parcourant les messages en ordre d'insertion
(l'ordre first-seen), et pour chaque détection, en enregistrant le rôle du
message si la valeur casefold n'a pas déjà été vue.

### Pipeline (ThreadAnonymizationPipeline)

- `anonymize(text, thread_id, role: MessageRole = MessageRole.USER)`. `_detect`
  transmet le rôle à `remember`.
- `_thread_tokens` retire les entités de provenance assistant avant
  d'assigner les tokens :

```python
async def _thread_tokens(self, thread_id):
    union = await self.memory.get_detections(thread_id) or []
    entities = self.linker.link(union)
    thread_entities = self._resolve_entities(entities)
    provenance = await self.memory.get_provenance(thread_id)
    anonymizable = [
        entity
        for entity in thread_entities
        if provenance.get(entity.text.casefold()) is not MessageRole.ASSISTANT
    ]
    return self.anonymizer.create(anonymizable)
```

- Au rendu, `message_tokens` n'inclut que les entités ayant reçu un token, donc
  les valeurs préservées restent en clair et rien n'est à désanonymiser :

```python
message_tokens = {
    entity: token_of[entity.detections[0]]
    for entity in message_entities
    if entity.detections[0] in token_of
}
```

- L'ensemble des valeurs préservées du message (entités sans token) est passé au
  guard (voir plus bas).

### Middleware

- `assistant_strategy: AssistantEntityStrategy = AssistantEntityStrategy.PRESERVE`.
- `abefore_model` mappe le rôle par type de message et le transmet à
  `anonymize`. Sous IGNORE, les AIMessage sortent de l'ensemble analysé. Sous
  ANONYMIZE, un AIMessage est passé avec le rôle USER ; sous PRESERVE, avec
  ASSISTANT. Un HumanMessage est toujours USER.
- `_rewrite` est ajusté pour donner le message (donc son type, donc le rôle) à
  la transform, au lieu de son seul contenu. `aafter_model` continue de lire
  `message.content` et ignore le rôle.
- `_anonymize` gagne un paramètre `role` transmis à `pipeline.anonymize`.

### Interaction avec le guard

Une valeur préservée reste en clair dans le texte rendu, donc un détecteur-guard
la re-détecterait et lèverait PIIRemainingError. `_guard` reçoit l'ensemble des
valeurs préservées attendues et écarte du verdict les détections résiduelles qui
les matchent :

```python
async def _guard(self, text, expected: frozenset[str] = frozenset()) -> None:
    if self.guard is None:
        return
    verdict = await self.guard.check(text)
    if verdict.detections:
        residual = tuple(
            detection
            for detection in verdict.detections
            if detection.text.casefold() not in expected
        )
        if not residual:
            return
        verdict = replace(verdict, detections=residual)
    if verdict.flagged:
        raise _pii_remaining(verdict)
```

Le pipeline de base (AnonymizationPipeline) appelle `_guard(text)` sans
`expected`, donc son comportement est inchangé. Limitation documentée : un guard
par score (modération ou LLM) ne localise pas ses détections, donc une valeur
préservée ne peut pas être écartée finement de son verdict.

## Flux de données, le scénario Napoléon

Sous PRESERVE, thread t1 :

1. user « qui a fait la campagne d'Égypte ? » : aucune détection.
2. ai « c'est Napoléon ! » : au tour suivant, `abefore_model` parcourt
   l'historique dans l'ordre. Le message IA est détecté et remembered avec le
   rôle ASSISTANT avant le message user courant. `get_provenance` renvoie
   napoléon vers ASSISTANT, l'entité est retirée de l'assignation, le texte
   reste « c'est Napoléon ! ».
3. user « qu'a fait Napoléon ? » : napoléon a déjà pour provenance ASSISTANT
   (première occurrence, le message IA), l'entité est retirée, le texte reste en
   clair. Le modèle voit « Napoléon », pas un jeton.

Cas inverse, user d'abord : si l'utilisateur dit « mon ami Napoléon » avant que
l'IA ne le mentionne, la première occurrence est USER, la valeur est anonymisée,
même répétée par l'IA.

## Cas limites

- Ordre first-seen : `abefore_model` re-parcourt l'historique complet à chaque
  tour, dans l'ordre chronologique. La mémoire, clé par texte de message et à
  ordre d'insertion stable, préserve la première occurrence. Re-remember d'un
  message déjà connu remplace son entrée sans changer sa position.
- Timing intra-appel : dans `anonymize`, l'ordre est détecter, remember (avec le
  rôle), puis `get_provenance` qui inclut donc le message courant. Un message IA
  qui introduit une valeur la voit bien préservée dès son propre rendu.
- Appelants directs : `role=USER` par défaut, donc aucun comportement de
  préservation ne se déclenche sans passer explicitement ASSISTANT.
- Value avec deux labels : la provenance est indexée par valeur casefold, ce qui
  suffit au v1 ; le cas d'une même valeur sous deux labels n'est pas distingué.

## Tests

Data-driven (constantes de cas plus parametrize, règle 12) et layout
conformance puis comportement (règle 22).

- Mémoire : `get_provenance` premier-gagne (user-first, assistant-first, ordre
  mixte sur plusieurs messages) ; rôle stocké et relu ; round-trip Redis avec le
  rôle ; `forget` inchangé.
- Pipeline : valeur assistant-first préservée (aucun token émis pour elle),
  valeur user-first anonymisée, séquence user-puis-assistant reste anonymisée,
  séquence assistant-puis-user reste en clair, `role=USER` par défaut inchangé.
- Middleware : mapping des rôles par type de message, les trois stratégies sur
  le scénario Napoléon bout-en-bout avec le modèle factice scripté, IGNORE
  n'analyse pas les AIMessage.
- Guard : un détecteur-guard ne flague pas une valeur préservée ; une PII
  résiduelle réelle est toujours flaguée.

## Fichiers touchés

- src/piighost/conversation_memory/base.py : MessageRole, port remember et
  get_provenance.
- src/piighost/conversation_memory/memory.py : InMemory.
- src/piighost/conversation_memory/redis_backend.py : Redis.
- src/piighost/conversation_memory/__init__.py : export MessageRole.
- src/piighost/pipeline/thread.py : role, filtre `_thread_tokens`, exemption
  guard.
- src/piighost/pipeline/base.py : `_guard` paramètre `expected`.
- src/piighost/integrations/middleware/strategy.py : AssistantEntityStrategy.
- src/piighost/integrations/middleware/langchain.py : assistant_strategy,
  mapping des rôles, refactor `_rewrite`, `_anonymize` role.
- src/piighost/integrations/middleware/__init__.py : export.
- tests des trois zones (conversation_memory, pipeline, middleware).
- tests/regression/test_imports.py : PUBLIC_API pour MessageRole et
  AssistantEntityStrategy.
- design/rewrite-blueprint.md : entrée du journal de décisions.
- examples/langchain_assistant_provenance.py : scénario Napoléon sur les trois
  stratégies.

## Hors périmètre v1 (YAGNI)

- Provenance des ToolMessage.
- Scoping par label (tous les labels sont couverts).
- Exemption fine d'un guard par score.
- Exposition de la stratégie en config TOML.
- Retry LLM sur placeholder inventé (stratégie distincte déjà notée).
- Docs bilingues, pas encore en place sur la v2.

## Critères de succès

- Le scénario Napoléon se comporte correctement sur les trois stratégies.
- `role=USER` par défaut ne change aucun comportement existant.
- Suite complète verte, ruff, pyrefly et bandit propres.

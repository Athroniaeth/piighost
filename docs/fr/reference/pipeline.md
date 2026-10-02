---
icon: lucide/database
---

# Référence Pipeline

Un pipeline enchaîne les étages qui transforment un texte en texte dé-identifié, et l'inverse. `AnonymizationPipeline` traite un seul texte, sans mémoire d'un appel à l'autre. `ThreadAnonymizationPipeline` traite une conversation, en gardant un jeton par valeur sur tous ses messages.

Les deux renvoient une [`Anonymization`](anonymizer.md#anonymization), le texte dé-identifié associé au jeton qui a remplacé chaque entité.

!!! note "Dé-identification, pas anonymisation"
    Les pipelines par défaut gardent la correspondance entre une valeur et son jeton pour pouvoir restaurer la valeur. C'est une pseudonymisation réversible. Le mot anonymisation reste réservé à une suppression irréversible.

---

## `AnonymizationPipeline`

Module : `piighost.pipeline`

Dé-identifie un seul texte à travers les étages, dans l'ordre. Détecter les données confidentielles, appliquer l'override du serveur, résoudre les spans qui se chevauchent, retrouver les occurrences manquées, grouper les détections en entités, résoudre les conflits d'entités, remplacer par des jetons, puis revérifier avec un guard. Chaque appel à `anonymize()` est indépendant.

### Constructeur

```python
AnonymizationPipeline(
    detector: AnyDetector,
    linker: AnyEntityLinker | None = None,
    anonymizer: AnyAnonymizer[PreservationT] | None = None,
    overlap_resolver: AnyOverlapResolver | None = None,
    expander: AnyDetectionExpander | None = None,
    entity_resolver: AnyEntityResolver | None = None,
    guard: AnyGuardRail | None = None,
    observation_redactor: AnyPlaceholderFactory | None = None,
    override: AnyDetectionOverride | None = None,
    trace_clear_text: bool = False,
)
```

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `detector` | `AnyDetector` | requis | Détecteur d'entités async |
| `linker` | `AnyEntityLinker \| None` | `None` | Groupe les détections en entités. Par défaut `ExactEntityLinker()` |
| `anonymizer` | `AnyAnonymizer[PreservationT] \| None` | `None` | Moteur de remplacement et sa placeholder factory. Par défaut `Anonymizer(LabelCounterPlaceholderFactory())` |
| `overlap_resolver` | `AnyOverlapResolver \| None` | `None` | Résout les détections qui se chevauchent. Par défaut `ConfidenceOverlapResolver()`, car l'étape de rendu a besoin de spans disjoints |
| `expander` | `AnyDetectionExpander \| None` | `None` | Ajoute les occurrences manquées d'une valeur détectée. Désactivé quand `None` |
| `entity_resolver` | `AnyEntityResolver \| None` | `None` | Réconcilie les entités en conflit. Désactivé quand `None` |
| `guard` | `AnyGuardRail \| None` | `None` | Revérifie la sortie pour des valeurs confidentielles résiduelles. Désactivé quand `None` |
| `observation_redactor` | `AnyPlaceholderFactory \| None` | `None` | Placeholder factory remplaçant les valeurs en clair dans les payloads d'observation. `None` trace le texte en clair, ce qui permet aux traces de servir de jeux d'annotation. Avec un tracer actif et sans masqueur, le constructeur émet un `PIIGhostSecurityWarning` sauf si `trace_clear_text=True` l'acquitte |
| `override` | `AnyDetectionOverride \| None` | `None` | Whitelist et blacklist du serveur imposées à chaque ensemble de détections. Désactivé quand `None` |
| `trace_clear_text` | `bool` | `False` | Acquitte le traçage en clair de l'observation pour supprimer l'avertissement de sécurité quand aucun `observation_redactor` n'est défini |

!!! note "Les composants sont des protocoles"
    `AnyDetector`, `AnyEntityLinker`, `AnyAnonymizer`, `AnyOverlapResolver`, `AnyDetectionExpander`, `AnyEntityResolver`, `AnyGuardRail`, `AnyDetectionOverride`. Toute implémentation du protocole est acceptée. Voir [Étendre PIIGhost](../extending.md).

### Méthodes

#### `anonymize(text) -> Anonymization` *(async)*

Exécute le pipeline complet et renvoie le texte dé-identifié avec le jeton utilisé pour chaque entité.

**Lève** `PIIRemainingError` quand un guard configuré signale des valeurs confidentielles restées dans la sortie.

```python
--8<-- "snippets/reference_pipeline.py:anonymize"
```

#### `deanonymize(text, tokens) -> str`

Renvoie le texte avec chaque jeton connu remplacé par la valeur de son entité. `tokens` est la correspondance issue d'une `Anonymization`, lue à l'envers. Les jetons absents de la correspondance sont laissés intacts.

La restauration n'est sans ambiguïté que si les jetons préservent l'identité, car deux entités partageant un même jeton se confondent en une seule valeur.

```python
--8<-- "snippets/reference_pipeline.py:deanonymize"
```

---

## `ThreadAnonymizationPipeline`

Module : `piighost.pipeline`

Dé-identifie chaque message d'une conversation avec des jetons stables sur toute la conversation. Une valeur vue dans un premier message puis à nouveau plus tard porte le même jeton, car les jetons sont assignés sur l'union des détections de tous les messages, pas sur un message seul. Les détections de chaque message sont mises en cache dans la mémoire, donc renvoyer un message évite la détection.

Le composant en plus est une mémoire de conversation, `memory`, le stockage par conversation des détections de chaque message.

### Constructeur

```python
ThreadAnonymizationPipeline(
    detector: AnyDetector,
    linker: AnyEntityLinker | None = None,
    anonymizer: AnyAnonymizer[PreservationT] | None = None,
    memory: AnyConversationMemory | None = None,
    overlap_resolver: AnyOverlapResolver | None = None,
    expander: AnyDetectionExpander | None = None,
    entity_resolver: AnyEntityResolver | None = None,
    guard: AnyGuardRail | None = None,
    observation_redactor: AnyPlaceholderFactory | None = None,
    override: AnyDetectionOverride | None = None,
    trace_clear_text: bool = False,
    token_memo_ttl: float | None = None,
    time_source: Callable[[], float] = time.monotonic,
)
```

En plus de tous les paramètres de `AnonymizationPipeline` :

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `memory` | `AnyConversationMemory \| None` | `None` | Stockage par conversation des détections de chaque message. Par défaut `InMemoryConversationMemory()` pour un seul processus, passez `RedisConversationMemory` pour un backend partagé |
| `token_memo_ttl` | `float \| None` | `None` | Secondes pendant lesquelles la correspondance de jetons mémoïsée d'une conversation est gardée. Ce mémo garde les valeurs de la conversation en clair et `forget_thread` n'atteint que le processus où il tourne, donc sur un déploiement multi-worker ce délai borne combien de temps les autres workers le gardent. `None` garde une entrée jusqu'à ce que la borne de taille l'évince |
| `time_source` | `Callable[[], float]` | `time.monotonic` | L'horloge que lit `token_memo_ttl`, injectable pour les tests |

### Méthodes

#### `anonymize(text, thread_id, role=MessageRole.USER) -> Anonymization` *(async)*

Détecte les entités du message, les enregistre dans la mémoire de `thread_id`, puis dé-identifie avec des jetons assignés sur toute la conversation. Le jeton d'une valeur reste le même d'un message à l'autre.

Le `thread_id` est requis. Il n'y a pas de défaut partagé, donc deux appelants ne peuvent pas tomber dans une même conversation et laisser fuir mutuellement leurs données confidentielles. `role` date les valeurs que le message introduit. Une valeur introduite d'abord par l'assistant est laissée en clair, car ce n'est pas une donnée confidentielle de l'utilisateur.

**Lève** `PIIRemainingError` quand un guard configuré signale des valeurs confidentielles restées dans la sortie.

```python
--8<-- "snippets/reference_thread_pipeline.py:anonymize"
```

#### `anonymize_corrected(text, thread_id, detections) -> Anonymization` *(async)*

Redé-identifie un message utilisateur avec un ensemble de détections corrigé par un humain. L'ensemble corrigé remplace les détections de ce message dans la mémoire, puis le message est dé-identifié avec des jetons cohérents sur la conversation. La détection ne relance pas. Cela ne concerne que les propres messages d'un utilisateur, donc la correction est enregistrée comme un message utilisateur.

L'ensemble corrigé est stocké tel quel, sans résolution de chevauchement ni recherche d'occurrences, car l'humain fait autorité sur lui. Un `override` configuré s'applique encore, donc les listes du serveur priment sur la correction.

```python
--8<-- "snippets/reference_thread_pipeline.py:anonymize_corrected"
```

#### `deanonymize(text, thread_id) -> str` *(async)*

Renvoie le texte avec chaque jeton de la conversation remplacé par sa valeur. Les jetons de la conversation sont reconstruits depuis sa mémoire, donc tout texte qui les porte est restauré, y compris une réponse du modèle que le pipeline n'a jamais dé-identifiée.

```python
--8<-- "snippets/reference_thread_pipeline.py:deanonymize"
```

#### `thread_token_map(thread_id) -> dict[str, str]` *(async)*

Renvoie la correspondance placeholder vers valeur de la conversation, dérivée du cache, pour qu'un appelant puisse résoudre tout un flux d'un coup plutôt que de restaurer jeton par jeton. Un jeton que la conversation n'a jamais émis est absent de la correspondance.

#### `forget_thread(thread_id) -> Forgotten` *(async)*

Efface la mémoire d'une conversation et renvoie un `Forgotten` indiquant ce qui a été supprimé. Oublier une conversation inconnue ne supprime rien et rapporte zéro.

```python
--8<-- "snippets/reference_thread_pipeline.py:forget_thread"
```

La correspondance de jetons mémoïsée de la conversation part avec elle. Ce mémo garde les valeurs de la conversation en clair, donc effacer le store seul les laisserait vivantes dans le processus. Les autres conversations gardent le leur. L'appel n'atteint que le processus où il tourne, donc sur un déploiement multi-worker posez `token_memo_ttl` au constructeur pour borner la fenêtre sur les autres, comme décrit dans [Déploiement multi-instance](../multi-instance.md). Un cache reste debout, celui des motifs de frontière de mot, partagé par tout le processus et indexé sur le fragment cherché, donc porteur de valeurs venant de toutes les conversations. Videz-le avec `clear_boundary_cache` quand une demande d'effacement couvre tout le processus.

```python
--8<-- "snippets/reference_thread_pipeline.py:clear_boundary_cache"
```

#### `recognizer` (propriété)

La grammaire des jetons que ce pipeline émet, une `BaseDelimitedPlaceholderFactory`, ou `None`. Une factory à délimiteurs est son propre recognizer, car ses jetons portent une grammaire retrouvable. Une factory sans grammaire, comme un masque, n'a pas de recognizer.

---

## Ports

Deux protocoles typent un pipeline là où un appelant, comme le middleware, doit l'accepter sans dépendre d'une classe concrète. Les deux sont génériques sur ce que les jetons émis préservent, donc un consommateur peut exiger un pipeline dont les jetons préservent l'identité et rejeter celui dont les jetons ne la préservent pas.

### `AnyPipeline`

Un composant qui dé-identifie un seul texte et sait le restaurer.

```python
@runtime_checkable
class AnyPipeline(Protocol[PreservationT_co]):
    async def anonymize(self, text: str) -> Anonymization[PreservationT_co]: ...
    def deanonymize(self, text: str, tokens: Mapping[Entity, str]) -> str: ...
```

### `AnyThreadPipeline`

Un pipeline scopé par conversation, local ou distant. Il dé-identifie chaque message d'une conversation, redé-identifie un message corrigé, restaure tout texte portant les jetons de la conversation, oublie une conversation en entier, et expose la grammaire de ses jetons.

```python
@runtime_checkable
class AnyThreadPipeline(Protocol[PreservationT_co]):
    async def anonymize(
        self, text: str, thread_id: str, role: MessageRole = MessageRole.USER
    ) -> Anonymization[PreservationT_co]: ...
    async def anonymize_corrected(
        self, text: str, thread_id: str, detections: list[Detection]
    ) -> Anonymization[PreservationT_co]: ...
    async def deanonymize(self, text: str, thread_id: str) -> str: ...
    async def forget_thread(self, thread_id: str) -> Forgotten: ...
    @property
    def recognizer(self) -> BaseDelimitedPlaceholderFactory | None: ...
```

---

## `BaseAnonymizationPipeline`

Module : `piighost.pipeline`

La machinerie partagée que les deux pipelines étendent. Elle tient les composants d'étage et les étapes communes à tous les pipelines. Les étages optionnels de chevauchement, de recherche d'occurrences et de résolution d'entités, la vérification du guard, et les payloads d'observation. Les pipelines concrets ajoutent leur propre `anonymize`, sur un texte seul ou sur une conversation.

---

## Construire depuis une configuration

Module : `piighost.config`

`load_pipeline` et `load_thread_pipeline` lisent un fichier de configuration, TOML ou JSON selon son suffixe, ou une référence du hub, et renvoient un pipeline construit. Une mémoire configurée fait de la configuration un pipeline de conversation. Les deux loaders imposent cette distinction, et la vérifient avant de construire quoi que ce soit.

- `load_pipeline(path)` renvoie un `AnonymizationPipeline`. Il lève `ConfigError` quand la configuration déclare une mémoire.
- `load_thread_pipeline(path)` renvoie un `ThreadAnonymizationPipeline`. Il lève `ConfigError` quand la configuration ne déclare pas de mémoire.

```python
--8<-- "snippets/loaders.py"
```

Une référence écrite `hub:namespace/nom:sélecteur` charge toute la configuration que le [hub piighost](https://hub.piighost.dev) publie sous ce nom, toutes les étapes comprises, exactement comme le ferait un fichier qui la contiendrait. Une référence épinglée sur un commit est téléchargée au premier chargement, puis lue depuis le cache disque. Une variable d'environnement préfixée `PIIGHOST_` l'emporte sur une valeur du hub comme sur celle d'un fichier.

```python
--8<-- "snippets/reference_hub_pipeline.py"
```

Ce package a besoin de l'extra `config`. Voir la référence [Configuration TOML](../configuration/toml.md) pour le format du fichier.

---

## Exemple complet

```python
--8<-- "snippets/reference_gliner2_pipeline.py"
```

---

## Voir aussi

- [Référence Anonymizer](anonymizer.md) pour l'`Anonymizer`, son résultat `Anonymization` et le port `AnyAnonymizer`.
- [Architecture](../architecture.md) pour l'agencement des étages.
- [Configuration TOML](../configuration/toml.md) pour la construction déclarative.

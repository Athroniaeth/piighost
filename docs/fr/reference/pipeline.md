---
icon: lucide/database
---

# Référence Pipeline

Un pipeline enchaîne les étages qui transforment un texte en texte dé-identifié, et l'inverse. `AnonymizationPipeline` traite un seul texte, sans mémoire d'un appel à l'autre. `ThreadAnonymizationPipeline` traite une conversation, en gardant un token par valeur sur tous les messages d'un thread.

Les deux renvoient une [`Anonymization`](anonymizer.md#anonymization), le texte dé-identifié associé au token qui a remplacé chaque entité.

!!! note "Dé-identification, pas anonymisation"
    Les pipelines par défaut gardent la correspondance entre une valeur et son token pour pouvoir restaurer la valeur. C'est une pseudonymisation réversible. Le mot anonymisation reste réservé à une suppression irréversible.

---

## `AnonymizationPipeline`

Module : `piighost.pipeline`

Dé-identifie un seul texte à travers les étages, dans l'ordre. Détecter les PII, résoudre les spans qui se chevauchent, retrouver les occurrences manquées, grouper les détections en entités, résoudre les conflits d'entités, remplacer par des tokens, puis revérifier avec un guard. Chaque appel à `anonymize()` est indépendant.

### Constructeur

```python
AnonymizationPipeline(
    detector: AnyDetector,
    linker: AnyEntityLinker | None = None,
    anonymizer: AnyAnonymizer | None = None,
    overlap_resolver: AnyOverlapResolver | None = None,
    expander: AnyDetectionExpander | None = None,
    entity_resolver: AnyEntityResolver | None = None,
    guard: AnyGuardRail | None = None,
    observation_redactor: AnyPlaceholderFactory | None = None,
    override: AnyDetectionOverride | None = None,
)
```

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `detector` | `AnyDetector` | requis | Détecteur d'entités async |
| `linker` | `AnyEntityLinker \| None` | `None` | Groupe les détections en entités. Par défaut `ExactEntityLinker()` |
| `anonymizer` | `AnyAnonymizer \| None` | `None` | Moteur de remplacement et sa placeholder factory. Par défaut `Anonymizer(LabelCounterPlaceholderFactory())` |
| `overlap_resolver` | `AnyOverlapResolver \| None` | `None` | Résout les détections qui se chevauchent. Par défaut `ConfidenceOverlapResolver()`, car l'étape de rendu a besoin de spans disjoints |
| `expander` | `AnyDetectionExpander \| None` | `None` | Ajoute les occurrences manquées d'une valeur détectée. Désactivé quand `None` |
| `entity_resolver` | `AnyEntityResolver \| None` | `None` | Réconcilie les entités en conflit. Désactivé quand `None` |
| `guard` | `AnyGuardRail \| None` | `None` | Revérifie la sortie pour de la PII résiduelle. Désactivé quand `None` |
| `observation_redactor` | `AnyPlaceholderFactory \| None` | `None` | Placeholder factory remplaçant les valeurs en clair dans les payloads d'observation. `None` trace le texte en clair, ce qui permet aux traces de servir de jeux d'annotation |
| `override` | `AnyDetectionOverride \| None` | `None` | Whitelist et blacklist du serveur imposées à chaque ensemble de détections. Désactivé quand `None` |

!!! note "Les composants sont des protocoles"
    `AnyDetector`, `AnyEntityLinker`, `AnyAnonymizer`, `AnyOverlapResolver`, `AnyDetectionExpander`, `AnyEntityResolver`, `AnyGuardRail`, `AnyDetectionOverride`. Toute implémentation du protocole est acceptée. Voir [Étendre PIIGhost](../extending.md).

### Méthodes

#### `anonymize(text) -> Anonymization` *(async)*

Exécute le pipeline complet et renvoie le texte dé-identifié avec le token utilisé pour chaque entité.

**Lève** `PIIRemainingError` quand un guard configuré signale de la PII restée dans la sortie.

```python
result = await pipeline.anonymize("Patrick lives in Paris.")
# result.text == "<<PERSON:1>> lives in <<LOCATION:1>>."
```

#### `deanonymize(text, tokens) -> str`

Renvoie le texte avec chaque token connu remplacé par la valeur de son entité. `tokens` est la correspondance issue d'une `Anonymization`, lue à l'envers. Les tokens absents de la correspondance sont laissés intacts.

La restauration n'est sans ambiguïté que si les tokens préservent l'identité, car deux entités partageant un même token se confondent en une seule valeur.

```python
original = pipeline.deanonymize(result.text, result.tokens)
# original == "Patrick lives in Paris."
```

---

## `ThreadAnonymizationPipeline`

Module : `piighost.pipeline`

Dé-identifie chaque message d'une conversation avec des tokens stables sur tout le thread. Une valeur vue dans un premier message puis à nouveau plus tard porte le même token, car les tokens sont assignés sur l'union des détections de tous les messages, pas sur un message seul. Les détections de chaque message sont mises en cache dans la mémoire, donc renvoyer un message évite la détection.

Le composant en plus est une mémoire de conversation, `memory`, le stockage par thread des détections de chaque message.

### Constructeur

```python
ThreadAnonymizationPipeline(
    detector: AnyDetector,
    linker: AnyEntityLinker | None = None,
    anonymizer: AnyAnonymizer | None = None,
    memory: AnyConversationMemory | None = None,
    overlap_resolver: AnyOverlapResolver | None = None,
    expander: AnyDetectionExpander | None = None,
    entity_resolver: AnyEntityResolver | None = None,
    guard: AnyGuardRail | None = None,
    observation_redactor: AnyPlaceholderFactory | None = None,
    override: AnyDetectionOverride | None = None,
)
```

En plus de tous les paramètres de `AnonymizationPipeline` :

| Paramètre | Type | Défaut | Description |
|-----------|------|--------|-------------|
| `memory` | `AnyConversationMemory \| None` | `None` | Stockage par thread des détections de chaque message. Par défaut `InMemoryConversationMemory()` pour un seul processus ; passez `RedisConversationMemory` pour un backend partagé |

### Méthodes

#### `anonymize(text, thread_id, role=MessageRole.USER) -> Anonymization` *(async)*

Détecte les entités du message, les enregistre dans la mémoire de `thread_id`, puis dé-identifie avec des tokens assignés sur tout le thread. Le token d'une valeur reste le même d'un message à l'autre.

Le `thread_id` est requis. Il n'y a pas de défaut partagé, donc deux appelants ne peuvent pas tomber dans un même thread et laisser fuir mutuellement leurs PII. `role` date les valeurs que le message introduit. Une valeur introduite d'abord par l'assistant est laissée en clair, car ce n'est pas une PII de l'utilisateur.

**Lève** `PIIRemainingError` quand un guard configuré signale de la PII restée dans la sortie.

```python
a1 = await pipeline.anonymize("Patrick lives in Paris.", thread_id="user-A")
a2 = await pipeline.anonymize("Patrick wrote to Marie.", thread_id="user-A")
# Patrick keeps <<PERSON:1>> across both turns.
```

#### `anonymize_corrected(text, thread_id, detections) -> Anonymization` *(async)*

Redé-identifie un message utilisateur avec un ensemble de détections corrigé par un humain. L'ensemble corrigé remplace les détections de ce message dans la mémoire, puis le message est dé-identifié avec des tokens cohérents sur le thread. La détection ne relance pas. Cela ne concerne que les propres messages d'un utilisateur, donc la correction est enregistrée comme un message utilisateur.

L'ensemble corrigé est stocké tel quel, sans résolution de chevauchement ni recherche d'occurrences, car l'humain fait autorité sur lui. Un `override` configuré s'applique encore, donc les listes du serveur priment sur la correction.

```python
detection = Detection(span=Span(0, 5), text="Marie", label="PERSON", confidence=1.0)
detections = [detection]
result = await pipeline.anonymize_corrected("Marie called.", "user-A", detections)
```

#### `deanonymize(text, thread_id) -> str` *(async)*

Renvoie le texte avec chaque token du thread remplacé par sa valeur. Les tokens du thread sont reconstruits depuis sa mémoire, donc tout texte qui les porte est restauré, y compris une réponse du modèle que le pipeline n'a jamais dé-identifiée.

```python
reply = await pipeline.deanonymize("Message sent to <<PERSON:2>>.", thread_id="user-A")
# reply == "Message sent to Marie."
```

#### `forget_thread(thread_id) -> Forgotten` *(async)*

Efface la mémoire d'un thread et renvoie un `Forgotten` indiquant ce qui a été supprimé. Oublier un thread inconnu ne supprime rien et rapporte zéro.

```python
forgotten = await pipeline.forget_thread("user-A")
# forgotten.messages, forgotten.detections
```

#### `recognizer` (propriété)

La grammaire des tokens que ce pipeline émet, une `BaseDelimitedPlaceholderFactory`, ou `None`. Une factory à délimiteurs est son propre recognizer, car ses tokens portent une grammaire retrouvable. Une factory sans grammaire, comme un masque, n'a pas de recognizer.

---

## Ports

Deux protocoles typent un pipeline là où un appelant, comme le middleware, doit l'accepter sans dépendre d'une classe concrète. Les deux sont génériques sur ce que les tokens émis préservent, donc un consommateur peut exiger un pipeline dont les tokens préservent l'identité et rejeter celui dont les tokens ne la préservent pas.

### `AnyPipeline`

Un composant qui dé-identifie un seul texte et sait le restaurer.

```python
class AnyPipeline(Protocol[PreservationT_co]):
    async def anonymize(self, text: str) -> Anonymization[PreservationT_co]: ...
    def deanonymize(self, text: str, tokens: Mapping[Entity, str]) -> str: ...
```

### `AnyThreadPipeline`

Un pipeline scopé par thread, local ou distant. Il dé-identifie chaque message d'un thread, redé-identifie un message corrigé, désanonymise tout texte portant les tokens du thread, oublie un thread en entier, et expose la grammaire de ses tokens.

```python
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

`load_pipeline` et `load_thread_pipeline` lisent un fichier de configuration, TOML ou JSON selon son suffixe, et renvoient un pipeline construit. Une mémoire configurée fait de la configuration un pipeline de thread. Les deux loaders imposent cette distinction.

- `load_pipeline(path)` renvoie un `AnonymizationPipeline`. Il lève `ConfigError` quand la configuration déclare une mémoire.
- `load_thread_pipeline(path)` renvoie un `ThreadAnonymizationPipeline`. Il lève `ConfigError` quand la configuration ne déclare pas de mémoire.

```python
from piighost.config import load_pipeline, load_thread_pipeline

pipeline = load_pipeline("pipeline.toml")
thread_pipeline = load_thread_pipeline("thread.toml")
```

Ce package a besoin de l'extra `config`. Voir la référence [Configuration TOML](../configuration/toml.md) pour le format du fichier.

---

## Exemple complet

```python
import asyncio

from gliner2 import GLiNER2

from piighost.components.anonymizer import Anonymizer
from piighost.components.detector.ner.gliner2 import Gliner2Detector
from piighost.components.linker import ExactEntityLinker
from piighost.components.placeholder import LabelCounterPlaceholderFactory
from piighost.conversation_memory import InMemoryConversationMemory
from piighost.pipeline import ThreadAnonymizationPipeline

model = GLiNER2.from_pretrained("fastino/gliner2-multi-v1")
detector = Gliner2Detector(model=model, threshold=0.5, labels=["PERSON", "LOCATION"])
factory = LabelCounterPlaceholderFactory()
anonymizer = Anonymizer(factory)
linker = ExactEntityLinker()
memory = InMemoryConversationMemory()

pipeline = ThreadAnonymizationPipeline(
    detector=detector,
    linker=linker,
    anonymizer=anonymizer,
    memory=memory,
)


async def main():
    result = await pipeline.anonymize("Patrick is in Lyon.", thread_id="user-A")
    print(result.text)  # <<PERSON:1>> is in <<LOCATION:1>>.

    original = await pipeline.deanonymize(result.text, thread_id="user-A")
    print(original)  # Patrick is in Lyon.


asyncio.run(main())
```

---

## Voir aussi

- [Référence Anonymizer](anonymizer.md) pour l'`Anonymizer`, son résultat `Anonymization` et le port `AnyAnonymizer`.
- [Architecture](../architecture.md) pour l'agencement des étages.
- [Configuration TOML](../configuration/toml.md) pour la construction déclarative.

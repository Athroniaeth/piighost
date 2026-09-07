---
icon: lucide/gavel
tags:
  - Avancé
  - Détecteur
---

# Comment forcer une détection ou laisser une valeur en clair

Votre détecteur lit le nom de votre entreprise comme une personne et vous voulez qu'il reste en clair. Vos noms de code internes ne sont jamais détectés et vous voulez qu'ils soient remplacés à chaque fois. Ces deux décisions portent sur le jeu de détections plutôt que sur le détecteur, et `DetectionOverride` est l'étape qui les impose, un détecteur whitelist dont les hits sont forcés dans le jeu et un détecteur blacklist dont les hits en sont retirés.

L'étape s'exécute juste après la détection, avant la résolution des chevauchements et la liaison, donc ses deux listes l'emportent sur la lecture du détecteur ainsi que sur un jeu corrigé qui revient d'une relecture humaine. Voir [Architecture](../architecture.md) pour l'ordre complet des étapes.

!!! note "Prérequis"
    `piighost` seul, `pip install piighost`. Chaque snippet ci-dessous s'exécute tel quel, sans téléchargement de modèle ni accès réseau. La dernière section lit un fichier de configuration, ce qui demande l'extra config, `pip install piighost[config]`.

## 1. Laisser une valeur en clair avec une blacklist

Pointez un détecteur sur la valeur, passez-le à `DetectionOverride` comme blacklist, puis passez l'override au pipeline. Ce que la blacklist trouve quitte le jeu de détections, donc la valeur arrive en clair au modèle.

```python
import asyncio

from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import ExactMatchDetector
from piighost.components.linker import ExactEntityLinker
from piighost.components.override import DetectionOverride
from piighost.components.placeholder import LabelCounterPlaceholderFactory
from piighost.pipeline import AnonymizationPipeline

detector = ExactMatchDetector({"Emma": "PERSON", "Acme": "ORG"})
blacklist = ExactMatchDetector({"Acme": "ORG"})
override = DetectionOverride(blacklist=blacklist)
linker = ExactEntityLinker()
factory = LabelCounterPlaceholderFactory()
anonymizer = Anonymizer(factory)
pipeline = AnonymizationPipeline(
    detector,
    linker,
    anonymizer,
    override=override,
)


async def main():
    result = await pipeline.anonymize("Emma works at Acme.")
    print(result.text)
    # <<PERSON:1>> works at Acme.


asyncio.run(main())
```

`blacklist_strategy` décide quelles détections un hit de blacklist emporte.

- Gardez `BlacklistStrategy.VALUE`, le défaut, quand la valeur ne doit jamais être dé-identifiée, quel que soit le label que le détecteur lui donne. Il écarte toute détection portant le même texte replié en casse, position et label ignorés, si bien que le label que vous écrivez à côté de la valeur n'a jamais à correspondre à ce que le détecteur primaire émet.
- Utilisez `BlacklistStrategy.EXACT` quand c'est le label qui compte, et que les deux détecteurs lisent la valeur de la même façon. Il n'écarte une détection que si son span et son label correspondent tous les deux au hit.
- Utilisez `BlacklistStrategy.OVERLAP` quand une détection plus longue contenant la valeur doit tomber aussi. Il écarte toute détection dont le span touche un span blacklisté, labels ignorés.

Les trois modes sur un même texte, avec un détecteur qui étiquette `Acme`{ .pii } comme une personne et lit `Globex Ltd`{ .pii } comme une seule organisation.

```python
import asyncio

from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import ExactMatchDetector
from piighost.components.linker import ExactEntityLinker
from piighost.components.override import BlacklistStrategy, DetectionOverride
from piighost.components.placeholder import LabelCounterPlaceholderFactory
from piighost.pipeline import AnonymizationPipeline


def build_pipeline(strategy: BlacklistStrategy) -> AnonymizationPipeline:
    detector = ExactMatchDetector(
        {"Emma": "PERSON", "Acme": "PERSON", "Globex Ltd": "ORG"}
    )
    blacklist = ExactMatchDetector({"Acme": "ORG", "Globex": "ORG"})
    override = DetectionOverride(blacklist=blacklist, blacklist_strategy=strategy)
    linker = ExactEntityLinker()
    factory = LabelCounterPlaceholderFactory()
    anonymizer = Anonymizer(factory)
    return AnonymizationPipeline(
        detector,
        linker,
        anonymizer,
        override=override,
    )


async def main():
    text = "Emma works at Acme, formerly Globex Ltd."
    for strategy in BlacklistStrategy:
        pipeline = build_pipeline(strategy)
        result = await pipeline.anonymize(text)
        print(strategy.value, "->", result.text)


asyncio.run(main())
```

```text
exact -> <<PERSON:1>> works at <<PERSON:2>>, formerly <<ORG:1>>.
value -> <<PERSON:1>> works at Acme, formerly <<ORG:1>>.
overlap -> <<PERSON:1>> works at Acme, formerly Globex Ltd.
```

`EXACT` n'a rien trouvé à écarter, la blacklist disant que `Acme`{ .pii } est une organisation là où le détecteur dit une personne, et le span du détecteur couvrant `Globex Ltd`{ .pii } là où la blacklist ne couvre que `Globex`{ .pii }. `VALUE` compare des valeurs entières, donc il a écarté `Acme`{ .pii } et laissé `Globex Ltd`{ .pii }, dont le texte n'est pas celui de la blacklist. `OVERLAP` a écarté les deux, le span blacklisté étant à l'intérieur de la détection plus longue.

!!! note "Une valeur blacklistée ne déclenche pas le garde-fou"
    Un [garde-fou](../reference/guard-rails.md) relit la sortie et refuse les PII résiduelles. Le pipeline lui transmet les valeurs que la blacklist a trouvées dans le texte, donc une valeur que vous laissez volontairement en clair est exemptée. Toute autre fuite lève quand même `PIIRemainingError`.

## 2. Forcer une valeur ratée avec une whitelist

Pointez un détecteur sur le motif que le détecteur principal rate, ici un nom de code qu'une regex décrit exactement, et passez-le comme whitelist. Ses hits entrent dans le jeu de détections, quoi qu'ait vu le détecteur principal.

```python
import asyncio

from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import RegexDetector
from piighost.components.detector.patterns import GENERIC_PATTERNS
from piighost.components.linker import ExactEntityLinker
from piighost.components.override import DetectionOverride
from piighost.components.placeholder import LabelCounterPlaceholderFactory
from piighost.pipeline import AnonymizationPipeline

detector = RegexDetector(GENERIC_PATTERNS)
whitelist = RegexDetector({"CODENAME": r"ACME-[A-Z]+"})
override = DetectionOverride(whitelist=whitelist)
linker = ExactEntityLinker()
factory = LabelCounterPlaceholderFactory()
anonymizer = Anonymizer(factory)
pipeline = AnonymizationPipeline(
    detector,
    linker,
    anonymizer,
    override=override,
)


async def main():
    result = await pipeline.anonymize("Ship ACME-FALCON to alice@example.com.")
    print(result.text)
    # Ship <<CODENAME:1>> to <<EMAIL:1>>.


asyncio.run(main())
```

Un hit forcé remplace aussi toute détection qu'il chevauche, donc le label de la whitelist l'emporte sur la lecture principale. Servez-vous-en pour corriger un label, pas seulement pour ajouter une détection.

```python
from piighost.components.detector import ExactMatchDetector

detector = ExactMatchDetector({"Emma": "PERSON", "Acme": "PERSON"})
whitelist = ExactMatchDetector({"Acme": "ORG"})
override = DetectionOverride(whitelist=whitelist)
linker = ExactEntityLinker()
factory = LabelCounterPlaceholderFactory()
anonymizer = Anonymizer(factory)
pipeline = AnonymizationPipeline(
    detector,
    linker,
    anonymizer,
    override=override,
)


async def main():
    result = await pipeline.anonymize("Acme hired Emma.")
    print(result.text)
    # <<ORG:1>> hired <<PERSON:1>>.


asyncio.run(main())
```

Une valeur forcée passe par la liaison et l'attribution de token comme n'importe quelle détection, donc le pipeline conversationnel la stocke en mémoire et `deanonymize` la restaure.

## 3. Tokeniser une valeur introduite par l'assistant

Dans un thread, une valeur que l'assistant a écrite le premier reste en clair même si la whitelist la trouve. Le modèle a produit cette valeur parce qu'elle était utile dans le contexte et il ne sait pas qu'elle est confidentielle, donc la remplacer lui retirerait sa connaissance du monde et signalerait que cette valeur précise est sensible. `whitelist_strategy` décide qui l'emporte.

- Gardez `WhitelistStrategy.RESPECT_PROVENANCE`, le défaut, pour laisser en clair une valeur introduite par l'assistant. La whitelist garantit toujours que la valeur est détectée, et la même valeur introduite par l'utilisateur est bien tokenisée.
- Utilisez `WhitelistStrategy.FORCE` pour tokeniser une valeur whitelistée quel que soit celui qui l'a écrite le premier.

```python
import asyncio

from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import ExactMatchDetector
from piighost.components.linker import ExactEntityLinker
from piighost.components.override import DetectionOverride, WhitelistStrategy
from piighost.components.placeholder import LabelCounterPlaceholderFactory
from piighost.conversation_memory import InMemoryConversationMemory, MessageRole
from piighost.pipeline import ThreadAnonymizationPipeline


def build_pipeline(strategy: WhitelistStrategy) -> ThreadAnonymizationPipeline:
    detector = ExactMatchDetector({})
    whitelist = ExactMatchDetector({"Acme": "ORG"})
    override = DetectionOverride(whitelist=whitelist, whitelist_strategy=strategy)
    linker = ExactEntityLinker()
    factory = LabelCounterPlaceholderFactory()
    anonymizer = Anonymizer(factory)
    memory = InMemoryConversationMemory()
    return ThreadAnonymizationPipeline(
        detector,
        linker,
        anonymizer,
        memory,
        override=override,
    )


async def main():
    for strategy in WhitelistStrategy:
        pipeline = build_pipeline(strategy)
        assistant = await pipeline.anonymize("Acme rocks", "t1", MessageRole.ASSISTANT)
        user = await pipeline.anonymize("I love Acme", "t1")
        print(strategy.value, "->", assistant.text, "|", user.text)


asyncio.run(main())
```

```text
respect_provenance -> Acme rocks | I love Acme
force -> <<ORG:1>> rocks | I love <<ORG:1>>
```

## 4. Décider qui l'emporte quand les deux listes se contredisent

Une valeur que les deux listes trouvent est une contradiction, et `conflict_strategy` nomme le gagnant.

- Gardez `OverrideConflictStrategy.WHITELIST_WINS`, le défaut, pour dé-identifier la valeur contredite. La blacklist s'applique d'abord aux détections principales, puis la whitelist est forcée en dernier.
- Utilisez `OverrideConflictStrategy.BLACKLIST_WINS` pour la garder en clair. La whitelist est forcée d'abord, puis la blacklist écarte le résultat, hits forcés compris.
- Utilisez `OverrideConflictStrategy.RAISE` pour refuser la contradiction. Un span whitelisté qui chevauche un span blacklisté lève `ConflictingOverrideError` avant l'application de l'une ou l'autre liste.

```python
import asyncio

from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import ExactMatchDetector
from piighost.components.linker import ExactEntityLinker
from piighost.components.override import DetectionOverride, OverrideConflictStrategy
from piighost.components.placeholder import LabelCounterPlaceholderFactory
from piighost.exceptions import ConflictingOverrideError
from piighost.pipeline import AnonymizationPipeline


def build_pipeline(strategy: OverrideConflictStrategy) -> AnonymizationPipeline:
    detector = ExactMatchDetector({"Emma": "PERSON"})
    whitelist = ExactMatchDetector({"Acme": "ORG"})
    blacklist = ExactMatchDetector({"Acme": "ORG"})
    override = DetectionOverride(
        whitelist=whitelist,
        blacklist=blacklist,
        conflict_strategy=strategy,
    )
    linker = ExactEntityLinker()
    factory = LabelCounterPlaceholderFactory()
    anonymizer = Anonymizer(factory)
    return AnonymizationPipeline(
        detector,
        linker,
        anonymizer,
        override=override,
    )


async def main():
    for strategy in OverrideConflictStrategy:
        pipeline = build_pipeline(strategy)
        try:
            result = await pipeline.anonymize("Emma works at Acme.")
        except ConflictingOverrideError as error:
            print(strategy.value, "->", type(error).__name__, error)
        else:
            print(strategy.value, "->", result.text)


asyncio.run(main())
```

```text
whitelist_wins -> <<PERSON:1>> works at <<ORG:1>>.
blacklist_wins -> <<PERSON:1>> works at Acme.
raise -> ConflictingOverrideError Overrides contradict each other on 'Acme': a whitelisted span overlaps a blacklisted one.
```

`BLACKLIST_WINS` écarte un hit forcé via la stratégie de blacklist, donc le défaut `VALUE` écarte une valeur forcée quel que soit le label que la whitelist lui a attaché. Sous `EXACT`, les deux listes doivent s'accorder sur le label pour que la blacklist l'emporte.

## 5. Piloter l'override depuis un fichier de configuration

Les deux listes sont des configs de détecteur, `[override.whitelist]` et `[override.blacklist]`, et les trois stratégies sont des clés de `[override]`. Le fichier ci-dessous force le nom de code et garde en clair une boîte mail publique.

```toml
[detector]
type = "regex"
catalogs = ["generic"]

[override]
blacklist_strategy = "value"

[override.whitelist]
type = "regex"
patterns = { CODENAME = 'ACME-[A-Z]+' }

[override.blacklist]
type = "exact"
values = { "public@corp.com" = "EMAIL" }
```

`load_pipeline` lit le fichier et construit le pipeline, override compris.

```python
import asyncio

from piighost.config import load_pipeline

pipeline = load_pipeline("piighost.toml")


async def main():
    result = await pipeline.anonymize(
        "Mail public@corp.com or alice@example.com about ACME-FALCON."
    )
    print(result.text)
    # Mail public@corp.com or <<EMAIL:1>> about <<CODENAME:1>>.


asyncio.run(main())
```

Pour chaque clé et chaque valeur acceptée, voir la [configuration TOML](../configuration/toml.md).

## Voir aussi

- [Détecteurs prêts à l'emploi](detectors.md) pour les détecteurs sur lesquels reposent les deux listes.
- [Référence du pipeline](../reference/pipeline.md) pour le paramètre `override` et l'ordre des étapes.
- [Garde-fous](../reference/guard-rails.md) pour le contrôle de sortie dont la blacklist exempte une valeur.
- [Configuration TOML](../configuration/toml.md) pour les clés de `[override]`.

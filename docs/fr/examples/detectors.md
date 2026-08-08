---
icon: lucide/scan-search
tags:
  - Détecteur
  - Regex
---

# Comment utiliser les catalogues de patterns et combiner des détecteurs

`piighost` fournit des catalogues de patterns regex prêts à l'emploi pour les PII à structure fixe (email, IP, IBAN, téléphone). Ce guide montre comment les charger, les fusionner et combiner plusieurs détecteurs, avec le seul cœur de `piighost`.

Les quatre catalogues sont de simples dictionnaires `label` vers `pattern`.

```python
from piighost.components.detector.patterns import (
    EU_PATTERNS,
    FR_PATTERNS,
    GENERIC_PATTERNS,
    US_PATTERNS,
)
```

- `GENERIC_PATTERNS` : email, URL, IPv4, carte bancaire, indépendants du pays.
- `US_PATTERNS` : SSN, téléphone, ZIP, préfixés `US_`.
- `EU_PATTERNS` : IBAN ISO 13616 pan-européen.
- `FR_PATTERNS` : téléphone, IBAN, NIR, SIRET, préfixés `FR_`.

Pour le détail des labels, voir la [référence des détecteurs](../reference/detectors.md).

## Utiliser un seul catalogue

Passez le catalogue à un `RegexDetector`, puis montez le pipeline.

```python
import asyncio

from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import RegexDetector
from piighost.components.detector.patterns import GENERIC_PATTERNS
from piighost.components.linker import ExactEntityLinker
from piighost.components.placeholder import LabelCounterPlaceholderFactory
from piighost.pipeline import AnonymizationPipeline

pipeline = AnonymizationPipeline(
    RegexDetector(GENERIC_PATTERNS),
    ExactEntityLinker(),
    Anonymizer(LabelCounterPlaceholderFactory()),
)


async def main():
    result = await pipeline.anonymize("Email alice@example.com, server 192.168.1.42.")
    print(result.text)
    # Email <<EMAIL:1>>, server <<IPV4:1>>.


asyncio.run(main())
```

## Fusionner générique et régional

Si vous voulez couvrir à la fois les PII génériques et celles d'une région, fusionnez les dictionnaires. La fusion de droite l'emporte sur un même label.

```python
from piighost.components.detector.patterns import FR_PATTERNS, GENERIC_PATTERNS

patterns = {**GENERIC_PATTERNS, **FR_PATTERNS}
detector = RegexDetector(patterns)

pipeline = AnonymizationPipeline(
    detector,
    ExactEntityLinker(),
    Anonymizer(LabelCounterPlaceholderFactory()),
)


async def main():
    result = await pipeline.anonymize(
        "IBAN FR7630006000011234567890189, email marie@exemple.fr, tel 06 12 34 56 78."
    )
    print(result.text)
    # IBAN <<FR_IBAN:1>>, email <<EMAIL:1>>, tel <<FR_PHONE:1>>.


asyncio.run(main())
```

Pour ne garder que certains labels, construisez un dictionnaire à la carte.

```python
patterns = {
    "EMAIL": GENERIC_PATTERNS["EMAIL"],
    "FR_IBAN": FR_PATTERNS["FR_IBAN"],
}
detector = RegexDetector(patterns)
```

## Combiner plusieurs détecteurs

`CompositeDetector` exécute plusieurs détecteurs sur le même texte et concatène leurs détections. Les chevauchements sont arbitrés par l'étage de résolution du pipeline. C'est ainsi qu'on couple un détecteur regex à un détecteur qui reconnaît des noms.

```python
from piighost.components.detector import CompositeDetector, ExactMatchDetector, RegexDetector
from piighost.components.detector.patterns import GENERIC_PATTERNS

detector = CompositeDetector([
    ExactMatchDetector({"Patrick": "PERSON"}),
    RegexDetector(GENERIC_PATTERNS),
])

pipeline = AnonymizationPipeline(
    detector,
    ExactEntityLinker(),
    Anonymizer(LabelCounterPlaceholderFactory()),
)


async def main():
    result = await pipeline.anonymize("Patrick emailed alice@example.com.")
    print(result.text)
    # <<PERSON:1>> emailed <<EMAIL:1>>.


asyncio.run(main())
```

En production, remplacez `ExactMatchDetector` par un détecteur NER ou LLM, voir la [référence des détecteurs](../reference/detectors.md). `ExactMatchDetector` sert ici à garder l'exemple reproductible sans modèle.

## Traiter un texte long

Un détecteur NER a une fenêtre de contexte bornée, et un long document peut la dépasser. `ChunkedDetector` enveloppe n'importe quel détecteur, découpe le texte en fragments qui se chevauchent, détecte sur chacun et reprojette les positions sur le texte d'origine.

```python
from piighost.components.detector import ChunkedDetector, RegexDetector
from piighost.components.detector.patterns import GENERIC_PATTERNS
from piighost.text import RecursiveCharacterTextSplitter

detector = ChunkedDetector(
    RegexDetector(GENERIC_PATTERNS),
    splitter=RecursiveCharacterTextSplitter(chunk_size=40, chunk_overlap=10),
)

pipeline = AnonymizationPipeline(
    detector,
    ExactEntityLinker(),
    Anonymizer(LabelCounterPlaceholderFactory()),
)


async def main():
    text = (
        "Filler text here. Reach alice@example.com now. "
        "More filler padding words. Then bob@example.org later."
    )
    result = await pipeline.anonymize(text)
    print(result.text)
    # Filler text here. Reach <<EMAIL:1>> now. More filler padding words. Then <<EMAIL:2>> later.


asyncio.run(main())
```

Laissez `splitter=None` pour un `RecursiveCharacterTextSplitter` par défaut, réglé pour de vrais documents. Le `chunk_size` réduit ci-dessus ne sert qu'à forcer plusieurs fragments dans un court exemple.

## Charger les catalogues depuis un fichier de config

Si vous pilotez le pipeline par un fichier de configuration plutôt que par du code, un détecteur regex accepte une clé `catalogs`.

```toml
[detector]
type = "regex"
catalogs = ["generic", "fr"]
```

Les catalogues fusionnent d'abord, puis les `patterns` en ligne, donc un pattern en ligne l'emporte au même label. Voir la [configuration TOML](../configuration/toml.md).

## Voir aussi

- [Dé-identifier un texte et le restaurer](basic.md) pour l'aller-retour complet.
- [Référence des détecteurs](../reference/detectors.md) pour le catalogue des labels.
- [Étendre PIIGhost](../extending.md) pour écrire vos propres détecteurs.

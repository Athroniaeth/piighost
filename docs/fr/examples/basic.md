---
icon: lucide/code
---

# Comment dé-identifier un texte et le restaurer

Vous avez un texte contenant des PII et vous voulez le dé-identifier, l'envoyer à un LLM, puis restaurer les valeurs d'origine dans la réponse. Ce guide fait l'aller-retour avec le seul cœur de `piighost`, sans modèle ni dépendance optionnelle.

Installez le cœur.

```bash
uv add piighost
```

## Faire l'aller-retour

Un pipeline enchaîne un détecteur, un linker et un anonymiseur. `anonymize` renvoie le texte dé-identifié et le token attribué à chaque entité. `deanonymize` rejoue cette correspondance en sens inverse.

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
    result = await pipeline.anonymize("Contact alice@example.com from 192.168.1.42.")
    print(result.text)
    # Contact <<EMAIL:1>> from <<IPV4:1>>.

    restored = pipeline.deanonymize(result.text, result.tokens)
    print(restored)
    # Contact alice@example.com from 192.168.1.42.


asyncio.run(main())
```

`result.text` porte `<<EMAIL:1>>`{ .placeholder } à la place de `alice@example.com`{ .pii }. `result.tokens` associe chaque entité à son token. Passez-le tel quel à `deanonymize` pour retrouver le texte d'origine.

## Restaurer une réponse du LLM

`deanonymize` restaure n'importe quel texte portant les tokens, pas seulement celui que le pipeline a produit. Si le LLM répond avec `<<EMAIL:1>>`{ .placeholder }, réinjectez les vraies valeurs avec la même correspondance `result.tokens`.

```python
async def main():
    result = await pipeline.anonymize("Contact alice@example.com from 192.168.1.42.")

    llm_reply = "I sent the message to <<EMAIL:1>>."
    print(pipeline.deanonymize(llm_reply, result.tokens))
    # I sent the message to alice@example.com.


asyncio.run(main())
```

## Regrouper les occurrences répétées

Une même valeur citée plusieurs fois reçoit un seul token, donc le LLM garde le fil. `ExactEntityLinker` regroupe les occurrences par valeur et par label.

```python
from piighost.components.detector import ExactMatchDetector

pipeline = AnonymizationPipeline(
    ExactMatchDetector({"Patrick": "PERSON", "Paris": "LOCATION"}),
    ExactEntityLinker(),
    Anonymizer(LabelCounterPlaceholderFactory()),
)


async def main():
    result = await pipeline.anonymize("Patrick lives in Paris. Patrick loves Paris.")
    print(result.text)
    # <<PERSON:1>> lives in <<LOCATION:1>>. <<PERSON:1>> loves <<LOCATION:1>>.


asyncio.run(main())
```

`ExactMatchDetector` détecte des valeurs littérales fixées, ce qui rend l'exemple reproductible sans charger de modèle. Pour du texte libre, remplacez-le par un détecteur NER ou LLM, voir la [référence des détecteurs](../reference/detectors.md).

## Changer la forme des tokens

`LabelCounterPlaceholderFactory` produit `<<LABEL:N>>`{ .placeholder }. Si vous voulez une autre forme de token, changez la factory passée à l'`Anonymizer`.

```python
from piighost.components.placeholder import (
    LabelHashPlaceholderFactory,
    LabelPlaceholderFactory,
)

# Deterministic hash, one opaque token per value: <<PERSON:a1b2c3d4>>
Anonymizer(LabelHashPlaceholderFactory())

# Label only, no counter: <<PERSON>>
Anonymizer(LabelPlaceholderFactory())
```

Pour restaurer les valeurs, la factory doit préserver l'identité, ce que fait `LabelCounterPlaceholderFactory` et pas `LabelPlaceholderFactory`, qui donne le même `<<PERSON>>`{ .placeholder } à deux personnes distinctes. Voir la page [Placeholder factories](../placeholder-factories.md).

## Voir aussi

- [Détecteurs prêts à l'emploi](detectors.md) pour combiner catalogues et détecteurs.
- [Référence du pipeline](../reference/pipeline.md) pour les étages optionnels.
- [Étendre PIIGhost](../extending.md) pour écrire vos propres composants.

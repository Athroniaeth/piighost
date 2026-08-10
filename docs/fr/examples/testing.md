---
icon: lucide/test-tube
tags:
  - Tests
---

# Tester un pipeline sans modèle

Vous voulez vérifier ce que produit un pipeline sans télécharger de modèle NER ni accéder au réseau. `ExactMatchDetector` vous le permet. Vous lui indiquez quelles valeurs littérales correspondent à quel label, et il trouve leurs occurrences avec une simple regex. Le reste du pipeline s'exécute sans changement, si bien qu'un test exerce la vraie liaison, la vraie résolution et la vraie anonymisation contre un détecteur dont vous maîtrisez la sortie.

Servez-vous-en pour tester un pipeline que vous avez assemblé, ou un composant que vous avez écrit, contre `<<PERSON:1>>`{ .placeholder } plutôt que contre la prédiction d'un modèle.

## Vérifier une chaîne anonymisée

Construisez un pipeline avec `ExactMatchDetector`, exécutez-le sur un texte, puis comparez `result.text` à la sortie attendue.

```python
import asyncio

from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import ExactMatchDetector
from piighost.components.linker import ExactEntityLinker
from piighost.components.placeholder import LabelCounterPlaceholderFactory
from piighost.pipeline import AnonymizationPipeline

detector = ExactMatchDetector({"John Doe": "PERSON", "Paris": "LOCATION"})
pipeline = AnonymizationPipeline(
    detector,
    ExactEntityLinker(),
    Anonymizer(LabelCounterPlaceholderFactory()),
)


async def main() -> None:
    result = await pipeline.anonymize("John Doe lives in Paris.")
    assert result.text == "<<PERSON:1>> lives in <<LOCATION:1>>."


asyncio.run(main())
```

`ExactMatchDetector` prend un dictionnaire de valeur littérale vers label. Il émet une détection par occurrence avec une confiance de `1.0`, donc sa sortie ne varie jamais d'une exécution à l'autre.

## L'écrire comme un test pytest

Le projet lance pytest avec `asyncio_mode = "auto"`, donc un `async def test_...` n'a besoin d'aucun décorateur. Vérifiez à la fois la sortie exacte et l'absence de la valeur brute.

```python
from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import ExactMatchDetector
from piighost.components.linker import ExactEntityLinker
from piighost.components.placeholder import LabelCounterPlaceholderFactory
from piighost.pipeline import AnonymizationPipeline


def build_pipeline(values: dict[str, str]) -> AnonymizationPipeline:
    return AnonymizationPipeline(
        ExactMatchDetector(values),
        ExactEntityLinker(),
        Anonymizer(LabelCounterPlaceholderFactory()),
    )


async def test_person_is_tokenized() -> None:
    """A detected person becomes its token, and the raw value is gone."""
    pipeline = build_pipeline({"Alice": "PERSON"})
    result = await pipeline.anonymize("Alice lives in Lyon.")
    assert result.text == "<<PERSON:1>> lives in Lyon."
    assert "Alice" not in result.text
```

Si votre propre projet lance pytest en mode synchrone par défaut, installez `pytest-asyncio` et marquez le test avec `@pytest.mark.asyncio`, ou réglez `asyncio_mode = "auto"` dans la configuration pytest pour vous passer du décorateur.

## Vérifier que les répétitions partagent un jeton

La liaison d'entités regroupe chaque occurrence d'une valeur sous une seule entité, donc un nom répété réutilise son premier jeton. `ExactMatchDetector` trouve chaque occurrence, `ExactEntityLinker` les regroupe, et l'assertion contrôle le jeton `<<PERSON:1>>`{ .placeholder } partagé.

```python
async def test_repeat_shares_one_token() -> None:
    """A repeated value reuses its first token."""
    pipeline = build_pipeline({"Alice": "PERSON"})
    result = await pipeline.anonymize("Alice met Alice again.")
    assert result.text == "<<PERSON:1>> met <<PERSON:1>> again."
```

## Tester un composant personnalisé

Chaque étape du pipeline est un port, donc vous pouvez glisser votre propre composant à côté d'`ExactMatchDetector` et laisser le détecteur déterministe l'alimenter. Donnez à l'étape une entrée fixe via `ExactMatchDetector`, puis vérifiez `result.text`. Voir [Étendre PIIGhost](../extending.md) pour les ports et des exemples de composants complets.

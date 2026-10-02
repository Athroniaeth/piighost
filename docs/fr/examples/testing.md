---
icon: lucide/test-tube
tags:
  - Tests
---

# Tester un pipeline sans modèle

Vous voulez vérifier ce que produit un pipeline sans télécharger de modèle NER ni accéder au réseau. `ExactMatchDetector` vous le permet. Vous lui indiquez quelles valeurs littérales correspondent à quel label, et il trouve leurs occurrences avec une simple regex. Le reste du pipeline s'exécute sans changement, si bien qu'un test exerce la vraie liaison, la vraie résolution et la vraie dé-identification contre un détecteur dont vous maîtrisez la sortie.

Servez-vous-en pour tester un pipeline que vous avez assemblé, ou un composant que vous avez écrit, contre `<<PERSON:1>>`{ .placeholder } plutôt que contre la prédiction d'un modèle.

## Vérifier une chaîne dé-identifiée

Construisez un pipeline avec `ExactMatchDetector`, exécutez-le sur un texte, puis comparez `result.text` à la sortie attendue.

```python
--8<-- "snippets/testing.py"
```

`ExactMatchDetector` prend un dictionnaire de valeur littérale vers label. Il émet une détection par occurrence avec une confiance de `1.0`, donc sa sortie ne varie jamais d'une exécution à l'autre.

## L'écrire comme un test pytest

Le projet lance pytest avec `asyncio_mode = "auto"`, donc un `async def test_...` n'a besoin d'aucun décorateur. Vérifiez à la fois la sortie exacte et l'absence de la valeur brute.

```python
--8<-- "snippets/test_testing.py:helper"
```

Si votre propre projet lance pytest en mode synchrone par défaut, installez `pytest-asyncio` et marquez le test avec `@pytest.mark.asyncio`, ou réglez `asyncio_mode = "auto"` dans la configuration pytest pour vous passer du décorateur.

## Vérifier que les répétitions partagent un jeton

La liaison d'entités regroupe chaque occurrence d'une valeur sous une seule entité, donc un nom répété réutilise son premier jeton. `ExactMatchDetector` trouve chaque occurrence, `ExactEntityLinker` les regroupe, et l'assertion contrôle le jeton `<<PERSON:1>>`{ .placeholder } partagé.

```python
--8<-- "snippets/test_testing.py:repeat"
```

## Tester un composant personnalisé

Chaque étape du pipeline est un port, donc vous pouvez glisser votre propre composant à côté d'`ExactMatchDetector` et laisser le détecteur déterministe l'alimenter. Donnez à l'étape une entrée fixe via `ExactMatchDetector`, puis vérifiez `result.text`. Voir [Étendre PIIGhost](../extending.md) pour les ports et des exemples de composants complets.

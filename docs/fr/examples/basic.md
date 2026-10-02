---
icon: lucide/code
---

# Comment dé-identifier un texte et le restaurer

Vous avez un texte contenant des données confidentielles et vous voulez le dé-identifier, l'envoyer à un LLM, puis restaurer les valeurs d'origine dans la réponse. Ce guide fait l'aller-retour avec le seul cœur de `piighost`, sans modèle ni dépendance optionnelle. Les patterns du détecteur viennent du [hub piighost](https://hub.piighost.dev), récupérés à la première exécution, puis relus depuis le cache sur disque.

Installez le cœur.

```bash
uv add piighost
```

## Faire l'aller-retour

Un pipeline enchaîne un détecteur, un linker et un anonymiseur. `anonymize` renvoie le texte dé-identifié et le token attribué à chaque entité. `deanonymize` rejoue cette correspondance en sens inverse.

```python
--8<-- "snippets/basic.py:hub"
```

`result.text` porte `<<EMAIL:1>>`{ .placeholder } à la place de `alice@example.com`{ .pii }. `result.tokens` associe chaque entité à son token. Passez-le tel quel à `deanonymize` pour retrouver le texte d'origine.

## Restaurer une réponse du LLM

`deanonymize` restaure n'importe quel texte portant les tokens, pas seulement celui que le pipeline a produit. Si le LLM répond avec `<<EMAIL:1>>`{ .placeholder }, réinjectez les vraies valeurs avec la même correspondance `result.tokens`.

```python
--8<-- "snippets/basic.py:reply"
```

## Regrouper les occurrences répétées

Une même valeur citée plusieurs fois reçoit un seul token, donc le LLM garde le fil. `ExactEntityLinker` regroupe les occurrences par valeur et par label.

```python
--8<-- "snippets/basic_exact.fr.py:exact"
```

`ExactMatchDetector` détecte des valeurs littérales fixées, ce qui rend l'exemple reproductible sans charger de modèle. Pour du texte libre, remplacez-le par un détecteur NER ou LLM, voir la [référence des détecteurs](../reference/detectors.md).

## Changer la forme des tokens

`LabelCounterPlaceholderFactory` produit `<<LABEL:N>>`{ .placeholder }. Si vous voulez une autre forme de token, changez la factory passée à l'`Anonymizer`.

```python
--8<-- "snippets/basic_factories.py:factories"
```

Pour restaurer les valeurs, la factory doit préserver l'identité, ce que fait `LabelCounterPlaceholderFactory` et pas `LabelPlaceholderFactory`, qui donne le même `<<PERSON>>`{ .placeholder } à deux personnes distinctes. Voir la page [Placeholder factories](../placeholder-factories.md).

## Voir aussi

- [Détecteurs prêts à l'emploi](detectors.md) pour combiner catalogues et détecteurs.
- [Référence du pipeline](../reference/pipeline.md) pour les étages optionnels.
- [Étendre PIIGhost](../extending.md) pour écrire vos propres composants.

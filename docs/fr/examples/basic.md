---
icon: lucide/code
seo_title: Restaurer les données personnelles dans la réponse du LLM
description: Dé-identifiez un texte, envoyez-le à un LLM, puis restaurez les vraies valeurs de la réponse. L'aller-retour en Python avec piighost seul, sans modèle.
---

# Dé-identifier et restaurer un texte

Vous avez un texte contenant des données confidentielles et vous voulez le dé-identifier, l'envoyer à un LLM, puis restaurer les valeurs d'origine dans la réponse. Ce guide fait l'aller-retour avec le seul cœur de `piighost`, sans modèle ni dépendance optionnelle. Les motifs du détecteur viennent du [catalogue piighost](https://catalog.piighost.dev). Ils sont récupérés à chaque construction du détecteur, ce qui demande un accès réseau.

Installez le cœur.

=== "uv"

    ```bash
    uv add piighost
    ```

=== "pip"

    ```bash
    pip install piighost
    ```

## Faire l'aller-retour

Un pipeline enchaîne un détecteur, un linker et un anonymiseur. Seul le détecteur est obligatoire. Le linker vaut par défaut `ExactEntityLinker` et l'anonymiseur `Anonymizer(LabelCounterPlaceholderFactory())`. `anonymize` renvoie le texte dé-identifié et le jeton attribué à chaque entité. `deanonymize` rejoue cette correspondance en sens inverse.

```python
--8<-- "snippets/basic.py:catalog"
```

La sortie doit être :

```text
--8<-- "snippets/basic.out:catalog"
```

`result.text` porte `<<EMAIL:1>>`{ .placeholder } à la place de `alice@example.com`{ .pii }. `result.tokens` associe chaque entité à son jeton. Passez-le tel quel à `deanonymize` pour retrouver le texte d'origine.

## Restaurer une réponse du LLM

`deanonymize` restaure n'importe quel texte portant les jetons, pas seulement celui que le pipeline a produit. Si le LLM répond avec `<<EMAIL:1>>`{ .placeholder }, réinjectez les vraies valeurs avec la même correspondance `result.tokens`.

```python
--8<-- "snippets/basic.py:reply"
```

La sortie doit être :

```text
--8<-- "snippets/basic.out:reply"
```

## Regrouper les occurrences répétées

Une même valeur citée plusieurs fois reçoit un seul jeton, donc le LLM garde le fil. `ExactEntityLinker` regroupe les occurrences par valeur et par label.

```python
--8<-- "snippets/basic_exact.fr.py:exact"
```

La sortie doit être :

```text
--8<-- "snippets/basic_exact.fr.out"
```

`ExactMatchDetector` détecte des valeurs littérales fixées. L'exemple reste ainsi reproductible sans charger de modèle. Pour du texte libre, remplacez-le par un détecteur NER (reconnaissance d'entités nommées) ou LLM, voir la [référence des détecteurs](../reference/detectors.md).

## Changer la forme des jetons

`LabelCounterPlaceholderFactory`, la factory par défaut, produit `<<LABEL:N>>`{ .placeholder }. Si vous voulez une autre forme de jeton, passez au pipeline un `Anonymizer` construit sur une autre factory. Ici, `LabelHashPlaceholderFactory` remplace le numéro par une empreinte courte.

```python
--8<-- "snippets/basic_factories.py:factories"
```

La sortie doit être :

```text
--8<-- "snippets/basic_factories.out"
```

L'empreinte est calculée à partir du label et du rang de l'entité, jamais à partir de la valeur. `Patrick`{ .pii } garde donc le même jeton à ses deux apparitions, et `Marie`{ .pii } en reçoit un autre.

Pour restaurer les valeurs, la factory doit préserver l'identité, c'est-à-dire donner un jeton distinct à chaque valeur. `LabelCounterPlaceholderFactory` le fait. `LabelPlaceholderFactory` ne le fait pas, parce qu'elle donne le même `<<PERSON>>`{ .placeholder } à deux personnes distinctes. Voir la page [Fabriques de placeholders](../placeholder-factories.md).

## Voir aussi

- [Détecteurs prêts à l'emploi](detectors.md) pour combiner groupes du catalogue et détecteurs.
- [Référence du pipeline](../reference/pipeline.md) pour les étages optionnels.
- [Étendre piighost](../extending.md) pour écrire vos propres composants.

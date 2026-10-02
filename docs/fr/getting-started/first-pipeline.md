---
icon: lucide/play
---

# Premier pipeline

Vous allez construire un pipeline qui détecte des noms et des lieux arbitraires, pas seulement des valeurs connues d'avance, et le voir tourner à chaque étape. Deux détecteurs conviennent pour ça, un modèle NER (GLiNER2) ou un catalogue de motifs regex. Vous partez d'un détecteur, ajoutez les trois composants restants un par un, puis lancez le pipeline sur une phrase.

!!! note "Prérequis"
    `piighost` installé, voir [Installation](installation.md). Le chemin regex n'utilise que le socle, sans extra. Le chemin GLiNER2 demande l'extra `gliner2` et télécharge un modèle au premier chargement.

## 1. Choisir un détecteur

Le détecteur lit le texte et renvoie des détections, une par valeur trouvée. Le reste du pipeline est identique quel que soit le détecteur, alors choisissez celui qui correspond à votre texte.

=== "Regex (catalogue)"

    Un `RegexDetector` reconnaît des motifs, c'est-à-dire des chaînes de caractères qui suivent une structure fixe. Pour des noms et des lieux arbitraires, on lui passe un dictionnaire qui associe un label à un motif. Ici deux motifs, un pour les prénoms, un pour la ville.

    ```python
    --8<-- "snippets/first_pipeline.py:detector"
    ```

    Pour les formats non spécifiques à une langue, comme l'email et l'URL, le [hub piighost](https://hub.piighost.dev) publie des catalogues tout faits. Le groupe épinglé ci-dessous est récupéré à la première construction, puis relu depuis le cache sur disque.

    ```python
    --8<-- "snippets/detector_hub.py:detector"
    ```

=== "GLiNER2 (NER)"

    Un NER est un modèle d'IA qui, sur un texte, classe les mots selon une classification décidée à l'avance (nom, prénom, lieu, organisation). Contrairement à la regex, il n'a pas besoin de connaître les valeurs à l'avance, il détecte un prénom qu'il n'a jamais vu.

    ```python
    --8<-- "snippets/detector_gliner2.py:detector"
    ```

    Le premier argument est un nom de modèle chargé par GLiNER2, ou une instance déjà chargée. `labels` fixe les catégories interrogées. `threshold` est la confiance minimale au-dessus de laquelle une détection est gardée.

## 2. Regrouper les détections en entités

Un même prénom peut apparaître plusieurs fois. Le linker regroupe les détections d'une même valeur et d'un même label en une seule entité, pour que chaque occurrence reçoive plus tard le même jeton.

```python
--8<-- "snippets/first_pipeline.py:linker"
```

## 3. Assigner un jeton à chaque entité

L'anonymiseur remplace chaque entité par un placeholder, c'est-à-dire le jeton qui prend sa place dans le texte. Le jeton dépend de la factory choisie. `LabelCounterPlaceholderFactory` numérote par label, donc `<<PERSON:1>>`{ .placeholder }, `<<PERSON:2>>`{ .placeholder }, `<<LOCATION:1>>`{ .placeholder }.

```python
--8<-- "snippets/first_pipeline.py:anonymizer"
```

## 4. Assembler et lancer

`AnonymizationPipeline` enchaîne les trois composants dans l'ordre, détecter, regrouper, remplacer. Son appel `anonymize` est asynchrone et renvoie un résultat dont `text` porte la phrase dé-identifiée.

```python
--8<-- "snippets/first_pipeline.py:run"
```

La sortie doit être :

```text
--8<-- "snippets/first_pipeline.out"
```

Chaque occurrence de `Patrick`{ .pii } reçoit le même `<<PERSON:1>>`{ .placeholder }, `Paris`{ .pii } garde `<<LOCATION:1>>`{ .placeholder } à ses deux apparitions, et `Marie`{ .pii } reçoit le numéro suivant `<<PERSON:2>>`{ .placeholder }. C'est le linker de l'étape 2 qui rend cette cohérence possible.

## Comment ça marche

`AnonymizationPipeline` exécute trois étapes obligatoires. Le détecteur trouve les données confidentielles, le linker regroupe les occurrences d'une même valeur en une entité, l'anonymiseur remplace chaque entité par le jeton de sa factory. Des étapes optionnelles existent (expansion des occurrences manquées, fusion d'entités), désactivées par défaut, tandis que la résolution de chevauchement s'exécute par défaut. Seul le détecteur est strictement requis pour construire, ce qui suffit pour un premier pipeline.

## Et ensuite

- Pour décrire ce pipeline dans un fichier plutôt qu'en Python, voir la [Référence TOML](../configuration/toml.md). Un détecteur regex y prend ses catalogues avec `catalogs = ["hub:piighost/generic:fab51b33"]`.
- Pour dé-identifier au fil d'une conversation avec des jetons stables entre les messages, voir le [Pipeline conversationnel](conversation.md).

---
icon: lucide/play
---

# Premier pipeline

Vous allez construire un pipeline composant par composant, puis le lancer sur une phrase. Vous partez d'un détecteur, ajoutez le linker et l'anonymiseur, puis assemblez le tout. Le détecteur dépend de ce que vous cherchez. Un modèle NER comme GLiNER2 détecte des noms et des lieux qu'il n'a jamais vus. Une regex ne reconnaît que des formats fixes, comme une adresse email.

!!! note "Prérequis"
    `piighost` installé, voir [Installation](installation.md). Le chemin regex n'utilise que le socle, sans extra. Le chemin GLiNER2 demande l'extra `gliner2` et télécharge un modèle au premier chargement.

## 1. Choisir un détecteur

Le détecteur lit le texte et renvoie des détections, une par valeur trouvée. Le reste du pipeline est identique quel que soit le détecteur, alors choisissez celui qui correspond à votre texte.

=== "Regex (catalogue)"

    Un `RegexDetector` reconnaît des motifs, c'est-à-dire des chaînes de caractères qui suivent une structure fixe. On lui passe un dictionnaire qui associe un label à un motif. Un prénom n'a pas de structure fixe, donc les deux motifs ci-dessous listent simplement les valeurs de la phrase d'exemple. Ils illustrent le fonctionnement du pipeline, ils ne détectent pas d'autres noms.

    ```python
    --8<-- "snippets/first_pipeline.fr.py:detector"
    ```

    Pour les formats fixes qui ne dépendent pas d'une langue, comme l'email et l'URL, le [hub piighost](https://hub.piighost.dev) publie des catalogues tout faits. Le groupe `generic` ci-dessous ne contient aucun motif de nom ni de lieu. Il est récupéré depuis le hub à chaque construction du détecteur.

    ```python
    --8<-- "snippets/detector_hub.py:detector"
    ```

=== "GLiNER2 (NER)"

    Un NER est un modèle d'IA qui classe les mots d'un texte dans des catégories décidées à l'avance (nom, prénom, lieu, organisation). Contrairement à la regex, il n'a pas besoin de connaître les valeurs à l'avance. Il détecte un prénom qu'il n'a jamais vu.

    ```python
    --8<-- "snippets/detector_gliner2.py:detector"
    ```

    Le premier argument est un nom de modèle chargé par GLiNER2, ou une instance déjà chargée. `labels` fixe les catégories interrogées. `threshold` est la confiance minimale au-dessus de laquelle une détection est gardée.

## 2. Regrouper les détections en entités

Un même prénom peut apparaître plusieurs fois. Le linker regroupe les détections d'une même valeur et d'un même label en une seule entité, pour que chaque occurrence reçoive plus tard le même jeton.

```python
--8<-- "snippets/first_pipeline.fr.py:linker"
```

## 3. Assigner un jeton à chaque entité

L'anonymiseur remplace chaque entité par un placeholder, c'est-à-dire le jeton qui prend sa place dans le texte. Le jeton dépend de la factory choisie. `LabelCounterPlaceholderFactory` numérote les jetons par label. Cela donne `<<PERSON:1>>`{ .placeholder }, `<<PERSON:2>>`{ .placeholder }, `<<LOCATION:1>>`{ .placeholder }.

```python
--8<-- "snippets/first_pipeline.fr.py:anonymizer"
```

## 4. Assembler et lancer

`AnonymizationPipeline` enchaîne les trois composants dans l'ordre. Il détecte, regroupe, puis remplace. Sa méthode `anonymize` est asynchrone. Elle renvoie un résultat dont l'attribut `text` porte la phrase dé-identifiée.

```python
--8<-- "snippets/first_pipeline.fr.py:run"
```

La sortie doit être :

```text
--8<-- "snippets/first_pipeline.fr.out"
```

Chaque occurrence de `Patrick`{ .pii } reçoit le même `<<PERSON:1>>`{ .placeholder }. `Paris`{ .pii } garde `<<LOCATION:1>>`{ .placeholder } à ses deux apparitions. `Marie`{ .pii } reçoit le numéro suivant, `<<PERSON:2>>`{ .placeholder }. C'est le linker de l'étape 2 qui rend cette cohérence possible.

## Comment ça marche

`AnonymizationPipeline` exécute trois étapes obligatoires. Le détecteur trouve les données confidentielles. Le linker regroupe les occurrences d'une même valeur en une entité. L'anonymiseur remplace chaque entité par le jeton de sa factory. Des étapes optionnelles (expansion des occurrences manquées, fusion d'entités) existent, désactivées par défaut. La résolution de chevauchement, elle, s'exécute par défaut. Seul le détecteur est strictement requis pour construire le pipeline, et ce minimum suffit pour un premier pipeline.

## Voir aussi

- Pour décrire ce pipeline dans un fichier plutôt qu'en Python, voir la [référence de configuration](../configuration/toml.md). Un détecteur regex y prend ses catalogues avec `catalogs = ["hub:piighost/generic"]`.
- Pour dé-identifier au fil d'une conversation avec des jetons stables entre les messages, voir le [Pipeline conversationnel](conversation.md).

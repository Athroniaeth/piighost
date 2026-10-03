---
icon: lucide/zap
---

# Quickstart

Le chemin le plus court pour voir `piighost` à l'œuvre, sans télécharger de modèle. Vous allez dé-identifier une phrase à partir d'un dictionnaire de valeurs connues, en moins d'une minute.

!!! note "Prérequis"
    `piighost` installé, voir [Installation](installation.md). Cet exemple n'utilise que le socle, sans extra.

```python
--8<-- "snippets/quickstart.fr.py"
```

La sortie doit être :

```text
--8<-- "snippets/quickstart.fr.out"
```

## Comment ça marche

`ExactMatchDetector` repère les occurrences exactes, aux frontières de mots, des valeurs du dictionnaire fourni. Le détecteur suffit à lui seul, parce que le pipeline complète les étapes obligatoires avec leurs valeurs par défaut. Il regroupe les détections d'une même valeur et d'un même label avec un `ExactEntityLinker`, puis remplace chaque entité avec un `LabelCounterPlaceholderFactory` qui numérote par label. Les placeholders obtenus sont `<<PERSON:1>>`{ .placeholder } et `<<LOCATION:1>>`{ .placeholder }. La résolution de chevauchement s'exécute par défaut. Les étapes optionnelles restent désactivées : expansion d'entités, résolution d'entités, override et garde-fou. C'est suffisant pour un premier essai, sans aucun modèle à charger.

## Et ensuite

- Pour une vraie détection automatique, noms et lieux arbitraires, passez au [Premier pipeline](first-pipeline.md) avec un NER comme GLiNER2.
- Pour décrire un pipeline complet dans un fichier plutôt qu'en Python, voir la [Référence TOML](../configuration/toml.md).
- Pour dé-identifier au fil d'une conversation avec mémoire persistante, voir le [Pipeline conversationnel](conversation.md).

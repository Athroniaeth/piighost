---
icon: lucide/zap
---

# Démarrage rapide

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

`ExactMatchDetector` repère les valeurs du dictionnaire aux frontières de mots. Le pipeline complète les autres étapes avec leurs valeurs par défaut, dont un anonymiseur qui numérote les jetons par label. Le [Premier pipeline](first-pipeline.md) construit ces étapes une par une.

## Voir aussi

- Pour une vraie détection automatique, noms et lieux arbitraires, passez au [Premier pipeline](first-pipeline.md) avec un NER comme GLiNER2.
- Pour décrire un pipeline complet dans un fichier plutôt qu'en Python, voir la [référence de configuration](../configuration/toml.md).
- Pour dé-identifier au fil d'une conversation avec mémoire persistante, voir le [Pipeline conversationnel](conversation.md).

---
icon: lucide/play
---

# Premier pipeline

Vous allez construire un pipeline qui détecte des noms et des lieux arbitraires, pas seulement des valeurs connues d'avance, et le voir tourner à chaque étape. Deux détecteurs conviennent pour ça, un modèle NER (GLiNER2) ou un catalogue de motifs regex. Vous partez d'un détecteur, ajoutez les trois composants restants un par un, puis lancez le pipeline sur une phrase.

!!! note "Prérequis"
    `piighost` installé, voir [Installation](installation.md). Le chemin regex n'utilise que le socle, sans extra. Le chemin GLiNER2 demande l'extra `gliner2` et télécharge un modèle au premier chargement.

## 1. Choisir un détecteur

Le détecteur lit le texte et renvoie des détections, une par PII trouvée. Le reste du pipeline est identique quel que soit le détecteur, alors choisissez celui qui correspond à votre texte.

=== "Regex (catalogue)"

    Un `RegexDetector` reconnaît des motifs, c'est-à-dire des chaînes de caractères qui suivent une structure fixe. Pour des noms et des lieux arbitraires, on lui passe un dictionnaire qui associe un label à un motif. Ici deux motifs, un pour les prénoms, un pour la ville.

    ```python
    from piighost.components.detector import RegexDetector

    patterns = {
        "PERSON": r"\b(?:Patrick|Marie)\b",
        "LOCATION": r"\bParis\b",
    }
    detector = RegexDetector(patterns)
    ```

    `piighost` fournit aussi des catalogues prêts à l'emploi pour les formats non spécifiques à une langue, comme l'email et l'URL.

    ```python
    from piighost.components.detector import RegexDetector
    from piighost.components.detector.patterns import GENERIC_PATTERNS

    detector = RegexDetector(GENERIC_PATTERNS)
    ```

=== "GLiNER2 (NER)"

    Un NER est un modèle d'IA qui, sur un texte, classe les mots selon une classification décidée à l'avance (nom, prénom, lieu, organisation). Contrairement à la regex, il n'a pas besoin de connaître les valeurs à l'avance, il détecte un prénom qu'il n'a jamais vu.

    ```python
    from piighost.components.detector.ner import Gliner2Detector

    detector = Gliner2Detector(
        model="fastino/gliner2-multi-v1",
        labels=["PERSON", "LOCATION"],
        threshold=0.5,
    )
    ```

    Le premier argument est un nom de modèle chargé par GLiNER2, ou une instance déjà chargée. `labels` fixe les catégories interrogées. `threshold` est la confiance minimale au-dessus de laquelle une détection est gardée.

## 2. Regrouper les détections en entités

Un même prénom peut apparaître plusieurs fois. Le linker regroupe les détections d'une même valeur et d'un même label en une seule entité, pour que chaque occurrence reçoive plus tard le même jeton.

```python
from piighost.components.linker import ExactEntityLinker

linker = ExactEntityLinker()
```

## 3. Assigner un jeton à chaque entité

L'anonymiseur remplace chaque entité par un placeholder, c'est-à-dire le jeton qui prend sa place dans le texte. Le jeton dépend de la factory choisie. `LabelCounterPlaceholderFactory` numérote par label, donc `<<PERSON:1>>`{ .placeholder }, `<<PERSON:2>>`{ .placeholder }, `<<LOCATION:1>>`{ .placeholder }.

```python
from piighost.components.anonymizer import Anonymizer
from piighost.components.placeholder import LabelCounterPlaceholderFactory

anonymizer = Anonymizer(LabelCounterPlaceholderFactory())
```

## 4. Assembler et lancer

`AnonymizationPipeline` enchaîne les trois composants dans l'ordre, détecter, regrouper, remplacer. Son appel `anonymize` est asynchrone et renvoie un résultat dont `text` porte la phrase dé-identifiée.

```python
import asyncio

from piighost.pipeline import AnonymizationPipeline

pipeline = AnonymizationPipeline(detector, linker, anonymizer)


async def main() -> None:
    text = "Patrick habite à Paris. Patrick aime Paris. Marie aussi."
    result = await pipeline.anonymize(text)
    print(result.text)


asyncio.run(main())
```

La sortie doit être :

```text
<<PERSON:1>> habite à <<LOCATION:1>>. <<PERSON:1>> aime <<LOCATION:1>>. <<PERSON:2>> aussi.
```

Chaque occurrence de `Patrick`{ .pii } reçoit le même `<<PERSON:1>>`{ .placeholder }, `Paris`{ .pii } garde `<<LOCATION:1>>`{ .placeholder } à ses deux apparitions, et `Marie`{ .pii } reçoit le numéro suivant `<<PERSON:2>>`{ .placeholder }. C'est le linker de l'étape 2 qui rend cette cohérence possible.

## Comment ça marche

`AnonymizationPipeline` exécute trois étapes obligatoires. Le détecteur trouve les PII, le linker regroupe les occurrences d'une même valeur en une entité, l'anonymiseur remplace chaque entité par le jeton de sa factory. Des étapes optionnelles existent (résolution de chevauchement, expansion des occurrences manquées, fusion d'entités), toutes désactivées par défaut, ce qui suffit pour un premier pipeline.

## Et ensuite

- Pour décrire ce pipeline dans un fichier plutôt qu'en Python, voir la [Référence TOML](../configuration/toml.md). Un détecteur regex y prend ses catalogues avec `catalogs = ["generic"]`.
- Pour dé-identifier au fil d'une conversation avec des jetons stables entre les messages, voir le [Pipeline conversationnel](conversation.md).

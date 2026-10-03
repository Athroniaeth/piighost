---
icon: lucide/scan-search
tags:
  - Détecteur
  - Regex
---

# Comment utiliser les catalogues de patterns et combiner des détecteurs

`piighost` tire du [hub piighost](https://hub.piighost.dev) des catalogues de patterns regex prêts à l'emploi pour les PII à structure fixe (email, IP, IBAN, téléphone). Ce guide montre comment les charger, les fusionner et combiner plusieurs détecteurs, avec le seul cœur de `piighost`.

Quatre groupes du hub couvrent les formats courants. Chacun est un ensemble d'entrées `label` vers `pattern`. Le suffixe après le dernier deux-points épingle le groupe sur un commit.

- `hub:piighost/generic:fab51b33`, email, URL, IPv4, carte bancaire, indépendants du pays
- `hub:piighost/us:29d5c0a5`, téléphone, ZIP, ITIN, SSN, préfixés `US_`
- `hub:piighost/eu:b0303ae6`, IBAN ISO 13616 pan-européen
- `hub:piighost/fr:6802f5ef`, téléphone, IBAN, NIR, SIRET, SIREN, préfixés `FR_`

Un groupe épinglé est récupéré depuis le hub à la première construction d'un détecteur, puis relu depuis le cache sur disque, hors ligne compris. Les secrets comme les clés d'API sont dans les groupes du hub `piighost/secrets` et `piighost/secrets-extended`. Ces groupes se tirent de la même façon, par exemple avec `catalogs = ["hub:piighost/secrets:d822d04c"]` dans une config.

Pour le détail des labels, voir la [référence des détecteurs](../reference/detectors.md).

## Utiliser un seul catalogue

Construisez un `RegexDetector` à partir du groupe avec `from_hub`, puis montez le pipeline.

```python
--8<-- "snippets/detectors_hub.py"
```

## Fusionner générique et régional

Si vous voulez couvrir à la fois les PII génériques et celles d'une région, tirez chaque groupe avec `pull` et fusionnez les dictionnaires obtenus. `pull` renvoie un dictionnaire `label` vers `pattern`. Quand deux dictionnaires ont un label en commun, l'entrée du dictionnaire de droite l'emporte.

```python
--8<-- "snippets/detectors_merge.py:example"
```

Pour ne garder que certains labels, construisez un dictionnaire à la carte.

```python
--8<-- "snippets/detectors_pick.py:example"
```

## Combiner plusieurs détecteurs

`CompositeDetector` exécute plusieurs détecteurs sur le même texte et concatène leurs détections. Les chevauchements sont arbitrés par l'étage de résolution du pipeline. C'est ainsi qu'on couple un détecteur regex à un détecteur qui reconnaît des noms.

```python
--8<-- "snippets/detectors_composite.py:example"
```

En production, remplacez `ExactMatchDetector` par un détecteur NER ou LLM, voir la [référence des détecteurs](../reference/detectors.md). `ExactMatchDetector` sert ici à garder l'exemple reproductible sans modèle.

## Traiter un texte long

Un détecteur NER a une fenêtre de contexte bornée, et un long document peut la dépasser. `ChunkedDetector` enveloppe n'importe quel détecteur, découpe le texte en fragments qui se chevauchent, détecte sur chacun et reprojette les positions sur le texte d'origine.

```python
--8<-- "snippets/detectors_chunked.py:example"
```

Laissez `splitter=None` pour un `RecursiveCharacterTextSplitter` par défaut, réglé pour de vrais documents. Le `chunk_size` réduit ci-dessus ne sert qu'à forcer plusieurs fragments dans un court exemple.

## Charger les catalogues depuis un fichier de config

Si vous pilotez le pipeline par un fichier de configuration plutôt que par du code, un détecteur regex accepte une clé `catalogs`.

```toml
--8<-- "snippets/detectors_config.toml"
```

Le détecteur fusionne d'abord les catalogues, puis les `patterns` en ligne. Pour un même label, un pattern en ligne l'emporte donc sur celui d'un catalogue. Voir la [configuration TOML](../configuration/toml.md).

## Voir aussi

- [Dé-identifier un texte et le restaurer](basic.md) pour l'aller-retour complet.
- [Référence des détecteurs](../reference/detectors.md) pour le catalogue des labels.
- [Étendre PIIGhost](../extending.md) pour écrire vos propres détecteurs.

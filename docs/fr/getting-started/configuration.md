---
icon: lucide/file-cog
---

# Fichier de configuration

Vous allez décrire un pipeline complet dans un fichier TOML, en le faisant passer de trois lignes à un pipeline conversationnel qui garde un jeton stable d'un tour de conversation à l'autre. Chaque étape change une seule chose dans le fichier, puis vous vérifiez le fichier et vous le lancez pour voir ce qui a changé.

!!! note "Prérequis"
    `piighost` installé avec l'extra `config`, `pip install "piighost[config]"`, voir [Installation](installation.md). Chaque étape tourne sans modèle et sans accès réseau. L'étape 6 ajoute l'extra `fuzzy`.

## 1. Mettre en place la boucle de vérification

Deux commandes pilotent toutes les étapes qui suivent. Commencez par un `pipeline.toml` volontairement faux, avec `pattern` là où le schéma attend `patterns`.

```toml
[detector]
type = "regex"
pattern = { EMAIL = '[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}' }
```

Validez-le.

```bash
piighost validate pipeline.toml
```

La sortie doit être :

```text
invalid configuration in pipeline.toml: 1 validation error for PipelineConfig
detector.regex.pattern
  Extra inputs are not permitted [type=extra_forbidden, input_value={'EMAIL': '[a-z0-9._%+-]+...a-z0-9.-]+\\.[a-z]{2,}'}, input_type=dict]
    For further information visit https://errors.pydantic.dev/2.13/v/extra_forbidden
```

La commande nomme la section et la clé qui coince, et sort en code `1`, ce qui en fait aussi un garde-fou de CI. Relancez-la après chaque modification ci-dessous. Elle ne construit aucun composant, donc elle ne charge aucun modèle.

Exportez le schéma une fois et pointez votre éditeur dessus pour obtenir la complétion sur les noms de sections et de clés.

```bash
piighost schema > schema.json
```

Les deux commandes sont documentées dans l'[interface en ligne de commande](../reference/cli.md).

## 2. Construire un pipeline en trois lignes

Corrigez la clé, `patterns` avec un s. Le fichier ne porte plus qu'une section, et cela suffit à construire un pipeline.

```toml
[detector]
type = "regex"
patterns = { EMAIL = '[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}' }
```

```bash
piighost validate pipeline.toml
```

```text
OK: pipeline.toml
```

Écrivez `run.py` à côté. Il charge le fichier et dé-identifie le texte que vous passez en ligne de commande, et toutes les étapes suivantes le réutilisent tel quel.

```python
import asyncio
import sys

from piighost.config import load_pipeline


async def main() -> None:
    pipeline = load_pipeline("pipeline.toml")
    result = await pipeline.anonymize(sys.argv[1])
    print(result.text)


asyncio.run(main())
```

```bash
python run.py "Write to alice@corp.com from 10.0.0.7."
```

La sortie doit être :

```text
Write to <<EMAIL:1>> from 10.0.0.7.
```

Le jeton nomme le label et le numérote alors que le fichier ne déclare aucun anonymiseur, et les deux occurrences d'une même adresse partageraient ce jeton alors que le fichier ne déclare aucun linker. Chacune de ces deux étapes retombe sur sa valeur par défaut, la résolution des chevauchements aussi. Ce fichier est sur le disque sous `examples/config/detector_only.toml`.

## 3. Choisir le jeton

Demandez un caviardage simple à la place du jeton numéroté, avec une section `[anonymizer.placeholder]`.

```toml
[detector]
type = "regex"
patterns = { EMAIL = '[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}' }

[anonymizer.placeholder]
type = "redact"
```

```bash
python run.py "Write to alice@corp.com from 10.0.0.7."
```

La sortie doit être :

```text
Write to <<REDACT>> from 10.0.0.7.
```

L'adresse a disparu, et son label avec elle. `examples/config/minimal.toml` porte ce fichier avec le linker par défaut écrit explicitement, et `examples/config/minimal.json` le porte en JSON, le suffixe choisissant le parseur. La [référence de configuration](../configuration/toml.md) liste tous les styles de jeton.

## 4. Tirer un catalogue prêt à l'emploi

Votre motif ne couvre que l'email, donc l'adresse IP du texte d'exemple est passée en clair. Remplacez le motif inline par le catalogue `generic`, qui porte l'email, l'URL, l'IPv4 et la carte bancaire. Quatre labels arrivent maintenant à l'anonymiseur, donc remettez le jeton numéroté pour les distinguer.

```toml
[detector]
type = "regex"
catalogs = ["generic"]

[anonymizer.placeholder]
type = "label_counter"
```

```bash
python run.py "Write to alice@corp.com and prénom@corp.com from 10.0.0.7."
```

La sortie doit être :

```text
Write to <<EMAIL:1>> and pré<<EMAIL:2>> from <<IPV4:1>>.
```

L'adresse IP est couverte, et `prénom@corp.com`{ .pii } l'est à moitié. Les motifs du catalogue reconnaissent des formes ASCII, donc la correspondance démarre après l'accent. Ajoutez un motif inline sur le même label, et il prend le pas sur celui du catalogue.

```toml
[detector]
type = "regex"
catalogs = ["generic"]
patterns = { EMAIL = '[A-Za-zÀ-ÿ0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}' }

[anonymizer.placeholder]
type = "label_counter"
```

```bash
python run.py "Write to alice@corp.com and prénom@corp.com from 10.0.0.7."
```

La sortie doit être :

```text
Write to <<EMAIL:1>> and <<EMAIL:2>> from <<IPV4:1>>.
```

L'adresse entière est devenue un jeton. Les catalogues fusionnent d'abord, vos motifs inline ensuite, donc un label déclaré des deux côtés prend votre motif.

## 5. Faire tourner deux détecteurs à la fois

Le catalogue reconnaît des formats, et un prénom n'a pas de format. Déclarez les prénoms que vous connaissez déjà dans un second détecteur, et laissez un détecteur `composite` lancer les deux et fusionner ce qu'ils renvoient.

```toml
[detector]
type = "composite"

[[detector.detectors]]
type = "regex"
catalogs = ["generic"]
patterns = { EMAIL = '[A-Za-zÀ-ÿ0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}' }

[[detector.detectors]]
type = "exact"
values = { Patrick = "PERSON", Patrik = "PERSON" }

[anonymizer.placeholder]
type = "label_counter"
```

```bash
python run.py "Patrick writes to alice@corp.com. Patrik answers from 10.0.0.7."
```

La sortie doit être :

```text
<<PERSON:1>> writes to <<EMAIL:1>>. <<PERSON:2>> answers from <<IPV4:1>>.
```

Les prénoms et les formats sont attrapés en une seule passe. Une même personne écrite de deux façons reçoit encore deux jetons, `<<PERSON:1>>`{ .placeholder } et `<<PERSON:2>>`{ .placeholder }, ce que l'étape suivante règle.

## 6. Fusionner les entités presque identiques

`Patrick`{ .pii } et `Patrik`{ .pii } sont la même personne, et un modèle qui lit deux jetons suit deux personnes. Installez l'extra `fuzzy`.

```bash
pip install "piighost[config,fuzzy]"
```

Ajoutez une section `[entity_resolver]` à la fin du fichier, qui regroupe les entités dont les valeurs sont assez proches l'une de l'autre.

```toml
[entity_resolver]
type = "fuzzy"
threshold = 0.85
```

```bash
python run.py "Patrick writes to alice@corp.com. Patrik answers from 10.0.0.7."
```

La sortie doit être :

```text
<<PERSON:1>> writes to <<EMAIL:1>>. <<PERSON:1>> answers from <<IPV4:1>>.
```

Les deux orthographes partagent `<<PERSON:1>>`{ .placeholder }. Retirez la section et l'étape disparaît, comme pour toute étape optionnelle.

## 7. Garder les jetons d'un message à l'autre

Chaque exécution de `run.py` repart de zéro dans la numérotation, car le pipeline ne garde rien d'un appel au suivant. Ajoutez une section `[memory]` à la fin du fichier, qui lui donne un stockage par fil et change le chargeur que vous appelez.

```toml
[memory]
type = "in_memory"
```

```bash
piighost validate pipeline.toml
```

```text
OK: pipeline.toml
```

Le fichier est valide, et `run.py` le refuse maintenant.

```bash
python run.py "Patrick writes to alice@corp.com."
```

La trace se termine sur :

```text
piighost.exceptions.ConfigError: this configuration declares a memory; use load_thread_pipeline
```

Un fichier qui porte une mémoire décrit un pipeline conversationnel, donc il passe par `load_thread_pipeline`. Écrivez `thread.py`, qui envoie deux messages sur le fil `"thread-42"`.

```python
import asyncio

from piighost.config import load_thread_pipeline


async def main() -> None:
    pipeline = load_thread_pipeline("pipeline.toml")
    first = await pipeline.anonymize("Patrick writes to alice@corp.com.", "thread-42")
    print(first.text)
    second = await pipeline.anonymize("Patrik answers from 10.0.0.7.", "thread-42")
    print(second.text)


asyncio.run(main())
```

```bash
python thread.py
```

La sortie doit être :

```text
<<PERSON:1>> writes to <<EMAIL:1>>.
<<PERSON:1>> answers from <<IPV4:1>>.
```

Le second message réutilise le `<<PERSON:1>>`{ .placeholder } attribué par le premier. Les deux chargeurs se refusent mutuellement les fichiers, donc `load_thread_pipeline` sur un fichier sans mémoire lève `this configuration declares no memory; use load_pipeline`.

## Et ensuite

- [Référence de configuration](../configuration/toml.md) pour chaque section, chaque `type` et chaque clé.
- [Déployer un pipeline en production](../deployment.md) pour une mémoire partagée entre workers, Redis ou une base SQL, avec les valeurs stockées chiffrées au repos. Les deux fichiers sont `examples/config/thread_redis.toml` et `examples/config/thread_sqlalchemy.toml`.
- [Forcer une détection ou laisser une valeur en clair](../examples/overrides.md) pour la whitelist et la blacklist.

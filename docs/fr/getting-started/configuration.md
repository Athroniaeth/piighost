---
icon: lucide/file-cog
---

# Fichier de configuration

Vous allez décrire un pipeline complet dans un fichier TOML, en le faisant passer de trois lignes à un pipeline conversationnel qui garde un jeton stable d'un tour de conversation à l'autre. Chaque étape change une seule chose dans le fichier, puis vous vérifiez le fichier et vous le lancez pour voir ce qui a changé.

!!! note "Prérequis"
    `piighost` installé avec l'extra `config`, `pip install "piighost[config]"`, voir [Installation](installation.md). Chaque étape tourne sans modèle. L'étape 4 récupère une fois un catalogue depuis le [hub piighost](https://hub.piighost.dev), puis le relit depuis le cache sur disque. L'étape 6 ajoute l'extra `fuzzy`.

## 1. Mettre en place la boucle de vérification

Deux commandes pilotent toutes les étapes qui suivent. Commencez par un `pipeline.toml` volontairement faux, avec `pattern` là où le schéma attend `patterns`.

```toml
--8<-- "snippets/configuration/typo.toml"
```

Validez-le.

```bash
--8<-- "snippets/configuration/validate.sh"
```

La sortie doit être :

```text
--8<-- "snippets/configuration/typo.out"
```

La commande nomme la section et la clé qui coince, et sort en code `1`, ce qui en fait aussi un garde-fou de CI. Relancez-la après chaque modification ci-dessous. Elle ne construit aucun composant, donc elle ne charge aucun modèle.

Exportez le schéma une fois et pointez votre éditeur dessus pour obtenir la complétion sur les noms de sections et de clés.

```bash
--8<-- "snippets/configuration/schema.sh"
```

Les deux commandes sont documentées dans l'[interface en ligne de commande](../reference/cli.md).

## 2. Construire un pipeline en trois lignes

Corrigez la clé, `patterns` avec un s. Le fichier ne porte plus qu'une section, et cela suffit à construire un pipeline.

```toml
--8<-- "snippets/configuration/email.toml"
```

```bash
--8<-- "snippets/configuration/validate.sh"
```

```text
--8<-- "snippets/configuration/validated.out"
```

Écrivez `run.py` à côté. Il charge le fichier et dé-identifie le texte que vous passez en ligne de commande, et toutes les étapes suivantes le réutilisent tel quel.

```python
--8<-- "snippets/configuration/run.py"
```

```bash
--8<-- "snippets/configuration/run_email.sh"
```

La sortie doit être :

```text
--8<-- "snippets/configuration/email.out"
```

Le jeton nomme le label et le numérote alors que le fichier ne déclare aucun anonymiseur, et les deux occurrences d'une même adresse partageraient ce jeton alors que le fichier ne déclare aucun linker. Chacune de ces deux étapes retombe sur sa valeur par défaut, la résolution des chevauchements aussi. Ce fichier est sur le disque sous `examples/config/detector_only.toml`.

## 3. Choisir le jeton

Demandez un caviardage simple à la place du jeton numéroté, avec une section `[anonymizer.placeholder]`.

```toml
--8<-- "snippets/configuration/redact.toml"
```

```bash
--8<-- "snippets/configuration/run_email.sh"
```

La sortie doit être :

```text
--8<-- "snippets/configuration/redact.out"
```

L'adresse a disparu, et son label avec elle. `examples/config/minimal.toml` porte ce fichier avec le linker par défaut écrit explicitement, et `examples/config/minimal.json` le porte en JSON, le suffixe choisissant le parseur. La [référence de configuration](../configuration/toml.md) liste tous les styles de jeton.

## 4. Tirer un catalogue du hub

Votre motif ne couvre que l'email, donc l'adresse IP du texte d'exemple est passée en clair. Remplacez le motif inline par le groupe `generic` du hub, qui porte l'email, l'URL, l'IPv4 et la carte bancaire. Le suffixe `:fab51b33` l'épingle sur un commit, donc il est récupéré depuis le hub à la première construction du pipeline, puis relu depuis le cache. Quatre labels arrivent maintenant à l'anonymiseur, donc remettez le jeton numéroté pour les distinguer.

```toml
--8<-- "snippets/configuration/hub.toml"
```

```bash
--8<-- "snippets/configuration/run_hub.sh"
```

La sortie doit être :

```text
--8<-- "snippets/configuration/hub.out"
```

L'adresse IP est couverte, et l'adresse accentuée aussi. Un format qui vous est propre, un numéro de commande comme `CMD-2024-0042`{ .pii }, n'est dans aucun catalogue. Déclarez-le inline, à côté du catalogue.

```toml
--8<-- "snippets/configuration/order.toml"
```

```bash
--8<-- "snippets/configuration/run_order.sh"
```

La sortie doit être :

```text
--8<-- "snippets/configuration/order.out"
```

Le numéro de commande est devenu un jeton. Les catalogues fusionnent d'abord, vos motifs inline ensuite, donc un label déclaré des deux côtés prend votre motif.

## 5. Faire tourner deux détecteurs à la fois

Le catalogue reconnaît des formats, et un prénom n'a pas de format. Déclarez les prénoms que vous connaissez déjà dans un second détecteur, et laissez un détecteur `composite` lancer les deux et fusionner ce qu'ils renvoient.

```toml
--8<-- "snippets/configuration/composite.toml"
```

```bash
--8<-- "snippets/configuration/run_names.sh"
```

La sortie doit être :

```text
--8<-- "snippets/configuration/composite.out"
```

Les prénoms et les formats sont attrapés en une seule passe. Une même personne écrite de deux façons reçoit encore deux jetons, `<<PERSON:1>>`{ .placeholder } et `<<PERSON:2>>`{ .placeholder }, ce que l'étape suivante règle.

## 6. Fusionner les entités presque identiques

`Patrick`{ .pii } et `Patrik`{ .pii } sont la même personne, et un modèle qui lit deux jetons suit deux personnes. Installez l'extra `fuzzy`.

```bash
pip install "piighost[config,fuzzy]"
```

Ajoutez une section `[entity_resolver]` à la fin du fichier, qui regroupe les entités dont les valeurs sont assez proches l'une de l'autre.

```toml
--8<-- "snippets/configuration/fuzzy.toml"
```

```bash
--8<-- "snippets/configuration/run_names.sh"
```

La sortie doit être :

```text
--8<-- "snippets/configuration/fuzzy.out"
```

Les deux orthographes partagent `<<PERSON:1>>`{ .placeholder }. Retirez la section et l'étape disparaît, comme pour toute étape optionnelle.

## 7. Garder les jetons d'un message à l'autre

Chaque exécution de `run.py` repart de zéro dans la numérotation, car le pipeline ne garde rien d'un appel au suivant. Ajoutez une section `[memory]` à la fin du fichier, qui lui donne un stockage par fil et change le chargeur que vous appelez.

```toml
--8<-- "snippets/configuration/memory.toml"
```

```bash
--8<-- "snippets/configuration/validate.sh"
```

```text
--8<-- "snippets/configuration/validated.out"
```

Le fichier est valide, et `run.py` le refuse maintenant.

```bash
--8<-- "snippets/configuration/run_memory.sh"
```

La trace se termine sur :

```text
--8<-- "snippets/configuration/memory.out"
```

Un fichier qui porte une mémoire décrit un pipeline conversationnel, donc il passe par `load_thread_pipeline`. Écrivez `thread.py`, qui envoie deux messages sur le fil `"thread-42"`.

```python
--8<-- "snippets/configuration/thread.py"
```

```bash
--8<-- "snippets/configuration/thread.sh"
```

La sortie doit être :

```text
--8<-- "snippets/configuration/thread.out"
```

Le second message réutilise le `<<PERSON:1>>`{ .placeholder } attribué par le premier. Les deux chargeurs se refusent mutuellement les fichiers, donc `load_thread_pipeline` sur un fichier sans mémoire lève `this configuration declares no memory; use load_pipeline`.

## Et ensuite

- [Référence de configuration](../configuration/toml.md) pour chaque section, chaque `type` et chaque clé.
- [Déployer un pipeline en production](../deployment.md) pour une mémoire partagée entre workers, Redis ou une base SQL, avec les valeurs stockées chiffrées au repos. Les deux fichiers sont `examples/config/thread_redis.toml` et `examples/config/thread_sqlalchemy.toml`.
- [Forcer une détection ou laisser une valeur en clair](../examples/overrides.md) pour la whitelist et la blacklist.

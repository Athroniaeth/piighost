---
icon: lucide/file-cog
seo_title: Configurer la dé-identification dans un fichier TOML
description: Décrivez un pipeline piighost dans un fichier TOML, de trois lignes à un pipeline conversationnel. Choix du token, regex du catalogue, deux détecteurs.
---

# Fichier de configuration

Vous allez décrire un pipeline complet dans un fichier TOML. Le fichier part de trois lignes et devient un pipeline conversationnel, qui garde un jeton stable d'un tour de conversation à l'autre. Chaque étape change une seule chose dans le fichier, puis vous vérifiez le fichier et vous le lancez pour voir ce qui a changé.

!!! note "Prérequis"
    `piighost` installé avec l'extra `config`, `pip install "piighost[config]"`, voir [Installation](installation.md). Chaque étape tourne sans modèle. À partir de l'étape 4, le pipeline récupère un groupe sur le [catalogue piighost](https://catalog.piighost.dev) à chaque exécution, ce qui demande un accès réseau. L'étape 6 ajoute l'extra `fuzzy`.

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

La commande nomme la section et la clé fautive, et sort en code `1`. Ce code de sortie en fait aussi un garde-fou de CI. Relancez-la après chaque modification ci-dessous. Elle ne construit aucun composant, donc elle ne charge aucun modèle.

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

La sortie doit être :

```text
--8<-- "snippets/configuration/validated.out"
```

Écrivez `run.py` à côté. Il charge le fichier et dé-identifie le texte que vous passez en ligne de commande. Toutes les étapes suivantes réutilisent `run.py` tel quel.

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

Le fichier ne déclare aucun anonymiseur, et pourtant le jeton nomme le label et le numérote. Il ne déclare aucun linker, et pourtant les deux occurrences d'une même adresse partageraient ce jeton. L'anonymiseur et le linker retombent chacun sur leur valeur par défaut, et la résolution des chevauchements aussi. Ce fichier est sur le disque sous `examples/config/detector_only.toml`.

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

L'adresse a disparu, et son label avec elle. `examples/config/minimal.toml` porte ce fichier, avec le linker par défaut écrit explicitement. `examples/config/minimal.json` porte le même fichier en JSON. Le suffixe du fichier choisit le parseur. La [référence de configuration](../configuration/toml.md) liste tous les styles de jeton.

## 4. Tirer un groupe du catalogue

Votre motif ne couvre que l'email, donc l'adresse IP du texte d'exemple est passée en clair. Remplacez le motif en ligne par le groupe `generic` du catalogue, qui porte l'email, l'URL, l'IPv4 et la carte bancaire. Sans suffixe, la référence suit la dernière version du groupe, récupérée sur le catalogue à chaque construction du pipeline. Pour figer le groupe, épinglez-le sur un commit, comme `catalog:piighost/generic:fab51b33`. Il est alors récupéré une seule fois, puis relu depuis le cache sur disque. Le fichier n'a plus de section `[anonymizer.placeholder]`, donc le jeton numéroté par défaut revient et distingue les quatre labels.

```toml
--8<-- "snippets/configuration/catalog.toml"
```

```bash
--8<-- "snippets/configuration/run_catalog.sh"
```

La sortie doit être :

```text
--8<-- "snippets/configuration/catalog.out"
```

L'adresse IP est couverte, et l'adresse accentuée aussi. Un format qui vous est propre, un numéro de commande comme `CMD-2024-0042`{ .pii }, n'est dans aucun groupe. Déclarez-le en ligne, à côté du groupe.

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

Le numéro de commande est devenu un jeton. Un label déclaré des deux côtés prend votre motif, parce que les groupes fusionnent d'abord et vos motifs en ligne ensuite.

## 5. Faire tourner deux détecteurs à la fois

Le groupe `generic` reconnaît des formats, et un prénom n'a pas de format. Déclarez les prénoms que vous connaissez déjà dans un second détecteur, et laissez un détecteur `composite` lancer les deux et fusionner ce qu'ils renvoient.

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

Les prénoms et les formats sont attrapés en une seule passe. Une même personne écrite de deux façons reçoit encore deux jetons, `<<PERSON:1>>`{ .placeholder } et `<<PERSON:2>>`{ .placeholder }. L'étape suivante règle ce doublon.

## 6. Fusionner les entités presque identiques

`Patrick`{ .pii } et `Patrik`{ .pii } sont la même personne, et un modèle qui lit deux jetons suit deux personnes. Installez l'extra `fuzzy`.

=== "uv"

    ```bash
    uv add "piighost[config,fuzzy]"
    ```

=== "pip"

    ```bash
    pip install "piighost[config,fuzzy]"
    ```

Ajoutez une section `[entity_resolver]` à la fin du fichier. Cette section regroupe les entités dont les valeurs sont assez proches l'une de l'autre.

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

Chaque exécution de `run.py` repart de zéro dans la numérotation, car le pipeline ne garde rien d'un appel au suivant. Ajoutez une section `[memory]` à la fin du fichier. Cette section donne au pipeline un stockage par conversation, et change le chargeur que vous appelez.

```toml
--8<-- "snippets/configuration/memory.toml"
```

```bash
--8<-- "snippets/configuration/validate.sh"
```

La sortie doit être :

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

Un fichier qui porte une mémoire décrit un pipeline conversationnel, donc il passe par `load_thread_pipeline`. Écrivez `thread.py`, qui envoie deux messages sur la conversation `"thread-42"`.

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

Le second message réutilise le `<<PERSON:1>>`{ .placeholder } attribué par le premier. Chaque chargeur refuse les fichiers de l'autre. `load_thread_pipeline` sur un fichier sans mémoire lève donc `this configuration declares no memory; use load_pipeline`.

## Voir aussi

- [Référence de configuration](../configuration/toml.md) pour chaque section, chaque `type` et chaque clé.
- [Déploiement](../deployment.md) pour une mémoire partagée entre workers, Redis ou une base SQL, avec les valeurs stockées chiffrées au repos. Les deux fichiers sont `examples/config/thread_redis.toml` et `examples/config/thread_sqlalchemy.toml`.
- [Masquer ou laisser en clair](../examples/overrides.md) pour la liste à masquer et la liste à laisser en clair.

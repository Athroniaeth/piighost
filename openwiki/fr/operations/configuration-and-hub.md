---
type: operations
title: Configurer un pipeline par fichier, hub et ligne de commande
description: Comment décrire un pipeline PIIGhost dans un fichier TOML ou JSON, le surcharger par l'environnement, tirer des catalogues de motifs du hub, fournir les secrets et contrôler le tout avec la commande piighost.
tags: [configuration, toml, hub, cli, secrets, environment]
verified:
  - by: openwiki/0.6.1
    at: 2026-10-01T18:36:49.731Z
sources:
  - id: openwiki-source-edd617907d8703b014c2a6c7
    resource: repo://src/piighost/cli/__init__.py
  - id: openwiki-source-845a3e90c784289b153f646a
    resource: repo://src/piighost/config/models/cipher.py
  - id: openwiki-source-41e1e26a4994aaf47da714b8
    resource: repo://src/piighost/config/models/detector.py
  - id: openwiki-source-7ef27c7836ed8bc6a9f4f484
    resource: repo://src/piighost/config/models/hasher.py
  - id: openwiki-source-884a2e563fa6c83993666a78
    resource: repo://src/piighost/config/models/memory.py
  - id: openwiki-source-78a981471914dd9a421617be
    resource: repo://src/piighost/config/settings.py
  - id: openwiki-source-025fa1ad7c6dbf188e59fca7
    resource: repo://src/piighost/hub.py
generated: { by: "claude-code", at: "2026-10-01T18:36:49.731Z" }
---

# Configurer un pipeline par fichier, hub et ligne de commande

## En bref

- Un fichier texte (TOML ou JSON) décrit toute la chaîne de protection, c'est-à-dire ce qu'on cherche, comment on le remplace, où on garde la mémoire des conversations.
- Le fichier ne contient jamais de secret. Les clés et mots de passe viennent des variables d'environnement du serveur.
- Les listes de motifs (e-mails, numéros de carte, etc.) peuvent venir d'un registre en ligne, le hub. Une version figée est téléchargée une fois, puis lue en local.
- La commande `piighost validate` contrôle un fichier sans rien lancer. Elle convient à une vérification automatique avant mise en production.
- Une faute de frappe dans le fichier est refusée, jamais ignorée.

Il n'y a pas d'interface graphique. Toute la configuration passe par ce fichier et par la ligne de commande. Les termes sont définis dans le [glossaire](../glossary.md). Chaque section et chaque clé du fichier sont listées dans la [référence de configuration](../../../docs/fr/configuration/toml.md) du guide technique. Le [tutoriel de configuration](../../../docs/fr/getting-started/configuration.md) construit un fichier pas à pas.

## Choisir comment charger la configuration

| Vous voulez… | Appelez | Résultat |
|---|---|---|
| Vérifier un fichier sans rien construire | `load_config(source)` ou `piighost validate` | un `PipelineConfig` validé, aucun modèle chargé |
| Protéger des textes isolés | `load_pipeline(source)` | un `AnonymizationPipeline` |
| Protéger une conversation | `load_thread_pipeline(source)` | un `ThreadAnonymizationPipeline` |

`source` est un chemin de fichier ou une référence hub (`hub:piighost/generic:fab51b33`). Le suffixe `.json` choisit le lecteur JSON, tout autre suffixe le lecteur TOML (`config/settings.py:54-69`).

## Écrire un fichier minimal

Le plus petit fichier valide ne déclare qu'un détecteur (`examples/config/detector_only.toml`) :

```toml
[detector]
type = "regex"
patterns = { EMAIL = '[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}' }
```

Le regroupement en entités, l'anonymiseur et le résolveur de chevauchements prennent leur valeur par défaut. Une adresse devient `<<EMAIL:1>>`. D'autres exemples sont dans `examples/config/`, à savoir `pipeline.toml`, `thread_redis.toml`, `thread_sqlalchemy.toml`, `minimal.json`.

## Règles à connaître

**BR-CFG-01.** Quand le fichier contient une clé non déclarée, alors le chargement échoue avec `ConfigValidationError`. Par exemple, `[detectr]` au lieu de `[detector]` est refusé.

**BR-CFG-02.** Quand le fichier déclare une section `[memory]`, alors il décrit un pipeline de conversation. `load_pipeline` le refuse avec `this configuration declares a memory; use load_thread_pipeline`. À l'inverse, `load_thread_pipeline` refuse un fichier sans `[memory]`.

**BR-CFG-03.** Quand `token_memo_ttl` est renseigné sans section `[memory]`, alors la validation échoue. Seul un pipeline de conversation garde ce cache.

**BR-CFG-04.** Quand une valeur est donnée à plusieurs endroits, alors les arguments explicites priment, puis les variables `PIIGHOST_*`, puis le fichier ou le hub.

**BR-CFG-05.** Quand une variable vise une sous-clé, comme `PIIGHOST_DETECTOR__TYPE`, alors elle n'a aucun effet, parce qu'aucun délimiteur imbriqué (le `__` qui sépare une section de sa clé) n'est configuré. Une section entière se surcharge par un objet JSON, par exemple `PIIGHOST_DETECTOR='{"type": "exact", "values": {"Patrick": "PERSON"}}'`.

**BR-CFG-06.** Quand un secret manque, alors l'erreur `ConfigError` survient à la construction, pas à la validation. `piighost validate` accepte donc un fichier dont les secrets ne sont pas encore fournis.

**BR-CFG-07.** Quand une référence hub se termine par huit caractères hexadécimaux (un commit), alors la réponse est mise en cache sur disque et n'est plus jamais téléchargée. Une référence qui finit par un tag, ou qui n'a pas de sélecteur (`latest`), est retéléchargée à chaque construction.

**BR-CFG-08.** Quand un détecteur regex combine catalogues et motifs en ligne, alors les catalogues fusionnent dans l'ordre, puis les motifs en ligne. Sur une même étiquette, le dernier gagne, donc un motif en ligne l'emporte sur tout catalogue.

**BR-CFG-09.** Quand un catalogue s'appelle `generic`, `us`, `eu` ou `fr` sans préfixe hub, alors il est refusé avec la référence hub qui le remplace (`hub:piighost/generic`).

## Fournir les secrets

Les secrets ne se lisent que dans l'environnement. Ne les écrivez jamais dans le fichier.

| Secret | Variable | Utilisé par | Erreur si absent |
|---|---|---|---|
| Poivre du hachage | `PIIGHOST_HASH_PEPPER` | `[memory.hasher]` | `a hasher requires the PIIGHOST_HASH_PEPPER environment variable to be set` |
| Clé de chiffrement (base64) | `PIIGHOST_CIPHER_KEY` | `[memory.cipher]` | `the cipher requires the PIIGHOST_CIPHER_KEY environment variable to be set` |
| URL de la base | valeur de `url_env`, `PIIGHOST_DATABASE_URL` par défaut | `[memory]` de type `sqlalchemy` | `The SQLAlchemy memory needs the … environment variable holding the database URL` |
| Clé Mistral | `MISTRAL_API_KEY` | garde-fou `moderation` | `ConfigError` à la construction |

Les variables non secrètes lues ailleurs sont `PIIGHOST_HUB_URL` (registre privé), `XDG_CACHE_HOME` (racine du cache hub), `PIIGHOST_API_URL` et `PIIGHOST_HOOK_LOG` (hooks Claude Code, voir [Brancher la protection sur un agent](../integrations/agents-and-tools.md)).

## Tirer des motifs du hub

Le hub est la seule source de motifs. La bibliothèque n'en embarque aucun. Une référence s'écrit `namespace/name`, avec un sélecteur facultatif `:tag` ou `:commit`, et le préfixe `hub:` facultatif.

- Origine : `https://hub.piighost.dev`, ou `PIIGHOST_HUB_URL`. Seuls `http` et `https` sont acceptés.
- Délai d'attente : 10 secondes (`hub.py:44`).
- Cache : `$XDG_CACHE_HOME/piighost/hub/`, sinon `~/.cache/piighost/hub/`. Le nom du fichier est une empreinte SHA-256 de l'URL.
- Un détecteur regex ne prend que la partie `?part=detector`. Si la référence décrit un détecteur à modèle, le chargement lève `HubPayloadError`. Chargez alors la configuration entière avec `load_config("hub:…")`.

## Contrôler depuis la ligne de commande

La commande `piighost` demande l'extra `config` (typer). Sans lui, elle affiche `The piighost CLI requires typer. Install it with: pip install piighost[config]` et sort en code 1.

| Commande | Effet | Code de sortie |
|---|---|---|
| `piighost validate <fichier ou hub:…>` | Valide sans construire. Affiche `OK: <chemin>`. | 0 si valide, 1 sur `ConfigError` ou `HubError` |
| `piighost schema` | Affiche le schéma JSON de `PipelineConfig`. | 0 |
| `piighost anonymize "<texte>"` | Construit et lance le pipeline. Lit l'entrée standard avec `-` ou sans argument. | 0, ou 1 sur erreur de config ou de hub |

Les options de `anonymize` sont `--config <fichier>`, `--api <url>` (exclusives, sinon `Pass at most one of --config and --api.`), `--thread-id` (défaut `default`), `--json`. Sans `--config` ni `--api`, la commande lance un détecteur regex sur `hub:piighost/generic:fab51b33` (e-mail, URL, IPv4, numéro de carte).

### Vérifier

```bash
uv run piighost validate examples/config/pipeline.toml
echo "Écrivez à claire.dubois@example.com" | uv run piighost anonymize --config examples/config/detector_only.toml
```

La première commande affiche `OK: examples/config/pipeline.toml`. La seconde affiche `Écrivez à <<EMAIL:1>>`.

## Pièges

- **`validate` ne prouve pas que le pipeline démarre.** Les secrets, les catalogues hub et les modèles ne sont lus qu'à la construction (BR-CFG-06).
- **Construire un fichier qui nomme un catalogue appelle le réseau** au premier lancement. Un serveur sans accès sortant échoue avec `HubUnreachableError`, sauf si le cache est déjà rempli.
- **Un cache non inscriptible est ignoré en silence** (`hub.py:268-278`). Le pipeline retélécharge alors à chaque démarrage.
- **`anonymize` ne capture que `ConfigError` et `HubError`.** Un extra manquant ou un garde-fou qui bloque (`PIIRemainingError`) remonte en trace Python complète.
- **`--thread-id` vaut `default` par défaut.** Deux appels sans identifiant partagent la même conversation sur un pipeline de conversation.

## Où vivent les règles

| Règle | Emplacement |
|---|---|
| BR-CFG-01 | `config/settings.py:97` (`extra="forbid"` de `PipelineConfig`), `config/models/common.py:13` (le même refus dans chaque section) |
| BR-CFG-02 | `config/settings.py:236-262` (`load_pipeline` et `load_thread_pipeline`) |
| BR-CFG-03 | `config/settings.py:114-127` (`_token_memo_ttl_needs_a_memory`) |
| BR-CFG-04 | `config/settings.py:129-143` (`settings_customise_sources`) |
| BR-CFG-05 | `config/settings.py:97` (`env_prefix="PIIGHOST_"`, sans délimiteur imbriqué) |
| BR-CFG-06 | `config/models/hasher.py:40` et `config/models/cipher.py:26-40` (`build`, qui lit le secret) |
| BR-CFG-07 | `hub.py:144-162` (`_read`, le cache des seules références à un commit) |
| BR-CFG-08 | `config/models/detector.py:101-115` (`build`, catalogues puis motifs en ligne) |
| BR-CFG-09 | `config/models/detector.py:53-74` (`_catalogs_are_hub_refs`) |

## Écarts doc / code

Aucun écart constaté sur cette page. Le message `removed in piighost 2.0` est traité dans [Ajouter ou remplacer un composant](../architecture/ports-and-extension.md#écarts-doc--code) et dans le [registre des écarts](../reference/doc-code-gaps.md).

## Tests

| Test | Couvre |
|---|---|
| `tests/config/test_settings.py` | Erreurs de fichier, ordre de priorité sur un scalaire (`PIIGHOST_NAME`), construction de chaque étape |
| `tests/cli/test_cli.py` | Codes de sortie de `validate`, `schema`, `anonymize`, exclusivité `--config`/`--api` |
| `tests/test_hub.py` | Analyse des références, origine privée, refus d'un détecteur à modèle, cache épinglé, sélecteur mobile jamais caché |
| `tests/config/test_hub_config.py` | Chargement d'une configuration entière depuis le hub |

La surcharge d'une section entière par un objet JSON n'est pas couverte dans `test_settings.py`. [à vérifier] : ajoutez un test qui pose `PIIGHOST_DETECTOR` pour confirmer BR-CFG-05.

Voir aussi [Stocker les conversations et protéger les traces](storage-and-encryption.md) pour la section `[memory]`.

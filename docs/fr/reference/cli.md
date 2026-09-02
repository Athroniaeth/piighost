# Interface en ligne de commande

Module : `piighost.cli`

`piighost` est un petit outil en ligne de commande qui valide et inspecte une configuration de pipeline et anonymise du texte depuis le shell. Il est installé comme point d'entrée console avec l'extra `config`.

```bash
pip install "piighost[config]"
```

L'outil a besoin de `typer`, livré avec l'extra `config`. Lancé sans lui, la CLI imprime un court message d'installation sur stderr et sort en `1`, plutôt qu'une traceback. Les sous-commandes `validate` et `schema` n'instancient aucun composant du pipeline, donc aucun détecteur n'est construit et aucun modèle chargé, ce qui les rend rapides et sûres à lancer en CI.

---

## `piighost validate`

Analyse et valide un fichier de configuration, TOML ou JSON selon son suffixe, contre le schéma du pipeline. Il vérifie la structure et chaque valeur sans construire de composant.

```bash
$ piighost validate ./pipeline.toml
OK: pipeline.toml
```

```
piighost validate <PATH>
```

| Argument | Description |
|----------|-------------|
| `PATH` | Chemin vers une config de pipeline TOML ou JSON |

Le code de sortie est `0` en cas de succès et `1` en cas d'erreur de configuration, qu'il s'agisse d'un fichier absent, d'une syntaxe TOML ou JSON invalide, ou d'une valeur qui échoue à la validation. Le message d'erreur est écrit sur stderr, ce qui rend la commande adaptée à une barrière de CI.

```bash
$ piighost validate ./broken.toml
invalid configuration in broken.toml: ...
$ echo $?
1
```

---

## `piighost schema`

Imprime le JSON Schema de `PipelineConfig` sur stdout. Le schéma est généré par Pydantic à partir des modèles de config, il correspond donc toujours à la version de `piighost` installée.

```bash
$ piighost schema > schema.json
```

Pointez un éditeur vers `schema.json` pour l'autocomplétion et la validation en ligne d'un fichier de config, ou fournissez-le à tout outil qui consomme du JSON Schema.

---

## `piighost anonymize`

Anonymise un texte et imprime le résultat. Le texte est un argument, ou `-` pour lire stdin. Par défaut elle lance un `RegexDetector` générique ; `--config` lance un pipeline configuré, et `--api` un serveur `piighost-api` distant. Contrairement à `validate` et `schema`, cette commande construit et exécute le pipeline.

```bash
$ piighost anonymize "mail me at a@b.co"
mail me at <<EMAIL:1>>

$ echo "mail me at a@b.co" | piighost anonymize -
mail me at <<EMAIL:1>>

$ piighost anonymize "reach a@b.co" --config ./pipeline.toml
$ piighost anonymize "reach a@b.co" --api https://piighost.internal
```

```
piighost anonymize [TEXT] [--config PATH | --api URL] [--thread-id ID] [--json]
```

| Option | Description |
|--------|-------------|
| `TEXT` | Le texte à anonymiser, ou `-` pour lire stdin |
| `--config PATH` | Un fichier de config de pipeline (TOML ou JSON) |
| `--api URL` | URL de base d'un serveur `piighost-api`, utilisé via le client HTTP |
| `--thread-id ID` | Thread id pour l'API ou une config à mémoire (défaut `default`) |
| `--json` | Imprime le texte anonymisé et les détections en JSON |

`--config` et `--api` sont mutuellement exclusifs. Avec `--json`, la sortie est `{"anonymized_text": ..., "detections": [...]}`.

---

## Obtenir de l'aide

```bash
$ piighost --help
$ piighost anonymize --help
```

---

## Voir aussi

- [Configuration TOML](../configuration/toml.md) pour le schéma que la CLI valide.

# Interface en ligne de commande

Module : `piighost.cli`

`piighost` est un petit outil en ligne de commande qui valide et inspecte une configuration de pipeline depuis le shell. Il est installé comme point d'entrée console avec l'extra `config`.

```bash
pip install "piighost[config]"
```

L'outil a besoin de `typer`, livré avec l'extra `config`. Sans lui, importer la CLI lève une `ImportError` nommant l'extra. Aucune des deux sous-commandes n'instancie les composants du pipeline, donc aucun détecteur n'est construit et aucun modèle n'est chargé, ce qui les rend rapides et sûres à lancer en CI.

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

## Obtenir de l'aide

```bash
$ piighost --help
$ piighost validate --help
```

---

## Voir aussi

- [Configuration TOML](../configuration/toml.md) pour le schéma que la CLI valide.

# Interface en ligne de commande

PIIGhost fournit un petit outil en ligne de commande nommé `piighost`,
installé comme point d'entrée console avec la dépendance optionnelle
`config` :

```bash
pip install "piighost[config]"
```

Il expose deux sous-commandes, toutes deux construites autour d'une
[configuration de pipeline TOML](../configuration/toml.md). Aucune
n'instancie les composants du pipeline, donc aucun détecteur n'est
construit et aucun modèle n'est chargé. Les deux commandes sont ainsi
rapides et sûres à lancer en CI.

## `piighost validate`

Analyse un fichier TOML et le valide contre le schéma du pipeline. Elle
vérifie la structure et chaque valeur sans construire de détecteur ni
charger de modèle, ce qui permet de repérer une config cassée avant
qu'elle n'atteigne un serveur en fonctionnement.

```bash
$ piighost validate ./pipeline.toml
OK: pipeline.toml
```

Le code de sortie est `0` en cas de succès et `1` en cas d'erreur :
fichier absent, syntaxe TOML invalide, ou valeur qui échoue à la
validation. Le message d'erreur est écrit sur stderr, ce qui rend la
commande adaptée à une barrière de CI.

## `piighost schema`

Imprime le JSON Schema de la configuration du pipeline sur stdout. Le
schéma est généré par Pydantic à partir des modèles de config, il
correspond donc toujours à la version de PIIGhost que vous avez
installée.

```bash
$ piighost schema > schema.json
```

Pointez un éditeur vers `schema.json` pour l'autocomplétion et la
validation en ligne du TOML, ou fournissez-le à n'importe quel outil qui
consomme du JSON Schema.

## Obtenir de l'aide

```bash
$ piighost --help
$ piighost validate --help
```

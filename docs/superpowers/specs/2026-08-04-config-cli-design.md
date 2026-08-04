# Config CLI Design

Design spec for the CLI sub-brick of the configuration subsystem of the PIIGhost
v2 rewrite. Internal design document, French prose, English code identifiers.

## Context

Le sous-système config a été découpé en trois sous-briques au brainstorming
initial : core (fait), couverture (à venir), CLI (ce document). Le core livre
piighost.config avec load_config, load_pipeline et PipelineConfig. Le CLI donne
un point d'entrée ligne de commande pour valider et inspecter une config sans
écrire de Python.

La v1 avait un cli/__init__.py typer avec validate et schema, et le point
d'entrée piighost = piighost.cli:main est déjà déclaré dans le pyproject v2.
typer vit dans l'extra config et est installé dans l'environnement dev.

## Goal

Une commande piighost avec deux sous-commandes, validate et schema, derrière
l'extra config, qui valident une config TOML et impriment le JSON Schema du
PipelineConfig, sans construire de composant lourd.

## Key decisions

- **Le CLI réutilise l'extra config.** typer y est déjà. Le CLI ne sert qu'à
  valider et inspecter une config, il dépend intrinsèquement de config, donc pas
  d'extra dédié. cli/__init__.py garde find_spec("typer") et lève un ImportError
  pointant piighost[config].
- **schema appelle PipelineConfig.model_json_schema() directement.** Pas de
  fonction publique export_schema, le CLI reste mince. YAGNI.
- **Un seul module cli/__init__.py.** Les deux commandes plus main() dans un
  fichier, comme v1. Deux commandes, une responsabilité, l'interface ligne de
  commande.
- **validate valide seulement, ne construit rien.** Il appelle load_config, pas
  load_pipeline, donc aucun modèle lourd n'est chargé pour vérifier une config.
- **Imports de config différés dans le corps des commandes.** Charger le module
  CLI ne tire que typer, l'import de piighost.config se fait à l'exécution de la
  commande.

## Architecture

Module src/piighost/cli/__init__.py, derrière l'extra config.

- En tête du module, la garde optionnelle standard : find_spec("typer") None lève
  un ImportError expliquant d'installer piighost[config]. typer est ensuite
  importé.
- app = typer.Typer(no_args_is_help=True, add_completion=False).
- main() appelle app(). C'est la cible du point d'entrée piighost =
  piighost.cli:main, déjà déclaré.

Commande validate :

- Signature validate(path: Path), l'argument en exists=False, c'est load_config
  qui décide de l'existence.
- Corps : importe load_config et ConfigError depuis piighost.config et
  piighost.exceptions, appelle load_config(path). Sur ConfigError, écrit le
  message sur stderr et lève typer.Exit(code=1). Sur succès, écrit OK suivi du
  chemin sur stdout et sort en code 0.
- ConfigError est la base de la famille, donc l'unique except couvre fichier
  absent, TOML invalide et schéma invalide.

Commande schema :

- Signature schema(), aucun argument.
- Corps : importe PipelineConfig depuis piighost.config, sérialise
  PipelineConfig.model_json_schema() en JSON avec indent=2 et
  ensure_ascii=False, l'imprime sur stdout, sort en code 0.

## Errors

Aucune nouvelle exception. validate traduit toute ConfigError en un code de
sortie 1 avec le message sur stderr. Les exceptions de config vivent déjà dans le
core exceptions.py depuis la brique core.

## Testing

typer CliRunner, TOML écrit dans un fichier temporaire, detecteur regex :

- conformité : l'app expose les commandes validate et schema (les noms sont
  présents dans app.registered_commands) ;
- validate sur un TOML valide sort en code 0 et imprime OK avec le chemin ;
- validate sur un schéma invalide, un détecteur sans type, sort en code 1 avec
  un message sur stderr ;
- validate sur un TOML syntaxiquement invalide sort en code 1 ;
- validate sur un fichier absent sort en code 1 ;
- schema sort en code 0 et sa sortie se parse en JSON, contenant les champs
  attendus du PipelineConfig, à savoir detector, linker et anonymizer.

## Packaging

Rien de neuf. typer est déjà dans l'extra config et dans le groupe dev, et le
point d'entrée piighost = piighost.cli:main est déjà déclaré dans le pyproject.
La commande piighost devient utilisable une fois le module en place.

Régression PUBLIC_API : rien à ajouter. main est un point d'entrée, pas un
symbole d'API publique, et le module cli est derrière l'extra, couvert par le
walk test_every_module_imports_cleanly qui l'importe dans l'environnement dev où
typer est présent.

## Out of scope

- Toute autre commande, anonymize, detect, run, à ajouter quand un besoin réel
  émerge.
- L'entrée JSON, comme pour le core, reportée à la brique couverture.
- La construction du pipeline dans validate, volontairement écartée pour ne pas
  charger de modèle.
- Les composants et le câblage TOML de la brique couverture.

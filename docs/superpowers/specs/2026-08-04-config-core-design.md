# Config Core Design

Design spec for the first sub-brick of the configuration subsystem of the
PIIGhost v2 rewrite, the composition-root core. Internal design document, French
prose, English code identifiers.

## Context

Le blueprint place la config comme composition root, le seul endroit autorisé à
connaître à la fois les ports et les adaptateurs concrets pour les assembler. La
v1 avait des modèles pydantic par composant, un loader TOML, un registre de
builders et des from_config. Le blueprint v2 change deux choses : build() porté
par les modèles (plus de registre), et pydantic-settings pour le chargement
multi-source (TOML/JSON + surcharge env, fichier en base).

Le sous-système config est trop vaste pour une spec unique. Il est découpé en
trois sous-briques : core (ce document), couverture des composants restants,
CLI. Le core prouve le mécanisme de bout en bout en bâtissant un
AnonymizationPipeline simple depuis un TOML.

## Goal

Un package config derrière l'extra config qui charge un TOML via
pydantic-settings, valide des modèles en unions discriminées portant chacun une
méthode build(), et assemble un AnonymizationPipeline fonctionnel, avec une
surcharge env des scalaires top-level et un couplage à sens unique config vers
core.

## Key decisions

- **build() porté par les modèles, pas de registre de builders.** Chaque modèle
  de config a une méthode build() qui construit son composant core en important
  la classe core, couplage à sens unique config vers core. Le build() est
  polymorphe : config.build() appelle le build() du modèle concret que pydantic
  a parsé via le discriminant type. PipelineConfig.build() compose en appelant
  les build() de ses sous-configs.
- **pydantic-settings pour le chargement.** PipelineConfig(BaseSettings), sources
  ordonnées par settings_customise_sources : init args, puis env, puis fichier
  TOML, puis défauts. Le fichier est la base, l'env surcharge. Le piège v1 du
  model_config est résolu par un model_config: ClassVar[SettingsConfigDict].
- **Surcharge env des scalaires top-level seulement.** L'env (prefixe PIIGHOST_)
  surcharge les champs scalaires de haut niveau du PipelineConfig, tel un champ
  name. L'arbre de composants (listes, unions discriminées imbriquées) vient du
  fichier, pas de l'env.
- **Pas de PipelineManifest.** Le PipelineConfig validé est déjà introspectable,
  la classe d'introspection de v1 est abandonnée, YAGNI.
- **Le core bâtit un AnonymizationPipeline simple.** Detecteur, linker,
  anonymizer, sans mémoire. Le ThreadAnonymizationPipeline et ses backends
  passent à la brique couverture.
- **Package guardé derrière l'extra config.** Importer piighost.config sans
  l'extra lève un ImportError pointant piighost[config], le core n'importe
  jamais piighost.config.

## Architecture

Package src/piighost/config/, derrière l'extra config.

- config/__init__.py : garde find_spec("pydantic_settings") levant l'ImportError
  vers piighost[config], puis expose load_config, load_pipeline, PipelineConfig.
  Exports directs, tout le package est derrière l'extra, aucun lazy interne
  nécessaire.
- config/settings.py : PipelineConfig(BaseSettings) avec model_config:
  ClassVar[SettingsConfigDict] (env_prefix PIIGHOST_), settings_customise_sources
  fixant la précédence, la méthode build() composant l'AnonymizationPipeline, et
  les entrées load_config / load_pipeline.
- config/errors.py : ConfigError(PIIGhostError) et ses sous-classes. Ces
  exceptions vivent en réalité dans le exceptions.py du core (voir Errors), ce
  module ne fait que les rendre accessibles si besoin.
- config/models/common.py : _ComponentConfig, la base commune.
- config/models/detector.py : RegexDetectorConfig, CompositeDetectorConfig, et
  l'union DetectorConfig discriminée sur type. Chacun build() son détecteur.
- config/models/placeholder.py : les modèles de factory du core (redact, label,
  label_counter, mask) et leur union PlaceholderConfig, chacun build() sa
  factory.
- config/models/anonymizer.py : AnonymizerConfig référençant un PlaceholderConfig,
  build() renvoyant un Anonymizer sur la factory construite.
- config/models/linker.py : LinkerConfig pour l'ExactEntityLinker, un
  case_sensitive transformé en flags au build (cas transformant de la règle 7).

PipelineConfig (dans settings.py) porte les champs name (scalaire top-level,
surchargeable par env), detector (DetectorConfig), linker (LinkerConfig),
anonymizer (AnonymizerConfig). Son build() assemble
AnonymizationPipeline(detector, linker, anonymizer).

## Loading and precedence

PipelineConfig(BaseSettings). settings_customise_sources renvoie les sources
dans l'ordre de précédence décroissante : init_settings, env_settings, la source
TOML, puis les défauts implicites. L'env surcharge donc le fichier, le fichier
surcharge les défauts.

Le chemin du fichier est injecté à l'appel, pas figé à la définition de classe :
les entrées load_config / load_pipeline construisent la source TOML pointée sur
le path fourni. Un TomlConfigSettingsSource lit le fichier.

Points d'entrée :

- load_config(path) -> PipelineConfig : parse et valide, ne construit aucun
  composant. C'est ce que la CLI validate appellera plus tard.
- load_pipeline(path) -> AnonymizationPipeline : load_config(path).build().

Format TOML seul dans le core ; JSON est une source de plus, ajoutée à la brique
couverture.

## Errors

Ajouts à exceptions.py (core, toujours importables, ce sont de simples
sous-classes sans dépendance pydantic) :

- ConfigError(PIIGhostError) : base de la famille config.
- ConfigFileError(ConfigError) : fichier illisible ou TOML syntaxiquement
  invalide.
- ConfigValidationError(ConfigError) : échec de validation pydantic, enveloppant
  la ValidationError dans un message lisible.

## Testing

Déterministe, TOML écrit dans un fichier temporaire, detecteur regex (aucun
modèle) :

- load_config valide un TOML minimal (regex + linker + anonymizer redact) et
  renvoie un PipelineConfig ;
- load_pipeline(path) construit un AnonymizationPipeline qui anonymise un texte
  connu de bout en bout, un EMAIL redacté ;
- l'union discriminée dispatche : type regex construit un RegexDetector, type
  composite enveloppant une liste construit un CompositeDetector ;
- chaque factory du core (redact, label, label_counter, mask) se construit et
  rend le bon token ;
- surcharge env : PIIGHOST_NAME surcharge le name du fichier, et l'arbre de
  composants n'est pas surchargeable par env ;
- un TOML syntaxiquement invalide lève ConfigFileError ; un schéma invalide, un
  détecteur sans type, lève ConfigValidationError ;
- le couplage à sens unique tient, le test_core_no_extras.py existant reste vert,
  le core n'importe pas config.

Packaging : ajout de pydantic-settings>=2.0 à l'extra config (les deux blocs) et
au groupe dev (pydantic y est déjà, pydantic-settings non), pour que les tests
tournent. tomllib est stdlib en 3.11+.

Régression PUBLIC_API : load_config, load_pipeline, PipelineConfig ne sont pas
ajoutés, ils sont derrière l'extra et couverts par le walk
test_every_module_imports_cleanly. ConfigError, ConfigFileError,
ConfigValidationError sont ajoutés (core, toujours importables).

## Out of scope

- La brique couverture : thread + backends mémoire et cache, JSON, étapes
  optionnelles overlap expand entity_resolver guard override, détecteurs à
  modèle, factories hash et faker, observation, client.
- La brique CLI : validate et schema via typer.
- Le PipelineManifest de v1, abandonné.
- La surcharge env profonde de l'arbre de composants.

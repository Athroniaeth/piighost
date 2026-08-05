# Config Coverage D: Remote Client and JSON Format Design

Design spec for the last sub-brick of the config coverage brick of the PIIGhost
v2 rewrite, the remote client config and the JSON file format. Internal design
document, French prose, English code identifiers.

## Context

La couverture se découpe en A étapes (fait), B détecteurs (fait), C1 thread plus
in_memory (fait), C2 redis plus crypto (fait), D client plus JSON, ce document,
le dernier sous-lot.

Deux pièces indépendantes. Le format JSON ajoute une source de chargement à côté
du TOML. La config client bâtit un PIIGhostClient, le remplaçant distant du
pipeline de thread, depuis un fichier, pour qu'un déploiement choisisse local ou
distant par config.

httpx est dans l'environnement dev et construire un PIIGhostClient ne se connecte
pas, donc les build() sont testables hors ligne.

## Goal

Le chargement accepte un fichier .json comme un .toml sur les entrées existantes,
et une nouvelle entrée load_client bâtit un PIIGhostClient depuis un ClientConfig
portant une base_url, les secrets et l'auth restant hors config.

## Key decisions

- **Le format est choisi par le suffixe du fichier.** settings.py garde un seul
  ContextVar de chemin, renommé _config_path, et un helper choisit la source,
  .json donne JsonConfigSettingsSource, tout autre suffixe TomlConfigSettingsSource.
  load_config, load_pipeline et load_thread_pipeline gagnent JSON sans nouvelle
  entrée. La précédence init puis env puis fichier est inchangée.
- **ClientConfig est un modèle settings de haut niveau, pair de PipelineConfig.**
  Il vit dans settings.py, pas dans config/models/, car config/models/ tient les
  modèles de composant, et un modèle client dans config/models/ importerait le
  helper de source de settings.py, un cycle. ClientConfig porte base_url, son
  build() importe PIIGhostClient en différé et renvoie PIIGhostClient(base_url).
- **Une entrée dédiée load_client.** Le client satisfait AnyThreadPipeline mais
  n'est pas un ThreadAnonymizationPipeline, donc il ne passe pas par
  load_thread_pipeline. load_client(path) parse un ClientConfig et renvoie le
  client construit.
- **Le recognizer garde son défaut, YAGNI.** ClientConfig n'expose que base_url,
  le recognizer reste le LabelCounterPlaceholderFactory par défaut, la grammaire
  standard d'un serveur piighost. Un serveur à grammaire différente est reporté,
  limite documentée.
- **Le chargement est factorisé.** Un helper _read parse un fichier dans un modèle
  settings donné, mappe TOMLDecodeError, JSONDecodeError et OSError en
  ConfigFileError et ValidationError en ConfigValidationError. load_config et
  load_client l'appellent tous deux.

## Architecture

settings.py (modifié) :

- _config_path, ContextVar de chemin renommé depuis _toml_path.
- _file_source(settings_cls), lit _config_path, renvoie None si absent,
  JsonConfigSettingsSource quand le suffixe est .json, TomlConfigSettingsSource
  sinon.
- _read(config_cls, path), résout le chemin, lève ConfigFileError si le fichier
  manque, pose _config_path, construit config_cls(), mappe TOMLDecodeError,
  JSONDecodeError et OSError en ConfigFileError et ValidationError en
  ConfigValidationError, réinitialise le ContextVar en finally.
- PipelineConfig.settings_customise_sources utilise _file_source.
- load_config(path) devient _read(PipelineConfig, path). load_pipeline et
  load_thread_pipeline sont inchangés, ils appellent load_config(path).build() et
  gagnent JSON gratuitement.
- ClientConfig(BaseSettings), model_config env_prefix PIIGHOST_ et extra forbid,
  champ base_url str, settings_customise_sources utilisant _file_source, build()
  important PIIGhostClient en différé et renvoyant PIIGhostClient(base_url). Le
  type PIIGhostClient est importé sous TYPE_CHECKING et l'annotation est une
  chaîne, pour ne pas exiger httpx à l'import de settings.py.
- load_client(path) renvoie _read(ClientConfig, path).build().

config/__init__.py (modifié) : ajoute ClientConfig et load_client aux exports,
derrière l'extra config.

## Errors

Aucune nouvelle exception. _read mappe un JSON syntaxiquement invalide, comme un
TOML invalide, en ConfigFileError, un schéma invalide en ConfigValidationError.
load_client réutilise ce mécanisme. PIIGhostClient derrière l'extra client lève
son ImportError nommant l'extra si httpx manque.

## Testing

Déterministe, fichier écrit dans un dossier temporaire, httpx étant dans le dev :

- JSON : load_config sur un .json valide, équivalent structurel du .toml de
  référence, rend un PipelineConfig ; load_pipeline sur ce .json anonymise un
  texte connu de bout en bout, identique au .toml ; un .json syntaxiquement
  invalide lève ConfigFileError ;
- client : ClientConfig(base_url=...).build() rend un PIIGhostClient dont le
  recognizer est un LabelCounterPlaceholderFactory par défaut ; load_client sur un
  TOML puis sur un JSON déclarant base_url rend un PIIGhostClient ; conformité,
  isinstance(client, AnyThreadPipeline) ;
- non-régression : load_pipeline et load_thread_pipeline sur les TOML existants
  restent verts, le renommage du ContextVar et l'extraction de _read ne changent
  rien ;
- le couplage à sens unique tient, le core n'importe pas config.

Packaging et régression PUBLIC_API : rien à ajouter. httpx est déjà l'extra
client, et ClientConfig et load_client vivent derrière l'extra config, couverts
par le walk. Aucune exception nouvelle.

## Out of scope

- L'auth et les en-têtes du client, fournis en injectant un httpx.AsyncClient au
  PIIGhostClient, jamais par la config.
- Un recognizer configurable pour le client, reporté, défaut standard seul.
- Un choix polymorphe local ou distant sous un point d'entrée unique, les deux
  entrées restent séparées, load_pipeline ou load_thread_pipeline pour le local,
  load_client pour le distant.
- La surcharge env profonde de l'arbre, inchangée depuis le core.

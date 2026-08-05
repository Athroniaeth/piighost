# Config Coverage B: Model Detectors and Catalogs Design

Design spec for the second sub-brick of the config coverage brick of the
PIIGhost v2 rewrite, the model-backed detectors and the pattern catalogs.
Internal design document, French prose, English code identifiers.

## Context

La couverture se découpe en A étapes optionnelles (fait), B détecteurs à modèle
plus catalogues (ce document), C thread plus mémoire, D client plus JSON.

Le core plus la couverture A n'exposent que deux détecteurs en config, regex et
composite. Le sous-lot B élargit l'union DetectorConfig avec les détecteurs à
modèle, les enveloppes et le référencement des catalogues pré-bâtis. Comme les
guards, l'override, le composite et le chunked référencent tous DetectorConfig,
ils gagnent ces types sans être touchés.

## Goal

Élargir l'union DetectorConfig avec exact, chunked, gliner2, spacy, transformers,
llm, et permettre à un détecteur regex de tirer les catalogues de patterns
pré-bâtis, chaque modèle portant un build() couplé à sens unique vers le core,
les détecteurs à modèle derrière leur extra en import différé.

## Key decisions

- **model est un str en config.** Le core accepte model ou pipeline sous forme
  d'objet vivant ou de str. Un TOML ne sait dire qu'un str, le nom ou le chemin
  d'un modèle. La branche objet n'est pas exposée, faiblesse assumée et
  documentée, comme le recognizer du client.
- **Les catalogues sont un champ de RegexDetectorConfig, pas un détecteur à
  part.** RegexDetectorConfig gagne catalogs, une liste de noms parmi generic,
  us, eu, fr. build() fusionne les catalogues nommés puis les patterns inline,
  l'inline surchargeant en cas de collision. patterns devient optionnel, un
  model_validator exige qu'au moins un des deux soit non vide.
- **Le détecteur exact est inclus.** ExactMatchDetectorConfig câble une liste de
  valeurs littérales vers un label. Utile au-delà des tests, une liste de valeurs
  connues à toujours anonymiser, notamment pour la whitelist et la blacklist de
  l'override.
- **Les détecteurs à modèle vivent dans un module séparé.** config/models/
  detector_model.py groupe gliner2, spacy, transformers, llm, les quatre configs
  à extra, pour que detector.py reste le noyau sans extra, regex, composite,
  exact, chunked, plus l'union. detector.py importe les quatre configs pour
  l'union, sans cycle, aucun détecteur à modèle n'imbrique un DetectorConfig.
- **Le chunked expose chunk_size et chunk_overlap sur le splitter par défaut.**
  ChunkedDetectorConfig imbrique un DetectorConfig et deux entiers, il bâtit
  toujours un RecursiveCharacterTextSplitter interne. Un splitter pluggable
  complet reste hors périmètre.

## Architecture

Deux fichiers sous src/piighost/config/models/.

config/models/detector.py (étendu) :

- RegexDetectorConfig gagne catalogs, list de Literal generic us eu fr, défaut
  liste vide. patterns passe optionnel, défaut dict vide. Un model_validator
  mode after exige patterns ou catalogs non vide, sinon une erreur de validation.
  Le field_validator de compilation reste sur les patterns inline, les catalogues
  sont déjà valides. build() construit le dict fusionné, catalogues d'abord puis
  patterns inline, et renvoie un RegexDetector dessus. Un mapping module
  _CATALOGS relie chaque nom à son dict, importé du paquet patterns, sans extra.
- CompositeDetectorConfig inchangé.
- ExactMatchDetectorConfig, type exact, values dict str str non vide, build()
  renvoyant ExactMatchDetector(values). Sans extra.
- ChunkedDetectorConfig, type chunked, detector DetectorConfig, chunk_size int
  défaut 1000 strictement positif, chunk_overlap int défaut 100 positif ou nul,
  un model_validator exigeant chunk_overlap plus petit que chunk_size. build()
  construit un RecursiveCharacterTextSplitter sur les deux entiers et renvoie
  ChunkedDetector sur le détecteur construit et ce splitter. Sans extra, le
  splitter vient de piighost.text.
- L'union DetectorConfig, discriminée sur type, réunit RegexDetectorConfig,
  CompositeDetectorConfig, ExactMatchDetectorConfig, ChunkedDetectorConfig et les
  quatre configs de detector_model.py. Le model_rebuild final résout les
  références avant définies.

config/models/detector_model.py (nouveau), chaque build() important sa classe en
différé, derrière son extra :

- Gliner2DetectorConfig, type gliner2, model str, labels list str ou dict str
  str, threshold float défaut 0.5, max_concurrency int ou None. build() renvoyant
  Gliner2Detector(model, labels, threshold, max_concurrency). Extra gliner2.
- SpacyDetectorConfig, type spacy, model str, labels list str ou dict str str ou
  None, max_concurrency int ou None. build() renvoyant SpacyDetector(model,
  labels, max_concurrency). Extra spacy.
- TransformersDetectorConfig, type transformers, model str, labels list str ou
  dict str str ou None, threshold float défaut 0.0, max_concurrency int ou None.
  build() renvoyant TransformersDetector(pipeline=model, labels, threshold,
  max_concurrency). Le champ model est passé au paramètre pipeline, cas
  transformant de la règle 7. Extra transformers.
- LLMDetectorConfig, type llm, model str, labels list str ou dict str str, prompt
  str ou None, provider str ou None. build() renvoyant LLMDetector(model, labels,
  prompt, provider). Extra llm. Miroir de LLMGuardRailConfig.

Les détecteurs à modèle sont importés dans detector.py pour l'union. Dans
detector_model.py, le port AnyDetector reste importé en tête pour l'annotation
des build(), les classes concrètes en différé dans chaque build().

## Errors

Aucune nouvelle exception. Un extra manquant, gliner2, spacy, transformers ou
llm, fait lever au build() l'ImportError du module composant, qui nomme l'extra.
Un chunk_overlap non inférieur au chunk_size, ou un regex sans patterns ni
catalogs, échoue à la validation en ConfigValidationError via load_config, pas au
build().

## Testing

Déterministe, TOML écrit dans un fichier temporaire. Les extras gliner2, spacy,
transformers ne sont pas dans l'environnement dev, ni un package provider llm.

- exact, build() et effet, un ExactMatchDetector qui repère une valeur connue ;
- catalogs, un RegexDetectorConfig catalogs generic bâtit un RegexDetector dont
  les patterns contiennent ceux du catalogue et qui détecte un motif du
  catalogue ; la fusion, un pattern inline surcharge une clé du catalogue ; ni
  patterns ni catalogs lève ConfigValidationError ;
- chunked, build() enveloppant un regex, chunk_size et chunk_overlap transmis au
  splitter, et un chunk_overlap non inférieur au chunk_size lève
  ConfigValidationError ;
- pour gliner2, spacy, transformers, llm, la config parse, l'union dispatche sur
  type vers la bonne config, et les champs sont stockés, threshold, labels,
  model. build() n'est pas appelé, l'extra ou le provider manquant le ferait
  échouer, c'est un souci de déploiement, pas de la config ;
- l'union DetectorConfig dispatche chaque type vers sa config ;
- l'élargissement tient, un guard detector, un override whitelist ou un composite
  imbriquant un type exact se parse, la nesting de DetectorConfig voit les
  nouveaux types ;
- le couplage à sens unique tient, le core n'importe pas config, garanti par le
  walk test_every_module_imports_cleanly.

Packaging et régression PUBLIC_API : rien à ajouter. Les extras gliner2, spacy,
transformers, llm existent déjà, et les modèles de config sont derrière l'extra
config, couverts par le walk. Aucune exception nouvelle.

## Out of scope

- Le thread et la mémoire, sous-lot C. PipelineConfig reste le pipeline simple.
- Le client distant et le format JSON, sous-lot D.
- Un splitter pluggable complet, une union AnySplitter en config. Seuls chunk_size
  et chunk_overlap du splitter par défaut sont exposés.
- L'injection d'un modèle vivant, model ou pipeline en objet. La config n'accepte
  qu'un str, nom ou chemin.
- Le paramètre separators du splitter, laissé au défaut.

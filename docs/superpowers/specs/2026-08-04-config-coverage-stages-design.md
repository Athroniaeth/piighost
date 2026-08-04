# Config Coverage A: Optional Stages and Hash Factory Design

Design spec for the first sub-brick of the config coverage brick of the PIIGhost
v2 rewrite, the optional pipeline stages and the hash placeholder factory.
Internal design document, French prose, English code identifiers.

## Context

La brique config a été découpée en core (fait), couverture, CLI (fait). La
couverture se re-découpe elle-même en quatre sous-lots : A étapes optionnelles
plus factory hash (ce document), B détecteurs à modèle plus catalogues, C thread
plus mémoire, D client plus JSON.

Le core bâtit un AnonymizationPipeline simple, detecteur plus linker plus
anonymizer. Son constructeur accepte déjà six étapes optionnelles à None,
overlap_resolver, expander, entity_resolver, guard, observation_redactor,
override, mais le PipelineConfig du core ne les expose pas. Ce sous-lot les
expose, et ajoute la factory label_hash à l'union placeholder.

## Goal

Étendre PipelineConfig avec les six étapes optionnelles et étendre l'union
placeholder avec label_hash, chaque modèle portant un build() couplé à sens
unique vers le core, de sorte qu'un TOML décrive un pipeline simple complet, ses
résolveurs, son expander, son garde-fou, son override et le masquage des traces
d'observation.

## Key decisions

- **Étapes à membre unique en alias, étapes à plusieurs membres en union
  discriminée.** overlap_resolver et expander n'ont qu'un adaptateur, leur config
  est un alias portant un type Literal, comme LinkerConfig. entity_resolver,
  guard et placeholder ont plusieurs adaptateurs, leur config est une union
  Annotated discriminée sur type.
- **build() couplé à sens unique.** Chaque modèle importe sa classe core et
  l'instancie. Un adaptateur derrière un extra manquant lève l'ImportError du
  module composant, nommant l'extra, propagée telle quelle depuis build().
- **Les trois guards sont couverts.** detector imbrique un DetectorConfig, llm
  prend un model str, moderation construit un client Mistral. llm et moderation
  lisent leurs identifiants dans l'environnement, jamais dans le TOML.
- **L'observation se limite à observation_redactor.** Le pipeline n'accepte
  qu'une factory de masquage des charges utiles de trace. Le tracer est un seam
  OTel global, configuré au déploiement via le SDK OTel, hors config piighost. Il
  n'y a donc aucun modèle de config de tracer, observation_redactor réutilise
  PlaceholderConfig.
- **Les scalaires exposés, les objets et callables laissés par défaut.** On
  expose ce qu'un TOML sait dire, threshold, case_sensitive, hash_length, model,
  labels, prompt, provider, et les stratégies d'override par leurs valeurs
  string. La similarité fuzzy, un callable, reste au défaut Jaro-Winkler.

## Architecture

Nouveaux modules sous src/piighost/config/models/, plus deux fichiers modifiés.

- config/models/overlap_resolver.py : ConfidenceOverlapResolverConfig
  (type confidence) build() renvoyant ConfidenceOverlapResolver(). Alias
  OverlapResolverConfig = ConfidenceOverlapResolverConfig.
- config/models/expander.py : WordBoundaryExpanderConfig
  (type word_boundary, case_sensitive bool défaut False) build() renvoyant
  WordBoundaryExpander(case_sensitive=...). Alias ExpanderConfig.
- config/models/entity_resolver.py : MergeEntityResolverConfig (type merge),
  SeparateEntityResolverConfig (type separate), FuzzyEntityResolverConfig
  (type fuzzy, threshold float défaut 0.85) et l'union EntityResolverConfig
  discriminée sur type. build() renvoie MergeEntityResolver(),
  SeparateEntityResolver(), FuzzyEntityResolver(threshold=...). Le build fuzzy
  importe FuzzyEntityResolver, qui garde l'extra fuzzy.
- config/models/guard.py : DetectorGuardRailConfig (type detector, detector
  DetectorConfig), LLMGuardRailConfig (type llm, model str, labels list str ou
  dict str str, prompt str ou None, provider str ou None), ModerationGuardRailConfig
  (type moderation, model str défaut mistral-moderation-latest, threshold float
  défaut 0.5) et l'union GuardConfig discriminée sur type. build() renvoie
  DetectorGuardRail(detector.build()), LLMGuardRail(model, labels, prompt,
  provider), ModerationGuardRail(client=Mistral(), model, threshold). Le build
  llm importe LLMGuardRail, qui garde l'extra llm ; le build moderation importe
  ModerationGuardRail et la classe Mistral depuis mistralai.client, gardant
  l'extra mistral, et construit le client qui lit MISTRAL_API_KEY dans
  l'environnement.
- config/models/override.py : OverrideConfig, avec whitelist et blacklist des
  DetectorConfig ou None, blacklist_strategy BlacklistStrategy défaut EXACT,
  whitelist_strategy WhitelistStrategy défaut RESPECT_PROVENANCE,
  conflict_strategy OverrideConflictStrategy défaut WHITELIST_WINS. build()
  renvoie DetectionOverride avec les deux détecteurs construits ou None et les
  trois stratégies. Les enums viennent de piighost.components.override.strategy et
  se parsent depuis leurs valeurs string. Pas une union.
- config/models/placeholder.py (modifié) : ajout de LabelHashPlaceholderConfig
  (type label_hash, hash_length int défaut 8) build() renvoyant
  LabelHashPlaceholderFactory(hash_length=...), et ajout du membre à l'union
  PlaceholderConfig.

PipelineConfig (settings.py, modifié) gagne les champs optionnels, tous None par
défaut : overlap_resolver OverlapResolverConfig ou None, expander ExpanderConfig
ou None, entity_resolver EntityResolverConfig ou None, guard GuardConfig ou None,
override OverrideConfig ou None, observation_redactor PlaceholderConfig ou None.
Son build() passe chaque champ.build() ou None au mot-clé correspondant de
AnonymizationPipeline.

## Errors

Aucune nouvelle exception. Un extra manquant, fuzzy, llm ou mistral, fait lever
au build() l'ImportError du module composant, qui nomme l'extra. Le core reste
la source de ces exceptions, la config n'en ajoute pas.

## Testing

Déterministe, TOML écrit dans un fichier temporaire, détecteur regex. Les
dépendances rapidfuzz, langchain, mistralai.client et opentelemetry sont dans
l'environnement dev.

- chaque étape à effet déterministe est testée par la config qui parse, le
  build() qui dispatche le bon type, et le pipeline assemblé qui montre l'effet :
  overlap_resolver confidence garde la détection la plus confiante sur un
  chevauchement, expander word_boundary ajoute une occurrence manquée,
  entity_resolver merge fusionne deux entités liées, entity_resolver fuzzy
  regroupe deux variantes proches, override force ou efface une détection, le
  guard detector lève sur une PII résiduelle, la factory label_hash rend un token
  de forme LABEL deux-points hash ;
- pour les guards llm et moderation, la config parse et build() renvoie la bonne
  classe sans appel réseau. Le test moderation monkeypatche MISTRAL_API_KEY pour
  que le client Mistral se construise, le test llm vérifie le type retourné ;
- l'union entity_resolver et l'union guard dispatchent sur type, type merge
  construit un MergeEntityResolver, type fuzzy un FuzzyEntityResolver, type
  detector un DetectorGuardRail ;
- les stratégies d'override se parsent depuis leurs valeurs string TOML, exact,
  respect_provenance, whitelist_wins ;
- un TOML complet, détecteur regex plus toutes les étapes déterministes, se
  charge et anonymise un texte connu de bout en bout ;
- le couplage à sens unique tient, le core n'importe pas config, garanti par le
  walk test_every_module_imports_cleanly.

Packaging et régression PUBLIC_API : rien à ajouter. Toutes les dépendances sont
déjà dans les extras existants, fuzzy, llm, mistral, et les modèles de config
sont derrière l'extra config, couverts par le walk. Aucune exception nouvelle,
donc aucun ajout à PUBLIC_API.

## Out of scope

- Les détecteurs à modèle et les catalogues, sous-lot B. Les guards detector et
  override imbriquent un DetectorConfig, qui reste limité à regex et composite
  tant que le sous-lot B n'a pas élargi l'union.
- Le thread et la mémoire, sous-lot C. PipelineConfig reste le pipeline simple
  sans état.
- Le client distant et le format JSON, sous-lot D.
- La configuration du tracer OTel, affaire de déploiement, jamais de la config
  piighost.
- La similarité fuzzy personnalisée, un callable non exprimable en TOML, laissée
  au défaut Jaro-Winkler.
- Les factories streaming, non exposées faute de besoin config.

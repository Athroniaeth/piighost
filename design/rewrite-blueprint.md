# PIIGhost — Blueprint de réécriture (from scratch)

Document de conception interne. Sert de référence pour repartir de zéro sur
`src/`, au propre, avec le moins de code possible et une couverture de tests
maximale. Prose en français, identifiants de code en anglais.

Ce n'est pas un plan d'exécution TDD. C'est la carte de la base à reconstruire,
le journal des décisions, et le guide qualité.

---

## 1. Objectif et principes directeurs

- **Repartir propre.** Supprimer le superflu, une seule façon de faire chaque
  chose, pas de chemin dupliqué.
- **Moins de code.** L'uniformité des contrats est ce qui garde la lib petite.
  Chaque composant enfichable suit le même patron (port + adaptateur + config).
- **Testabilité d'abord.** Le domaine est pur et rapide à tester sans charger de
  modèle. Les cas limites (offsets, casse, chevauchements) sont couverts par des
  tests dédiés dès le départ.
- **Couplage à sens unique.** Le domaine ne dépend de rien. Les adaptateurs
  dépendent du domaine. La config dépend des deux (elle est le composition root).
  Jamais l'inverse.
- **Dépendances optionnelles isolées.** gliner2, spacy, transformers, llm, faker,
  langchain, redis, sqlalchemy, langfuse, opik restent des extras. Chaque import
  d'extra vit dans l'adaptateur qui en a besoin, derrière une garde
  `find_spec(...) -> raise ImportError`.

---

## 2. Architecture en couches (hexagonale / ports & adaptateurs)

La lib se lit naturellement en trois anneaux. Ce découpage rend l'invariant de
couplage **structurel** (les imports ne peuvent pas partir dans le mauvais sens)
plutôt que conventionnel.

- **Domain (coeur pur).** Aucune dépendance externe, pas de pydantic, pas d'I/O.
  Contient les données (`Entity`, `Detection`, `Span`, frozen dataclasses), les
  **ports** (Protocols), les phantom tags, les constantes de labels.
- **Application (use cases).** L'orchestration du pipeline. Ne dépend que des
  ports du domaine. C'est ici que vivent les opérations métier (`anonymize`,
  `deanonymize`, `forget_thread`).
- **Adapters (infrastructure).** Les implémentations concrètes des ports.
  Détecteurs, resolvers, factories, guards, backends de cache, observation,
  client HTTP, middleware. Chaque adaptateur importe le domaine, jamais l'inverse.
- **Config (composition root).** Les modèles pydantic et le câblage. C'est le
  seul endroit autorisé à connaître à la fois les ports et les adaptateurs
  concrets, pour les assembler.

Correspondance avec le vocabulaire repository / service / use case :

- **use case** = les méthodes du pipeline (`AnonymizationPipeline.anonymize`, ...).
- **service** = les composants du domaine (détecteurs, resolvers, anonymizer).
- **repository** = les ports de persistance (`MappingStore`, `ConversationMemory`)
  et leurs backends (memory, redis, sqlalchemy).

---

## 3. Squelette de packages proposé

```
src/piighost/
  domain/
    models.py        # Entity, Detection, Span (frozen dataclasses)
    ports.py         # Protocols: AnyDetector, AnySpanResolver, AnyEntityLinker,
                     #   AnyEntityResolver, AnyAnonymizer, AnyPlaceholderFactory,
                     #   AnyGuardRail, MappingStore, ConversationMemory
    tags.py          # phantom preservation tags (label / identity / realism / shape)
    labels.py        # constantes de labels communes
  application/
    pipeline.py      # AnonymizationPipeline (template method, un seul chemin)
    thread.py        # ThreadAnonymizationPipeline (surcharge les hooks)
  text/
    normalization.py # NormalizedText + carte d'offset norm -> orig
    patterns.py      # boundary_wrap, WORD_JOIN_CHARS (source unique)
    validators.py    # Luhn, IBAN, NIR (checksum modulateur de confiance)
  adapters/
    detectors/       # gliner2, spacy, transformers, llm, regex, exact, composite, chunked
    resolvers/       # span conflict, entity linker, entity conflict
    anonymizer/      # Anonymizer + factories (redact/label/mask/faker/hash)
    guard/           # detector guard, llm guard
    cache/           # memory, redis, sqlalchemy (impls de MappingStore)
    observation/     # langfuse, opik
    client/          # httpx client
    middleware/      # langchain
  config/
    models/          # *Config pydantic (unions discriminees) avec build() lazy
    settings.py      # PipelineConfig(BaseSettings), multi-source toml/json/env
```

Compromis assumé. Ce découpage est plus profond que le plat actuel. Il se
justifie par la nature à plugins de la lib (beaucoup d'adaptateurs pour peu de
domaine). Si un anneau reste quasi vide, le fusionner plutôt que le garder par
principe.

---

## 4. Composants porteurs et leurs contrats

Checklist de la base à reconstruire. Chaque ligne est un port dans `domain/ports.py`
plus au moins un adaptateur.

- **Detector** (`AnyDetector`). Regex, NER (gliner2/spacy/transformers), LLM,
  exact (tests). Wrappers `CompositeDetector` et `ChunkedDetector`.
- **SpanConflictResolver**. Résout les chevauchements (garde la meilleure
  confiance).
- **EntityLinker**. Regroupe les détections en entités, retrouve les occurrences
  non détectées via frontières de mots.
- **EntityConflictResolver**. Fusion (union-find) ou fuzzy (Jaro-Winkler).
- **Anonymizer** + **PlaceholderFactory**. Trois axes orthogonaux, label /
  identité / réalisme, plus le masque (shape). Pepper via env pour les hash.
- **GuardRail** (optionnel). Re-vérifie la sortie, ignore les tokens déjà émis,
  lève `PIIRemainingError`.
- **MappingStore / ConversationMemory** (repository). Réversibilité, isolation
  par thread, `forget_thread`, backend cache pour le multi-worker.
- **Validators**. Checksums en modulateur de confiance, jamais en filtre dur.
- **Overrides**. Liste noire (post-filtre de suppression) et liste blanche
  (détecteur exact de forçage), deux composants distincts.

---

## 5. Journal des décisions

| Sujet | Décision |
|---|---|
| Checksums / OCR | Modulateur de confiance, jamais filtre dur. Configurable par pattern (`strict` / `lenient` / `off`). Fautes OCR traitées en amont par la normalisation. |
| CompositeDetector | Options au-delà de la liste. `mode` (`union` / `first_match`), poids de confiance par détecteur, allowlist de labels par détecteur, exécution parallèle/séquentielle, seuil min par détecteur. À n'ajouter que quand le besoin est réel (YAGNI). |
| Garantie au type | Inchangée. Phantom tags + middleware borné à `PreservesIdentity`. |
| Overrides | Deux composants. Liste noire (suppression) et liste blanche (forçage). |
| Idempotence | Warning si un token déjà émis est re-traité (mauvais mode), pas une erreur. |
| Placeholder inventé par le LLM | Stratégie enum `KEEP` / `DROP` / `RAISE`, défaut `KEEP`. |
| Store de mapping | Le reverse map est de la PII en clair. Chiffrement au repos, TTL, contrôle d'accès. Préférer le hash irréversible quand la réversibilité n'est pas requise. |
| Faker | Warning sur collision possible avec une valeur réelle. |
| Config | pydantic-settings + `build()` porté par les modèles de config (unions discriminées). Supprime le registre de builders et les `from_config`. Multi-source toml/json avec surcharge env (fichier en base). |
| Labels NER (externe vers interne) | Le mapping label NER vers label piighost se fait dans l'adaptateur, avant de retourner. Un seul port `AnyDetector` label-agnostique, pas de sous-Protocol NER (violerait l'ISP). Le code partagé vit dans un `BaseNERDetector` en Template Method (règle 6), une `ABC` dont `_raw_detect` est `@abstractmethod`, les sous-classes le fournissent. Le mapping est de la donnée (`dict[str, str]`), la normalisation liste/dict vit dans `config`. À coder avec le premier détecteur NER, pas avant (YAGNI). |
| Chunking | Décorateur `ChunkedDetector` qui enveloppe un `AnyDetector`, `chunk_size` et `overlap` sur le wrapper, pas sur le port. Logique récursive par séparateurs reprise de LangChain mais range-based, chunks = tranches contiguës donc offsets exacts pour `Span.shift`. `RecursiveCharacterTextSplitter` réimplémenté, pas de dépendance langchain. `chunk_size` est une limite dure (sauf morceau insécable plus grand), l'overlap est au mieux (la progression prime). Composition plutôt qu'héritage, le chunking reste séparé du mapping de labels NER, son activation par défaut pour les NER se règle au composition root qui enveloppe les NER. Dédup des détections strictement identiques via `dict.fromkeys`, les conflits de label et confiances différentes partent au `SpanConflictResolver`. |

---

## 6. Guide qualité (SOLID / KISS / patterns)

### SOLID appliqué à ce domaine

- **S (responsabilité unique).** Le découpage en 5 étapes est déjà aligné SRP.
  Garder détection, résolution de spans, linking, résolution d'entités,
  anonymisation strictement séparés. Pas d'objet fourre-tout qui détecte et
  anonymise.
- **O (ouvert/fermé).** Un nouveau détecteur est un nouvel adaptateur qui
  implémente le port, plus un modèle de config avec `build()`. Le pipeline ne
  change pas. L'union discriminée absorbe l'ajout.
- **L (substitution).** Tout détecteur est interchangeable derrière `AnyDetector`.
  Surveiller que les sous-classes NER honorent le contrat (mapping label
  externe vers interne cohérent).
- **I (ségrégation d'interface).** Garder les ports petits et ciblés. Le guard a
  son port, le cache le sien. Ne pas fabriquer un port obèse que peu
  d'implémentations remplissent.
- **D (inversion de dépendance).** Le pipeline dépend des ports, pas des classes
  concrètes. L'injection se fait au composition root (`config`). Le core
  n'importe jamais un adaptateur.

### KISS / YAGNI

- Une seule traversée du pipeline (template method), les hooks pour la variante
  thread. Ne pas dupliquer les étapes entre pipeline simple et conversationnel.
- Frozen dataclasses pour le domaine, aucun pydantic dans le core.
- Ne pas rendre configurable ce qui n'a pas encore deux usages réels. Les options
  du CompositeDetector s'ajoutent une par une, quand un cas les demande.
- Une abstraction avec une seule implémentation et aucun test qui la remplace est
  suspecte. Ici les ports se justifient par la pluralité d'adaptateurs, mais
  vérifier ce critère pour chaque nouveau port.

### Design patterns en jeu

- **Ports & adaptateurs (hexagonal).** L'ossature globale.
- **Strategy.** Détecteurs, resolvers, placeholder factories, stratégie d'appels
  d'outils (`FULL` = `INPUT` + `OUTPUT`, `PASSTHROUGH`).
- **Template method.** Étapes du pipeline, resolvers, factories Faker.
- **Decorator.** `ChunkedDetector` et le guard enveloppent un détecteur.
- **Composite.** `CompositeDetector` agrège plusieurs détecteurs.
- **Factory.** Les placeholder factories.
- **Adapter.** Observation (langfuse/opik), client HTTP.
- **Union discriminée + `build()` polymorphe.** Remplace un Abstract Factory à
  registre. Moins de code, pas de table de dispatch à tenir.

---

## 7. Stratégie de test

- **Domaine pur, rapide.** Tests unitaires sans modèle chargé, via
  `ExactMatchDetector`. C'est la majorité de la suite.
- **Invariants d'offset (property-based, hypothesis).** `anonymize` puis
  `deanonymize` redonne l'original. Une entité plus courte, égale, plus longue
  que son placeholder retombe sur les bons indices. Roundtrip de la carte
  d'offset de `NormalizedText`.
- **Tests de contrat.** Un test paramétré sur toutes les implémentations de
  `AnyDetector` vérifie qu'elles respectent le port.
- **Golden tests.** Les catalogues de regex confrontés à un jeu de valeurs
  connues (vrais positifs et vrais négatifs, dont checksum KO).
- **Fuzzing du parsing de placeholder.** Tokens déformés par le LLM, vérifier la
  stratégie `KEEP` / `DROP` / `RAISE`.
- **Intégration derrière marqueur.** Les tests qui chargent torch/gliner2/spacy
  restent `integration`, exclus par défaut.
- **Non-régression du couplage.** Un test qui échoue si le domaine importe un
  adaptateur ou la config.

---

## 8. Points ouverts (à trancher pendant la réécriture)

- Formats de fichiers de config à supporter au lancement (toml et json sûrs,
  yaml optionnel).
- Emplacement exact de la carte d'offset (dans `NormalizedText` ou en paramètre
  de retour du détecteur).
- Faut-il un manifest de pipeline comme avant, ou le `PipelineConfig` suffit.
- Streaming de la désanonymisation en sortie (concerne surtout le middleware).
- Chunking et résolution de conflits. L'overlap fait qu'une même valeur dans la
  zone de recouvrement est détectée par deux chunks. Après remap, deux cas. Même
  span et même label = doublon pur d'overlap, à dédupliquer. Même span mais label
  différent (ex "Chaumont" PERSON dans un chunk, COMPANY dans l'autre) = vrai
  conflit, à laisser passer vers le `SpanConflictResolver` qui tranche par
  confiance. Le resolver n'a pas besoin d'être conscient du chunking. En revanche
  la dédup du `ChunkedDetector` ne doit dédupliquer que sur `(span, label)`, pas
  sur le span seul, sinon elle écraserait un conflit avant que le resolver
  puisse choisir. Question à trancher, où vit la dédup exacte, dans le
  `ChunkedDetector` ou déléguée au resolver. Bonus, l'overlap donne deux vues
  contextuelles d'une même valeur, ce qui aide la résolution par confiance.

---

## Plans dérivés en attente

1. Normalisation du texte + centralisation des regex (`text/normalization.py`,
   `text/patterns.py`). Point délicat, la remontée d'offset.
2. Rewrite config pydantic-settings avec `build()` sur les modèles. Référence,
   la branche `proto/pydantic-settings` (pièges déjà résolus, conflit
   `model_config` via `ClassVar[SettingsConfigDict]`, précédence des sources via
   `settings_customise_sources`).

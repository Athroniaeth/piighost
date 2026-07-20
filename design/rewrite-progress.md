# Avancement de la réécriture v2

Point de reprise pour continuer sur un autre poste. À lire avec
`design/rewrite-blueprint.md` (vocabulaire et contrats des composants).

## But et méthode

Réécriture v2 de PIIGhost from scratch, brique par brique. L'utilisateur pilote
et revoit chaque brique de près. On construit le domaine (modèles + composants
enfichables) avant l'orchestration. Ne pas coder sans y être invité.

## Contraintes permanentes (ne pas oublier)

- **`README.fr.v2.md` reste non tracké**, ne jamais le committer ni le modifier.
- Artefacts de code (docstrings, commentaires, erreurs) **en anglais**, même si le
  chat est en français.
- **Pas d'em dash** en prose ; docstrings en prose simple + listes à puces, aucun
  markup RST/markdown.
- Outils via **`uv run --no-sync`** (sinon uv réinstalle et casse l'env local).
- Jetons de placeholder au format **`<<...>>`** (`<<REDACT>>`, `<<PERSON>>`,
  `<<PERSON:1>>`, `<<PERSON:a1b2c3d4>>`).
- Conventions de style dans le skill `.claude/skills/piighost-code-style`
  (règles 1 à 20). Règle 18 : `base.py` porte le port `Any*` + le template
  `Base*`. Règle 20 : tout port de composant reçoit un `Base*` template, même avec
  un seul adaptateur, sauf si la décision variable est pairwise (pas un simple
  hook sur une entrée).
- Commits Conventional Commits, propres et non pollués (amender plutôt que
  empiler quand c'est un correctif de la brique précédente).
- Tests : pas de `__init__.py` sous `tests/`, donc **basenames de fichiers de test
  uniques** (sinon collision de collecte pytest).

## Composants terminés (chaîne du domaine)

Chaque composant est un package plat sous `src/piighost/`, avec `base.py`
(port + éventuel template), des adaptateurs en modules frères, un `__init__.py`
qui réexporte, et des tests miroirs sous `tests/`. Le guard d'imports
`tests/regression/test_imports.py` liste tout le public dans `PUBLIC_API`.

1. **models/** : `Span`, `Detection`, `Entity`, `Chunk` (frozen dataclasses,
   spans demi-ouverts `[start, end)`, `order=True`).
2. **text/** : `RecursiveCharacterTextSplitter` (offsets préservés),
   `boundary_wrap` + `find_all_word_boundary` (renvoie des `Span`), trait d'union
   et apostrophe comptés comme internes au mot.
3. **detector/** : port `AnyDetector`, `ExactMatchDetector`, `ChunkedDetector`.
4. **overlap_resolver/** : port `AnyOverlapResolver` + template
   `BaseOverlapResolver` (clustering des chevauchements + `_reduce` abstrait),
   adaptateur `ConfidenceOverlapResolver`. (package renommé depuis `resolver/`.)
5. **expander/** : port `AnyDetectionExpander`, `WordBoundaryExpander`. Signature
   `expand(text, detections)`. Ajoute les occurrences ratées d'une valeur détectée.
6. **linker/** : port `AnyEntityLinker` + template `BaseEntityLinker` (groupe par
   `_key`, hook), adaptateur `ExactEntityLinker` (clé `(text.casefold(), label)`).
   Groupement exact seulement, jamais de création de détection.
7. **entity_resolver/** : port `AnyEntityResolver` + template `BaseEntityResolver`
   (clustering des entités partageant une détection, `_reduce` abstrait rend une
   `list[Entity]`), adaptateurs `MergeEntityResolver` (union-find, A-B-C + C-D →
   A-B-C-D) et `SeparateEntityResolver` (le plus gros garde la détection partagée,
   égalité tranchée par occurrence la plus précoce).
8. **placeholder/** : `tags.py` (hiérarchie phantom de préservation, **sous-classes
   de `str`** pour que le jeton porte son tag), port générique covariant
   `AnyPlaceholderFactory[PreservationT_co]` avec `create(entities) ->
   Mapping[Entity, T]` (Mapping pour la covariance, pas dict). Adaptateurs :
   `RedactPlaceholderFactory` (`PreservesNothing`), `LabelPlaceholderFactory`
   (`PreservesLabel`), `LabelCounterPlaceholderFactory` et
   `LabelHashPlaceholderFactory` (`PreservesLabeledIdentityOpaque` ; le hash porte
   sur l'ordinal du compteur, jamais sur la valeur, format seulement),
   `MaskPlaceholderFactory` (`PreservesShape`, garde des chaînes courtes).
9. **anonymizer/** : port générique covariant `AnyAnonymizer[PreservationT_co]` +
   résultat `Anonymization[T]` (frozen : `.text`, `.tokens: Mapping[Entity, T]`),
   adaptateur `Anonymizer` (tient une factory). Remplacement en une passe
   gauche→droite en lisant le texte d'origine (pas d'édition en place, pas de
   décalage d'offsets). Suppose les spans non-chevauchants.
10. **déanonymisation** : méthode `deanonymize(text, tokens)` sur le port
    `AnyAnonymizer` et l'adaptateur `Anonymizer`. Prend le mapping `entity→token`
    d'une anonymisation, l'inverse en `token→valeur`, et remplace chaque jeton
    connu dans n'importe quel texte (voie 2, réponse inédite du modèle). Jetons
    inconnus laissés tels quels. Param typé `Mapping[Entity, str]` (la méthode ne
    lit que la chaîne, et ça évite l'usage covariant en position paramètre).
    Restauration non ambiguë seulement sous identité (deux entités partageant un
    jeton se collapsent, dernière valeur gagne) ; la garantie de type reste au
    middleware borné à `PreservesIdentity`.
11. **conversation_memory/** (repository) : port `AnyConversationMemory` +
    résultat `Forgotten(messages, detections)`, adaptateur
    `InMemoryConversationMemory` (`_threads` en `defaultdict`). Structure
    `(thread_id, message) -> détections` servant à la fois le cache forward et
    l'union first-seen via un seul `get_detections(thread_id, message=None)` :
    sans message (ou None) = union ; avec message = ses détections (None = miss,
    [] = vu sans PII). `remember` / `get_detections` / `forget`. Pas de template
    `Base*` (backends = mécanismes entiers, exception pairwise règle 20).
    Conception complète et plan crypto (hash de clé + chiffrement de valeur,
    backend Redis) dans `design/conversation-memory.md`.

## Décisions de design notables

- **Phantom tags = sous-classes de `str`.** Un jeton est une vraie chaîne taguée,
  ce qui fait remonter le `TypeVar` dans le type de sortie de `create`. Retour en
  `Mapping` (lecture seule, covariant) et pas `dict` (mutable, invariant) pour
  garder la covariance saine.
- **Hiérarchie des tags** : quatre combinaisons sœurs sous `PlaceholderPreservation`
  (Nothing, Label, Identity, LabeledIdentity). `PreservesNothing` est le tag de
  `[REDACT]`, pas la racine. `PreservesLabeledIdentity` hérite de Label et
  Identity. Le **tag Faker a été supprimé** (commit 322b0ee) : Faker n'est pas de
  l'Identity (pool fini donc collisions possibles, et collision avec le monde
  réel). Il devra revenir sous `PreservesLabel`, en frère de `PreservesShape`.
- **Middleware et covariance** : le port factory/anonymizer est covariant sur le
  tag pour qu'un consommateur exigeant `PreservesIdentity` accepte les sous-tags
  et refuse Label/Shape/Nothing à la vérification de types.

## En attente / différé

- **FuzzyExpander** (frère de `WordBoundaryExpander`) : ajouter les mots
  ressemblants comme détections (le fuzzy « ajout » se fait à l'expander, pas au
  linker ni au resolver).
- **Faker factory** + retour du tag Faker sous `PreservesLabel`.
- **FuzzyEntityResolver** (Jaro-Winkler) si besoin, via un autre template pairwise.
- Composants restants du blueprint : **déanonymisation**, **Guardrails**,
  **MappingStore / ConversationMemory**, **Validators**, **Overrides**,
  **orchestrateur de pipeline**, **config TOML**, **middleware LangChain**,
  **client HTTP**, **observation**.

## Prochaine étape

ConversationMemory in-memory faite (composant 11). Suites possibles, dans l'ordre
naturel :
- ports crypto **`Hasher`** (HmacSha256 défaut / Argon2 optionnel, pepper env) et
  **`Cipher`** (AES-GCM via pyca `cryptography`, clé env), deps optionnelles ;
- backend **`RedisConversationMemory`** qui compose serde + hasher + cipher (voir
  layout et flux dans `design/conversation-memory.md`) ;
- puis **Guardrails**, l'**orchestrateur de pipeline**, la config, le middleware.

À trancher avec l'utilisateur.

## Commandes dev

```bash
uv run --no-sync pytest -q                                   # toute la suite
uv run --no-sync pytest --doctest-modules src/piighost/text/boundaries.py
uv run --no-sync ruff check <paths>
uv run --no-sync pyrefly check <paths>
uv run --no-sync bandit -q -r <paths>
```

Purger `tests/**/__pycache__` avant un run complet si un fichier de test a été
renommé (collisions de basename fantômes).

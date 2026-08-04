# Detection Overrides Design

Design spec for the whitelist/blacklist override component of the PIIGhost v2
rewrite. Internal design document, French prose, English code identifiers.

## Context

Le détecteur se trompe dans les deux sens et l'opérateur de l'API doit pouvoir
le corriger en continu : forcer une valeur toujours manquée (whitelist), ne
jamais anonymiser un faux positif récurrent (blacklist). La v1 exposait un
endpoint override_detections ; la v2 n'a encore aucun composant d'override.

Règle de précédence posée par le mainteneur : les décisions serveur (overrides)
surclassent le retour utilisateur (les corrections HITL de
anonymize_corrected), qui surclasse la détection automatique. Conséquence
structurelle : une whitelist réalisée comme simple détecteur composite ne
surclasse pas le HITL, car une correction remplace les détections en mémoire et
le détecteur ne retourne plus sur un message corrigé (lecture cache).
L'override doit donc être une étape à part, appliquée sur l'ensemble de
détections quel qu'en soit l'origine.

## Goal

Un composant d'override pilotable par détecteurs : une whitelist dont les
détections sont ajoutées d'office et une blacklist dont les détections
invalident, avec des stratégies explicites pour le matching d'invalidation et
les collisions, appliqué de façon à surclasser les corrections HITL.

## Key decisions

- **Les listes sont des détecteurs.** DetectionOverride(whitelist:
  AnyDetector | None, blacklist: AnyDetector | None). Tout l'écosystème
  détecteurs sert des deux côtés (exact, regex, composite, NER), aucun DSL de
  matching maison, et le futur bloc config réutilise les configs détecteurs.
  Idée du mainteneur pendant le brainstorm, remplaçant des listes statiques
  valeur vers label.
- **Les sémantiques sont des stratégies** (enums, patron de
  middleware/strategy.py, mais vivant dans le composant) :
  - BlacklistStrategy, comment une détection de la blacklist invalide une
    détection existante. EXACT, le défaut : span identique et label identique.
    VALUE : même texte casefoldé, positions et labels ignorés, la valeur est
    retirée partout. OVERLAP : tout chevauchement invalide, aveugle au label.
  - OverrideConflictStrategy, quand whitelist et blacklist se contredisent sur
    un span. WHITELIST_WINS, le défaut, fail-closed : blacklist appliquée aux
    détections primaires d'abord, whitelist ajoutée en dernier. BLACKLIST_WINS :
    whitelist d'abord, blacklist invalide ensuite y compris le forcé. RAISE :
    une collision entre les sorties des deux détecteurs lève
    ConflictingOverrideError.
  - WhitelistStrategy, quand une valeur whitelistée a une provenance assistant
    (la revue finale a montré que sans décision explicite, la provenance
    gagnait en silence). RESPECT_PROVENANCE, le défaut : la whitelist garantit
    la détection, mais une valeur introduite d'abord par l'assistant reste en
    clair. Le modèle l'a émise parce qu'elle était utile au contexte et ne sait
    pas qu'elle est confidentielle ; la remplacer par un token lui signalerait
    précisément que cette valeur est sensible, une fuite de métadonnée, en plus
    de le priver de sa connaissance du monde. FORCE : une valeur whitelistée
    est tokenisée quel que soit son introducteur. Mécanique : le port gagne
    forces_value(value), vrai quand la whitelist matche la valeur entière et
    que la stratégie est FORCE ; le filtre de provenance de _thread_tokens
    garde les entités que l'override force.
- **La whitelist remplace ce qu'elle chevauche.** Une détection whitelistée
  écrase toute détection primaire chevauchante, sinon le rendu recevrait des
  spans conflictuels et la précédence serveur serait violée.
- **Placement : après la détection, avant tout le reste.** L'override
  s'applique sur les détections brutes, avant la résolution d'overlaps,
  l'expansion et le linking (exigence du mainteneur, éviter que les étapes
  aval décident sur un ensemble que l'override modifie ensuite).
- **Composant pur, exports eager.** Il ne dépend que du port détecteur, donc
  pas d'extra, imports directs, symboles dans PUBLIC_API.

## Architecture

Nouveau package src/piighost/components/override/ :

- strategy.py : les deux enums BlacklistStrategy (EXACT, VALUE, OVERLAP) et
  OverrideConflictStrategy (WHITELIST_WINS, BLACKLIST_WINS, RAISE), chacune avec
  docstrings par membre.
- base.py : le port AnyDetectionOverride, protocol runtime-checkable avec
  async def apply(text: str, detections: list[Detection]) -> list[Detection].
  Pas de template Base : comme les guards, des implémentations divergeraient
  par tout leur mécanisme, pas par un hook unique (exception documentée à la
  règle 20).
- detector.py : DetectionOverride(whitelist=None, blacklist=None,
  blacklist_strategy=BlacklistStrategy.EXACT,
  conflict_strategy=OverrideConflictStrategy.WHITELIST_WINS).
  - apply exécute les détecteurs configurés sur le texte. La blacklist invalide
    les détections selon la stratégie de matching ; la whitelist ajoute ses
    détections en remplaçant les chevauchantes ; l'ordre des deux applications
    découle de la stratégie de conflit, et RAISE compare les deux sorties et
    lève sur collision de spans.
  - Un composant sans aucun détecteur configuré est accepté et laisse les
    détections inchangées (utile au câblage config).

## Pipeline integration

Ordre des étapes (les deux pipelines) : detect, override, overlap, expand,
link. Le paramètre override: AnyDetectionOverride | None = None s'ajoute en fin
de signature des deux constructeurs.

Pipeline de base : appliqué dans anonymize entre la détection et la résolution
d'overlaps.

Thread pipeline, aux points d'écriture de la mémoire, ce qui réalise la
précédence sur le HITL :

- chemin frais de _detect : detect, override, overlap, expand, puis remember,
  la mémoire stocke le post-override ;
- anonymize_corrected : l'ensemble corrigé passe par override.apply avant
  remember, donc une valeur whitelistée retirée par l'utilisateur est
  ré-imposée, et une valeur blacklistée ré-ajoutée est retirée.

Pourquoi à l'écriture : l'assignation des tokens du thread unionne les
détections en mémoire. Une détection whitelistée absente de la mémoire n'aurait
pas de token et sortirait en clair, l'inverse exact de l'intention. Trade-off
accepté et documenté : un changement des listes serveur ne se ré-applique pas
aux messages déjà en cache ; re-soumettre le message ou forget_thread.

Observation : un span piighost.override est émis seulement quand le composant
est configuré, via le mécanisme _stage_span existant.

## Guard interplay

Une valeur que la blacklist laisse en clair serait re-détectée par un
DetectorGuardRail et ferait échouer l'anonymisation en PIIRemainingError, ce qui
rendrait la blacklist inutilisable avec une garde. Quand une garde et une
blacklist sont toutes deux configurées, le pipeline exécute le détecteur de
blacklist sur le message et alimente les valeurs matchées (casefoldées) dans le
paramètre expected de _guard, le mécanisme d'exemption existant déjà utilisé
pour les valeurs de provenance assistant. L'exemption est par valeur, pas par
span, comme le reste du mécanisme expected. Coût accepté : le détecteur de
blacklist tourne une seconde fois par appel gardé (une fois dans apply, une
fois pour l'exemption) ; si une blacklist lourde (modèle) est un jour
configurée, mettre en cache sa sortie au sein de l'appel est l'optimisation
connue.

## Errors

Ajouts à exceptions.py : OverrideError(PIIGhostError), base de la famille, et
ConflictingOverrideError(OverrideError), levée par la stratégie de conflit
RAISE quand les sorties whitelist et blacklist se chevauchent.

## Testing

Déterministe, ExactMatchDetector et RegexDetector comme détecteurs d'override,
squelette conformance-then-behavior :

- conformité au port AnyDetectionOverride ;
- whitelist : ajoute une valeur manquée, remplace une détection chevauchante
  (label serveur gagnant), casse source préservée ;
- blacklist : les trois stratégies de matching (EXACT ne retire que le span et
  label identiques, VALUE retire partout, OVERLAP retire tout chevauchement) ;
- conflit : les trois stratégies (WHITELIST_WINS anonymise, BLACKLIST_WINS
  laisse en clair, RAISE lève ConflictingOverrideError) ;
- composant vide : détections inchangées ;
- pipeline de base : l'override s'applique avant overlap et link (ordre) ;
- thread : précédence sur HITL, une correction qui retire une valeur
  whitelistée la voit ré-imposée au re-rendu, une correction qui ré-ajoute une
  valeur blacklistée la voit retirée ;
- garde : une valeur blacklistée en clair ne fait pas échouer une
  DetectorGuardRail qui la connaît (exemption), et une vraie fuite hors listes
  échoue toujours ;
- régression : nouveaux symboles eager dans PUBLIC_API, exceptions comprises.

## Documentation notes (pour les pages du site, bloc docs ultérieur)

- Le point garde ci-dessus, tel quel : pourquoi l'exemption existe, qu'elle est
  par valeur, et qu'une blacklist sans cette exemption serait incompatible avec
  un DetectorGuardRail.
- Positionnement whitelist vs ExactMatchDetector : la whitelist (un
  ExactMatchDetector ou RegexDetector passé à DetectionOverride) est le moyen de
  production pour forcer des valeurs, car elle surclasse les corrections HITL ;
  ExactMatchDetector employé seul comme détecteur primaire est d'abord une aide
  de test.
- L'interaction EXACT plus expander : un expander peut ré-ajouter un span que
  la blacklist EXACT venait d'invalider (il ré-étend les occurrences des
  détections survivantes de la même valeur) ; recommander VALUE quand un
  expander est configuré.
- Le trade-off de fraîcheur : les changements de listes ne se ré-appliquent pas
  aux messages en cache, re-soumettre ou forget_thread. Cas plus large du même
  mécanisme : des messages mis en cache par une instance sans override (override
  ajouté plus tard, ou déploiement multi-worker où un worker partage le backend
  mémoire sans les listes) sont servis tels quels, les listes n'y sont pas
  imposées. Même remède, et à couvrir explicitement en doc.
- Angle mort d'observabilité assumé : l'application de l'override sur le chemin
  corrigé (anonymize_corrected, avant remember) n'émet pas de span, elle se
  produit hors de toute trace racine ; le rendu qui suit lit le cache, donc le
  moment où le serveur surclasse une correction humaine n'est pas visible en
  trace.
- La chaîne de précédence complète : overrides serveur, puis corrections HITL,
  puis détection automatique.

## Out of scope

- Le câblage TOML des overrides (bloc config ultérieur).
- Un endpoint API (côté piighost-api, pas cette lib).
- La résolution du staleness des messages en cache lors d'un changement de
  listes (versionnage des overrides), noté comme évolution possible.
- Toute modification des ports détecteur, mémoire ou garde.

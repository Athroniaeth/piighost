---
icon: lucide/triangle-alert
---

# Limites

`piighost` dé-identifie, il ne rend pas un texte magiquement sûr. Cette page liste les limites connues, leur raison d'être et comment les atténuer. Elle prolonge le [modèle de menaces](security.md).

## Les détecteurs sont au mieux

Un détecteur ne trouve que ce qu'il sait reconnaître. Deux familles se partagent le travail, avec des angles morts différents.

Un détecteur à motif (`RegexDetector`) reconnaît des chaînes de caractères qui suivent une structure fixe, comme un email, une IP ou une forme de carte bancaire. Il est déterministe sur ces formats et aveugle au reste. Un détecteur NER (`Gliner2Detector`, `SpacyDetector`, `TransformersDetector`) ou LLM (`LLMDetector`) reconnaît des entités en texte libre, un nom, un lieu, une organisation, mais il en manque. Un nom rare, une orthographe inhabituelle, une entité hors distribution passent en clair vers le LLM.

Une donnée confidentielle non détectée n'est pas dé-identifiée. C'est un enjeu d'ingénierie, pas un défaut conceptuel.

**Mitigation** : chaîner un détecteur NER et un `RegexDetector` via le `CompositeDetector`, pour couvrir à la fois le texte libre et les formats structurés. Charger un modèle NER spécifique à la locale pour une meilleure précision. Voir [Étendre PIIGhost](extending.md).

## Un modèle peut tronquer un texte plus long que son contexte

Un modèle NER a une longueur d'entrée maximale. Un texte plus long est tronqué par le modèle, et la fin tronquée n'est jamais analysée, sa PII passe donc en clair. Rien ne vous avertit par défaut.

La limite est celle du modèle, pas du pipeline. Elle s'impose à toute dé-identification adossée à un modèle NER, et `piighost` fournit de quoi la contourner plutôt que de la subir.

**Mitigation** : fixer `max_chars` sur le détecteur NER à la longueur d'entrée sûre du modèle. Avec `auto_chunk` activé (le défaut), un texte plus long est découpé en morceaux chevauchants analysés séparément puis recollés, si bien que la fin est couverte. Avec `auto_chunk` désactivé, un texte trop long lève `TextTooLongError` plutôt que d'être analysé en partie. Pour de très longues entrées, envelopper le détecteur dans un `ChunkedDetector`.

## La couverture linguistique dépend du modèle

L'ensemble des langues qu'un détecteur NER peut couvrir est fixé par le modèle branché. La couverture varie d'un modèle à l'autre, et toutes les langues ne sont pas supportées avec la même précision. Avant de déployer sur une nouvelle locale, lisez la fiche du modèle et exécutez un petit jeu de validation.

Là encore, la limite est celle du modèle, pas du pipeline. Un détecteur à motif ne la connaît pas, un IBAN ou une adresse mail a la même forme dans toutes les langues.

**Mitigation** : charger un modèle spécifique à la locale, ou combiner plusieurs détecteurs via le `CompositeDetector`.

## La recherche par mot entier suppose des espaces entre les mots

Pour retrouver une valeur, `piighost` la cherche comme un mot entier, si bien que `Jean`{ .pii } n'est pas trouvé dans `Jeanne`{ .pii }. Une valeur ne doit toucher ni lettre, ni chiffre, ni trait d'union, d'un côté comme de l'autre. Le chinois, le japonais et le thaï écrivent les mots sans espace entre eux, donc une valeur dans ces écritures touche toujours une lettre, et elle n'est jamais trouvée.

| Texte | Valeur cherchée | Trouvé |
|---|---|---|
| `Jeanne et Jean`{ .pii } | `Jean`{ .pii } | le second `Jean`{ .pii } |
| `田中さんは田中です`{ .pii } | `田中`{ .pii } | rien |

Trois composants reposent sur cette recherche. `ExactMatchDetector` ne trouve rien, `WordBoundaryExpander` ne trouve aucune répétition, et `LLMDetector`, qui place dans le texte chaque valeur que nomme le LLM, écarte une valeur que le LLM a pourtant trouvée, si bien qu'elle part telle quelle. Les détecteurs qui rendent des positions, `RegexDetector` et les détecteurs NER, ne sont pas concernés.

Prendre en charge ces écritures demanderait un segmenteur de mots par langue, et le pipeline n'en a pas.

**Mitigation** : sur un texte chinois, japonais ou thaï, détecter avec un modèle NER ou un motif plutôt qu'avec `ExactMatchDetector` ou `LLMDetector`, et ne pas compter sur l'expander pour les répétitions.

## Un motif ne couvre pas toutes les écritures à la fois

Le module `re` de Python ne connaît pas la segmentation en mots, et il ne compte pas les signes combinants, les voyelles du hindi et des autres écritures indiennes, comme des lettres. Un motif e-mail doit donc choisir les lettres qu'il accepte, et chaque choix en manque.

| Texte | Motif qui accepte les lettres Unicode, `(?u:\w)` | `EMAIL` de `hub:piighost/generic` |
|---|---|---|
| `écrire à expéditeur@exemple.fr`{ .pii } | `expéditeur@exemple.fr`{ .pii } | `expéditeur@exemple.fr`{ .pii } |
| `メールはtanaka@example.jpです`{ .pii } | toute la phrase | `tanaka@example.jp`{ .pii } |
| `ελένη@example.gr`{ .pii } | `ελένη@example.gr`{ .pii } | rien |
| `राम@उदाहरण.भारत`{ .pii } | rien | rien |

Un motif qui accepte les lettres Unicode trouve entière une adresse accentuée ou grecque. Dans un texte chinois ou japonais sans espace autour de l'adresse, les idéogrammes voisins sont aussi des lettres, donc le motif les englobe. Le jeton masque plus que l'adresse, et rien ne part en clair. L'adresse en hindi lui échappe quand même, car ses voyelles sont des signes combinants.

Le motif `EMAIL` de `hub:piighost/generic` n'accepte que les lettres latines, les lettres et chiffres ASCII plus la plage latine de `À` à `ɏ`. Il trouve exactement les exemples accentué et japonais, et manque toute adresse écrite dans une autre écriture, qui part telle quelle.

**Mitigation** : pour un texte dans une écriture non latine, écrire le motif e-mail de votre config pour les adresses qu'il contient vraiment, puisqu'un motif en ligne l'emporte sur celui du groupe au même label, ou détecter les adresses avec un modèle NER.

## Pas de validation par checksum (volontaire)

`RegexDetector` matche sur la forme seule. Il ne vérifie aucun checksum, pas de Luhn sur les cartes, pas de clé IBAN, pas de clé NIR. C'est délibéré.

Une valeur structurée peut arriver déformée par de l'OCR, un caractère lu de travers. Un validateur par checksum rejetterait alors un IBAN ou un NIR réel mais mal transcrit, et cette PII repartirait en clair vers le LLM. `piighost` préfère garder un faux positif de forme plutôt que laisser fuiter une vraie valeur abîmée. C'est un choix de sécurité, échouer du côté qui détecte.

La contrepartie est que `RegexDetector` peut détecter des chaînes qui ont la forme d'une PII sans en être une (une suite de chiffres qui ressemble à une carte). Le coût d'un tel faux positif est bénin, un token de plus. Le coût du faux négatif inverse serait une fuite.

**Mitigation** : affiner les motifs si les faux positifs de forme gênent une charge précise. Ne pas réintroduire de filtre par checksum en amont d'un texte qui peut venir d'OCR. Si vos entrées sont saisies au clavier et ne passent jamais par de l'OCR, le compromis s'inverse et vous pouvez écrire votre propre détecteur avec validation par checksum, le port `AnyDetector` est ouvert. Voir [Étendre PIIGhost](extending.md).

## Les placeholders peuvent se confondre selon la factory

La factory de placeholder décide de ce qui distingue deux entités. Certaines familles produisent la même sortie pour deux entrées différentes.

- `RedactPlaceholderFactory` ramène toute valeur sur `<<REDACT>>`{ .placeholder }. `LabelPlaceholderFactory` ramène toute valeur d'un même label sur `<<PERSON>>`{ .placeholder }. Ces deux familles ne distinguent pas les entités, donc elles ne sont pas réversibles.
- `MaskPlaceholderFactory` garde un fragment de la valeur, `j***@mail.com`{ .placeholder }. Deux valeurs de forme voisine peuvent se confondre sur un même masque, et un masque peut aussi se confondre avec une vraie valeur dans une réponse d'outil.
- `LabelCounterPlaceholderFactory` (`<<PERSON:1>>`{ .placeholder }) et `LabelHashPlaceholderFactory` (`<<PERSON:a1b2c3d4>>`{ .placeholder }) donnent un token distinct par entité et se retrouvent dans le texte, donc elles restent réversibles sans ambiguïté.

**Mitigation** : voir [Placeholder factories](placeholder-factories.md) pour la taxonomie complète et le choix par usage.

## La restauration n'est fiable que sous identité

Restaurer une valeur à partir d'un placeholder suppose que le placeholder identifie une entité unique. Deux propriétés se combinent dans le token. Le **typage** dit de quelle sorte de valeur il s'agit, personne, lieu, email. L'**identité** dit de laquelle il s'agit parmi celles du même type. Chaque factory porte un tag de préservation qui déclare ce que son token garde des deux.

| Factory | Tag de préservation | Token émis | Typage | Identité | Restauration |
|---|---|---|---|---|---|
| `RedactPlaceholderFactory` | `PreservesNothing` | `<<REDACT>>`{ .placeholder } | non | non | impossible |
| `LabelPlaceholderFactory` | `PreservesLabel` | `<<PERSON>>`{ .placeholder } | oui | non | impossible |
| `MaskPlaceholderFactory` | `PreservesShape` | `j***@mail.com`{ .placeholder } | oui | partielle | ambiguë |
| `LabelCounterPlaceholderFactory` | `PreservesLabeledIdentityOpaque` | `<<PERSON:1>>`{ .placeholder } | oui | oui | fiable |
| `LabelHashPlaceholderFactory` | `PreservesLabeledIdentityOpaque` | `<<PERSON:a1b2c3d4>>`{ .placeholder } | oui | oui | fiable |

Sur `Patrick et Marie habitent à Paris`{ .pii }, la différence se voit tout de suite.

- Avec `LabelPlaceholderFactory`, les deux personnes deviennent le même `<<PERSON>>`{ .placeholder }. Le type est là, l'identité non, donc rien ne dit lequel des deux tokens valait `Patrick`{ .pii }.
- Avec `LabelCounterPlaceholderFactory`, `Patrick`{ .pii } devient `<<PERSON:1>>`{ .placeholder } et `Marie`{ .pii } devient `<<PERSON:2>>`{ .placeholder }. Chaque token retombe sur une seule valeur, la restauration est sans ambiguïté.

Le middleware `PIIAnonymizationMiddleware` impose cette contrainte au niveau du type. Il exige une factory `PreservesRecognizableIdentity`, c'est-à-dire un token unique par entité et reconnaissable dans un texte. Une factory qui ne remplit pas ce contrat est refusée à la construction (`UnrecognizableFactoryError`). La frontière d'appel d'outil s'appuie sur du remplacement de chaîne, elle a besoin de tokens uniques pour rester réversible.

**Mitigation** : garder `LabelCounterPlaceholderFactory` ou `LabelHashPlaceholderFactory` avec le middleware. Voir [Stratégies d'appel outil](tool-call-strategies.md) pour les modes `FULL`, `INPUT`, `OUTPUT` et `PASSTHROUGH`.

## Les PII inventées par le LLM ne sont pas dans le mapping

La restauration fonctionne sur les valeurs vues à l'entrée. Si le LLM hallucine un nom qui n'a jamais figuré dans les messages de l'utilisateur, par exemple en inventant un nom de client plausible, cette PII n'est dans aucun mapping. Elle ne peut donc pas être rattachée à une valeur d'origine.

Le middleware détecte un cas voisin, le placeholder inventé. Si le LLM fabrique un jeton qui ressemble à un placeholder mais n'a jamais été émis, `piighost` le repère (le token n'a pas de valeur associée) et le refuse par défaut (`InventedPlaceholderError`, stratégie `RAISE`). Les stratégies `KEEP` et `DROP` existent pour d'autres politiques.

**Mitigation** : exécuter une étape de re-détection sur la sortie du LLM au niveau applicatif, et décider s'il faut supprimer, signaler ou re-dé-identifier avant l'affichage. Un garde-fou (`DetectorGuardRail`, `LLMGuardRail`, `ModerationGuardRail`) re-vérifie la sortie dé-identifiée et signale des données confidentielles résiduelles, à charge pour l'appelant de lever `PIIRemainingError`.

## La mémoire est locale au processus par défaut

`InMemoryConversationMemory` garde le mapping thread par thread dans un dictionnaire du processus. Rien ne survit à un redémarrage, rien n'est partagé entre processus. Dès que vous passez à l'échelle horizontalement, deux workers ont deux mémoires et deux espaces de placeholders indépendants, donc la même entité peut recevoir deux tokens différents selon le worker qui la traite.

**Mitigation** : configurer `RedisConversationMemory` pour partager le mapping entre workers et le faire survivre à un redémarrage. Ce backend peut chiffrer les valeurs et hacher les clés (optionnel, tout ou rien). Le backend en mémoire est borné par défaut, `max_threads` et `ttl` ajustent la limite de sa croissance dans un processus de longue durée. Voir [Sécurité](security.md) et [Déploiement](deployment.md).

## Un thread isole le mapping

La mémoire est cloisonnée par `thread_id`. Deux conversations séparées ne partagent aucun placeholder, ce qui est voulu, mais implique que la même personne dans deux threads reçoit deux tokens sans lien. Le middleware exige un `thread_id` et ne se rabat pas sur un thread partagé par défaut, pour éviter qu'une conversation ne voie le mapping d'une autre.

**Mitigation** : propager un `thread_id` stable et par conversation. Appeler `forget_thread` pour purger une conversation de la mémoire quand elle n'a plus lieu d'être.

## La latence ajoutée n'est pas encore mesurée

Il n'existe pas de benchmark officiel de la latence ajoutée par le pipeline sur des charges typiques. Le surcoût dépend du détecteur (inférence du NER choisi), de la longueur du texte, et de la présence de valeurs déjà connues dans la mémoire du thread.

**Mitigation** : mesurer sur votre propre charge avant de dimensionner le trafic de production. Garder les détecteurs sur GPU quand c'est possible pour les chemins à forte densité NER.

## Couverture minimale des menaces

`piighost` traite l'exfiltration *vers le LLM et son hébergeur*. Il ne remplace pas le chiffrement au repos, le contrôle d'accès, ni les bonnes pratiques de journalisation du reste de votre système. Voir [Sécurité](security.md) pour le modèle de menaces complet.

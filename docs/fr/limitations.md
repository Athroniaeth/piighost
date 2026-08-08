---
icon: lucide/triangle-alert
---

# Limites

`piighost` dé-identifie, il ne rend pas un texte magiquement sûr. Cette page liste les limites connues, leur raison d'être et comment les atténuer. Elle prolonge le [modèle de menaces](security.md).

## Les détecteurs sont au mieux

Un détecteur ne trouve que ce qu'il sait reconnaître. Deux familles se partagent le travail, avec des angles morts différents.

Un détecteur à motif (`RegexDetector`) reconnaît des chaînes de caractères qui suivent une structure fixe, comme un email, une IP ou une forme de carte bancaire. Il est déterministe sur ces formats et aveugle au reste. Un détecteur NER (`Gliner2Detector`, `SpacyDetector`, `TransformersDetector`) ou LLM (`LLMDetector`) reconnaît des entités en texte libre, un nom, un lieu, une organisation, mais il en manque. Un nom rare, une orthographe inhabituelle, une entité hors distribution passent en clair vers le LLM.

Une PII non détectée n'est pas dé-identifiée. C'est un enjeu d'ingénierie, pas un défaut conceptuel.

**Mitigation** : chaîner un détecteur NER et un `RegexDetector` via le `CompositeDetector`, pour couvrir à la fois le texte libre et les formats structurés. Charger un modèle NER spécifique à la locale pour une meilleure précision. Voir [Étendre PIIGhost](extending.md).

## La couverture linguistique dépend du modèle

L'ensemble des langues qu'un détecteur NER peut couvrir est fixé par le modèle branché. La couverture varie d'un modèle à l'autre, et toutes les langues ne sont pas supportées avec la même précision. Avant de déployer sur une nouvelle locale, lisez la fiche du modèle et exécutez un petit jeu de validation.

**Mitigation** : charger un modèle spécifique à la locale, ou combiner plusieurs détecteurs via le `CompositeDetector`.

## Pas de validation par checksum, par choix

`RegexDetector` matche sur la forme seule. Il ne vérifie aucun checksum, pas de Luhn sur les cartes, pas de clé IBAN, pas de clé NIR. C'est délibéré.

Une valeur structurée peut arriver déformée par de l'OCR, un caractère lu de travers. Un validateur par checksum rejetterait alors un IBAN ou un NIR réel mais mal transcrit, et cette PII repartirait en clair vers le LLM. `piighost` préfère garder un faux positif de forme plutôt que laisser fuiter une vraie valeur abîmée. C'est un choix de sécurité, échouer du côté qui détecte.

La contrepartie est que `RegexDetector` peut détecter des chaînes qui ont la forme d'une PII sans en être une (une suite de chiffres qui ressemble à une carte). Le coût d'un tel faux positif est bénin, un token de plus. Le coût du faux négatif inverse serait une fuite.

**Mitigation** : affiner les motifs si les faux positifs de forme gênent une charge précise. Ne pas réintroduire de filtre par checksum en amont d'un texte qui peut venir d'OCR.

## Les placeholders peuvent se confondre selon la factory

La factory de placeholder décide de ce qui distingue deux entités. Certaines familles laissent deux valeurs différentes retomber sur le même token.

- `RedactPlaceholderFactory` collapse toute PII sur `<<REDACT>>`{ .placeholder }. `LabelPlaceholderFactory` collapse toute PII d'un même label sur `<<PERSON>>`{ .placeholder }. Ces deux familles ne distinguent pas les entités, donc elles ne sont pas réversibles.
- `MaskPlaceholderFactory` garde un fragment de la valeur, `j***@mail.com`{ .placeholder }. Deux valeurs de forme voisine peuvent se confondre sur un même masque, et un masque peut aussi se confondre avec une vraie valeur dans une réponse d'outil.
- `LabelCounterPlaceholderFactory` (`<<PERSON:1>>`{ .placeholder }) et `LabelHashPlaceholderFactory` (`<<PERSON:a1b2c3d4>>`{ .placeholder }) donnent un token distinct par entité et se retrouvent dans le texte, donc elles restent réversibles sans ambiguïté.

**Mitigation** : voir [Placeholder factories](placeholder-factories.md) pour la taxonomie complète et le choix par usage.

## La désanonymisation n'est fiable que sous identité

Restaurer une valeur à partir d'un placeholder suppose que le placeholder identifie une entité unique. Une factory qui préserve l'identité (`LabelCounterPlaceholderFactory`, `LabelHashPlaceholderFactory`) garantit qu'un token retombe toujours sur la même valeur. Une factory qui collapse (redact, label, masque) ne le garantit pas, donc la désanonymisation devient ambiguë ou impossible.

Le middleware `PIIAnonymizationMiddleware` impose cette contrainte au niveau du type. Il exige une factory `PreservesRecognizableIdentity`, c'est-à-dire un token unique par entité et reconnaissable dans un texte. Une factory qui ne remplit pas ce contrat est refusée à la construction (`UnrecognizableFactoryError`). La frontière d'appel d'outil s'appuie sur du remplacement de chaîne, elle a besoin de tokens uniques pour rester réversible.

**Mitigation** : garder `LabelCounterPlaceholderFactory` ou `LabelHashPlaceholderFactory` avec le middleware. Voir [Stratégies d'appel outil](tool-call-strategies.md) pour les modes `FULL`, `INPUT`, `OUTPUT` et `PASSTHROUGH`.

## Les PII inventées par le LLM ne sont pas dans le mapping

La restauration fonctionne sur les valeurs vues à l'entrée. Si le LLM hallucine un nom qui n'a jamais figuré dans les messages de l'utilisateur, par exemple en inventant un nom de client plausible, cette PII n'est dans aucun mapping. Elle ne peut donc pas être rattachée à une valeur d'origine.

Le middleware détecte un cas voisin, le placeholder inventé. Si le LLM fabrique un jeton qui ressemble à un placeholder mais n'a jamais été émis, `piighost` le repère (le token n'a pas de valeur associée) et le refuse par défaut (`InventedPlaceholderError`, stratégie `RAISE`). Les stratégies `KEEP` et `DROP` existent pour d'autres politiques.

**Mitigation** : exécuter une étape de re-détection sur la sortie du LLM au niveau applicatif, et décider s'il faut supprimer, signaler ou re-dé-identifier avant l'affichage. Un garde-fou (`DetectorGuardRail`, `LLMGuardRail`, `ModerationGuardRail`) re-vérifie la sortie dé-identifiée et signale une PII résiduelle, à charge pour l'appelant de lever `PIIRemainingError`.

## La mémoire est locale au processus par défaut

`InMemoryConversationMemory` garde le mapping thread par thread dans un dictionnaire du processus. Rien ne survit à un redémarrage, rien n'est partagé entre processus. Dès que vous passez à l'échelle horizontalement, deux workers ont deux mémoires et deux espaces de placeholders indépendants, donc la même entité peut recevoir deux tokens différents selon le worker qui la traite.

**Mitigation** : configurer `RedisConversationMemory` pour partager le mapping entre workers et le faire survivre à un redémarrage. Ce backend chiffre les valeurs et hache les clés. Voir [Sécurité](security.md) et [Déploiement](deployment.md).

## Un thread isole le mapping

La mémoire est cloisonnée par `thread_id`. Deux conversations séparées ne partagent aucun placeholder, ce qui est voulu, mais implique que la même personne dans deux threads reçoit deux tokens sans lien. Le middleware exige un `thread_id` et ne se rabat pas sur un thread partagé par défaut, pour éviter qu'une conversation ne voie le mapping d'une autre.

**Mitigation** : propager un `thread_id` stable et par conversation. Appeler `forget_thread` pour purger une conversation de la mémoire quand elle n'a plus lieu d'être.

## La latence ajoutée n'est pas encore mesurée

Il n'existe pas de benchmark officiel de la latence ajoutée par le pipeline sur des charges typiques. Le surcoût dépend du détecteur (inférence du NER choisi), de la longueur du texte, et de la présence de valeurs déjà connues dans la mémoire du thread.

**Mitigation** : mesurer sur votre propre charge avant de dimensionner le trafic de production. Garder les détecteurs sur GPU quand c'est possible pour les chemins à forte densité NER.

## Couverture minimale des menaces

`piighost` traite l'exfiltration *vers le LLM et son hébergeur*. Il ne remplace pas le chiffrement au repos, le contrôle d'accès, ni les bonnes pratiques de journalisation du reste de votre système. Voir [Sécurité](security.md) pour le modèle de menaces complet.

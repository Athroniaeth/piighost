---
icon: lucide/book-a
---

# Glossaire

Termes utilisés dans la documentation `piighost`. Chaque entrée définit le
concept par ce qu'il fait. Les noms de classes restent en anglais.

PII
:   Personally Identifiable Information, en français donnée à caractère
    personnel. Toute valeur qui peut identifier une personne, c'est-à-dire nom,
    adresse, numéro de téléphone, email, lieu, organisation, numéro de compte.
    `piighost` trouve et remplace les PII pour qu'un LLM en aval ne voie jamais
    la valeur brute.

Dé-identification
:   Remplacement des PII par des placeholders tout en gardant la correspondance
    entre chaque valeur et son placeholder, de sorte que l'original peut être
    restauré ensuite. Le pipeline `piighost` par défaut dé-identifie. Au sens du
    RGPD c'est de la pseudonymisation, pas de l'anonymisation.

Anonymisation
:   Suppression des PII sans aucun moyen de les restaurer. Irréversible par
    définition. Une placeholder factory de caviardage anonymise, puisqu'elle ne
    garde aucune correspondance vers la valeur.

Placeholder
:   Token qui remplace une PII dans le texte anonymisé, par exemple
    `<<PERSON:1>>`{ .placeholder } ou `<<EMAIL:1>>`{ .placeholder }. L'apparence
    d'un placeholder est décidée par une placeholder factory.

Placeholder factory
:   Composant qui produit les placeholders. Il décide la forme du token et ce que
    le token préserve, c'est-à-dire un label, une identité stable, les deux ou
    rien. Factories fournies : `RedactPlaceholderFactory`,
    `LabelPlaceholderFactory`, `LabelCounterPlaceholderFactory`,
    `LabelHashPlaceholderFactory` et `MaskPlaceholderFactory`.

Détecteur
:   Composant qui trouve les PII dans un texte et retourne des détections. Les
    détecteurs implémentent le protocole `AnyDetector` et sont interchangeables.
    Trois familles existent, chacune sous son entrée : regex, NER et LLM.

Détecteur regex
:   Détecteur qui reconnaît des motifs fixes, c'est-à-dire des chaînes de
    caractères qui suivent une structure connue comme un IBAN ou un numéro de
    téléphone. Efficace sur les formats structurés, inutilisable sur du texte
    libre comme un prénom ou une date écrite. `RegexDetector`.

Détecteur NER
:   Named Entity Recognition, reconnaissance d'entités nommées. Modèle d'IA qui
    classe les mots d'un texte dans des catégories décidées à l'avance, comme
    personne, lieu ou organisation. Fonctionne sur le texte libre là où un motif
    échoue. `SpacyDetector`, `Gliner2Detector`, `TransformersDetector`.

Détecteur LLM
:   Détecteur qui demande à un grand modèle de langage de retourner les PII
    trouvées en sortie structurée. Plus lent et moins déterministe que le regex
    ou le NER, mais capable de raisonner sur le contexte. `LLMDetector`.

Span
:   Intervalle de caractères semi-ouvert `[start, end)` dans un texte, calqué sur
    la sémantique du slice Python. Chaque détection porte un `Span` qui marque où
    se trouve la PII. `Span`.

Détection
:   Une occurrence de PII repérée par un détecteur, c'est-à-dire un `Span`, le
    texte apparié, un label et une confiance dans l'intervalle 0 à 1. Détecter
    `Patrick`{ .pii } comme `PERSON` en `(0, 7)` avec une confiance de `0.95` est
    une `Detection`.

Entité
:   Groupe de détections qui référent à la même valeur de PII. Chaque occurrence
    de la valeur est une détection. Le groupe partage un placeholder et restaure
    vers une valeur. Différent d'une détection, qui est une occurrence unique.
    `Entity`.

Linker
:   Composant qui regroupe les détections en entités. Il trouve les occurrences
    qui référent à la même valeur, afin qu'elles partagent un placeholder. Lier
    `Patrick`{ .pii } en `(0, 7)` et `patrick`{ .pii } en `(34, 41)` donne une
    entité. `ExactEntityLinker`.

Résolveur d'entités
:   Composant qui réconcilie les conflits d'entités, par exemple deux groupes qui
    devraient n'en faire qu'un quand leurs valeurs sont proches.
    `MergeEntityResolver` fusionne les groupes qui se recouvrent,
    `FuzzyEntityResolver` fusionne les valeurs presque identiques,
    `SeparateEntityResolver` laisse chaque groupe tel quel.

Guard rail
:   Composant qui revérifie le texte anonymisé à la recherche d'une PII que le
    pipeline a manquée. Il tourne après le remplacement et lève une erreur si une
    PII résiduelle demeure. Un guard rail peut relancer un détecteur
    (`DetectorGuardRail`) ou interroger un LLM (`LLMGuardRail`).

Thread
:   Portée de conversation identifiée par un `thread_id`. La mémoire est isolée
    par thread, donc deux conversations parallèles ne partagent jamais l'état des
    PII. Un placeholder reste stable sur tous les messages d'un même thread.

thread_id
:   Chaîne qui identifie un thread. Le pipeline de thread et le middleware s'en
    servent pour cadrer la mémoire et router chaque message vers la bonne
    conversation.

Mémoire de conversation
:   Stockage qui accumule les entités d'un thread au fil des messages, de sorte
    qu'une valeur vue dans un message garde son placeholder dans le suivant.
    `InMemoryConversationMemory` la tient dans le processus.
    `RedisConversationMemory` la persiste dans Redis, avec les valeurs chiffrées
    par un cipher et les clés hachées.

Recognizer
:   Grammaire de tokens que le middleware utilise pour retrouver les placeholders
    d'un pipeline dans une réponse LLM, sans passer par l'anonymizer. Un pipeline
    l'expose via `recognizer`, un `BaseDelimitedPlaceholderFactory` ou `None`.

Tag de préservation de placeholder
:   Type fantôme sur une placeholder factory qui énonce ce que ses tokens
    préservent : `PreservesNothing`, `PreservesLabel`, `PreservesIdentity` ou
    `PreservesLabeledIdentity`. Le middleware exige `PreservesIdentity` pour
    pouvoir restaurer les valeurs, et rejette une factory qui ne le fournit pas,
    au moment de la vérification de types.

Pepper
:   Secret qui clé un hasher, lu depuis la variable d'environnement
    `PIIGHOST_HASH_PEPPER`. Hacher une PII à faible entropie sans secret la laisse
    attaquable par force brute, donc le pepper est obligatoire. Utilisé par
    `Sha256Hasher` et `Argon2Hasher`.

Cipher
:   Composant qui chiffre et déchiffre des octets de façon réversible, de sorte
    qu'un stockage garde du chiffré au lieu du clair. Une fuite du stockage ne
    donne rien sans la clé, tenue en dehors. `RedisConversationMemory` en utilise
    un pour chiffrer les valeurs persistées. `AesGcmCipher` est le backend AES-GCM
    fourni.

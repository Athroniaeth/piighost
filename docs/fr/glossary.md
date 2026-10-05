---
icon: lucide/book-a
---

# Glossaire

Termes utilisés dans la documentation `piighost`. Chaque entrée définit le
concept par ce qu'il fait. Les noms de classes restent en anglais.

Anonymisation
:   Suppression des PII sans aucun moyen de les restaurer. Irréversible par
    définition. Une placeholder factory de caviardage anonymise, puisqu'elle ne
    garde aucune correspondance vers la valeur.

Cipher
:   Composant qui chiffre et déchiffre des octets de façon réversible, de sorte
    qu'un stockage garde du chiffré au lieu du clair. Une fuite du stockage ne
    donne rien sans la clé, tenue en dehors du stockage. `RedisConversationMemory`
    et `SqlAlchemyConversationMemory` peuvent en utiliser un pour chiffrer les
    valeurs persistées. `AesGcmCipher` est le backend AES-GCM fourni.

Conversation (thread)
:   Suite de messages identifiée par un `thread_id`. La mémoire est isolée
    par conversation, donc deux conversations parallèles ne partagent jamais leurs
    données confidentielles. Un placeholder reste stable sur tous les messages d'une même conversation.

Dé-identification
:   Remplacement des données confidentielles par des placeholders tout en
    gardant la correspondance entre chaque valeur et son placeholder, de sorte que l'original peut être
    restauré ensuite. Le pipeline `piighost` par défaut dé-identifie. Au sens du
    RGPD c'est de la pseudonymisation, pas de l'anonymisation.

Détection
:   Une occurrence d'une valeur repérée par un détecteur, c'est-à-dire un `Span`, le
    texte apparié, un label et une confiance dans l'intervalle 0 à 1. Détecter
    `Patrick`{ .pii } comme `PERSON` en `(0, 7)` avec une confiance de `0.95` est
    une `Detection`.

Détecteur
:   Composant qui trouve les données confidentielles dans un texte et retourne des détections. Les
    détecteurs implémentent le protocole `AnyDetector` et sont interchangeables.
    Les trois familles sont regex, NER et LLM, chacune sous son entrée.

Détecteur LLM
:   Détecteur qui demande à un grand modèle de langage de retourner les valeurs
    trouvées en sortie structurée. Plus lent et moins déterministe que le regex
    ou le NER, mais capable de raisonner sur le contexte. `LLMDetector`.

Détecteur NER
:   Named Entity Recognition, reconnaissance d'entités nommées. Modèle d'IA qui
    classe les mots d'un texte dans des catégories décidées à l'avance, comme
    personne, lieu ou organisation. Fonctionne sur le texte libre là où un motif
    échoue. `Gliner2Detector`, `Gliner2PiiDetector`, `SpacyDetector`,
    `TransformersDetector`, `PresidioDetector`, et `BridgeDetector`, qui attend
    un modèle exécuté ailleurs, par exemple en JavaScript dans le navigateur.

Détecteur regex
:   Détecteur qui reconnaît des motifs fixes, c'est-à-dire des chaînes de
    caractères qui suivent une structure connue comme un IBAN ou un numéro de
    téléphone. Efficace sur les formats structurés, inutilisable sur du texte
    libre comme un prénom ou une date écrite. `RegexDetector`.

Données confidentielles
:   Tout ce que `piighost` protège, c'est-à-dire les données personnelles (PII)
    et les secrets comme les clés d'API. Chaque élément détecté est une valeur,
    remplacée par un placeholder dans le texte dé-identifié.

Entité
:   Groupe de détections qui référent à la même valeur. Chaque occurrence
    de la valeur est une détection. Le groupe partage un placeholder, qui se
    restaure en une seule valeur. Différent d'une détection, qui est une occurrence unique.
    `Entity`.

Garde-fou
:   Composant qui revérifie le texte dé-identifié à la recherche de données confidentielles
    que le pipeline a manquées. Il tourne après le remplacement et lève une erreur si une
    valeur résiduelle demeure. Un garde-fou peut relancer un détecteur
    (`DetectorGuardRail`), classer la sortie avec un modèle GLiNER2 local
    (`Gliner2GuardRail`), interroger un LLM (`LLMGuardRail`) ou l'API de
    modération de Mistral (`ModerationGuardRail`).

Linker
:   Composant qui regroupe les détections en entités. Il trouve les occurrences
    qui référent à la même valeur, afin qu'elles partagent un placeholder. Lier
    `Patrick`{ .pii } en `(0, 7)` et `patrick`{ .pii } en `(34, 41)` donne une
    entité. `ExactEntityLinker`.

Mémoire de conversation
:   Stockage qui accumule les entités d'une conversation au fil des messages, de sorte
    qu'une valeur vue dans un message garde son placeholder dans le suivant.
    `InMemoryConversationMemory` la tient dans le processus.
    `RedisConversationMemory` la persiste dans Redis, et
    `SqlAlchemyConversationMemory` dans une table SQL. Ces deux backends peuvent
    chiffrer les valeurs avec un cipher et hacher les clés.

PII
:   Personally Identifiable Information, en français donnée à caractère
    personnel. C'est la partie données personnelles des données confidentielles.
    Toute valeur qui peut identifier une personne, c'est-à-dire nom,
    adresse, numéro de téléphone, email, lieu, organisation, numéro de compte.
    `piighost` trouve et remplace les PII pour qu'un LLM en aval ne voie jamais
    la valeur brute.

Placeholder
:   Jeton qui remplace une valeur dans le texte dé-identifié, par exemple
    `<<PERSON:1>>`{ .placeholder } ou `<<EMAIL:1>>`{ .placeholder }. L'apparence
    d'un placeholder est décidée par une placeholder factory.

Placeholder factory
:   Composant qui produit les placeholders. Il décide la forme du jeton et ce que
    le jeton préserve, c'est-à-dire un label, une identité stable, les deux ou
    rien. Les factories fournies sont `RedactPlaceholderFactory`,
    `LabelPlaceholderFactory`, `LabelCounterPlaceholderFactory`,
    `LabelHashPlaceholderFactory` et `MaskPlaceholderFactory`.

Poivre
:   Secret qui sert de clé à un hasher, lu depuis la variable d'environnement
    `PIIGHOST_HASH_PEPPER`. Le poivre est obligatoire, parce qu'une valeur à
    faible entropie hachée sans secret reste attaquable par force brute. Utilisé par
    `Sha256Hasher` et `Argon2Hasher`.

Recognizer
:   Grammaire de jetons que le middleware utilise pour retrouver les placeholders
    d'un pipeline dans une réponse LLM, sans passer par l'anonymiseur. Un pipeline
    l'expose dans son attribut `recognizer`, qui vaut un
    `BaseDelimitedPlaceholderFactory` ou `None`.

Résolveur d'entités
:   Composant qui réconcilie les entités en conflit, c'est-à-dire des entités qui
    partagent une détection ou dont les valeurs sont proches.
    `MergeEntityResolver` fusionne les entités qui partagent une détection,
    `FuzzyEntityResolver` fusionne les valeurs presque identiques.
    `SeparateEntityResolver` garde les entités séparées. Il donne chaque
    détection partagée à la plus grande entité qui la contient et la retire des
    autres.

Secret
:   Identifiant d'accès qui ne doit jamais atteindre un modèle, comme une clé
    d'API, un jeton d'accès, une clé privée ou une chaîne de connexion. Les
    secrets sont l'autre partie des données confidentielles. Ils sont détectés
    par les groupes du catalogue `piighost/secrets` et `piighost/secrets-extended`,
    tirés par exemple avec `catalogs = ["catalog:piighost/secrets"]`. Les
    autres groupes du catalogue, `piighost/generic` et les groupes régionaux, ne
    contiennent aucun motif de secret. `Gliner2PiiDetector` demande
    aussi à son modèle les clés d'API et les mots de passe.

Span
:   Intervalle de caractères semi-ouvert `[start, end)` dans un texte, calqué sur
    la sémantique du slice Python. Chaque détection porte un `Span` qui marque où
    se trouve la valeur. `Span`.

Tag de préservation de placeholder
:   Type fantôme (un type qui ne sert qu'au vérificateur de types) posé sur
    une placeholder factory, qui énonce ce que ses jetons préservent. Les tags
    concrets sont `PreservesNothing`, `PreservesLabel`, `PreservesShape`,
    `PreservesIdentityOnly`, `PreservesLabeledIdentityOpaque` et
    `PreservesLabeledIdentityHashed`. `PreservesIdentity`,
    `PreservesRecognizableIdentity` et `PreservesLabeledIdentity` sont des tags
    abstraits qui les regroupent. Le middleware exige `PreservesRecognizableIdentity`
    pour pouvoir restaurer les valeurs. Il rejette une factory qui ne fournit pas
    ce tag dès la vérification de types.

thread_id
:   Chaîne qui identifie une conversation. Le pipeline de conversation et le middleware s'en
    servent pour cadrer la mémoire et router chaque message vers la bonne
    conversation.

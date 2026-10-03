---
icon: lucide/scale
---

# Comment PIIGhost se compare

`piighost` réunit quatre propriétés dont un agent conversationnel a besoin : restaurer la réponse pour l'utilisateur, garder le même jeton sur toute la conversation, donner la vraie valeur aux outils, et restaurer pendant le flux. Aucun des outils ci-dessous ne les réunit toutes. Chacun fait en revanche mieux que `piighost` sur un autre terrain, et sa fiche le dit.

Ouvrez une solution pour voir ses différences avec `piighost`.

??? note "`piighost`, ses choix et ses limites"

    - Détecte avec des regex, des modèles NER (GLiNER2, spaCy, Transformers, Presidio) ou un LLM, seuls ou combinés.
    - Remplace chaque valeur par un jeton réversible, le même sur toute la conversation, gardé en mémoire ou dans Redis.
    - Restaure la réponse pour l'utilisateur, y compris pendant le flux, et donne la vraie valeur aux outils de l'agent.
    - Choix : aucune validation par checksum (Luhn, clé IBAN). Une valeur abîmée par l'OCR reste détectée, au prix de faux positifs.
    - Choix : la dé-identification est réversible. Au sens du RGPD c'est une pseudonymisation, et la table de correspondance est une donnée personnelle à protéger.
    - Ne fait pas : garantir qu'aucune valeur n'échappe. Un détecteur rate des valeurs, et un garde-fou ne fait que les signaler.
    - Ne fait pas : restaurer une valeur que le LLM invente, ni partager la mémoire entre processus sans Redis.
    - Ne fait pas : transformer un jeu de données entier. La latence ajoutée n'est pas encore mesurée.

??? note "Presidio (Microsoft, MIT)"

    - Détecte avec un NER, des regex, des règles et des clés de contrôle.
    - Masque, ou remplace par un jeton chiffré.
    - Restaure seulement à la main, avec `decrypt`.
    - Ne garde pas le même jeton d'un message à l'autre.
    - Rien de prévu pour les outils ni pour le flux.
    - Fait mieux : valider un format par clé de contrôle, sur un texte saisi au clavier.
    - `piighost` peut l'utiliser comme détecteur, avec `PresidioDetector`.

??? note "LangChain PII (`PIIMiddleware`, MIT)"

    - Détecte avec des regex et des validateurs.
    - Masque ou hache, sans restauration pour l'utilisateur.
    - Protège la frontière des outils et le flux.
    - Ne garde pas de jeton sur la conversation.
    - La version JS (`piiRedactionMiddleware`) fait le compromis inverse : elle restaure, mais sans flux.
    - Fait mieux : rien de plus à installer dans un agent LangChain, si l'utilisateur n'a pas besoin de relire ses vraies valeurs.

??? note "AWS Comprehend et Azure AI Language (cloud, payants)"

    - Détectent par apprentissage automatique et masquent.
    - Aucune restauration. Le mode Conversation d'Azure ne fait que détecter.
    - Rien de prévu pour la conversation, les outils ni le flux.
    - Le texte part chez le fournisseur cloud.
    - Font mieux : des modèles maintenus par le fournisseur, pour masquer des documents dans un cloud déjà en place.

??? note "Google DLP (cloud, payant)"

    - Détecte par apprentissage automatique et par types prédéfinis (infoTypes).
    - Remplace par un jeton chiffré sans état, toujours le même pour une même valeur.
    - Restaure par un appel d'API.
    - Rien de prévu pour les outils ni pour le flux.
    - Le texte part chez Google.
    - Fait mieux : transformer des jeux de données entiers dans Google Cloud.

??? note "pii-redactor (MIT)"

    - Le plus proche de `piighost`.
    - Détecte avec des regex et un NER.
    - Remplace par un jeton réversible gardé dans un coffre, le même sur la session, et restaure pendant le flux.
    - Ne donne pas la vraie valeur aux outils.
    - Pas d'étape configurable après la détection (liaison, rapprochement approximatif, expansion, garde-fou).

??? note "Modèles de détection seule (spaCy, GLiNER, Piiranha)"

    - Repèrent les données sans les remplacer ni les restaurer.
    - Ce ne sont pas des concurrents mais des briques : `piighost` les utilise comme détecteurs, Piiranha via `TransformersDetector`.

??? note "Anonymiseurs de jeux de données (ARX, Amnesia)"

    - Transforment un tableau entier par k-anonymity ou differential privacy.
    - Le résultat est anonyme et irréversible, là où `piighost` est réversible.
    - Font mieux : publier ou partager un jeu de données. Pas faits pour une conversation en direct.

Voir [Limites](limitations.md) pour le détail de ce que `piighost` ne fait pas, et les partis pris derrière ces choix.

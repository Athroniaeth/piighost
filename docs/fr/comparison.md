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

??? note "Presidio (Microsoft)"

    | | `piighost` | Presidio |
    |---|---|---|
    | Détection | regex, NER ou LLM | NER, regex, règles, clés de contrôle |
    | Traitement des valeurs | jeton réversible (mémoire ou Redis) | masque ou jeton chiffré |
    | Restauration pour l'utilisateur | ✅ | ⚠️ à la main (`decrypt`) |
    | Même jeton sur la conversation | ✅ par conversation | ❌ |
    | Vraie valeur aux outils, jeton au LLM | ✅ | ❌ |
    | Restauration pendant le flux | ✅ | ❌ |
    | Étapes configurables après détection | ✅ liaison, rapprochement, expansion, garde-fou | ⚠️ opérateurs seulement |
    | Unité traitée | texte, conversation | texte |
    | Hébergement | ✅ auto-hébergé | ✅ auto-hébergé |
    | Licence | MIT | MIT |

    **Fait mieux** : valider un format par clé de contrôle, sur un texte saisi au clavier. `piighost` peut d'ailleurs l'utiliser comme détecteur, avec `PresidioDetector`.

??? note "LangChain PII (`PIIMiddleware` Python)"

    | | `piighost` | LangChain PII |
    |---|---|---|
    | Détection | regex, NER ou LLM | regex, validateurs |
    | Traitement des valeurs | jeton réversible (mémoire ou Redis) | masque ou hash |
    | Restauration pour l'utilisateur | ✅ | ❌ |
    | Même jeton sur la conversation | ✅ par conversation | ❌ |
    | Vraie valeur aux outils, jeton au LLM | ✅ | ✅ |
    | Restauration pendant le flux | ✅ | ✅ |
    | Étapes configurables après détection | ✅ liaison, rapprochement, expansion, garde-fou | ❌ |
    | Unité traitée | texte, conversation | texte, conversation |
    | Hébergement | ✅ auto-hébergé | ✅ auto-hébergé |
    | Licence | MIT | MIT |

    **Fait mieux** : il n'y a rien de plus à installer dans un agent LangChain. Cela suffit si l'utilisateur n'a pas besoin de relire ses vraies valeurs. La version JS (`piiRedactionMiddleware`) restaure les vraies valeurs pour l'utilisateur, mais pas pendant le flux.

??? note "AWS Comprehend et Azure AI Language"

    | | `piighost` | AWS / Azure |
    |---|---|---|
    | Détection | regex, NER ou LLM | apprentissage automatique |
    | Traitement des valeurs | jeton réversible (mémoire ou Redis) | masque |
    | Restauration pour l'utilisateur | ✅ | ❌ |
    | Même jeton sur la conversation | ✅ par conversation | ❌ |
    | Vraie valeur aux outils, jeton au LLM | ✅ | ❌ |
    | Restauration pendant le flux | ✅ | ❌ |
    | Étapes configurables après détection | ✅ liaison, rapprochement, expansion, garde-fou | ❌ |
    | Unité traitée | texte, conversation | texte, documents |
    | Hébergement | ✅ auto-hébergé | ❌ cloud |
    | Licence | MIT | payant |

    **Fait mieux** : des modèles maintenus par le fournisseur, pour masquer des documents dans un cloud déjà en place. Le mode Conversation d'Azure ne fait que détecter.

??? note "Google DLP"

    | | `piighost` | Google DLP |
    |---|---|---|
    | Détection | regex, NER ou LLM | apprentissage automatique, types prédéfinis (infoTypes) |
    | Traitement des valeurs | jeton réversible (mémoire ou Redis) | jeton chiffré sans état |
    | Restauration pour l'utilisateur | ✅ | ⚠️ par appel d'API |
    | Même jeton sur la conversation | ✅ par conversation | ✅ toujours le même jeton pour une valeur |
    | Vraie valeur aux outils, jeton au LLM | ✅ | ❌ |
    | Restauration pendant le flux | ✅ | ❌ |
    | Étapes configurables après détection | ✅ liaison, rapprochement, expansion, garde-fou | ⚠️ transformations |
    | Unité traitée | texte, conversation | texte, jeu de données |
    | Hébergement | ✅ auto-hébergé | ❌ cloud |
    | Licence | MIT | payant |

    **Fait mieux** : transformer des jeux de données entiers dans Google Cloud.

??? note "pii-redactor"

    | | `piighost` | pii-redactor |
    |---|---|---|
    | Détection | regex, NER ou LLM | regex, NER |
    | Traitement des valeurs | jeton réversible (mémoire ou Redis) | jeton réversible (coffre) |
    | Restauration pour l'utilisateur | ✅ | ✅ |
    | Même jeton sur la conversation | ✅ par conversation | ✅ par session |
    | Vraie valeur aux outils, jeton au LLM | ✅ | ❌ |
    | Restauration pendant le flux | ✅ | ✅ |
    | Étapes configurables après détection | ✅ liaison, rapprochement, expansion, garde-fou | ❌ |
    | Unité traitée | texte, conversation | texte, conversation |
    | Hébergement | ✅ auto-hébergé | ✅ auto-hébergé |
    | Licence | MIT | MIT |

    **À noter** : c'est le plus proche de `piighost`. Il lui manque la vraie valeur aux outils et les étapes configurables.

??? note "Modèles de détection seule (spaCy, GLiNER, Piiranha)"

    - Repèrent les données sans les remplacer ni les restaurer.
    - Ce ne sont pas des concurrents mais des briques : `piighost` les utilise comme détecteurs, Piiranha via `TransformersDetector`.

??? note "Anonymiseurs de jeux de données (ARX, Amnesia)"

    - Transforment un tableau entier par k-anonymity ou differential privacy.
    - Le résultat est anonyme et irréversible, là où `piighost` est réversible.
    - Font mieux : publier ou partager un jeu de données. Pas faits pour une conversation en direct.

Voir [Limites](limitations.md) pour le détail de ce que `piighost` ne fait pas, et les partis pris derrière ces choix.

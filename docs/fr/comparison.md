---
icon: lucide/scale
---

# Comment piighost se compare

`piighost` réunit quatre propriétés dont un agent conversationnel a besoin. Il restaure la réponse pour l'utilisateur, garde le même jeton sur toute la conversation, donne la vraie valeur aux outils, et restaure pendant le flux. Aucun des outils ci-dessous ne les réunit toutes. Chacun fait en revanche mieux que `piighost` sur un autre terrain, et sa fiche le dit.

Ouvrez une solution pour voir ses différences avec `piighost`.

??? note "Presidio (Microsoft)"

    | | `piighost` | Presidio |
    |---|---|---|
    | Détection | regex, NER ou LLM | NER, regex, règles, clés de contrôle |
    | Traitement des valeurs | jeton réversible (mémoire, Redis ou SQL) | masque ou jeton chiffré |
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
    | Traitement des valeurs | jeton réversible (mémoire, Redis ou SQL) | masque ou hash |
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
    | Traitement des valeurs | jeton réversible (mémoire, Redis ou SQL) | masque |
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
    | Traitement des valeurs | jeton réversible (mémoire, Redis ou SQL) | jeton chiffré sans état |
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
    | Traitement des valeurs | jeton réversible (mémoire, Redis ou SQL) | jeton réversible (coffre) |
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
    - Ce ne sont pas des concurrents mais des briques. `piighost` les utilise comme détecteurs, Piiranha via `TransformersDetector`.

??? note "Anonymiseurs de jeux de données (ARX, Amnesia)"

    - Transforment un tableau entier par k-anonymity ou differential privacy.
    - Le résultat est anonyme et irréversible, là où `piighost` est réversible.
    - Font mieux : publier ou partager un jeu de données. Pas faits pour une conversation en direct.

Voir [Limites](limitations.md) pour le détail de ce que `piighost` ne fait pas, et les partis pris derrière ces choix.

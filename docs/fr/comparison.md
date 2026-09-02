---
icon: lucide/scale
---

# Comment PIIGhost se compare

Ce tableau n'est pas neutre. Ses lignes sont les capacités pour lesquelles PIIGhost a été conçu, donc il en ressort forcément bien. Il sert à montrer ce que les outils moyens ne couvrent pas, pas à désigner un gagnant. Pour un travail que PIIGhost ne vise pas, comme publier un jeu de données entier, un outil de k-anonymity est le bon choix.

| Capacité | **PIIGhost** | Presidio | LangChain PII | Cloud (AWS/Azure) | Google DLP | pii-redactor |
|---|---|---|---|---|---|---|
| **Détection** | regex / NER / LLM | NER + regex + règles + checksum | regex + validateurs | ML/NER | ML + infoTypes | regex + NER |
| **Traitement de la PII** | jeton réversible (mémoire / Redis) | masque / jeton | masque / hash | masque | jeton crypto (sans état) | jeton réversible (vault) |
| **Restauration transparente pour l'utilisateur** | ✅ | ⚠️ manuel (`decrypt`) | ❌ | ❌ | ⚠️ ré-id par API | ✅ |
| **Cohérent sur toute la conversation** | ✅ par thread | ❌ | ❌ | ❌ | ✅ déterministe | ✅ par session |
| **Frontière outils** (l'outil reçoit la vraie valeur, le LLM le jeton) | ✅ | ❌ | ✅ | ❌ | ❌ | ❌ |
| **Streaming** (restauration token par token) | ✅ | ❌ | ✅ | ❌ | ❌ | ✅ |
| **Étapes configurables après détection** (liaison, fuzzy, expansion, guard) | ✅ | ⚠️ opérateurs seulement | ❌ | ❌ | ⚠️ transformations | ❌ |
| **Unité traitée** | texte / conversation | texte | texte / conversation | texte / documents | texte / dataset | texte / conversation |
| **Auto-hébergé (OSS)** | ✅ | ✅ | ✅ | ❌ cloud | ❌ cloud | ✅ |
| **Licence** | MIT | MIT | MIT | Commercial | Commercial | MIT |

Notes : ici, **LangChain PII** désigne le `PIIMiddleware` Python. Le `piiRedactionMiddleware` JS fait le compromis inverse, réversible mais sans streaming. **Cloud** regroupe AWS Comprehend et Azure AI Language, et le mode Conversation d'Azure ne fait que détecter, il ne restaure pas.

Les modèles de détection seule (spaCy, GLiNER, Piiranha) et les anonymiseurs de dataset (ARX, Amnesia) sont d'une autre catégorie. Les premiers ne font que repérer les PII, les seconds transforment un jeu de données tabulaire entier avec de la k-anonymity ou de la differential privacy, donc ils ne dé-identifient pas une conversation en direct.

Voir [Limites](limitations.md) pour ce que PIIGhost ne fait pas et les partis pris derrière ces choix.

---
icon: lucide/scale
description: Comparez piighost à Presidio, au middleware PII de LangChain, à LLM Guard et aux DLP cloud, et trouvez l'alternative à Presidio qui restaure les PII.
seo_title: piighost, Presidio, LangChain PII et LLM Guard comparés
---

# Comment piighost se compare

`piighost` réunit quatre propriétés dont un agent conversationnel a besoin. Il restaure la réponse pour l'utilisateur, garde le même jeton sur toute la conversation, donne la vraie valeur aux outils, et restaure pendant le flux. Aucun des outils ci-dessous ne documente les quatre ensemble. Chacun fait en revanche mieux que `piighost` sur un autre terrain, et sa section le dit.

## Synthèse

Vérifié le 6 octobre 2026.

<div class="wide-table" markdown="1">

| Outil | Restaure les valeurs dans la réponse | Restaure les arguments des appels d'outils | Même jeton sur toute la conversation | Flux (streaming) | Intégrations | Licence | Statut |
|---|---|---|---|---|---|---|---|
| `piighost` | ✅ | ✅ | ✅ par conversation | ✅ restaure pendant le flux | LangChain, Pydantic AI, LlamaIndex, Claude Code, proxy OpenAI et Anthropic (`piighost-api`) | MIT | actif |
| [Presidio](#piighost-et-presidio) | ⚠️ à la main (`decrypt`) | ❌ | ❌ | ❌ | aucune, une librairie et un service REST | MIT | actif, sous Data Privacy Stack |
| [`PresidioReversibleAnonymizer`](#piighost-et-presidioreversibleanonymizer) | ✅ | ❌ | ⚠️ une correspondance par objet | ❌ | chaînes LangChain | MIT | archivé le 22 mai 2026 |
| [LangChain `PIIMiddleware` (Python)](#piighost-et-le-middleware-pii-de-langchain) | ❌ | ❌ | ⚠️ avec la stratégie `hash` | ❌ masque le flux | agents LangChain | MIT | actif |
| [LangChain `piiRedactionMiddleware` (JS)](#piighost-et-le-middleware-pii-de-langchain) | ✅ après l'appel au modèle | ✅ | ❌ un nouveau marqueur par occurrence | ❌ | agents LangChain.js | MIT | déprécié |
| [LLM Guard](#piighost-et-llm-guard) | ✅ | non documenté | ⚠️ tant que le même coffre est réutilisé | non documenté | librairie, serveur d'API | MIT | archivé le 8 juillet 2026 |
| [AWS Comprehend, Azure AI Language](#piighost-aws-comprehend-et-azure-ai-language) | ❌ | ❌ | ❌ | ❌ | API cloud | payant | actif |
| [Google DLP](#piighost-et-google-dlp) | ⚠️ par appel d'API | ❌ | ✅ toujours le même jeton pour une valeur | ❌ | API cloud | payant | actif |
| [PrivAiTe](#piighost-et-privaite) | ✅ | ✅ | ⚠️ par requête | ✅ | proxy compatible OpenAI, passerelle Claude Code et Codex, Open WebUI, LiteLLM | BSD-3-Clause | actif |
| [`pseudo_api` d'Etalab](#piighost-et-pseudo_api-detalab) | ❌ | ❌ | sans objet, un document à la fois | ❌ | API REST | MIT | archivé |

</div>

Les modèles de détection seule et les anonymiseurs de jeux de données ne sont pas dans le tableau, parce qu'ils ne remplacent ni ne restaurent de valeurs dans une conversation. Leurs sections sont en fin de page.

## `piighost` et Presidio

[Presidio](https://github.com/data-privacy-stack/presidio) détecte les données personnelles et les remplace avec des opérateurs. Le projet a quitté Microsoft en 2026. C'est désormais un projet communautaire de l'organisation [Data Privacy Stack](https://github.com/data-privacy-stack/presidio/blob/main/docs/project_transition.md), toujours sous licence MIT. Son [anonymiseur](https://presidio.dataprivacystack.org/anonymizer/) ne sait rétablir qu'une valeur chiffrée, avec l'opérateur `decrypt`.

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

## `piighost` et PresidioReversibleAnonymizer

`PresidioReversibleAnonymizer` enveloppe Presidio dans un objet LangChain doté des méthodes `anonymize()` et `deanonymize()`. Il faisait partie du paquet `langchain-experimental`, que LangChain a [abandonné](https://github.com/langchain-ai/langchain-experimental/issues/87) le 22 mai 2026. Le [dépôt](https://github.com/langchain-ai/langchain-experimental) est archivé, la classe ne recevra donc plus de correctif.

- Par défaut, il remplace chaque valeur par une fausse valeur tirée de Faker, puis la restaure depuis une correspondance gardée dans l'objet.
- Un objet garde une seule correspondance pour tous les textes qu'il voit, donc deux conversations la partagent tant que vous ne la videz pas.
- Il ne restaure ni les arguments des appels d'outils ni une réponse en flux.

**Fait mieux** : il s'ajoutait en une ligne à une chaîne LangChain qui utilisait déjà Presidio. Pour passer cette chaîne à `piighost`, voir [Migrer depuis PresidioReversibleAnonymizer](examples/migrate-from-presidio-reversible-anonymizer.md).

## `piighost` et le middleware PII de LangChain

Le [`PIIMiddleware`](https://docs.langchain.com/oss/python/langchain/middleware/built-in#pii-detection) Python bloque, caviarde, masque ou hache une valeur dans les messages d'un agent. Son [code source](https://github.com/langchain-ai/langchain/blob/master/libs/langchain_v1/langchain/agents/middleware/pii.py) masque aussi la sortie en flux. Il ne restaure jamais une valeur, donc un outil reçoit ce que le modèle a écrit.

| | `piighost` | LangChain PII |
|---|---|---|
| Détection | regex, NER ou LLM | regex, validateurs |
| Traitement des valeurs | jeton réversible (mémoire, Redis ou SQL) | masque ou hash |
| Restauration pour l'utilisateur | ✅ | ❌ |
| Même jeton sur la conversation | ✅ par conversation | ⚠️ avec la stratégie `hash` |
| Vraie valeur aux outils, jeton au LLM | ✅ | ❌ |
| Restauration pendant le flux | ✅ | ❌ masque le flux |
| Étapes configurables après détection | ✅ liaison, rapprochement, expansion, garde-fou | ❌ |
| Unité traitée | texte, conversation | texte, conversation |
| Hébergement | ✅ auto-hébergé | ✅ auto-hébergé |
| Licence | MIT | MIT |

Le [`piiRedactionMiddleware`](https://reference.langchain.com/javascript/langchain/index/piiRedactionMiddleware) JavaScript restaurait les valeurs après l'appel au modèle, dans la réponse et dans les [arguments des appels d'outils](https://github.com/langchain-ai/langchainjs/blob/main/libs/langchain/src/agents/middleware/piiRedaction.ts). Il donne à chaque occurrence un nouveau marqueur aléatoire, et il ne restaure qu'une fois l'appel au modèle terminé. Il est désormais marqué comme déprécié, et LangChain a [migré sa documentation](https://github.com/langchain-ai/docs/pull/6366) vers `piiMiddleware`, qui bloque, caviarde, masque ou hache sans restaurer.

**Fait mieux** : il n'y a rien de plus à installer dans un agent LangChain. Cela suffit si l'utilisateur n'a pas besoin de relire ses vraies valeurs.

## `piighost` et LLM Guard

[LLM Guard](https://github.com/protectai/llm-guard) a été archivé le 8 juillet 2026 et n'est plus maintenu. `piighost` ne couvre que ses scanners [Anonymize](https://protectai.github.io/llm-guard/input_scanners/anonymize/) et [Deanonymize](https://protectai.github.io/llm-guard/output_scanners/deanonymize/), qui remplacent les valeurs puis les restaurent depuis un [coffre](https://github.com/protectai/llm-guard/blob/main/llm_guard/input_scanners/anonymize.py). `piighost` n'a pas d'équivalent des autres scanners, comme l'injection de prompt, la toxicité ou les sujets interdits.

## `piighost`, AWS Comprehend et Azure AI Language

[AWS Comprehend](https://docs.aws.amazon.com/comprehend/latest/dg/how-pii.html) et [Azure AI Language](https://learn.microsoft.com/en-us/azure/ai-services/language-service/personally-identifiable-information/overview) détectent les données personnelles et renvoient un texte masqué depuis une API cloud.

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

**Fait mieux** : des modèles maintenus par le fournisseur, pour masquer des documents dans un cloud déjà en place.

## `piighost` et Google DLP

Sensitive Data Protection de Google, anciennement Cloud DLP, sait [pseudonymiser](https://cloud.google.com/sensitive-data-protection/docs/pseudonymization) une valeur avec une clé, puis la ré-identifier par un second appel d'API.

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

## `piighost` et PrivAiTe

[PrivAiTe](https://github.com/crp4222/PrivAiTe) est un proxy auto-hébergé, placé entre une application et le fournisseur du modèle. Il remplace les valeurs dans les messages et dans les arguments des appels d'outils, puis les restaure dans la réponse, flux compris.

- Il garde la correspondance le temps d'une requête et l'efface à la fin de celle-ci. Un client de chat renvoie tout l'historique, donc la numérotation reste cohérente dans chaque requête.
- Il se branche comme proxy compatible OpenAI, comme passerelle pour Claude Code et Codex, comme filtre Open WebUI ou comme garde-fou LiteLLM.
- C'est un proxy, il ne s'exécute donc pas dans un framework d'agents comme le fait un middleware.

**Fait mieux** : couvrir un agent en ligne de commande ou une application compatible OpenAI sans toucher à son code, avec un banc de mesure des fuites publié.

## `piighost` et `pseudo_api` d'Etalab

[`pseudo_api`](https://github.com/etalab-ia/pseudo_api) est l'API de pseudonymisation du Lab IA d'Etalab, au sein de la direction interministérielle du numérique (DINUM). Elle remplace les prénoms, les noms et les adresses dans les décisions du Conseil d'État, pour pouvoir les publier. Elle n'a aucun point d'accès qui restaure une valeur, et le dépôt est archivé.

**À noter** : elle montre l'approche de l'administration française, qui pseudonymise un document une fois pour toutes avant de le publier. Le dépôt ne fournit pas le modèle entraîné, parce que les données d'entraînement ne sont pas publiques.

## Modèles de détection seule

spaCy, GLiNER, Piiranha et [OpenAI Privacy Filter](https://github.com/openai/privacy-filter), publié le 22 avril 2026 sous licence Apache-2.0, repèrent les données. Au mieux ils les masquent, et ils ne les restaurent jamais.

- Ce ne sont pas des concurrents mais des briques. `piighost` utilise spaCy, GLiNER et Piiranha comme détecteurs, Piiranha via `TransformersDetector`.

## Anonymiseurs de jeux de données

ARX et Amnesia transforment un tableau entier par k-anonymity ou differential privacy.

- Le résultat est anonyme et irréversible, là où `piighost` est réversible.
- Font mieux : publier ou partager un jeu de données. Pas faits pour une conversation en direct.

Voir [Limites](limitations.md) pour le détail de ce que `piighost` ne fait pas, et les partis pris derrière ces choix. Pour le vocabulaire de cette page, voir [Anonymisation, pseudonymisation, caviardage, masquage](anonymization-vs-pseudonymization.md).

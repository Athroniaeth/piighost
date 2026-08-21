---
icon: lucide/list-checks
---

# Roadmap

Cette page liste ce qui reste en attente pour `piighost` et les capacités écartées volontairement. Tout ce que la réécriture v2 a livré est documenté dans le reste du site. Détecteurs enfichables, linking et résolution d'entités, placeholder factories, guard de PII résiduelle, mémoire de conversation Redis à valeurs chiffrées, configuration TOML et JSON, middleware LangChain, et observation OpenTelemetry.

!!! note "Comment lire cette page"
    Cette roadmap n'est pas un engagement de calendrier. Elle liste les items identifiés comme encore manquants, pas une promesse de les construire dans l'ordre.

## Proxy compatible OpenAI

`piighost` dé-identifie aujourd'hui à l'intérieur d'un framework d'agent, via le middleware LangChain ou les hooks Pydantic AI. Un proxy déplacerait cette protection à la frontière HTTP. `piighost-api` exposerait un endpoint compatible OpenAI, une application ne change donc que son `base_url` et n'a besoin d'aucun autre code. À chaque appel `/v1/chat/completions`, le proxy anonymise les messages, relaie la requête anonymisée au vrai fournisseur, désanonymise la réponse, et la renvoie au format OpenAI, le fournisseur ne reçoit donc jamais `Patrick`{ .pii }, seulement `<<PERSON:1>>`{ .placeholder }. Le même proxy se place devant n'importe quel endpoint compatible OpenAI, comme Azure OpenAI ou un serveur auto-hébergé.

Trois briques existent déjà pour ça. Le pipeline conversationnel anonymise et restaure, la dé-identification de la frontière des outils couvre les appels d'outils, et le décodeur de streaming réécrit un jeton coupé entre deux chunks server-sent-event. Les questions ouvertes sont la façon dont une requête sans état cadre ses jetons, via un thread par requête ou un header d'identifiant de thread adossé à la mémoire de conversation, et la part du streaming et des appels d'outils qu'une première version couvre.

## Intégration LlamaIndex

`piighost` s'intègre aujourd'hui à LangChain et Pydantic AI. LlamaIndex expose la dé-identification de PII comme un node postprocessor dans un pipeline RAG, donc une intégration piighost enroberait le pipeline conversationnel dans un `NodePostprocessor` qui anonymise les nodes retrouvés avant que le modèle ne les lise et restaure la réponse pour l'utilisateur. Elle suit la forme que `examples/langchain/rag.py` montre déjà à la main. Chaque chunk est anonymisé dans un thread corpus unique pour qu'une valeur garde son token, la retrieval tourne sur le texte anonymisé, et la réponse est désanonymisée. Un postprocessor natif emballe tout ça en une ligne de câblage sur un index existant.

## Normalisation de texte

Un détecteur voit le texte exactement tel qu'il est écrit. Accents, casse, espacement ou bruit d'OCR peuvent cacher une valeur à une regex ou décaler les frontières d'un modèle NER. Un étage de normalisation tournerait avant la détection, en donnant au détecteur une forme nettoyée tout en gardant une carte d'offsets vers le texte d'origine, pour qu'un span trouvé sur le texte normalisé soit remonté sur le texte brut au moment du remplacement. La remontée d'offset est le point délicat, car une normalisation qui insère ou supprime des caractères ne s'aligne plus un pour un avec la source.

## Cache de résultat optionnel

La mémoire de conversation cache les détections de chaque message par thread, donc renvoyer un message dans un thread évite la détection. Il n'existe pas de cache sous le thread, donc le même texte envoyé sous deux `thread_id` différents est détecté deux fois. Un cache de résultat optionnel clé par hash de texte laisserait un contenu identique éviter la détection quel que soit le thread, avec un backend SQLAlchemy (aiosqlite pour le développement, PostgreSQL pour un déploiement partagé) comme option persistante à côté de celle en processus.

## Hors périmètre

Certaines capacités ont été envisagées puis écartées volontairement. Le raisonnement est consigné ici pour que la frontière soit explicite. Un besoin futur qui répond au caveat pourrait réexaminer chacune d'elles.

- **Placeholders surrogates réalistes (Faker).** Un faux plausible se lit naturellement, mais un vivier de faux fini finit par collisionner. Deux personnes peuvent tirer le même surrogate, et un faux peut coïncider avec une vraie valeur, donc la substitution n'est pas restaurable de façon fiable. piighost garde plutôt des jetons synthétiques sans collision.
- **Chiffrer la valeur dans le jeton.** La restauration lit la map jeton-vers-valeur depuis la mémoire de conversation, pas un chiffré autoportant. Embarquer le chiffré donne un jeton long que le modèle doit recracher mot pour mot, ce qu'il fait de façon peu fiable.
- **Hachage déterministe de la valeur.** Un hash à clé d'une valeur à faible entropie comme un prénom ou un e-mail est réversible par dictionnaire et révèle l'égalité des valeurs entre enregistrements. Le jeton d'une valeur est déjà stable au sein d'un thread, et les jointures cross-corpus ne sont pas le cas d'usage visé.
- **Bloquer des requêtes ou supprimer des PII.** piighost sécurise les PII en les détectant et en les anonymisant. Refuser une requête ou effacer une valeur relève de la politique de l'appelant, décidée à partir des détections que piighost expose, pas imposée ici.
- **Schémas qui transforment la valeur, décalage de dates et chiffrement format-preserving.** piighost substitue un span détecté par un jeton restaurable, pas une valeur transformée. Le décalage de dates sort de ce modèle, et les schémas FPE courants FF3 et FF3-1 ont été retirés du standard NIST.

La regex par forme seule, sans validation de checksum, est un autre hors-périmètre assumé. Voir [Limitations](limitations.md).

## Voir aussi

- [Placeholder factories](placeholder-factories.md) : les axes de tags et les factories actuels.
- [Sécurité](security.md) : le modèle de menace et la comparaison des backends de mémoire.
- [Déployer un pipeline en production](deployment.md) : la mémoire Redis en production.

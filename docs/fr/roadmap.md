---
icon: lucide/list-checks
---

# Roadmap

Cette page liste ce qui reste en attente pour `piighost`. Tout ce que la réécriture v2 a livré est documenté dans le reste du site. Détecteurs enfichables, linking et résolution d'entités, placeholder factories, guard de PII résiduelle, mémoire de conversation Redis à valeurs chiffrées, configuration TOML et JSON, middleware LangChain, et observation OpenTelemetry.

!!! note "Comment lire cette page"
    Cette roadmap n'est pas un engagement de calendrier. Elle liste les items identifiés comme encore manquants, pas une promesse de les construire dans l'ordre.

## Proxy compatible OpenAI

`piighost` dé-identifie aujourd'hui à l'intérieur d'un framework d'agent, via le middleware LangChain ou les hooks Pydantic AI. Un proxy déplacerait cette protection à la frontière HTTP. `piighost-api` exposerait un endpoint compatible OpenAI, une application ne change donc que son `base_url` et n'a besoin d'aucun autre code. À chaque appel `/v1/chat/completions`, le proxy anonymise les messages, relaie la requête anonymisée au vrai fournisseur, désanonymise la réponse, et la renvoie au format OpenAI, le fournisseur ne reçoit donc jamais `Patrick`{ .pii }, seulement `<<PERSON:1>>`{ .placeholder }. Le même proxy se place devant n'importe quel endpoint compatible OpenAI, comme Azure OpenAI ou un serveur auto-hébergé.

Trois briques existent déjà pour ça. Le pipeline conversationnel anonymise et restaure, la dé-identification de la frontière des outils couvre les appels d'outils, et le décodeur de streaming réécrit un jeton coupé entre deux chunks server-sent-event. Les questions ouvertes sont la façon dont une requête sans état cadre ses jetons, via un thread par requête ou un header d'identifiant de thread adossé à la mémoire de conversation, et la part du streaming et des appels d'outils qu'une première version couvre.

## Placeholder factory Faker

La hiérarchie de tags de placeholder porte un axe de réalisme, mais aucune factory ne produit encore de valeur réaliste. Une factory Faker émettrait des valeurs qui ressemblent à du vrai, par exemple un nom plausible à la place de `Patrick`{ .pii }, plutôt qu'un token synthétique comme `<<PERSON:1>>`{ .placeholder }. Elle se range sous la branche qui préserve le label, pas sous celle qui préserve l'identité. Un pool Faker est fini, donc deux personnes distinctes peuvent tirer le même faux nom et une fausse valeur peut se confondre avec une vraie. C'est pourquoi la factory ne porte aucune garantie de restauration et se place à côté de la factory de masquage plutôt qu'à côté des factories à compteur et à hash. Voir [Placeholder factories](placeholder-factories.md) pour les axes de tags actuels.

## Normalisation de texte

Un détecteur voit le texte exactement tel qu'il est écrit. Accents, casse, espacement ou bruit d'OCR peuvent cacher une valeur à une regex ou décaler les frontières d'un modèle NER. Un étage de normalisation tournerait avant la détection, en donnant au détecteur une forme nettoyée tout en gardant une carte d'offsets vers le texte d'origine, pour qu'un span trouvé sur le texte normalisé soit remonté sur le texte brut au moment du remplacement. La remontée d'offset est le point délicat, car une normalisation qui insère ou supprime des caractères ne s'aligne plus un pour un avec la source.

## Cache de résultat optionnel

La mémoire de conversation cache les détections de chaque message par thread, donc renvoyer un message dans un thread évite la détection. Il n'existe pas de cache sous le thread, donc le même texte envoyé sous deux `thread_id` différents est détecté deux fois. Un cache de résultat optionnel clé par hash de texte laisserait un contenu identique éviter la détection quel que soit le thread, avec un backend SQLAlchemy (aiosqlite pour le développement, PostgreSQL pour un déploiement partagé) comme option persistante à côté de celle en processus.

## Voir aussi

- [Placeholder factories](placeholder-factories.md) : les axes de tags et les factories actuels.
- [Sécurité](security.md) : le modèle de menace et la comparaison des backends de mémoire.
- [Déployer un pipeline en production](deployment.md) : la mémoire Redis en production.

---
type: guide
title: Par où commencer
description: Point d'entrée de la documentation métier de piighost, qui oriente selon le besoin (comprendre une règle de protection ou modifier le code), résume le trajet d'un message et liste les pièges qui traversent plusieurs processus.
tags: [quickstart, overview, routing, pii, de-identification]
sources:
  - id: openwiki-source-05ccef8d4cf1698187f20464
    resource: repo://pyproject.toml
  - id: openwiki-source-edd617907d8703b014c2a6c7
    resource: repo://src/piighost/cli/__init__.py
  - id: openwiki-source-9703fc61b3e278e6ef8403ff
    resource: repo://src/piighost/integrations/claude_code/hooks.py
  - id: openwiki-source-85881a85af445f438a8d7d5f
    resource: repo://src/piighost/integrations/langchain/middleware.py
  - id: openwiki-source-07566b3f03a831d37fa4fbce
    resource: repo://src/piighost/pipeline/thread.py
generated: { by: "claude-code", at: "2026-10-02T18:00:00.000Z" }
---

# Par où commencer

## En bref

`piighost` masque les données confidentielles d'un texte avant qu'un modèle d'IA le lise, puis remet les vraies valeurs dans la réponse. C'est une bibliothèque Python, sans interface graphique. Elle se branche sur LangChain, Pydantic AI, LlamaIndex ou Claude Code, ou s'utilise à distance par le serveur `piighost-api`. Elle se configure par un fichier TOML ou JSON et par la commande `piighost`. Les raisons de dé-identifier, juridiques et techniques, sont expliquées dans [Pourquoi dé-identifier ?](../../docs/fr/why-anonymize.md).

**Le trajet d'un message :**

1. L'utilisateur écrit son message avec ses vraies données, par exemple son nom et son e-mail.
2. `piighost` repère les valeurs sensibles, par exemple les noms, les e-mails, les téléphones ou les secrets.
3. Il les remplace par des jetons. Un jeton est un texte de remplacement, comme `<<PERSON:1>>`, qui reste le même dans toute la conversation.
4. Le modèle répond avec ces jetons.
5. `piighost` remet les vraies valeurs dans la réponse affichée.

**Ce qu'est cette documentation métier.** Elle décrit ce que `piighost` doit faire. La façon de l'utiliser est dans la documentation technique. On y définit :

- les besoins de chaque profil, c'est-à-dire le responsable conformité, le développeur, l'exploitant et l'utilisateur de l'application.
- les règles que suit chaque traitement, chacune avec son identifiant, comme `BR-MSG-05`.
- les tests d'acceptation qui vérifient chaque besoin.
- l'endroit du code où chaque règle s'applique.

**Son objectif.** Dé-identifier une conversation avec un LLM est une pratique encore nouvelle, et ses règles ne sont écrites nulle part. Cette documentation les écrit, pour qu'on puisse les discuter, les vérifier et les faire évoluer ensemble. Chacun peut proposer un besoin ou contester une règle.

**Comment la lire.** Commencez par [Besoins par profil](needs-by-profile.md) pour trouver ce qui concerne votre profil. En cas de désaccord, le code et les tests ont raison. Les termes sont définis dans le [glossaire](glossary.md).

## Je cherche à comprendre…

| Besoin métier | Page à lire |
|---|---|
| Ce que chaque profil attend de `piighost`, et comment le vérifier | [Besoins par profil](needs-by-profile.md) |
| Ce que le modèle voit vraiment d'un message | [Protéger un message avant l'envoi au modèle](processes/protect-a-message.md) |
| Pourquoi un nom est resté en clair, ou à moitié | [Protéger un message avant l'envoi au modèle](processes/protect-a-message.md#questions-fréquentes) |
| Comment une personne garde le même jeton d'un message à l'autre | [Suivre une conversation et restaurer la réponse](processes/follow-a-conversation.md) |
| Ce qui se passe quand on corrige un message à la main | [Suivre une conversation et restaurer la réponse](processes/follow-a-conversation.md#corriger-un-repérage) |
| Comment effacer une conversation (droit à l'effacement) | [Suivre une conversation et restaurer la réponse](processes/follow-a-conversation.md) |
| Garder le nom de l'entreprise en clair, ou toujours masquer un code interne | [Imposer une liste à masquer et une liste à laisser en clair](processes/impose-a-deny-list-and-an-allow-list.md) |
| Ce que reçoit un outil de l'agent, et ce que le modèle lit de son résultat | [Laisser un outil agir sur les vraies valeurs](processes/let-a-tool-act.md) |
| Pourquoi un jeton apparaît pendant qu'une réponse s'affiche | [Afficher une réponse au fil de l'eau](processes/show-a-streamed-reply.md) |
| Ce que voit chaque acteur selon l'outil utilisé (LangChain, Claude Code…) | [Brancher la protection sur un agent et ses outils](integrations/agents-and-tools.md) |
| Ce qui se passe quand un modèle répond mal | [Besoins par profil, points de vigilance](needs-by-profile.md#points-de-vigilance) |
| Où sont stockées les données des conversations, et si elles sont chiffrées | [Stocker les conversations et protéger les traces](operations/storage-and-encryption.md) |
| Pourquoi `piighost` fonctionne ainsi, décision par décision | [Décisions de conception](reference/decisions.md) |
| Le sens d'un terme ou d'un sigle | [Glossaire](glossary.md) |
| Ce qui est décidé et reste à faire | [Points à régler](reference/open-points.md) |

## Pourquoi piighost fonctionne ainsi

Chaque règle découle d'une décision de conception. La page [Décisions de conception](reference/decisions.md) les explique dans l'ordre où elles se sont posées, avec un exemple pour chacune.

- **Dé-identifier un texte** :
    - DEC-01 : Remplacer chaque donnée confidentielle par un jeton.
    - DEC-02 : Trouver chaque valeur et sa position exacte.
    - DEC-03 : Encadrer chaque jeton par `<<` et `>>`.
    - DEC-04 : Dire dans le jeton de quel type de donnée il s'agit.
    - DEC-05 : Donner à chaque entité son propre identifiant.
    - DEC-06 : Regrouper les détections d'une même entité.
    - DEC-07 : Ne garder qu'un passage quand deux détections se recouvrent.
    - DEC-08 : Garder la correspondance pour restaurer les vraies valeurs.
    - DEC-09 : Laisser corriger la détection.
    - DEC-10 : Relire le texte protégé avant l'envoi, en option.
- **Tenir une conversation** :
    - DEC-11 : Garder le même jeton pendant toute la conversation.
    - DEC-12 : Exiger l'identifiant de la conversation.
    - DEC-13 : Neutraliser un jeton tapé par l'utilisateur.
    - DEC-14 : Refuser un jeton inventé par le modèle.
    - DEC-15 : Laisser en clair une valeur que l'assistant cite le premier.
- **Laisser un agent agir** :
    - DEC-16 : Donner la vraie valeur aux outils, et le jeton au modèle.
    - DEC-17 : Restaurer la réponse pendant qu'elle arrive.
- **Mettre en production** :
    - DEC-18 : Protéger la mémoire stockée.
    - DEC-19 : Préférer la protection à la disponibilité.
    - DEC-20 : Configurer un pipeline par fichier et par le catalogue.
- **L'architecture** :
    - DEC-21 : Faire de chaque étape un port remplaçable.
    - DEC-22 : Rendre asynchrones les étapes qui attendent.

## Modifier le code

Pour modifier le code, la documentation technique indique quelles pages lire et quels fichiers ouvrir. Voir [Modifier le code de piighost](../../docs/fr/community/changing-the-code.md).

## Les groupes de la documentation métier

- **Besoins** :
    - [Besoins par profil](needs-by-profile.md)
- **Processus** :
    - [Protéger un message](processes/protect-a-message.md)
    - [Suivre une conversation](processes/follow-a-conversation.md)
    - [Imposer une liste à masquer et une liste à laisser en clair](processes/impose-a-deny-list-and-an-allow-list.md)
    - [Laisser un outil agir](processes/let-a-tool-act.md)
    - [Afficher une réponse au fil de l'eau](processes/show-a-streamed-reply.md)
- **Intégrations** :
    - [Brancher la protection sur un agent et ses outils](integrations/agents-and-tools.md)
- **Exploitation** :
    - [Configurer un pipeline par fichier, catalogue et ligne de commande](operations/configuration-and-catalog.md)
    - [Stocker les conversations et protéger les traces](operations/storage-and-encryption.md)
- **Architecture** :
    - [Ajouter ou remplacer un composant du pipeline](architecture/ports-and-extension.md)
- **Tests** :
    - [Lancer et écrire les tests](tests/run-and-write-tests.md)
    - [Tests d'acceptation](tests/acceptance-tests.md)
- **Référence** :
    - [Glossaire](glossary.md)
    - [Décisions de conception](reference/decisions.md)
    - [Points à régler](reference/open-points.md)

## Points de vigilance transverses

1. **L'identifiant de conversation décide du partage des jetons.** Un appel sans identifiant est refusé par LangChain, par les hooks Claude Code et par les routes de dé-identification et de restauration du serveur. Les proxys OpenAI et Anthropic du serveur font exception. Sans identifiant, ils ouvrent une conversation éphémère, propre à la requête et effacée à sa fin. Une application qui nomme `default` partage ses jetons entre tous ses utilisateurs. Seule la commande `piighost anonymize` se rabat sur `default`, pour essayer un texte isolé. Voir [Suivre une conversation](processes/follow-a-conversation.md#règles-à-connaître).
2. **Corriger un message ancien peut renuméroter les jetons**, et une réponse du modèle peut alors être restaurée avec le nom d'une autre personne. Voir [Suivre une conversation](processes/follow-a-conversation.md#règles-à-connaître).
3. **Des vraies valeurs restent stockées hors du modèle.** Le modèle ne voit que des jetons, mais deux endroits gardent les vraies valeurs. La mémoire de `piighost` les garde en clair si son stockage n'est pas chiffré. L'historique que l'agent enregistre, avec LangGraph ou Pydantic AI, garde le texte des messages restauré. Certains textes ne passent pas non plus par `piighost`. C'est le cas du résultat d'un outil Claude Code que `piighost` ne relit pas, comme Grep. C'est aussi le cas du résultat d'un outil dont le réglage l'envoie en clair au modèle, voir [Laisser un outil agir](processes/let-a-tool-act.md). Chiffrez la mémoire, et protégez l'historique de l'agent comme une donnée personnelle. Voir [Stocker les conversations](operations/storage-and-encryption.md) et [Brancher la protection sur un agent](integrations/agents-and-tools.md#pièges).
4. **Les traces techniques portent le texte en clair par défaut.** Configurez un masqueur de traces avant de les envoyer à un service tiers. Voir [Stocker les conversations et protéger les traces](operations/storage-and-encryption.md#masquer-les-traces).
5. **Effacer une conversation ne vide pas tout de suite les autres instances du serveur.** Le stockage et l'instance qui reçoit la demande sont vidés. Les autres instances gardent une copie des valeurs dans leur cache de jetons, jusqu'à la fin de la durée de vie de ce cache. Sans durée de vie réglée, la copie reste jusqu'à ce que le cache plein la chasse. Voir [Stocker les conversations](operations/storage-and-encryption.md#règles-à-connaître).
6. **Un détecteur ou un garde-fou LLM refuse le message quand il ne peut pas lire la réponse de son propre LLM.** Le message ne part pas, et l'application reçoit une erreur. Le réglage `fail_open` laisse partir le message sans cette détection ou sans cette vérification. Voir les [points de vigilance](needs-by-profile.md#points-de-vigilance) de [Besoins par profil](needs-by-profile.md) et DEC-19.

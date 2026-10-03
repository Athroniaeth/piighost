---
type: guide
title: Besoins par profil
description: Les besoins du responsable conformité, du développeur, de l'exploitant et de l'utilisateur de l'application, chacun avec ses critères observables, la page de la documentation métier qui le livre, et les points de vigilance quand un modèle répond mal.
tags: [personas, user-stories, dpo, developer, operator, end-user, vigilance]
generated: { by: "claude-code", at: "2026-10-02T18:00:00.000Z" }
---


# Besoins par profil

## En bref

- Quatre profils attendent des choses différentes de PIIGhost : le responsable conformité (DPO), le développeur, l'exploitant et l'utilisateur de l'application.
- Chaque besoin porte un identifiant en anglais, le même dans toutes les langues : `DPO-n`, `DEV-n`, `OPS-n`, `USER-n`.
- Chaque besoin donne des critères observables et la page de la documentation métier qui le livre.
- Les points de vigilance, en fin de page, listent les réponses imprévues d'un modèle et le besoin qui les couvre.

`piighost` sert quatre profils, qui n'en attendent pas la même chose. Le responsable conformité veut qu'aucune donnée confidentielle ne sorte. Le développeur veut intégrer `piighost` sans réécrire son application. L'exploitant veut le faire tourner en production. L'utilisateur de l'application ne doit jamais s'en apercevoir.

Chaque besoin est porté par un processus de la documentation métier, qui donne le scénario et les règles, et par des tests d'acceptation, listés dans [Tests d'acceptation](tests/acceptance-tests.md). Les termes sont définis dans le [glossaire](glossary.md).

---

## Responsable conformité (DPO)

**DPO-1. En tant que DPO, je veux qu'aucune donnée personnelle ni aucun secret ne parte en clair vers le LLM, afin de rester conforme au RGPD et de ne pas exposer d'identifiants d'accès.**

- Le message « Écrivez à Jean Dupont, jean.dupont@exemple.fr » part vers le LLM sous la forme « Écrivez à `<<PERSON:1>>`, `<<EMAIL:1>>` ».
- Une clé d'API collée dans un message part en jeton, dès qu'un groupe de secrets est configuré.
- Voir [Protéger un message](processes/protect-a-message.md) et les [points de vigilance](#points-de-vigilance). Tests : [AT-DPO-1-…](tests/acceptance-tests.md).

**DPO-2. En tant que DPO, je veux choisir les types de données protégées, afin d'adapter la protection à mon activité.**

- Une configuration qui tire le groupe français du hub masque un IBAN et un numéro de sécurité sociale.
- Un motif propre à l'entreprise, un numéro de dossier par exemple, s'ajoute en une ligne.
- Voir [Configurer un pipeline](operations/configuration-and-hub.md) et [Protéger un message](processes/protect-a-message.md). Tests : [AT-DPO-2-…](tests/acceptance-tests.md).

**DPO-3. En tant que DPO, je veux forcer la protection d'une valeur, ou laisser en clair un terme public, sans attendre le détecteur, afin d'imposer la politique de l'entreprise.**

- Une valeur de la liste blanche de la configuration (section `[override]`, dans l'application ou dans `piighost-api`) est masquée même si aucun détecteur ne la voit.
- Un terme de la liste noire de la même section reste en clair même quand un détecteur le relève.
- Voir [Imposer une liste blanche et une liste noire](processes/impose-a-whitelist-and-blacklist.md). Tests : [AT-DPO-3-…](tests/acceptance-tests.md).

**DPO-4. En tant que DPO, je veux refuser un texte qui contient encore une donnée, afin qu'une détection manquée ne parte pas.**

- Un texte dé-identifié qui garde une adresse e-mail en clair est refusé au lieu d'être envoyé.
- Voir [Protéger un message](processes/protect-a-message.md). Tests : [AT-DPO-4-…](tests/acceptance-tests.md).

**DPO-5. En tant que DPO, je veux savoir où sont gardées les vraies valeurs et qu'elles soient chiffrées au repos, afin de maîtriser la pseudonymisation.**

- Avec une mémoire Redis chiffrée, la base ne contient ni « Jean Dupont » ni le message en clair.
- Quand le chiffrement est configuré mais que ses secrets manquent dans l'environnement, le pipeline refuse de démarrer plutôt que de stocker en clair.
- Voir [Stocker les conversations et protéger les traces](operations/storage-and-encryption.md). Tests : [AT-DPO-5-…](tests/acceptance-tests.md).

**DPO-6. En tant que DPO, je veux effacer une conversation sur demande, afin de répondre au droit à l'effacement.**

- Après l'effacement d'une conversation, restaurer son jeton `<<PERSON:1>>` le rend tel quel, sans « Jean Dupont ».
- Le serveur d'API expose cet effacement sur une route.
- Voir [Suivre une conversation](processes/follow-a-conversation.md). Tests : [AT-DPO-6-…](tests/acceptance-tests.md).

**DPO-7. En tant que DPO, je veux observer le pipeline sans que les traces contiennent les données, afin de prouver la protection.**

- Une trace montre un jeton, `<<REDACT>>` par exemple, là où le message contenait « Jean Dupont ».
- Voir [Stocker les conversations et protéger les traces](operations/storage-and-encryption.md). Tests : [AT-DPO-7-…](tests/acceptance-tests.md).

**DPO-8. En tant que DPO, je veux documenter l'analyse d'impact, afin de justifier le traitement.**

- Voir [Comment documenter piighost dans une AIPD](../../docs/fr/dpia.md) et la page [Conformité](../../docs/fr/compliance.md) du guide technique. Tests : [AT-DPO-8-…](tests/acceptance-tests.md).

**DPO-9. En tant que DPO, je veux qu'un détecteur en panne bloque le message plutôt que de le laisser passer, afin qu'une panne ne devienne pas une fuite.**

- Quand le modèle d'un détecteur LLM rend une sortie illisible, le message doit être refusé avec une erreur au lieu de partir sans détection.
- Un réglage explicite doit laisser passer le message, pour qui préfère la disponibilité à la protection.
- Les hooks Claude Code doivent de même bloquer un prompt ou un appel d'outil quand le serveur ne répond pas, et remplacer une sortie d'outil par un avis.
- Voir les [points de vigilance](#points-de-vigilance) et [Points à régler](reference/open-points.md). Tests : [AT-DPO-9-…](tests/acceptance-tests.md).

**DPO-10. En tant que DPO, je veux choisir sous quelle forme les corrections humaines sont conservées, afin que leur stockage ne devienne pas une copie des données.**

- Une correction exportée vers un outil d'annotation, Langfuse par exemple, se conserve sous la forme choisie : jetons à la place des valeurs, valeurs en clair, ou entrée et sortie entièrement masquées.
- Le développeur règle cette forme, le DPO la décide.
- Sans choix explicite, la correction est conservée sous forme de jetons. L'export ne contient alors aucune valeur réelle.

**Limite connue.** Le choix de la forme n'existe pas encore dans le code.

---

## Développeur

**DEV-1. En tant que développeur, je veux protéger les appels LLM de mon agent sans réécrire sa logique, afin d'ajouter la protection à un projet existant.**

- Le middleware LangChain s'ajoute à l'agent en une ligne.
- Le proxy compatible OpenAI ne demande qu'un changement d'URL de base.
- Voir [Brancher la protection sur un agent](integrations/agents-and-tools.md). Tests : [AT-DEV-1-…](tests/acceptance-tests.md).

**DEV-2. En tant que développeur, je veux que la réponse soit restaurée automatiquement, afin de ne rien écrire pour remettre les vraies valeurs.**

- « Bonjour `<<PERSON:1>>` », rendu par le LLM, arrive à l'application comme « Bonjour Jean Dupont ».
- Voir [Suivre une conversation](processes/follow-a-conversation.md). Tests : [AT-DEV-2-…](tests/acceptance-tests.md).

**DEV-3. En tant que développeur, je veux qu'une valeur garde le même jeton sur toute la conversation, afin que le LLM suive le fil.**

- « jean.dupont@exemple.fr » reste `<<EMAIL:1>>` trois messages plus tard.
- Un jeton d'une conversation ne se restaure pas dans une autre, même si les deux ont émis `<<PERSON:1>>`.
- Voir [Suivre une conversation](processes/follow-a-conversation.md). Tests : [AT-DEV-3-…](tests/acceptance-tests.md).

**DEV-4. En tant que développeur, je veux que mes outils reçoivent les vraies valeurs alors que le LLM ne voit que des jetons, afin que les actions s'exécutent.**

- Un outil appelé avec `<<EMAIL:1>>` reçoit « jean.dupont@exemple.fr », et son résultat repasse en jetons avant le LLM.
- Voir [Laisser un outil agir](processes/let-a-tool-act.md). Tests : [AT-DEV-4-…](tests/acceptance-tests.md).

**DEV-5. En tant que développeur, je veux ajouter mes propres détecteurs ou valeurs, afin de couvrir un identifiant propre à mon métier.**

- Un motif écrit dans la configuration masque un numéro de commande « CMD-2024-0042 ».
- Un détecteur maison se branche dans le pipeline sans toucher à la librairie.
- Voir [Ajouter ou remplacer un composant](architecture/ports-and-extension.md). Tests : [AT-DEV-5-…](tests/acceptance-tests.md).

**DEV-6. En tant que développeur, je veux décrire le pipeline dans un fichier et le valider en CI, afin de le faire relire sans lire de code.**

- La validation réussit sur une configuration correcte et échoue, en nommant la clé fautive, sur une faute de frappe.
- Voir [Configurer un pipeline](operations/configuration-and-hub.md). Tests : [AT-DEV-6-…](tests/acceptance-tests.md).

**DEV-7. En tant que développeur, je veux tester mon intégration sans télécharger de modèle, afin d'avoir des tests rapides et reproductibles.**

- Une liste de valeurs connues est dé-identifiée sans réseau ni modèle.
- Voir [Lancer et écrire les tests](tests/run-and-write-tests.md). Tests : [AT-DEV-7-…](tests/acceptance-tests.md).

**DEV-8. En tant que développeur, je veux décider quoi faire d'un jeton que le LLM a inventé, afin qu'il n'arrive pas tel quel à l'utilisateur.**

- Un `<<PERSON:9>>` jamais émis est refusé, retiré ou laissé, selon la stratégie choisie.
- Voir [Suivre une conversation](processes/follow-a-conversation.md) et [Laisser un outil agir](processes/let-a-tool-act.md). Tests : [AT-DEV-8-…](tests/acceptance-tests.md).

**DEV-9. En tant que développeur, je veux restaurer une réponse streamée au fil des morceaux, afin de l'afficher sans attendre la fin.**

- « `<<PER` » puis « `SON:1>>` » en deux morceaux donnent « Jean Dupont » une seule fois.
- Voir [Afficher une réponse streamée](processes/show-a-streamed-reply.md). Tests : [AT-DEV-9-…](tests/acceptance-tests.md).

**DEV-10. En tant que développeur, je veux que chaque conversation soit nommée explicitement, afin que deux utilisateurs ne partagent jamais leurs jetons par accident.**

- Un appel sans identifiant de conversation est refusé, par le middleware LangChain, par les hooks Claude Code et par le serveur d'API.
- Une application dont les conversations n'ont pas besoin d'être séparées passe `"default"`.
- Voir [Suivre une conversation](processes/follow-a-conversation.md) et [Brancher la protection sur un agent](integrations/agents-and-tools.md). Tests : [AT-DEV-10-…](tests/acceptance-tests.md).

**DEV-11. En tant que développeur, je veux choisir le sort d'une valeur que l'assistant introduit lui-même, afin de décider si le LLM garde ce qu'il sait d'elle.**

- Par défaut, « Napoléon », cité d'abord par l'assistant, reste en clair, même quand l'utilisateur le reprend ensuite.
- Un réglage passe cette valeur en jeton, un autre n'analyse pas du tout les messages de l'assistant.
- Voir [Suivre une conversation](processes/follow-a-conversation.md). Tests : [AT-DEV-11-…](tests/acceptance-tests.md).

---

## Exploitant

**OPS-1. En tant qu'exploitant, je veux déployer une API de dé-identification partagée, afin que plusieurs applications utilisent un seul pipeline et un seul modèle.**

- Le serveur démarre sur une configuration du hub et répond aux requêtes de dé-identification.
- Voir le tutoriel [Déployer une API de dé-identification](../../docs/fr/getting-started/api-server.md) et [Configurer un pipeline](operations/configuration-and-hub.md). Tests : [AT-OPS-1-…](tests/acceptance-tests.md).

**OPS-2. En tant qu'exploitant, je veux que la mémoire survive aux redémarrages et soit partagée entre instances, afin qu'une conversation ne perde pas ses jetons.**

- Deux instances rendent le même `<<PERSON:1>>` pour « Jean Dupont » dans la même conversation.
- Voir [Stocker les conversations et protéger les traces](operations/storage-and-encryption.md), [Suivre une conversation](processes/follow-a-conversation.md) et, pour plusieurs instances derrière un répartiteur de charge, [Déploiement multi-instance](../../docs/fr/multi-instance.md). Tests : [AT-OPS-2-…](tests/acceptance-tests.md).

**OPS-3. En tant qu'exploitant, je veux fournir les secrets par l'environnement, afin qu'aucune clé ne soit écrite dans un fichier.**

- Quand le chiffrement est configuré mais que ses secrets manquent, le démarrage échoue avec un message clair.
- Une mémoire Redis déclarée sans chiffrement démarre, mais en clair, avec un avertissement de sécurité.
- Voir [Stocker les conversations et protéger les traces](operations/storage-and-encryption.md). Tests : [AT-OPS-3-…](tests/acceptance-tests.md).

**OPS-4. En tant qu'exploitant, je veux protéger l'API par des clés, une taille de requête maximale et un débit, afin qu'elle ne soit ni ouverte ni abusée.**

- Sans clé configurée, le serveur refuse de démarrer, sauf mode anonyme demandé explicitement.
- Une requête trop grosse ou trop fréquente est refusée.
- Voir la [référence de la CLI du serveur](../../docs/fr/reference/api-cli.md) et la [référence des endpoints de l'API](../../docs/fr/reference/api-endpoints.md). Tests : [AT-OPS-4-…](tests/acceptance-tests.md).

**OPS-5. En tant qu'exploitant, je veux traiter un long document sans que le modèle en tronque la fin, afin qu'aucune valeur en fin de texte ne parte en clair.**

- Une valeur placée au-delà de la fenêtre du modèle est détectée quand le texte est découpé.
- Voir [Limites](../../docs/fr/limitations.md) et [Ajouter ou remplacer un composant](architecture/ports-and-extension.md). Tests : [AT-OPS-5-…](tests/acceptance-tests.md).

**OPS-6. En tant qu'exploitant, je veux charger une configuration relue depuis le hub par sa référence, afin de ne pas maintenir de copie locale.**

- Une référence épinglée sur un commit est téléchargée au premier démarrage, puis lue depuis le cache.
- Une référence sans commit, qui peut changer, est relue à chaque chargement et jamais mise en cache.
- Le hub n'est joint qu'en HTTP ou HTTPS, et une configuration du hub qui embarque un modèle est refusée.
- Voir [Configurer un pipeline](operations/configuration-and-hub.md). Tests : [AT-OPS-6-…](tests/acceptance-tests.md).

**Limite actuelle.** Le hub ne sert pour l'instant que des groupes de motifs. Un modèle NER reconnaît mieux certains labels que d'autres. Répartir les labels entre motifs et modèle demande un format de configuration que le hub n'a pas encore.

**OPS-7. En tant qu'exploitant, je veux que la mémoire en processus soit bornée par défaut, afin qu'un serveur qui tourne des semaines ne garde pas toutes les valeurs qu'il a vues.**

- Sans réglage, la mémoire garde au plus 10 000 conversations, et garde chacune pendant un jour après son dernier message.
- Les deux bornes se règlent dans la configuration.
- Voir [Stocker les conversations et protéger les traces](operations/storage-and-encryption.md) et [Suivre une conversation](processes/follow-a-conversation.md). Tests : [AT-OPS-7-…](tests/acceptance-tests.md).

---

## Utilisateur de l'application

Ce profil ne manipule jamais `piighost`. Il utilise l'application qu'un développeur a construite avec, et ses besoins disent ce que cette application doit lui garantir.

**USER-1. En tant qu'utilisateur, je veux lire la réponse avec mes vraies informations, afin de ne jamais voir de jeton.**

- L'utilisateur lit « Bonjour Jean Dupont », jamais « Bonjour `<<PERSON:1>>` ».
- Voir [Suivre une conversation](processes/follow-a-conversation.md) et [Brancher la protection sur un agent](integrations/agents-and-tools.md). Tests : [AT-USER-1-…](tests/acceptance-tests.md).

**Limite connue.** Avec les hooks Claude Code, la réponse affichée dans Claude Code garde ses jetons, car aucun hook ne peut réécrire ce texte. Le proxy compatible Anthropic restaure, lui, la réponse.

**USER-2. En tant qu'utilisateur, je veux que la conversation reste cohérente de bout en bout, afin que l'assistant ne confonde pas deux personnes.**

- Deux personnes citées gardent chacune leur jeton d'un message à l'autre, et la réponse les nomme correctement.
- Voir [Suivre une conversation](processes/follow-a-conversation.md). Tests : [AT-USER-2-…](tests/acceptance-tests.md).

**USER-3. En tant qu'utilisateur, je veux que les actions de l'assistant utilisent mes vraies données, afin que l'e-mail parte à la bonne adresse.**

- L'outil d'envoi reçoit « jean.dupont@exemple.fr », pas `<<EMAIL:1>>`.
- Voir [Laisser un outil agir](processes/let-a-tool-act.md). Tests : [AT-USER-3-…](tests/acceptance-tests.md).

**Limite connue.** Le proxy compatible OpenAI ne restaure pas les arguments d'un appel d'outil quand la réponse est streamée. Voir le proxy compatible OpenAI.

**USER-4. En tant qu'utilisateur, je veux voir la réponse s'afficher au fil de l'eau sans morceau de jeton, afin de la lire normalement.**

- Un fragment comme « `<<PER` » n'apparaît pas pendant le flux. Seul un flux coupé au milieu d'un jeton rend ce fragment à la fin, sans aucune valeur réelle.
- Voir [Afficher une réponse streamée](processes/show-a-streamed-reply.md). Tests : [AT-USER-4-…](tests/acceptance-tests.md).

**USER-5. En tant qu'utilisateur, je veux que les termes publics restent lisibles, afin que la réponse garde son sens.**

- Un nom de ville mis dans la liste noire de la configuration reste en clair, et une date de réunion n'est pas masquée par un groupe de motifs génériques.
- Voir [Imposer une liste blanche et une liste noire](processes/impose-a-whitelist-and-blacklist.md). Tests : [AT-USER-5-…](tests/acceptance-tests.md).

**USER-6. En tant qu'utilisateur, je veux corriger une détection, ajouter un nom oublié ou rendre lisible un terme masqué à tort, afin que l'assistant reçoive le bon texte.**

- Après correction, le nom ajouté part en jeton et le terme retiré part en clair, dans le message corrigé.
- La liste blanche et la liste noire de la configuration gardent le dernier mot, si bien qu'un terme de la liste blanche reste masqué même si l'utilisateur le retire.
- Voir [Suivre une conversation](processes/follow-a-conversation.md) et [Imposer une liste blanche et une liste noire](processes/impose-a-whitelist-and-blacklist.md). Tests : [AT-USER-6-…](tests/acceptance-tests.md).

---

## Points de vigilance

Un LLM peut mal répondre, qu'il serve de détecteur, de garde-fou ou de modèle principal. Ces cas définissent ce que `piighost` doit faire, et le besoin qui le porte.

| Situation | Ce que fait `piighost` | Besoin |
|---|---|---|
| Le LLM détecteur rend une sortie illisible, un JSON cassé ou un champ manquant | Le message est refusé avec une erreur, sauf si l'échec ouvert est demandé | DPO-9 |
| Le LLM garde-fou rend une sortie illisible | Le texte est refusé avec une erreur, sauf si l'échec ouvert est demandé | DPO-9 |
| Le LLM détecteur cite une valeur absente du texte | La valeur n'est retrouvée nulle part dans le texte et n'est pas retenue | DPO-1 |
| Le LLM détecteur oublie une valeur | Elle part en clair, sauf si un garde-fou relit le texte | DPO-4 |
| Le texte analysé contient une balise qui imite la zone de données du prompt | La balise est neutralisée avant l'envoi au LLM détecteur | DPO-1 |
| Le LLM principal invente un jeton, `<<PERSON:10>>` alors que la conversation n'a que `<<PERSON:1>>` | Refusé par défaut, retiré ou laissé selon la stratégie | DEV-8 |
| Le LLM principal change la casse ou les chiffres d'un jeton, `<<Person:1>>` ou `<<PERSON:01>>` | Il n'est pas restauré, et il est traité comme un jeton inventé | DEV-8 |
| Le LLM principal abîme les délimiteurs d'un jeton, `<< PERSON:1 >>` ou `PERSON:1` | Il n'est ni restauré ni reconnu comme jeton, et l'utilisateur le lit tel quel. Aucune valeur ne fuit, et ce comportement est accepté | USER-1 |
| Le LLM principal devine la vraie valeur derrière un jeton et l'écrit | La valeur est traitée comme introduite par l'assistant | DEV-11 |
| L'utilisateur tape lui-même un jeton, `<<PERSON:2>>` | Il ne fait pas apparaître la valeur d'une autre personne | DPO-1 |
| Le flux de réponse s'arrête au milieu d'un jeton | Le fragment est rendu tel quel, sans valeur réelle | USER-4 |
| Le LLM principal coupe ou reformule un jeton dans un argument d'outil | Seul un jeton écrit en entier est restauré, l'outil reçoit le reste tel quel | DEV-4 |
| Le serveur d'API est injoignable depuis les hooks Claude Code | Le prompt ou l'appel d'outil est bloqué, la sortie d'outil remplacée par un avis, sauf si l'échec ouvert est demandé | DPO-9 |

---

## Voir aussi

- [Processus](processes/), les scénarios complets avec leurs règles et leurs cas d'erreur.
- [Glossaire](glossary.md), les termes de la dé-identification.

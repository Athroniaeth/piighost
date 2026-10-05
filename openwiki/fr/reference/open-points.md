---
type: reference
title: Points à régler
description: Les décisions prises sur les besoins et ce qui reste à faire pour les tenir, la forme de stockage des corrections et les modèles sur le catalogue, puis les propositions qui restent à trancher.
tags: [backlog, decisions, personas]
generated: { by: "claude-code", at: "2026-10-02T18:00:00.000Z" }
---

# Points à régler

## En bref

- Cette page suit les décisions prises sur les besoins et ce qu'il reste à faire pour les tenir.
- Chaque point cite le besoin concerné, comme `DPO-10` ou `OPS-6`.
- Ce qui est fait n'est pas listé ici. Le besoin et ses tests d'acceptation le montrent, et l'historique git garde le détail.

## Décidé, à faire

Décidé le 2 octobre 2026.

- DPO-10 : concevoir l'export des validations humaines, vers Langfuse par exemple. Trois formes seront au choix, les jetons à la place des valeurs, les valeurs en clair, ou l'entrée et la sortie entièrement masquées. La forme par défaut est les jetons.
- OPS-6 : accepter les configurations à modèle sur le catalogue. Leur refus actuel est temporaire. Il faut un format qui répartit les labels entre les motifs et le modèle, parce que chaque modèle NER est plus fort sur certains labels.

## Proposé, pas encore tranché

Ces propositions ajoutent des critères à des besoins existants. Chaque critère décrit un comportement que des tests vérifient déjà. Il reste à décider s'il entre dans le texte du besoin.

- DPO-1 : ajouter deux critères.
    - Aucune valeur ne repart en clair vers le modèle, ni aux tours suivants de la conversation, ni dans un message découpé en plusieurs blocs, ni dans l'argument d'un appel d'outil.
    - Un jeton que l'utilisateur tape lui-même, comme `<<PERSON:2>>`, ne fait pas apparaître la valeur d'une autre personne.
- OPS-4 : ajouter deux critères.
    - Le serveur `piighost-api` refuse de démarrer si une clé d'API est mal formée, sauf si `PIIGHOST_ALLOW_ANONYMOUS` est activé.
    - Une route protégée appelée sans clé répond 401.

---
type: reference
title: Points à régler
description: Les décisions prises sur les besoins par profil et ce qui reste à faire pour les tenir, l'échec fermé d'un détecteur, la forme de stockage des corrections, les modèles sur le hub, avec ce qui est déjà fait et ce qui reste à trancher.
tags: [backlog, decisions, personas]
generated: { by: "claude-code", at: "2026-10-02T18:00:00.000Z" }
---

# Points à régler

## En bref

- Cette page suit les décisions prises sur les besoins et ce qu'il reste à faire pour les tenir.
- Chaque point cite le besoin concerné (`DPO-9`, `DEV-10`…) et, quand il existe, le commit qui l'a réglé.
- Les écarts entre la documentation et le code sont dans le [registre des écarts](doc-code-gaps.md), pas ici.

## Décidé, à faire

Décidé le 2026-10-02.

- **DPO-10, forme de stockage des corrections.** Concevoir l'export des validations humaines, vers Langfuse par exemple, avec trois formes au choix, c'est-à-dire jetons à la place des valeurs, valeurs en clair, entrée et sortie entièrement masquées. La forme par défaut est les jetons (décidé le 2026-10-02).
- **OPS-6, modèles sur le hub.** Le refus des configurations à modèle est temporaire. Il faut un format qui répartit les labels entre motifs et modèle, parce que chaque modèle NER est plus fort sur certains labels.

## Fait

Fait le 2026-10-02, sur les branches locales. Rien n'est poussé.

- **DPO-9.** `LLMDetector` et `LLMGuardRail` lèvent `UnreadableOutputError` sur une sortie illisible, et `fail_open=True` rétablit l'échec ouvert avec un avertissement (`4d47d65`). Les hooks Claude Code sortent en code 2 pour un prompt ou un appel d'outil qu'ils ne peuvent pas dé-identifier, remplacent une sortie d'outil par un avis, et `PIIGHOST_HOOK_FAIL_OPEN=1` laisse passer le texte (`5ec03d1`).
- **Jetons aux délimiteurs abîmés.** Accepté et documenté. Un jeton comme `<< PERSON:1 >>` n'est pas restauré et l'utilisateur le lit tel quel, sans qu'aucune valeur ne fuie.
- **Droits du job OpenWiki.** Il ne réécrit pas le texte d'un besoin ni d'une règle métier. Un désaccord avec le code devient une ligne du registre des écarts (`INSTRUCTIONS.md`).

- **DEV-10.** `require_thread_id` est supprimé. Le middleware LangChain, les hooks Claude Code et `PIIGhostClient.detect` exigent une conversation (`piighost` `97b1e78`), et le serveur répond 400 sans `thread_id` (`piighost-api` `7dec988`). La CLI garde `--thread-id default` pour une commande isolée.
- **OPS-7.** La mémoire en processus est bornée par défaut à 10 000 conversations et à une durée de vie d'un jour (`4af48d3`). La mémoire Redis garde son `ttl` facultatif, parce que sa persistance est voulue.
- **Documentation.** La réponse d'un outil passe par la détection complète, et un flux coupé rend son fragment (`3473217`).
- **Tests d'acceptation.** AT-DPO-1-2, AT-DPO-2-2, AT-DPO-5-2, AT-DPO-6-1, AT-DEV-3-2, AT-OPS-2-1 et AT-OPS-3-1 dans `tests/acceptance/` (`21e5ac9`).

## Proposé, pas encore tranché

- DPO-1 : ajouter en critères « aucun tour suivant, aucun bloc de contenu et aucun argument d'outil ne renvoie une valeur en clair » et « un jeton tapé par l'utilisateur ne fait pas apparaître la valeur d'un autre », déjà testés.
- OPS-4 : ajouter « une clé mal formée sans `PIIGHOST_ALLOW_ANONYMOUS` empêche le démarrage » et « une route protégée sans jeton répond 401 ».

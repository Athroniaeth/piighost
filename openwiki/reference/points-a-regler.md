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
- Les écarts entre la documentation et le code sont dans le [registre des écarts](ecarts-doc-code.md), pas ici.

## Décidé, à faire

Décidé le 2026-10-02.

- **DPO-9, échec fermé par défaut.** `LLMDetector` et `LLMGuardRail` lèvent une erreur sur une sortie illisible au lieu de rendre zéro détection, et un réglage explicite rétablit l'échec ouvert. Le test `test_malformed_output_fails_open` change de sens. Les hooks Claude Code doivent aussi bloquer le prompt quand le serveur est injoignable (code de sortie 2), au lieu de le laisser partir en clair.
- **DPO-10, forme de stockage des corrections.** Concevoir l'export des validations humaines, vers Langfuse par exemple, avec trois formes au choix : jetons à la place des valeurs, valeurs en clair, entrée et sortie entièrement masquées. La forme par défaut reste à décider.
- **OPS-6, modèles sur le hub.** Le refus des configurations à modèle est temporaire. Il faut un format qui répartit les labels entre motifs et modèle, chaque NER étant plus fort sur certains labels.
- **Points de vigilance à trancher.** Un jeton aux délimiteurs abîmés (`<< PERSON:1 >>`) n'est ni restauré ni signalé, et l'utilisateur le lit tel quel.

## Fait

Le 2026-10-02, sur les branches locales, rien n'est poussé.

- **DEV-10.** `require_thread_id` est supprimé. Le middleware LangChain, les hooks Claude Code et `PIIGhostClient.detect` exigent une conversation (`piighost` `97b1e78`), et le serveur répond 400 sans `thread_id` (`piighost-api` `7dec988`). La CLI garde `--thread-id default` pour une commande isolée.
- **OPS-7.** La mémoire en processus est bornée à 10 000 conversations et un jour par défaut (`4af48d3`). La mémoire Redis garde son `ttl` facultatif, sa persistance étant voulue.
- **Documentation.** La réponse d'un outil passe par la détection complète, et un flux coupé rend son fragment (`3473217`).
- **Tests d'acceptation.** AT-DPO-1-2, AT-DPO-2-2, AT-DPO-5-2, AT-DPO-6-1, AT-DEV-3-2, AT-OPS-2-1 et AT-OPS-3-1 dans `tests/acceptance/` (`21e5ac9`).

## Proposé, pas encore tranché

- DPO-1 : ajouter en critères « aucun tour suivant, aucun bloc de contenu et aucun argument d'outil ne renvoie une valeur en clair » et « un jeton tapé par l'utilisateur ne fait pas apparaître la valeur d'un autre », déjà testés.
- OPS-4 : ajouter « une clé mal formée sans `PIIGHOST_ALLOW_ANONYMOUS` empêche le démarrage » et « une route protégée sans jeton répond 401 ».

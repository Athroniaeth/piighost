---
icon: lucide/route
---

# Cas d'utilisation

Un cas d'utilisation suit un message de bout en bout, pour un but précis, et montre le texte réel à chaque étape. Chaque page décrit le déroulé normal, les écarts possibles avec ce que voit l'utilisateur, et les règles que `piighost` applique.

- [Protéger un message avant l'envoi au LLM](protect-a-message.md), les valeurs d'un message remplacées par des placeholders avant l'appel au LLM
- [Suivre une conversation et restaurer la réponse](follow-a-conversation.md), le même placeholder d'un message à l'autre, la réponse restaurée, la correction d'un message et l'effacement d'une conversation
- [Laisser un outil agir sur les vraies valeurs](call-a-tool.md), les arguments d'un appel d'outil restaurés et son résultat dé-identifié
- [Afficher une réponse streamée](stream-a-reply.md), un placeholder coupé entre deux morceaux restauré une seule fois
- [Imposer les listes du serveur](enforce-server-lists.md), les valeurs toujours ou jamais dé-identifiées, quoi que relève le détecteur

Les identifiants cités sous chaque titre, comme DPO-1 ou DEV-4, renvoient aux [besoins par profil](../needs-by-profile.md).

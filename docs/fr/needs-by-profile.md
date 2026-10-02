---
icon: lucide/users
---

# Besoins par profil

`piighost` sert quatre profils, qui n'en attendent pas la même chose. Le responsable conformité veut qu'aucune donnée confidentielle ne sorte, le développeur veut l'intégrer sans réécrire son application, l'exploitant veut la faire tourner en production, et l'utilisateur de l'application ne doit jamais s'en apercevoir.

Les scénarios complets, étape par étape avec leurs cas d'erreur, sont dans les [cas d'utilisation](use-cases/index.md).

---

## Responsable conformité (DPO)

**DPO-1. En tant que DPO, je veux qu'aucune donnée personnelle ni aucun secret ne parte en clair vers le LLM, afin de rester conforme au RGPD et de ne pas exposer d'identifiants d'accès.**

- Le message "Écrivez à `Jean Dupont`{ .pii }, `jean.dupont@exemple.fr`{ .pii }" part vers le LLM sous la forme "Écrivez à `<<PERSON:1>>`{ .placeholder }, `<<EMAIL:1>>`{ .placeholder }".
- Une clé d'API collée dans un message part en jeton, dès qu'un groupe de secrets est configuré.
- Voir [Pourquoi dé-identifier ?](why-anonymize.md), [Sécurité](security.md) et [Protéger un message](use-cases/protect-a-message.md). Un détecteur reste au mieux, ce que détaillent les [Limites](limitations.md).

**DPO-2. En tant que DPO, je veux choisir les types de données protégées, afin d'adapter la protection à mon activité.**

- Une configuration qui tire le groupe français du hub masque un IBAN et un numéro de sécurité sociale.
- Un motif propre à l'entreprise, un numéro de dossier par exemple, s'ajoute en une ligne.
- Voir [Fichier de configuration](getting-started/configuration.md) et les [catalogues de patterns](reference/detectors.md#catalogues-de-patterns).

**DPO-3. En tant que DPO, je veux forcer la protection d'une valeur, ou laisser en clair un terme public, sans attendre le détecteur, afin d'imposer la politique de l'entreprise.**

- Une valeur de la liste blanche est masquée même si aucun détecteur ne la voit.
- Un terme de la liste noire reste en clair même quand un détecteur le relève.
- Voir [Imposer les listes du serveur](use-cases/enforce-server-lists.md) et [Listes d'override](examples/overrides.md).

**DPO-4. En tant que DPO, je veux refuser un texte qui contient encore une donnée, afin qu'une détection manquée ne parte pas.**

- Un texte dé-identifié qui garde une adresse e-mail en clair est refusé au lieu d'être envoyé.
- Voir [Garde-fous](reference/guard-rails.md).

**DPO-5. En tant que DPO, je veux savoir où sont gardées les vraies valeurs et qu'elles soient chiffrées au repos, afin de maîtriser la pseudonymisation.**

- Avec une mémoire Redis chiffrée, la base ne contient ni `Jean Dupont`{ .pii } ni le message en clair.
- Quand le chiffrement est configuré mais que ses secrets manquent dans l'environnement, le pipeline refuse de démarrer plutôt que de stocker en clair.
- Voir [Sécurité](security.md) et [Mémoire de conversation](reference/memory.md).

**DPO-6. En tant que DPO, je veux effacer une conversation sur demande, afin de répondre au droit à l'effacement.**

- Après l'effacement d'une conversation, restaurer son jeton `<<PERSON:1>>`{ .placeholder } le rend tel quel, sans `Jean Dupont`{ .pii }.
- Le serveur d'API expose cet effacement sur une route.
- Voir [Suivre une conversation](use-cases/follow-a-conversation.md), [Documenter une AIPD](dpia.md) et les [endpoints](reference/api-endpoints.md).

**DPO-7. En tant que DPO, je veux observer le pipeline sans que les traces contiennent les données, afin de prouver la protection.**

- Une trace montre un jeton, `<<REDACT>>`{ .placeholder } par exemple, là où le message contenait `Jean Dupont`{ .pii }.
- Voir [Observation](observation.md).

**DPO-8. En tant que DPO, je veux documenter l'analyse d'impact, afin de justifier le traitement.**

- Voir [Documenter une AIPD](dpia.md) et [Conformité](compliance.md).

**DPO-9. En tant que DPO, je veux qu'un détecteur en panne bloque le message plutôt que de le laisser passer, afin qu'une panne ne devienne pas une fuite.**

- Quand le modèle d'un détecteur LLM rend une sortie illisible, le message est refusé avec une erreur au lieu de partir sans détection.
- Un réglage explicite laisse passer le message, pour qui préfère la disponibilité à la protection.
- Voir les [points de vigilance](#points-de-vigilance) et les [Garde-fous](reference/guard-rails.md).

!!! warning "Limite connue"
    Aujourd'hui, `LLMDetector` et `LLMGuardRail` rendent zéro détection sur une sortie illisible, et le message part sans protection.

**DPO-10. En tant que DPO, je veux choisir sous quelle forme les corrections humaines sont conservées, afin que leur stockage ne devienne pas une copie des données.**

- Une correction exportée vers un outil d'annotation, Langfuse par exemple, se conserve sous la forme choisie : jetons à la place des valeurs, valeurs en clair, ou entrée et sortie entièrement masquées.
- Le développeur règle cette forme, le DPO la décide.

!!! warning "Limite connue"
    Le choix de la forme n'existe pas encore.

---

## Développeur

**DEV-1. En tant que développeur, je veux protéger les appels LLM de mon agent sans réécrire sa logique, afin d'ajouter la protection à un projet existant.**

- Le middleware LangChain s'ajoute à l'agent en une ligne.
- Le proxy compatible OpenAI ne demande qu'un changement d'URL de base.
- Voir [Middleware LangChain](getting-started/langchain.md), [Pydantic AI](examples/pydantic-ai.md), [LlamaIndex](examples/llama-index.md), [Claude Code](examples/claude-code.md) et le [proxy compatible OpenAI](examples/openai-proxy.md).

**DEV-2. En tant que développeur, je veux que la réponse soit restaurée automatiquement, afin de ne rien écrire pour remettre les vraies valeurs.**

- "Bonjour `<<PERSON:1>>`{ .placeholder }", rendu par le LLM, arrive à l'application comme "Bonjour `Jean Dupont`{ .pii }".
- Voir [Pipeline conversationnel](getting-started/conversation.md).

**DEV-3. En tant que développeur, je veux qu'une valeur garde le même jeton sur toute la conversation, afin que le LLM suive le fil.**

- `jean.dupont@exemple.fr`{ .pii } reste `<<EMAIL:1>>`{ .placeholder } trois messages plus tard.
- Un jeton d'une conversation ne se restaure pas dans une autre, même si les deux ont émis `<<PERSON:1>>`{ .placeholder }.
- Voir [Suivre une conversation](use-cases/follow-a-conversation.md).

**DEV-4. En tant que développeur, je veux que mes outils reçoivent les vraies valeurs alors que le LLM ne voit que des jetons, afin que les actions s'exécutent.**

- Un outil appelé avec `<<EMAIL:1>>`{ .placeholder } reçoit `jean.dupont@exemple.fr`{ .pii }, et son résultat repasse en jetons avant le LLM.
- Voir [Laisser un outil agir](use-cases/call-a-tool.md) et [Stratégies d'appel outil](tool-call-strategies.md).

**DEV-5. En tant que développeur, je veux ajouter mes propres détecteurs ou valeurs, afin de couvrir un identifiant propre à mon métier.**

- Un motif écrit dans la configuration masque un numéro de commande `CMD-2024-0042`{ .pii }.
- Un détecteur maison se branche dans le pipeline sans toucher à la librairie.
- Voir [Étendre PIIGhost](extending.md) et [Détecteurs prêts à l'emploi](examples/detectors.md).

**DEV-6. En tant que développeur, je veux décrire le pipeline dans un fichier et le valider en CI, afin de le faire relire sans lire de code.**

- La validation réussit sur une configuration correcte et échoue, en nommant la clé fautive, sur une faute de frappe.
- Voir [Fichier de configuration](getting-started/configuration.md) et [CLI](reference/cli.md).

**DEV-7. En tant que développeur, je veux tester mon intégration sans télécharger de modèle, afin d'avoir des tests rapides et reproductibles.**

- Une liste de valeurs connues est dé-identifiée sans réseau ni modèle.
- Voir [Tests](examples/testing.md).

**DEV-8. En tant que développeur, je veux décider quoi faire d'un jeton que le LLM a inventé, afin qu'il n'arrive pas tel quel à l'utilisateur.**

- Un `<<PERSON:9>>`{ .placeholder } jamais émis est refusé, retiré ou laissé, selon la stratégie choisie.
- Voir [Laisser un outil agir](use-cases/call-a-tool.md) et la [référence LangChain](reference/langchain.md).

**DEV-9. En tant que développeur, je veux restaurer une réponse streamée au fil des morceaux, afin de l'afficher sans attendre la fin.**

- "`<<PER`" puis "`SON:1>>`" en deux morceaux donnent "`Jean Dupont`{ .pii }" une seule fois.
- Voir [Afficher une réponse streamée](use-cases/stream-a-reply.md).

**DEV-10. En tant que développeur, je veux que chaque conversation soit nommée explicitement, afin que deux utilisateurs ne partagent jamais leurs jetons par accident.**

- Un appel sans identifiant de conversation est refusé, par le middleware LangChain, par les hooks Claude Code et par le serveur d'API.
- Une application dont les conversations n'ont pas besoin d'être séparées passe `"default"`.
- Voir la [référence LangChain](reference/langchain.md) et [Suivre une conversation](use-cases/follow-a-conversation.md).

**DEV-11. En tant que développeur, je veux choisir le sort d'une valeur que l'assistant introduit lui-même, afin de décider si le LLM garde ce qu'il sait d'elle.**

- Par défaut, `Napoléon`{ .pii }, cité d'abord par l'assistant, reste en clair, même quand l'utilisateur le reprend ensuite.
- Un réglage passe cette valeur en jeton, un autre n'analyse pas du tout les messages de l'assistant.
- Voir la [référence LangChain](reference/langchain.md) et [Suivre une conversation](use-cases/follow-a-conversation.md).

---

## Exploitant

**OPS-1. En tant qu'exploitant, je veux déployer une API de dé-identification partagée, afin que plusieurs applications utilisent un seul pipeline et un seul modèle.**

- Le serveur démarre sur une configuration du hub et répond aux requêtes de dé-identification.
- Voir [Déployer une API de dé-identification](getting-started/api-server.md).

**OPS-2. En tant qu'exploitant, je veux que la mémoire survive aux redémarrages et soit partagée entre instances, afin qu'une conversation ne perde pas ses jetons.**

- Deux instances rendent le même `<<PERSON:1>>`{ .placeholder } pour `Jean Dupont`{ .pii } dans la même conversation.
- Voir [Déploiement](deployment.md) et [Déploiement multi-instance](multi-instance.md).

**OPS-3. En tant qu'exploitant, je veux fournir les secrets par l'environnement, afin qu'aucune clé ne soit écrite dans un fichier.**

- Quand le chiffrement est configuré mais que ses secrets manquent, le démarrage échoue avec un message clair.
- Une mémoire Redis déclarée sans chiffrement démarre, mais en clair, avec un avertissement de sécurité.
- Voir [Déploiement](deployment.md) et la [référence TOML](configuration/toml.md).

**OPS-4. En tant qu'exploitant, je veux protéger l'API par des clés, une taille de requête maximale et un débit, afin qu'elle ne soit ni ouverte ni abusée.**

- Sans clé configurée, le serveur refuse de démarrer, sauf mode anonyme demandé explicitement.
- Une requête trop grosse ou trop fréquente est refusée.
- Voir [CLI du serveur](reference/api-cli.md) et [Endpoints](reference/api-endpoints.md).

**OPS-5. En tant qu'exploitant, je veux traiter un long document sans que le modèle en tronque la fin, afin qu'aucune valeur en fin de texte ne parte en clair.**

- Une valeur placée au-delà de la fenêtre du modèle est détectée quand le texte est découpé.
- Voir [Limites](limitations.md) et la [référence des détecteurs](reference/detectors.md).

**OPS-6. En tant qu'exploitant, je veux charger une configuration relue depuis le hub par sa référence, afin de ne pas maintenir de copie locale.**

- Une référence épinglée sur un commit est téléchargée au premier démarrage, puis lue depuis le cache.
- Une référence sans commit, qui peut changer, est relue à chaque chargement et jamais mise en cache.
- Le hub n'est joint qu'en HTTP ou HTTPS, et une configuration du hub qui embarque un modèle est refusée.
- Voir la [référence du pipeline](reference/pipeline.md) et le [hub piighost](https://hub.piighost.dev).

!!! note "Limite actuelle"
    Le hub ne sert pour l'instant que des groupes de motifs. Un modèle NER reconnaît mieux certains labels que d'autres, et répartir les labels entre motifs et modèle demande un format de configuration que le hub n'a pas encore.

**OPS-7. En tant qu'exploitant, je veux que la mémoire en processus soit bornée par défaut, afin qu'un serveur qui tourne des semaines ne garde pas toutes les valeurs qu'il a vues.**

- Sans réglage, la mémoire garde au plus 10 000 conversations, chacune un jour après son dernier message.
- Les deux bornes se règlent dans la configuration.
- Voir [Déploiement](deployment.md#borner-le-store-in-process) et la [référence de la mémoire](reference/memory.md).

---

## Utilisateur de l'application

Ce profil ne manipule jamais `piighost`. Il utilise l'application qu'un développeur a construite avec, et ses besoins disent ce que cette application doit lui garantir.

**USER-1. En tant qu'utilisateur, je veux lire la réponse avec mes vraies informations, afin de ne jamais voir de jeton.**

- L'utilisateur lit "Bonjour `Jean Dupont`{ .pii }", jamais "Bonjour `<<PERSON:1>>`{ .placeholder }".
- Voir [Suivre une conversation](use-cases/follow-a-conversation.md).

!!! warning "Limite connue"
    Avec les hooks Claude Code, la réponse affichée dans Claude Code garde ses jetons, car aucun hook ne peut réécrire ce texte. Le [proxy compatible Anthropic](examples/anthropic-proxy.md) restaure, lui, la réponse.

**USER-2. En tant qu'utilisateur, je veux que la conversation reste cohérente de bout en bout, afin que l'assistant ne confonde pas deux personnes.**

- Deux personnes citées gardent chacune leur jeton d'un message à l'autre, et la réponse les nomme correctement.
- Voir [Suivre une conversation](use-cases/follow-a-conversation.md).

**USER-3. En tant qu'utilisateur, je veux que les actions de l'assistant utilisent mes vraies données, afin que l'e-mail parte à la bonne adresse.**

- L'outil d'envoi reçoit `jean.dupont@exemple.fr`{ .pii }, pas `<<EMAIL:1>>`{ .placeholder }.
- Voir [Laisser un outil agir](use-cases/call-a-tool.md).

!!! warning "Limite connue"
    Le proxy compatible OpenAI ne restaure pas les arguments d'un appel d'outil quand la réponse est streamée. Voir le [proxy compatible OpenAI](examples/openai-proxy.md).

**USER-4. En tant qu'utilisateur, je veux voir la réponse s'afficher au fil de l'eau sans morceau de jeton, afin de la lire normalement.**

- Un fragment comme "`<<PER`" n'apparaît pas pendant le flux. Seul un flux coupé au milieu d'un jeton rend ce fragment à la fin, sans aucune valeur réelle.
- Voir [Afficher une réponse streamée](use-cases/stream-a-reply.md).

**USER-5. En tant qu'utilisateur, je veux que les termes publics restent lisibles, afin que la réponse garde son sens.**

- Un nom de ville mis en liste noire reste en clair, et une date de réunion n'est pas masquée par un groupe de motifs génériques.
- Voir [Imposer les listes du serveur](use-cases/enforce-server-lists.md) et [Limites](limitations.md).

**USER-6. En tant qu'utilisateur, je veux corriger une détection, ajouter un nom oublié ou rendre lisible un terme masqué à tort, afin que l'assistant reçoive le bon texte.**

- Après correction, le nom ajouté part en jeton et le terme retiré part en clair, dans le message corrigé.
- Les listes du serveur gardent le dernier mot, si bien qu'un terme de la liste blanche reste masqué même si l'utilisateur le retire.
- Voir [Imposer les listes du serveur](use-cases/enforce-server-lists.md) et le [client d'API](getting-started/api-client.md).

---

## Points de vigilance

Un LLM peut mal répondre, qu'il serve de détecteur, de garde-fou ou de modèle principal. Ces cas définissent ce que `piighost` doit faire, et la story qui le porte.

| Situation | Ce que fait `piighost` | Story |
|---|---|---|
| Le LLM détecteur rend une sortie illisible, un JSON cassé ou un champ manquant | Aucune détection, le message part sans protection | DPO-9 |
| Le LLM garde-fou rend une sortie illisible | Aucun reste signalé, le texte passe | DPO-9 |
| Le LLM détecteur cite une valeur absente du texte | La valeur n'est retrouvée nulle part dans le texte et n'est pas retenue | DPO-1 |
| Le LLM détecteur oublie une valeur | Elle part en clair, sauf si un garde-fou relit le texte | DPO-4 |
| Le texte analysé contient une balise qui imite la zone de données du prompt | La balise est neutralisée avant l'envoi au LLM détecteur | DPO-1 |
| Le LLM principal invente un jeton, `<<PERSON:10>>`{ .placeholder } alors que le fil n'a que `<<PERSON:1>>`{ .placeholder } | Refusé par défaut, retiré ou laissé selon la stratégie | DEV-8 |
| Le LLM principal change la casse ou les chiffres d'un jeton, `<<Person:1>>`{ .placeholder } ou `<<PERSON:01>>`{ .placeholder } | Il n'est pas restauré, et il est traité comme un jeton inventé | DEV-8 |
| Le LLM principal abîme les délimiteurs d'un jeton, `<< PERSON:1 >>` ou `PERSON:1` | Il n'est ni restauré ni reconnu comme jeton, et l'utilisateur le lit tel quel | USER-1 |
| Le LLM principal devine la vraie valeur derrière un jeton et l'écrit | La valeur est traitée comme introduite par l'assistant | DEV-11 |
| L'utilisateur tape lui-même un jeton, `<<PERSON:2>>`{ .placeholder } | Il ne fait pas apparaître la valeur d'une autre personne | DPO-1 |
| Le flux de réponse s'arrête au milieu d'un jeton | Le fragment est rendu tel quel, sans valeur réelle | USER-4 |
| Le LLM principal coupe ou reformule un jeton dans un argument d'outil | Seul un jeton écrit en entier est restauré, l'outil reçoit le reste tel quel | DEV-4 |
| Le serveur d'API est injoignable depuis les hooks Claude Code | Le hook échoue sans bloquer, et le prompt part en clair | DPO-9 |

---

## Voir aussi

- [Cas d'utilisation](use-cases/index.md), les scénarios complets avec leurs cas d'erreur.
- [Glossaire](glossary.md), les termes de la dé-identification.

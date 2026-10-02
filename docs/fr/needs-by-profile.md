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

---

## Exploitant

**EXP-1. En tant qu'exploitant, je veux déployer une API de dé-identification partagée, afin que plusieurs applications utilisent un seul pipeline et un seul modèle.**

- Le serveur démarre sur une configuration du hub et répond aux requêtes de dé-identification.
- Voir [Déployer une API de dé-identification](getting-started/api-server.md).

**EXP-2. En tant qu'exploitant, je veux que la mémoire survive aux redémarrages et soit partagée entre instances, afin qu'une conversation ne perde pas ses jetons.**

- Deux instances rendent le même `<<PERSON:1>>`{ .placeholder } pour `Jean Dupont`{ .pii } dans la même conversation.
- Voir [Déploiement](deployment.md) et [Déploiement multi-instance](multi-instance.md).

**EXP-3. En tant qu'exploitant, je veux fournir les secrets par l'environnement, afin qu'aucune clé ne soit écrite dans un fichier.**

- Quand le chiffrement est configuré mais que ses secrets manquent, le démarrage échoue avec un message clair.
- Une mémoire Redis déclarée sans chiffrement démarre, mais en clair, avec un avertissement de sécurité.
- Voir [Déploiement](deployment.md) et la [référence TOML](configuration/toml.md).

**EXP-4. En tant qu'exploitant, je veux protéger l'API par des clés, une taille de requête maximale et un débit, afin qu'elle ne soit ni ouverte ni abusée.**

- Sans clé configurée, le serveur refuse de démarrer, sauf mode anonyme demandé explicitement.
- Une requête trop grosse ou trop fréquente est refusée.
- Voir [CLI du serveur](reference/api-cli.md) et [Endpoints](reference/api-endpoints.md).

**EXP-5. En tant qu'exploitant, je veux traiter un long document sans que le modèle en tronque la fin, afin qu'aucune valeur en fin de texte ne parte en clair.**

- Une valeur placée au-delà de la fenêtre du modèle est détectée quand le texte est découpé.
- Voir [Limites](limitations.md) et la [référence des détecteurs](reference/detectors.md).

**EXP-6. En tant qu'exploitant, je veux charger une configuration relue depuis le hub par sa référence, afin de ne pas maintenir de copie locale.**

- Une référence épinglée sur un commit est téléchargée au premier démarrage, puis lue depuis le cache.
- Voir la [référence du pipeline](reference/pipeline.md) et le [hub piighost](https://hub.piighost.dev).

---

## Utilisateur de l'application

Ce profil ne manipule jamais `piighost`. Il utilise l'application qu'un développeur a construite avec, et ses besoins disent ce que cette application doit lui garantir.

**UTI-1. En tant qu'utilisateur, je veux lire la réponse avec mes vraies informations, afin de ne jamais voir de jeton.**

- L'utilisateur lit "Bonjour `Jean Dupont`{ .pii }", jamais "Bonjour `<<PERSON:1>>`{ .placeholder }".
- Voir [Suivre une conversation](use-cases/follow-a-conversation.md).

!!! warning "Limite connue"
    Avec les hooks Claude Code, la réponse affichée dans Claude Code garde ses jetons, car aucun hook ne peut réécrire ce texte. Le [proxy compatible Anthropic](examples/anthropic-proxy.md) restaure, lui, la réponse.

**UTI-2. En tant qu'utilisateur, je veux que la conversation reste cohérente de bout en bout, afin que l'assistant ne confonde pas deux personnes.**

- Deux personnes citées gardent chacune leur jeton d'un message à l'autre, et la réponse les nomme correctement.
- Voir [Suivre une conversation](use-cases/follow-a-conversation.md).

**UTI-3. En tant qu'utilisateur, je veux que les actions de l'assistant utilisent mes vraies données, afin que l'e-mail parte à la bonne adresse.**

- L'outil d'envoi reçoit `jean.dupont@exemple.fr`{ .pii }, pas `<<EMAIL:1>>`{ .placeholder }.
- Voir [Laisser un outil agir](use-cases/call-a-tool.md).

!!! warning "Limite connue"
    Le proxy compatible OpenAI ne restaure pas les arguments d'un appel d'outil quand la réponse est streamée. Voir le [proxy compatible OpenAI](examples/openai-proxy.md).

**UTI-4. En tant qu'utilisateur, je veux voir la réponse s'afficher au fil de l'eau sans morceau de jeton, afin de la lire normalement.**

- Un fragment comme "`<<PER`" n'apparaît pas pendant le flux. Seul un flux coupé au milieu d'un jeton rend ce fragment à la fin, sans aucune valeur réelle.
- Voir [Afficher une réponse streamée](use-cases/stream-a-reply.md).

**UTI-5. En tant qu'utilisateur, je veux que les termes publics restent lisibles, afin que la réponse garde son sens.**

- Un nom de ville mis en liste noire reste en clair, et une date de réunion n'est pas masquée par un groupe de motifs génériques.
- Voir [Imposer les listes du serveur](use-cases/enforce-server-lists.md) et [Limites](limitations.md).

---

## Voir aussi

- [Cas d'utilisation](use-cases/index.md), les scénarios complets avec leurs cas d'erreur.
- [Glossaire](glossary.md), les termes de la dé-identification.

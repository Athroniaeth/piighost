---
icon: lucide/message-circle-question
---

# FAQ

??? question "Est-ce vraiment utile d'anonymiser les PII avant d'appeler un LLM ?"
    Oui, et ce indépendamment de `piighost`. Les enjeux (exfiltration vers les providers, réquisition légale, entraînement sur les conversations, conformité RGPD, fuites via RAG et outils) sont détaillés dans [Pourquoi anonymiser ?](../why-anonymize.md). La page est agnostique à la librairie : elle explique pourquoi le problème existe avant de justifier une solution comme `piighost`.

??? question "Mes placeholders doivent-ils avoir ce format `<<PERSON_1>>` ?"
    Non. Le format est piloté par `AnyPlaceholderFactory`. Par défaut `CounterPlaceholderFactory` produit `<<LABEL_N>>`, mais `HashPlaceholderFactory` produit des tags opaques déterministes, `RedactPlaceholderFactory` produit `<LABEL>` sans compteur, et vous pouvez écrire votre propre factory. Voir [Étendre PIIGhost](../extending.md).

??? question "Le LLM voit-il les vraies PII quand il appelle un outil ?"
    Non. Le middleware désanonymise les arguments juste avant l'exécution de l'outil, puis réanonymise la réponse avant qu'elle ne retourne au LLM. L'outil voit les vraies valeurs, le LLM ne voit que les placeholders. Voir le diagramme dans [Architecture](../architecture.md).

??? question "Comment contrôler ce que voit un outil : placeholder ou vraie valeur ?"
    Le paramètre `tool_strategy` de `PIIAnonymizationMiddleware` expose trois modes via l'enum `ToolCallStrategy` :

    - `FULL` (défaut) : l'outil reçoit les vraies valeurs, sa réponse est ré-anonymisée immédiatement via le pipeline complet. À utiliser pour les outils dont la sortie peut contenir de nouvelles PII (bases de données, CRM, recherche web).
    - `INBOUND_ONLY` : l'outil reçoit les vraies valeurs, sa réponse passe brute et est ré-anonymisée paresseusement au prochain `abefore_model`. Moins coûteux quand la sortie n'introduit pas de nouvelles PII.
    - `PASSTHROUGH` : l'outil reçoit les placeholders tels quels. À utiliser quand aucune PII ne doit jamais sortir du middleware, ou quand les outils de l'agent n'en ont pas besoin.

    Le choix du `PlaceholderFactory` importe : `HashPlaceholderFactory` est le plus sûr (tokens déterministes et quasi-sans collision), `CounterPlaceholderFactory` fonctionne bien dans un thread, et `FakerPlaceholderFactory` peut produire des collisions avec de vraies valeurs. `RedactPlaceholderFactory` et `MaskPlaceholderFactory` sont rejetés à la construction par `ThreadAnonymizationPipeline`.

    La règle est portée par le **tag de préservation** attaché à chaque factory (`PreservesIdentity`, `PreservesLabel`, `PreservesShape`, `PreservesNothing`). `PIIAnonymizationMiddleware` n'accepte qu'un `ThreadAnonymizationPipeline[PreservesIdentity]` : le mélange avec une factory plus faible est détecté par ton type-checker avant même d'exécuter le code. Voir [Étendre PIIGhost](../extending.md) pour les détails.

??? question "Que se passe-t-il si le LLM hallucine une PII qui n'était pas dans l'entrée ?"
    Elle n'est **pas** anonymisée par `piighost` : l'entity linking travaille sur les détections issues de l'entrée, pas sur des valeurs inventées. Pour couvrir ce cas, ajoutez une passe de détection sur la sortie du LLM au niveau applicatif. Voir [Limites](../limitations.md).

??? question "Le cache est-il partagé entre threads ou conversations ?"
    Non. Le cache `aiocache` est scopé par `thread_id`. Deux conversations parallèles ne voient pas les placeholders l'une de l'autre, ce qui évite les fuites latérales entre utilisateurs. Le `thread_id` est extrait automatiquement de la config LangGraph.

??? question "Puis-je utiliser `piighost` sans LangChain ?"
    Oui. `AnonymizationPipeline` et `ThreadAnonymizationPipeline` sont utilisables seuls, sans middleware. Voir [Usage basique](../examples/basic.md).

??? question "`piighost` chiffre-t-il les données en cache ?"
    Non. Le cache stocke le mapping `placeholder → valeur` en mémoire (ou dans le backend `aiocache` configuré). Voir [Sécurité](../security.md) pour la liste exhaustive de ce qui est hors périmètre.

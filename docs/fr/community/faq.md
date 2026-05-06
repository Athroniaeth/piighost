---
icon: lucide/message-circle-question
---

# FAQ

??? question "Est-ce vraiment utile d'anonymiser les PII avant d'appeler un LLM ?"
    Oui, et ce indépendamment de `piighost`. Les enjeux (exfiltration vers les providers, réquisition légale, entraînement sur les conversations, conformité RGPD, fuites de données) sont détaillés dans [Pourquoi anonymiser ?](../why-anonymize.md). La page est agnostique à la librairie : elle explique pourquoi le problème existe avant de justifier une solution comme `piighost`.

??? question "Quelles langues sont supportées ?"
    Cela dépend entièrement du détecteur que vous branchez. Le pipeline lui-même est agnostique à la langue. Avec `Gliner2Detector` et un modèle GLiNER2 multilingue, vous obtenez environ 100 langues d'office. Avec un détecteur spaCy, tout ce que spaCy supporte. Avec `RegexDetector`, la langue n'a pas d'importance. Voir [Étendre PIIGhost](../extending.md) pour le catalogue de détecteurs.

??? question "Quelles entités sont détectées d'origine ?"
    Aucune. `piighost` ne livre pas son propre modèle NER, c'est un choix volontaire. Vous apportez le détecteur. Utilisez `ExactMatchDetector` pour des dictionnaires fixes, `RegexDetector` avec `piighost.detector.patterns` (FR_IBAN, FR_NIR, EU_VAT…), `Gliner2Detector` pour du NER ouvert (`PERSON`, `LOCATION`, `ORGANIZATION`, `EMAIL`, n'importe quel label que vous lui demandez), ou composez-les avec `CompositeDetector`.

??? question "Quelle latence est ajoutée par le pipeline ?"
    Le pipeline lui-même est de l'ordre de la milliseconde (regex et lookups). Le vrai coût vient du détecteur. GLiNER2 sur CPU pour un message de 200 tokens, c'est typiquement 50 à 200 ms. Un LLM utilisé comme détecteur, plusieurs centaines de millisecondes. Le pipeline cache les détections par hash de texte via `aiocache`, le contenu répété est gratuit. Une mesure sur votre charge réelle reste recommandée avant de dimensionner la production.

??? question "`piighost` fonctionne-t-il 100 % offline ?"
    Oui, avec un détecteur local (`Gliner2Detector`, détecteur spaCy, `RegexDetector`, `ExactMatchDetector`), aucune donnée ne quitte votre processus. Le middleware ne transmet au LLM que du texte déjà anonymisé. C'est la raison principale de l'adoption de `piighost`, garder un LLM hébergé sous contraintes RGPD sans exfiltrer de PII brutes. Voir [Pourquoi anonymiser ?](../why-anonymize.md) pour le contexte juridique.

??? question "Mes placeholders doivent-ils avoir ce format `<<PERSON:1>>` ?"
    Non. Le format est piloté par `AnyPlaceholderFactory`. Par défaut `LabelCounterPlaceholderFactory` produit `<<LABEL:N>>`, mais `LabelHashPlaceholderFactory` produit `<<LABEL:hash>>`, `LabelPlaceholderFactory` produit `<<LABEL>>` sans compteur, et vous pouvez écrire votre propre factory. Voir [Placeholder factories](../placeholder-factories.md).

??? question "Le LLM voit-il les vraies PII quand il appelle un outil ?"
    Cela dépend de `tool_strategy`. Avec la valeur par défaut (`FULL`), non. Le middleware désanonymise les arguments juste avant l'exécution de l'outil, puis réanonymise la réponse avant qu'elle ne retourne au LLM. L'outil voit les vraies valeurs, le LLM ne voit que les placeholders. Les modes `INBOUND_ONLY` et `PASSTHROUGH` modifient ce comportement, voir la question suivante et [Stratégies d'appel outil](../tool-call-strategies.md). Diagramme complet dans [Architecture](../architecture.md).

??? question "Comment contrôler ce que voit un outil : placeholder ou vraie valeur ?"
    Le paramètre `tool_strategy` de `PIIAnonymizationMiddleware` expose trois modes (`FULL`, `INBOUND_ONLY`, `PASSTHROUGH`) via l'enum `ToolCallStrategy`. Le bon choix dépend de la possibilité que l'outil émette de nouvelles PII et du niveau de cloisonnement souhaité. Voir [Stratégies d'appel outil](../tool-call-strategies.md) pour les compromis et l'arbre de décision, et [Placeholder factories](../placeholder-factories.md) pour la contrainte de factory qui force `PreservesIdentity` dans tous les modes sauf `PASSTHROUGH`.

??? question "Que se passe-t-il si le LLM hallucine une PII qui n'était pas dans l'entrée ?"
    Elle n'est **pas** anonymisée par `piighost` : l'entity linking travaille sur les détections issues de l'entrée, pas sur des valeurs inventées. Pour couvrir ce cas, ajoutez une passe de détection sur la sortie du LLM au niveau applicatif. Voir [Limites](../limitations.md).

??? question "Le cache est-il partagé entre threads ou conversations ?"
    Non. Le cache `aiocache` est scopé par `thread_id`. Deux conversations parallèles ne voient pas les placeholders l'une de l'autre, ce qui évite les fuites latérales entre utilisateurs. Le `thread_id` est extrait automatiquement de la config LangGraph.

??? question "Puis-je utiliser `piighost` sans LangChain ?"
    Oui. `AnonymizationPipeline` et `ThreadAnonymizationPipeline` sont utilisables seuls, sans middleware. Voir [Usage basique](../examples/basic.md).

??? question "`piighost` chiffre-t-il les données en cache ?"
    Non. Le cache stocke le mapping `placeholder → valeur` en mémoire (ou dans le backend `aiocache` configuré). Voir [Sécurité](../security.md) pour la liste exhaustive de ce qui est hors périmètre.

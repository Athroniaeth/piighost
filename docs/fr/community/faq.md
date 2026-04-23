---
icon: lucide/message-circle-question
---

# FAQ

??? question "Pourquoi GLiNER2 plutôt qu'un autre NER ?"
    `piighost` n'est **pas** lié à GLiNER2. C'est juste le détecteur fourni par défaut car il offre un bon compromis multi-langues, zero-shot, et taille raisonnable (~500 Mo).

    Vous pouvez le remplacer par spaCy, un endpoint distant, une liste blanche, ou un ensemble de regex via le protocole [`AnyDetector`](../extending.md). Les autres étapes du pipeline (résolveurs, linker, factory) n'ont pas d'avis sur la source de détection.

??? question "Mes placeholders doivent-ils avoir ce format `<<PERSON_1>>` ?"
    Non. Le format est piloté par `AnyPlaceholderFactory`. Par défaut `CounterPlaceholderFactory` produit `<<LABEL_N>>`, mais `HashPlaceholderFactory` produit des tags opaques déterministes, `RedactPlaceholderFactory` produit `<LABEL>` sans compteur, et vous pouvez écrire votre propre factory. Voir [Étendre PIIGhost](../extending.md).

??? question "Le LLM voit-il les vraies PII quand il appelle un outil ?"
    Non. Le middleware désanonymise les arguments juste avant l'exécution de l'outil, puis réanonymise la réponse avant qu'elle ne retourne au LLM. L'outil voit les vraies valeurs, le LLM ne voit que les placeholders. Voir le diagramme dans [Architecture](../architecture.md).

??? question "Que se passe-t-il si le LLM hallucine une PII qui n'était pas dans l'entrée ?"
    Elle n'est **pas** anonymisée par `piighost` : l'entity linking travaille sur les détections issues de l'entrée, pas sur des valeurs inventées. Pour couvrir ce cas, ajoutez une passe de détection sur la sortie du LLM au niveau applicatif. Voir [Limites](../limitations.md).

??? question "Le cache est-il partagé entre threads ou conversations ?"
    Non. Le cache `aiocache` est scopé par `thread_id`. Deux conversations parallèles ne voient pas les placeholders l'une de l'autre, ce qui évite les fuites latérales entre utilisateurs. Le `thread_id` est extrait automatiquement de la config LangGraph.

??? question "Puis-je utiliser `piighost` sans LangChain ?"
    Oui. `AnonymizationPipeline` et `ThreadAnonymizationPipeline` sont utilisables seuls, sans middleware. Voir [Usage basique](../examples/basic.md).

??? question "`piighost` chiffre-t-il les données en cache ?"
    Non. Le cache stocke le mapping `placeholder → valeur` en mémoire (ou dans le backend `aiocache` configuré). Voir [Sécurité](../security.md) pour la liste exhaustive de ce qui est hors périmètre.

---
icon: lucide/message-circle-question
---

# FAQ

??? question "Est-ce vraiment utile de dé-identifier les PII avant d'appeler un LLM ?"
    Oui, et ce indépendamment de `piighost`. Les enjeux (exfiltration vers les providers, réquisition légale, entraînement sur les conversations, conformité RGPD, fuites de données) sont détaillés dans [Pourquoi dé-identifier ?](../why-anonymize.md). La page est agnostique à la librairie. Elle explique pourquoi le problème existe avant de justifier une solution comme `piighost`.

??? question "Quelles langues sont supportées ?"
    Cela dépend entièrement du détecteur que vous branchez. Le pipeline lui-même est agnostique à la langue. Avec un détecteur `gliner2` et un modèle GLiNER2 multilingue, vous obtenez environ 100 langues d'office. Avec un détecteur `spacy`, tout ce que spaCy supporte. Avec un détecteur `regex`, la langue n'a pas d'importance. Voir [Étendre PIIGhost](../extending.md) pour le catalogue de détecteurs.

??? question "Quelles entités sont détectées d'origine ?"
    Aucune. `piighost` ne livre pas son propre modèle NER, c'est un choix volontaire. Vous apportez le détecteur. Utilisez un détecteur `exact` pour des dictionnaires fixes, un détecteur `regex` avec un catalogue prêt à l'emploi (`generic`, `us`, `eu`, `fr`) ou vos propres motifs, un détecteur `gliner2` pour du NER ouvert (`PERSON`, `LOCATION`, `ORGANIZATION`, `EMAIL`, n'importe quel label que vous lui demandez), ou composez-les avec un détecteur `composite`.

??? question "Le détecteur regex valide-t-il les checksums (Luhn, IBAN, NIR) ?"
    Non, par conception. Un validateur de checksum rejette une valeur dont les chiffres ne calculent pas, ce que produit exactement du bruit d'OCR ou une faute de frappe. La rejeter ferait fuiter la PII qu'il était censé attraper. Le détecteur `regex` matche sur la forme seule et penche vers la sur-détection, la direction sûre pour la dé-identification. Si vous devez resserrer un match, ajoutez un motif plus strict plutôt qu'un validateur.

??? question "Comment configurer un pipeline ?"
    Écrivez un fichier TOML ou JSON décrivant chaque étage, puis chargez-le. `load_pipeline` construit un pipeline sans état, `load_thread_pipeline` construit un pipeline de thread avec une mémoire de conversation, et le suffixe du fichier choisit le parser. Chaque section et chaque `type` de composant sont dans la [référence de configuration](../configuration/toml.md). L'extra `config` est requis (`pip install piighost[config]`).

??? question "Quelle latence est ajoutée par le pipeline ?"
    Le pipeline lui-même est de l'ordre de la milliseconde (regex et lookups). Le vrai coût vient du détecteur. GLiNER2 sur CPU pour un message de 200 tokens, c'est typiquement 50 à 200 ms. Un LLM utilisé comme détecteur, plusieurs centaines de millisecondes. Un pipeline de thread cache les détections de chaque message, donc renvoyer un message dans un thread évite la détection. Une mesure sur votre charge réelle reste recommandée avant de dimensionner la production.

??? question "`piighost` fonctionne-t-il 100 % offline ?"
    Oui. Avec un détecteur local (`gliner2`, `spacy`, `regex`, `exact`), aucune donnée ne quitte votre processus. Le middleware ne transmet au LLM que du texte déjà dé-identifié. C'est la raison principale de l'adoption de `piighost`, garder un LLM hébergé sous contraintes RGPD sans exfiltrer de PII brutes. Voir [Pourquoi dé-identifier ?](../why-anonymize.md) pour le contexte juridique.

??? question "Mes placeholders doivent-ils avoir ce format `<<PERSON:1>>` ?"
    Non. Le format est piloté par la placeholder factory choisie dans `[anonymizer.placeholder]`. `label_counter` produit `<<PERSON:1>>`{ .placeholder }, `label_hash` produit `<<PERSON:a1b2c3d4>>`{ .placeholder }, `label` produit `<<PERSON>>`{ .placeholder } sans compteur, `mask` produit `P***`{ .placeholder }, et vous pouvez écrire votre propre factory. Voir [Placeholder factories](../placeholder-factories.md).

??? question "Puis-je obtenir de fausses valeurs réalistes plutôt que des tokens ?"
    Pas encore. Une factory Faker qui émet des valeurs réalistes (un nom plausible à la place de `Patrick`{ .pii }) est sur la [roadmap](../roadmap.md) mais pas réimplémentée en v2. Aujourd'hui les factories émettent des tokens synthétiques ou des masques, jamais une valeur qui ressemble à du vrai.

??? question "Le LLM voit-il les vraies PII quand il appelle un outil ?"
    Cela dépend de la stratégie d'appel outil. Avec la valeur par défaut (`FULL`), non. Le middleware restaure les arguments juste avant l'exécution de l'outil, puis re-dé-identifie la réponse avant qu'elle ne retourne au LLM. L'outil voit les vraies valeurs, le LLM ne voit que les placeholders. Les modes `INPUT`, `OUTPUT` et `PASSTHROUGH` modifient ce comportement, voir la question suivante et [Stratégies d'appel outil](../tool-call-strategies.md). Diagramme complet dans [Architecture](../architecture.md).

??? question "Comment contrôler ce que voit un outil : placeholder ou vraie valeur ?"
    La stratégie d'appel outil de `PIIAnonymizationMiddleware` expose quatre modes (`INPUT`, `OUTPUT`, `FULL`, `PASSTHROUGH`). Le bon choix dépend de la possibilité que l'outil émette de nouvelles PII et du niveau de cloisonnement souhaité. Voir [Stratégies d'appel outil](../tool-call-strategies.md) pour les compromis et l'arbre de décision, et [Placeholder factories](../placeholder-factories.md) pour la contrainte de factory, le middleware exige une factory qui préserve l'identité et reste reconnaissable.

??? question "Que se passe-t-il si le LLM hallucine une PII qui n'était pas dans l'entrée ?"
    Elle n'est **pas** dé-identifiée par `piighost`. Le linking d'entités travaille sur les détections issues de l'entrée, pas sur des valeurs inventées. Un guard de PII résiduelle peut re-vérifier la sortie et la refuser, voir la section guard de la [référence de configuration](../configuration/toml.md) et [Limites](../limitations.md).

??? question "La mémoire de conversation est-elle partagée entre threads ?"
    Non. La mémoire est scopée par `thread_id`. Deux conversations parallèles ne voient pas les tokens l'une de l'autre, ce qui évite les fuites latérales entre utilisateurs. Le `thread_id` est extrait automatiquement de la config LangGraph.

??? question "Comment faire tourner plus d'un worker derrière un load balancer ?"
    Utilisez la mémoire de conversation Redis, partagée par tous les workers. La mémoire en RAM est locale au processus, donc deux workers numéroteraient la même valeur différemment en pleine conversation. Voir [Déploiement multi-instance](../multi-instance.md) pour le piège et la parade, et [Déployer un pipeline en production](../deployment.md) pour la mise en place complète.

??? question "Puis-je utiliser `piighost` sans LangChain ?"
    Oui. Les pipelines sans état et de thread sont utilisables seuls, sans middleware. Voir [Comment dé-identifier un texte et le restaurer](../examples/basic.md).

??? question "`piighost` chiffre-t-il les données stockées ?"
    La mémoire de conversation Redis, oui. Elle chiffre chaque valeur stockée en AES-GCM et hache chaque clé, en lisant son pepper et sa clé de cipher dans l'environnement. La mémoire en RAM ne chiffre rien et sert au développement seulement. Voir [Sécurité](../security.md) pour le modèle de menace au repos.

??? question "Comment tracer ce que fait le pipeline ?"
    Via OpenTelemetry. Le pipeline émet un span par étage vers le `TracerProvider` OTel que votre application a configuré, et ne fait lui-même aucune corrélation de backend, cela relève de la configuration OTel du déploiement. Voir [Observation](../observation.md). L'extra `observation` est requis.

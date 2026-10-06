---
icon: lucide/message-circle-question
description: FAQ de piighost. Cacher des données personnelles à l'API OpenAI, comparer à Presidio, anonymiser ou pseudonymiser pour ChatGPT, ce que demande le RGPD.
---

# FAQ

## Est-ce vraiment utile de dé-identifier les données confidentielles avant d'appeler un LLM ?

Oui, et ce indépendamment de `piighost`. Les enjeux (exfiltration vers les providers, réquisition légale, entraînement sur les conversations, conformité RGPD, fuites de données) sont détaillés dans [Pourquoi dé-identifier ?](../why-anonymize.md). La page est agnostique à la librairie. Elle explique pourquoi le problème existe avant de justifier une solution comme `piighost`.

## Comment cacher des données personnelles à l'API OpenAI ?

Placez `piighost` entre votre code et l'API. Chaque valeur est remplacée par un placeholder comme `<<PERSON:1>>`{ .placeholder } avant que la requête ne parte, puis restaurée dans la réponse.

- Si votre code appelle le modèle via LangChain, Pydantic AI ou LlamaIndex, ajoutez l'intégration correspondante. Voir [Middleware LangChain](../getting-started/langchain.md), [Intégration Pydantic AI](../examples/pydantic-ai.md) et [Intégration LlamaIndex](../examples/llama-index.md).
- Si votre code appelle directement le SDK OpenAI, faites pointer son `base_url` vers le proxy compatible OpenAI de `piighost-api`. Voir [Proxy compatible OpenAI](../examples/openai-proxy.md).

## En quoi `piighost` diffère-t-il de Presidio ?

Presidio détecte les données personnelles dans un texte et les remplace avec un opérateur, comme un masque ou un jeton chiffré. `piighost` prend en charge ce qui vient après la détection dans une conversation avec un LLM. Il garde le même placeholder sur toute la conversation, donne les vraies valeurs aux outils, et restaure la réponse, flux compris. Les deux se combinent, puisque `piighost` peut utiliser Presidio comme détecteur. Voir [Comment piighost se compare](../comparison.md#piighost-et-presidio), et [Migrer depuis PresidioReversibleAnonymizer](../examples/migrate-from-presidio-reversible-anonymizer.md) si vous utilisiez l'enveloppe LangChain.

## `piighost` fonctionne-t-il avec OpenAI, Anthropic, Mistral ou un modèle local ?

Oui. Le pipeline réécrit le texte avant et après l'appel au modèle, et n'appelle lui-même aucun modèle, sauf si vous choisissez un LLM comme détecteur ou comme garde-fou. Tout modèle que votre framework prend en charge convient, une API hébergée comme un modèle sur votre propre matériel. Le serveur `piighost-api` fournit aussi un proxy compatible OpenAI et un proxy compatible Anthropic. Le proxy compatible OpenAI transmet à tout fournisseur compatible OpenAI, y compris un serveur vLLM auto-hébergé. Voir [Proxy compatible OpenAI](../examples/openai-proxy.md) et [Proxy compatible Anthropic](../examples/anthropic-proxy.md).

## La pseudonymisation suffit-elle pour le RGPD ?

Non. Les données pseudonymisées restent des données personnelles pour qui détient la correspondance, comme le dit le considérant 26 du RGPD. Le règlement s'applique donc toujours à tout le traitement, c'est-à-dire la base légale, l'information des personnes, la sécurité de la correspondance, et une AIPD quand le risque est élevé. La pseudonymisation fait partie des mesures que le RGPD cite, aux articles 25 et 32, parce qu'elle réduit le risque. Voir [Anonymisation, pseudonymisation, caviardage, masquage](../anonymization-vs-pseudonymization.md), [Conformité](../compliance.md) et [Comment documenter `piighost` dans une AIPD](../dpia.md).

## Comment anonymiser des données avant de les envoyer à ChatGPT ?

Ce que fait `piighost` est une pseudonymisation, pas une anonymisation. Chaque valeur devient un placeholder comme `<<PERSON:1>>`{ .placeholder } avant que le texte n'atteigne le modèle, et une correspondance gardée de votre côté restaure `Patrick`{ .pii } dans la réponse. Une anonymisation effacerait la valeur pour de bon, et la réponse ne pourrait plus nommer la personne. Voir [Anonymisation, pseudonymisation, caviardage, masquage](../anonymization-vs-pseudonymization.md) pour la différence.

`piighost` agit sur les appels à l'API du modèle, via une intégration ou le proxy compatible OpenAI, comme le décrit [Comment cacher des données personnelles à l'API OpenAI ?](#comment-cacher-des-donnees-personnelles-a-lapi-openai). Il ne se branche pas sur l'application web ChatGPT.

## Quelles langues sont supportées ?

Cela dépend entièrement du détecteur que vous branchez. Le pipeline lui-même est agnostique à la langue. Avec un détecteur `gliner2` et un modèle GLiNER2 multilingue, vous obtenez environ 100 langues d'office. Avec un détecteur `spacy`, tout ce que spaCy supporte. Avec un détecteur `regex`, la langue n'a pas d'importance. Voir [Étendre piighost](../extending.md) pour le catalogue de détecteurs.

## Quelles entités sont détectées d'origine ?

Aucune. `piighost` ne livre pas son propre modèle NER, c'est un choix volontaire. Vous apportez le détecteur. Utilisez un détecteur `exact` pour des dictionnaires fixes, un détecteur `regex` avec un groupe tiré du catalogue (`catalog:piighost/generic`, `catalog:piighost/us`, `catalog:piighost/eu`, `catalog:piighost/fr`) ou vos propres motifs, un détecteur `gliner2` pour du NER ouvert (`PERSON`, `LOCATION`, `ORGANIZATION`, `EMAIL`, n'importe quel label que vous lui demandez), ou composez-les avec un détecteur `composite`.

## Le détecteur regex valide-t-il les checksums (Luhn, IBAN, NIR) ?

Non, par conception. Un validateur de checksum rejette une valeur dont les chiffres ne calculent pas. Or c'est exactement ce que produit du bruit d'OCR ou une faute de frappe. Rejeter cette valeur ferait fuiter la PII que le validateur était censé attraper. Le détecteur `regex` matche sur la forme seule et penche vers la sur-détection, la direction sûre pour la dé-identification. Si vous devez resserrer un match, ajoutez un motif plus strict plutôt qu'un validateur.

## Comment configurer un pipeline ?

Écrivez un fichier TOML ou JSON décrivant chaque étage, puis chargez-le. `load_pipeline` construit un pipeline sans état. `load_thread_pipeline` construit un pipeline de conversation avec une mémoire de conversation. Le suffixe du fichier choisit le parser. Chaque section et chaque `type` de composant sont dans la [référence de configuration](../configuration/toml.md). L'extra `config` est requis (`pip install "piighost[config]"`).

## Quelle latence est ajoutée par le pipeline ?

Le pipeline lui-même est de l'ordre de la milliseconde (regex et lookups). Le vrai coût vient du détecteur. GLiNER2 sur CPU pour un message de 200 tokens, c'est typiquement 50 à 200 ms. Un LLM utilisé comme détecteur, plusieurs centaines de millisecondes. Renvoyer un message dans une conversation évite la détection, parce qu'un pipeline de conversation garde en cache les détections de chaque message. Une mesure sur votre charge réelle reste recommandée avant de dimensionner la production.

## `piighost` fonctionne-t-il 100 % offline ?

Oui. Avec un détecteur local (`gliner2`, `spacy`, `regex`, `exact`), aucune donnée ne quitte votre processus. Un groupe du catalogue épinglé sur un commit est récupéré à la première construction, puis relu depuis le cache sur disque, et cette récupération n'envoie aucun texte au catalogue. Le middleware ne transmet au LLM que du texte déjà dé-identifié. Garder un LLM hébergé sous contraintes RGPD sans exfiltrer de PII brutes est la raison principale de l'adoption de `piighost`. Voir [Pourquoi dé-identifier ?](../why-anonymize.md) pour le contexte juridique.

## Mes placeholders doivent-ils avoir ce format `<<PERSON:1>>` ?

Non. Le format est piloté par la placeholder factory choisie dans `[anonymizer.placeholder]`. `label_counter` produit `<<PERSON:1>>`{ .placeholder }, `label_hash` produit `<<PERSON:a1b2c3d4>>`{ .placeholder }, `label` produit `<<PERSON>>`{ .placeholder } sans compteur, `mask` produit `P***`{ .placeholder }, et vous pouvez écrire votre propre factory. Voir [Fabriques de placeholders](../placeholder-factories.md).

## Puis-je obtenir de fausses valeurs réalistes plutôt que des jetons ?

Non, et ce n'est pas prévu. Une factory Faker, qui émettrait un nom plausible à la place de `Patrick`{ .pii }, est écartée à dessein dans la [roadmap](../roadmap.md). Deux personnes pourraient tirer le même faux nom, et un faux pourrait coïncider avec une vraie valeur, donc la restauration ne serait plus fiable. Aujourd'hui les factories émettent des jetons synthétiques ou des masques, jamais une valeur qui ressemble à du vrai.

## Le LLM voit-il les vraies données confidentielles quand il appelle un outil ?

Cela dépend de la stratégie d'appel outil. Avec la valeur par défaut (`FULL`), non. Le middleware restaure les arguments juste avant l'exécution de l'outil, puis dé-identifie à nouveau la réponse avant qu'elle ne retourne au LLM. L'outil voit les vraies valeurs, le LLM ne voit que les placeholders. Les modes `INPUT`, `OUTPUT` et `PASSTHROUGH` modifient ce comportement, voir la question suivante et [Stratégies d'appel outil](../tool-call-strategies.md). Diagramme complet dans [Architecture](../architecture.md).

## Comment contrôler ce que voit un outil : placeholder ou vraie valeur ?

La stratégie d'appel outil de `PIIAnonymizationMiddleware` expose quatre modes (`INPUT`, `OUTPUT`, `FULL`, `PASSTHROUGH`). Le bon choix dépend de la possibilité que l'outil émette de nouvelles données confidentielles et du niveau de cloisonnement souhaité. Voir [Stratégies d'appel outil](../tool-call-strategies.md) pour les compromis et l'arbre de décision. Le middleware exige aussi une factory qui préserve l'identité et reste reconnaissable, voir [Fabriques de placeholders](../placeholder-factories.md) pour cette contrainte.

## Que se passe-t-il si le LLM hallucine une donnée confidentielle qui n'était pas dans l'entrée ?

Elle n'est **pas** dé-identifiée par `piighost`. Le linking d'entités travaille sur les détections issues de l'entrée, pas sur des valeurs inventées. Un guard de données confidentielles résiduelles peut re-vérifier la sortie et la refuser, voir la section guard de la [référence de configuration](../configuration/toml.md) et [Limites](../limitations.md).

## La mémoire de conversation est-elle partagée entre conversations ?

Non. La mémoire est scopée par `thread_id`. Deux conversations parallèles ne voient pas les jetons l'une de l'autre. Ce cloisonnement évite les fuites latérales entre utilisateurs. Le `thread_id` est extrait automatiquement de la config LangGraph.

## Comment faire tourner plus d'un worker derrière un load balancer ?

Utilisez la mémoire de conversation Redis, partagée par tous les workers. La mémoire en RAM est locale au processus, donc deux workers numéroteraient la même valeur différemment en pleine conversation. Voir [Déploiement multi-instance](../multi-instance.md) pour le piège et la parade, et [Déploiement](../deployment.md) pour la mise en place complète.

## Puis-je utiliser `piighost` sans LangChain ?

Oui. Les pipelines sans état et de conversation sont utilisables seuls, sans middleware. Voir [Comment dé-identifier un texte et le restaurer](../examples/basic.md).

## `piighost` chiffre-t-il les données stockées ?

La mémoire de conversation Redis, oui. Elle chiffre chaque valeur stockée en AES-GCM et hache chaque clé, en lisant son pepper et sa clé de cipher dans l'environnement. La mémoire en RAM ne chiffre rien et sert au développement seulement. Voir [Sécurité](../security.md) pour le modèle de menace au repos.

## Comment tracer ce que fait le pipeline ?

Via OpenTelemetry. Le pipeline émet un span par étage vers le `TracerProvider` OTel que votre application a configuré. Il ne fait lui-même aucune corrélation de backend, parce que cette corrélation relève de la configuration OTel du déploiement. Voir [Observation](../observation.md). L'extra `observation` est requis.

---
icon: lucide/shield
---

# PIIGhost

`piighost` est une librairie Python qui permet de protéger vos données personnelles (PII) dans les conversations avec les LLM via de la dé-identification. Les valeurs sensibles sont cachées avant l'envoi, puis restaurées dans la réponse. Les intégrations LangChain, Pydantic AI, LlamaIndex et Claude Code sont fournies, ainsi qu'un connecteur d'API OpenAI et Anthropic.

Cette dé-identification repère les PII grâce à des détecteurs modulables (regex, NER, LLM) et remplace chaque valeur par un placeholder, le token qui prend sa place. Par exemple :

- `John Doe`{ .pii } devient `<<PERSON:1>>`{ .placeholder }
- `john.doe@example.com`{ .pii } devient `<<EMAIL:1>>`{ .placeholder }

Ce placeholder reste le même d'un message à l'autre avec le pipeline conversationnel, qui garde la correspondance entre une valeur et son placeholder sur toute la conversation. Si `john.doe@example.com`{ .pii } réapparaît trois messages plus tard, le placeholder reste `<<EMAIL:1>>`{ .placeholder }, ce qui permet au LLM de suivre le fil.

Le LLM ne reçoit donc que du texte dé-identifié. Quand il retourne des placeholders, par exemple en répondant "Bonjour `<<PERSON:1>>`{ .placeholder }", `piighost` les remplace par les vraies valeurs. L'utilisateur voit `John Doe`{ .pii } et ne voit jamais la dé-identification.

La même mécanique protège les agents qui appellent des outils. Avec le middleware LangChain, un outil qui a besoin de la vraie adresse mail la reçoit en clair, alors que le LLM qui la fournit n'écrit que `<<EMAIL:1>>`{ .placeholder }.

![Un utilisateur discute avec un agent, les valeurs PII sont remplacées par des placeholders avant d'atteindre le LLM puis restaurées pour l'utilisateur et pour les appels d'outils.](assets/deid-chat-light.svg#only-light)
![Un utilisateur discute avec un agent, les valeurs PII sont remplacées par des placeholders avant d'atteindre le LLM puis restaurées pour l'utilisateur et pour les appels d'outils.](assets/deid-chat-dark.svg#only-dark)

*Aller-retour complet d'une requête agent. L'utilisateur et l'outil voient les vraies valeurs, le LLM ne voit que des placeholders.*
{ .figure-caption }

!!! note "Dé-identification réversible"
    Cette correspondance conservée fait de la dé-identification une pseudonymisation au sens du RGPD, pas une anonymisation définitive. Avec le pipeline conversationnel, les valeurs réelles restent stockées le temps de la conversation et doivent être protégées en conséquence.

## Pourquoi dé-identifier ?

Un LLM en cloud (GPT, Claude, Gemini) reçoit chaque information que vous lui envoyez, PII de vos utilisateurs comprises. Dé-identifier en amont découple le choix du LLM de la sensibilité du contenu. Quand les PII n'atteignent jamais le LLM, le fournisseur cesse d'être une décision de confidentialité et redevient une question de qualité, de coût et de latence.

Pour aller plus loin :

- [Pourquoi dé-identifier ?](why-anonymize.md), le spectre des fournisseurs, le détail juridique (CLOUD Act, FISA 702, Schrems II) et les cas d'usage
- [Comment PIIGhost se compare](comparison.md), les alternatives et leurs compromis

## Par où commencer

<div class="grid cards" markdown>

-   :lucide-rocket: __Démarrer__

    ---

    Installer et prendre `piighost` en main.

    - [Installation](getting-started/installation.md)
    - [Quickstart](getting-started/quickstart.md)
    - [Premier pipeline](getting-started/first-pipeline.md)
    - [Pipeline conversationnel](getting-started/conversation.md)
    - [Middleware LangChain](getting-started/langchain.md)

-   :lucide-wrench: __Recettes__

    ---

    Résoudre une tâche précise.

    - [Usage basique](examples/basic.md)
    - [Intégration LangChain](examples/langchain.md)
    - [Détecteurs prêts à l'emploi](examples/detectors.md)
    - [Étendre PIIGhost](extending.md)
    - [Tests](examples/testing.md)

-   :lucide-book-open: __Référence__

    ---

    La documentation d'API complète.

    - [Anonymizer](reference/anonymizer.md)
    - [Pipeline](reference/pipeline.md)
    - [LangChain](reference/langchain.md)
    - [Détecteurs](reference/detectors.md)

-   :lucide-layers: __Concepts__

    ---

    Comprendre les choix de conception.

    - [Pourquoi dé-identifier ?](why-anonymize.md)
    - [Architecture](architecture.md)
    - [Placeholder factories](placeholder-factories.md)
    - [Sécurité](security.md)

</div>

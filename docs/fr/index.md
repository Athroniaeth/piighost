---
icon: lucide/shield
---

# piighost

`piighost` est une librairie Python qui permet de protéger vos données confidentielles (données personnelles ou PII, secrets) dans les conversations avec les LLM, grâce à la dé-identification. Les valeurs sensibles sont cachées avant l'envoi, puis restaurées dans la réponse. Les intégrations LangChain, Pydantic AI, LlamaIndex et Claude Code sont fournies, ainsi qu'un connecteur d'API OpenAI et Anthropic.

Cette dé-identification repère les données confidentielles grâce à des détecteurs modulables (regex, NER, LLM) et remplace chaque valeur par un placeholder, le jeton qui prend sa place. Par exemple :

- `John Doe`{ .pii } devient `<<PERSON:1>>`{ .placeholder }
- `john.doe@example.com`{ .pii } devient `<<EMAIL:1>>`{ .placeholder }

Avec le pipeline conversationnel, ce placeholder reste le même d'un message à l'autre. Ce pipeline garde la correspondance entre une valeur et son placeholder sur toute la conversation. Si `john.doe@example.com`{ .pii } réapparaît trois messages plus tard, le placeholder reste `<<EMAIL:1>>`{ .placeholder }, et le LLM peut ainsi suivre le fil.

Le LLM ne reçoit donc que du texte dé-identifié. Quand il retourne des placeholders, par exemple en répondant "Bonjour `<<PERSON:1>>`{ .placeholder }", `piighost` les remplace par les vraies valeurs. L'utilisateur voit `John Doe`{ .pii } et ne voit jamais la dé-identification.

La même mécanique protège les agents qui appellent des outils. Avec le middleware LangChain, un outil qui a besoin de la vraie adresse mail la reçoit en clair, alors que le LLM qui la fournit n'écrit que `<<EMAIL:1>>`{ .placeholder }.

![Un utilisateur discute avec un agent, les valeurs confidentielles sont remplacées par des placeholders avant d'atteindre le LLM puis restaurées pour l'utilisateur et pour les appels d'outils.](assets/deid-chat-light.svg#only-light)
![Un utilisateur discute avec un agent, les valeurs confidentielles sont remplacées par des placeholders avant d'atteindre le LLM puis restaurées pour l'utilisateur et pour les appels d'outils.](assets/deid-chat-dark.svg#only-dark)

*Aller-retour complet d'une requête agent. L'utilisateur et l'outil voient les vraies valeurs, le LLM ne voit que des placeholders.*
{ .figure-caption }

!!! note "Dé-identification réversible"
    Cette correspondance conservée fait de la dé-identification une pseudonymisation au sens du RGPD, pas une anonymisation définitive. Avec le pipeline conversationnel, les valeurs réelles restent stockées le temps de la conversation et doivent être protégées en conséquence.

## Pourquoi dé-identifier ?

Un LLM en cloud (GPT, Claude, Gemini) reçoit chaque information que vous lui envoyez, PII de vos utilisateurs comprises. Dé-identifier en amont découple le choix du LLM de la sensibilité du contenu. Quand les données confidentielles n'atteignent jamais le LLM, le choix du fournisseur cesse d'être une décision de confidentialité. Il redevient une question de qualité, de coût et de latence.

Le spectre des fournisseurs, le détail juridique (CLOUD Act, FISA 702, Schrems II) et les cas d'usage sont dans [Pourquoi dé-identifier ?](why-anonymize.md). Les alternatives et leurs compromis sont dans [Comment piighost se compare](comparison.md).

## Par où commencer

<div class="grid cards" markdown>

-   :lucide-rocket: __Démarrer__

    ---

    Installer et prendre `piighost` en main.

    - [Installation](getting-started/installation.md)
    - [Démarrage rapide](getting-started/quickstart.md)
    - [Premier pipeline](getting-started/first-pipeline.md)
    - [Pipeline conversationnel](getting-started/conversation.md)
    - [Fichier de configuration](getting-started/configuration.md)
    - [Middleware LangChain](getting-started/langchain.md)
    - [Serveur d'API](getting-started/api-server.md)
    - [Client distant](getting-started/api-client.md)

-   :lucide-wrench: __Recettes__

    ---

    Résoudre une tâche précise.

    - [Dé-identifier et restaurer un texte](examples/basic.md)
    - [Détecteurs prêts à l'emploi](examples/detectors.md)
    - [Masquer ou laisser en clair](examples/overrides.md)
    - [Étendre piighost](extending.md)
    - [Tester sans modèle](examples/testing.md)
    - [Déploiement](deployment.md)
    - [Déploiement multi-instance](multi-instance.md)

-   :lucide-plug: __Intégrations__

    ---

    Brancher `piighost` dans un agent, un framework ou un client.

    - [Intégration LangChain](examples/langchain.md)
    - [Intégration Pydantic AI](examples/pydantic-ai.md)
    - [Intégration LlamaIndex](examples/llama-index.md)
    - [Hooks Claude Code](examples/claude-code.md)
    - [Proxy compatible OpenAI](examples/openai-proxy.md)
    - [Proxy compatible Anthropic](examples/anthropic-proxy.md)

-   :lucide-book-open: __Référence__

    ---

    La documentation d'API complète.

    - [Anonymizer](reference/anonymizer.md)
    - [Pipeline](reference/pipeline.md)
    - [Modèles de données](reference/models.md)
    - [LangChain](reference/langchain.md)
    - [Détecteurs](reference/detectors.md)
    - [Garde-fous](reference/guard-rails.md)
    - [Mémoire de conversation](reference/memory.md)
    - [Exceptions](reference/errors.md)
    - [CLI](reference/cli.md)
    - [Endpoints de l'API](reference/api-endpoints.md)
    - [CLI du serveur](reference/api-cli.md)
    - [Référence de configuration](configuration/toml.md)

-   :lucide-layers: __Concepts__

    ---

    Comprendre les choix de conception.

    - [Architecture](architecture.md)
    - [Fabriques de placeholders](placeholder-factories.md)
    - [Sécurité](security.md)

</div>

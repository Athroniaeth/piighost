---
icon: lucide/wrench
---

# Modifier le code de piighost

Cette page s'adresse à qui change le code de `piighost`. Chaque changement courant y renvoie d'abord à la page de la documentation métier qui décrit les règles concernées, puis aux fichiers et aux tests à ouvrir. Lisez la règle avant de toucher au code qui l'applique.

## Démarrer en local

- **Pile** : Python 3.11 ou plus, gestionnaire `uv`. Le cœur ne dépend que de `typing-extensions`. Tout le reste est un extra de `pyproject.toml` (`langchain`, `redis`, `gliner2`, `config`…), et `all` les réunit.
- **Installer** : `uv sync` à la racine du dépôt.
- **Tester** : `uv run pytest`, puis `make lint` avant toute fusion. Détails dans [Lancer et écrire les tests](../../../openwiki/fr/tests/run-and-write-tests.md).
- **Essayer** : `uv run piighost anonymize "Écrivez à claire.dubois@example.com"`. La première exécution télécharge le catalogue `hub:piighost/generic`.
- **Services** : aucun pour les tests. Redis, une base SQL ou `piighost-api` ne servent qu'en exploitation. Voir [Stocker les conversations](../../../openwiki/fr/operations/storage-and-encryption.md) et [Configurer un pipeline](../../../openwiki/fr/operations/configuration-and-hub.md).
- **Exemples** : scripts autonomes dans `examples/`, lancés par `uv run examples/<script>.py`.

## Trouver où modifier

| Type de changement | Lire d'abord | Puis |
|---|---|---|
| Ajouter un détecteur | [Ajouter ou remplacer un composant](../../../openwiki/fr/architecture/ports-and-extension.md#ajouter-un-détecteur) | `components/detector/regex.py` ou `components/detector/ner/spacy.py`, `config/models/detector_model.py`, `tests/components/detector/test_contract.py` |
| Changer l'arbitrage des chevauchements | [Protéger un message](../../../openwiki/fr/processes/protect-a-message.md) | `components/overlap_resolver/`, `tests/components/overlap_resolver/` |
| Changer la forme des jetons | [Glossaire](../../../openwiki/fr/glossary.md), [Ajouter ou remplacer un composant](../../../openwiki/fr/architecture/ports-and-extension.md#jetons-typés) | `components/placeholder/`, `tags.py`, `tests/components/placeholder/` |
| Toucher à la conversation ou à la correction humaine | [Suivre une conversation](../../../openwiki/fr/processes/follow-a-conversation.md) | `pipeline/thread.py`, `tests/pipeline/test_thread.py`, `test_thread_hitl.py` |
| Modifier la liste blanche ou la liste noire | [Imposer une liste blanche et une liste noire](../../../openwiki/fr/processes/impose-a-whitelist-and-blacklist.md) | `components/override/`, `tests/components/override/test_override.py` |
| Changer le traitement des appels d'outil | [Laisser un outil agir](../../../openwiki/fr/processes/let-a-tool-act.md) | `integrations/langchain/middleware.py` (`awrap_tool_call`), `integrations/pydantic_ai/hooks.py`, `tests/integrations/langchain/test_middleware.py` |
| Changer la restauration en flux | [Afficher une réponse streamée](../../../openwiki/fr/processes/show-a-streamed-reply.md) | `components/placeholder/streaming.py`, `tests/components/placeholder/test_streaming*.py` |
| Ajouter un test d'acceptation | [Tests d'acceptation](../../../openwiki/fr/tests/acceptance-tests.md) | `tests/acceptance/`, un identifiant `AT-<besoin>-<n>` dans la docstring |
| Ajouter une clé de configuration | [Configurer un pipeline](../../../openwiki/fr/operations/configuration-and-hub.md) | `config/models/`, `config/settings.py`, `tests/config/` |
| Modifier la commande `piighost` | [Configurer un pipeline](../../../openwiki/fr/operations/configuration-and-hub.md#contrôler-depuis-la-ligne-de-commande) | `cli/__init__.py`, `tests/cli/test_cli.py` |
| Ajouter un stockage ou changer le chiffrement | [Stocker les conversations](../../../openwiki/fr/operations/storage-and-encryption.md) | `conversation_memory/`, `crypto/`, `tests/conversation_memory/` |
| Changer le middleware LangChain ou une autre intégration | [Brancher la protection sur un agent](../../../openwiki/fr/integrations/agents-and-tools.md) | `integrations/`, `integrations/_deidentify.py`, `tests/integrations/` |
| Ajouter un outil aux hooks Claude Code | [Brancher la protection sur un agent](../../../openwiki/fr/integrations/agents-and-tools.md) | `integrations/claude_code/hooks.py` (`_TOOL_OUTPUT_TEXT_FIELDS`), `tests/integrations/test_claude_code_hooks.py` |

Pour le déroulé d'une contribution (branche, commits, revue), voir [Contribuer](contributing.md).

---
type: guide
title: Démarrer avec le wiki PIIGhost
description: Point d'entrée du wiki PIIGhost, qui oriente selon le besoin (comprendre une règle de protection ou modifier le code), résume le trajet d'un message et liste les pièges qui traversent plusieurs processus.
tags: [quickstart, overview, routing, pii, de-identification]
sources:
  - id: openwiki-source-05ccef8d4cf1698187f20464
    resource: repo://pyproject.toml
  - id: openwiki-source-edd617907d8703b014c2a6c7
    resource: repo://src/piighost/cli/__init__.py
  - id: openwiki-source-9703fc61b3e278e6ef8403ff
    resource: repo://src/piighost/integrations/claude_code/hooks.py
  - id: openwiki-source-85881a85af445f438a8d7d5f
    resource: repo://src/piighost/integrations/langchain/middleware.py
  - id: openwiki-source-07566b3f03a831d37fa4fbce
    resource: repo://src/piighost/pipeline/thread.py
generated: { by: "claude-code", at: "2026-10-02T18:00:00.000Z" }
---

# Démarrer avec le wiki PIIGhost

## En bref

PIIGhost masque les données confidentielles d'un texte avant qu'un modèle d'IA le lise, puis remet les vraies valeurs dans la réponse.

Cycle de vie d'un message :

1. L'utilisateur écrit en clair.
2. PIIGhost repère les valeurs sensibles : noms, e-mails, téléphones, secrets.
3. Il les remplace par des jetons comme `<<PERSON:1>>`, stables dans toute la conversation.
4. Le modèle répond en utilisant ces jetons.
5. PIIGhost remet les vraies valeurs dans la réponse affichée.

PIIGhost est une bibliothèque Python, sans interface graphique. Elle se branche sur LangChain, Pydantic AI, LlamaIndex ou Claude Code, ou se pilote à distance par le serveur compagnon `piighost-api`. Elle se configure par un fichier TOML ou JSON et par la commande `piighost`.

Le wiki s'adresse d'abord aux personnes qui décident de la protection des données (DPO, conformité, produit, support), puis aux développeurs. Ce que chaque profil attend est dans [Besoins par profil](besoins-par-profil.md). Le code et les tests font foi. Les écarts avec la documentation existante sont dans le [registre des écarts](reference/ecarts-doc-code.md). Les termes sont dans le [glossaire](glossaire.md).

## Je cherche à comprendre…

| Besoin métier | Page à lire |
|---|---|
| Ce que chaque profil attend de PIIGhost, et comment le vérifier | [Besoins par profil](besoins-par-profil.md) |
| Ce que le modèle voit vraiment d'un message | [Protéger un message avant l'envoi au modèle](processus/proteger-un-message.md) |
| Pourquoi un nom est resté en clair, ou à moitié | [Protéger un message avant l'envoi au modèle](processus/proteger-un-message.md#questions-fréquentes) |
| Comment une personne garde le même jeton d'un message à l'autre | [Suivre une conversation et restaurer la réponse](processus/suivre-une-conversation.md) |
| Ce qui se passe quand on corrige un message à la main | [Suivre une conversation et restaurer la réponse](processus/suivre-une-conversation.md#corriger-un-repérage) |
| Comment effacer une conversation (droit à l'effacement) | [Suivre une conversation et restaurer la réponse](processus/suivre-une-conversation.md) |
| Garder le nom de l'entreprise en clair, ou toujours masquer un code interne | [Imposer une liste blanche et une liste noire](processus/imposer-une-liste-blanche-et-noire.md) |
| Ce que reçoit un outil de l'agent, et ce que le modèle lit de son résultat | [Laisser un outil agir sur les vraies valeurs](processus/laisser-un-outil-agir.md) |
| Pourquoi un jeton apparaît pendant qu'une réponse s'affiche | [Afficher une réponse streamée](processus/afficher-une-reponse-streamee.md) |
| Ce que voit chaque acteur selon l'outil utilisé (LangChain, Claude Code…) | [Brancher la protection sur un agent et ses outils](integrations/agents-et-outils.md) |
| Ce qui se passe quand un modèle répond mal | [Besoins par profil, points de vigilance](besoins-par-profil.md#points-de-vigilance) |
| Où sont stockées les données des conversations, et si elles sont chiffrées | [Stocker les conversations et protéger les traces](exploitation/stockage-et-chiffrement.md) |
| Le sens d'un terme ou d'un sigle | [Glossaire](glossaire.md) |
| Les endroits où la documentation et le code divergent | [Registre des écarts doc / code](reference/ecarts-doc-code.md) |
| Ce qui est décidé et reste à faire | [Points à régler](reference/points-a-regler.md) |

```mermaid
flowchart LR
    A["Message de l'utilisateur"] --> B["Repérage des valeurs"]
    B --> C["Liste blanche et liste noire"]
    C --> D["Remplacement par jetons"]
    D --> E["Contrôle final"]
    E --> F["Modèle d'IA"]
    F --> G["Restauration des valeurs"]
    G --> H["Réponse affichée"]
    D --> M["Mémoire de la conversation"]
    M --> G
```

## Je dois modifier…

| Type de changement | Lire d'abord | Puis |
|---|---|---|
| Ajouter un détecteur | [Ajouter ou remplacer un composant](architecture/ports-et-extension.md#ajouter-un-détecteur) | `components/detector/regex.py` ou `ner/spacy.py`, `config/models/detector_model.py`, `tests/components/detector/test_contract.py` |
| Changer l'arbitrage des chevauchements | [Protéger un message](processus/proteger-un-message.md) | `components/overlap_resolver/`, `tests/components/overlap_resolver/` |
| Changer la forme des jetons | [Glossaire](glossaire.md), [Ajouter ou remplacer un composant](architecture/ports-et-extension.md#jetons-typés) | `components/placeholder/`, `tags.py`, `tests/components/placeholder/` |
| Toucher à la conversation ou à la correction humaine | [Suivre une conversation](processus/suivre-une-conversation.md) | `pipeline/thread.py`, `tests/pipeline/test_thread.py`, `test_thread_hitl.py` |
| Modifier la liste blanche ou la liste noire | [Imposer une liste blanche et une liste noire](processus/imposer-une-liste-blanche-et-noire.md) | `components/override/`, `tests/components/override/test_override.py` |
| Changer le traitement des appels d'outil | [Laisser un outil agir](processus/laisser-un-outil-agir.md) | `integrations/langchain/middleware.py` (`awrap_tool_call`), `integrations/pydantic_ai/hooks.py`, `tests/integrations/langchain/test_middleware.py` |
| Changer la restauration en flux | [Afficher une réponse streamée](processus/afficher-une-reponse-streamee.md) | `components/placeholder/streaming.py`, `tests/components/placeholder/test_streaming*.py` |
| Ajouter un test d'acceptation | [Tests d'acceptation](tests/tests-d-acceptation.md) | `tests/acceptance/`, un identifiant `AT-<besoin>-<n>` dans la docstring |
| Ajouter une clé de configuration | [Configurer un pipeline](exploitation/configuration-et-hub.md) | `config/models/`, `config/settings.py`, `tests/config/` |
| Modifier la commande `piighost` | [Configurer un pipeline](exploitation/configuration-et-hub.md#contrôler-depuis-la-ligne-de-commande) | `cli/__init__.py`, `tests/cli/test_cli.py` |
| Ajouter un stockage ou changer le chiffrement | [Stocker les conversations](exploitation/stockage-et-chiffrement.md) | `conversation_memory/`, `crypto/`, `tests/conversation_memory/` |
| Changer le middleware LangChain ou une autre intégration | [Brancher la protection sur un agent](integrations/agents-et-outils.md) | `integrations/`, `integrations/_deidentify.py`, `tests/integrations/` |
| Ajouter un outil aux hooks Claude Code | [Brancher la protection sur un agent](integrations/agents-et-outils.md) | `integrations/claude_code/hooks.py` (`_TOOL_OUTPUT_TEXT_FIELDS`), `tests/integrations/test_claude_code_hooks.py` |

## Repères pour démarrer en local

- **Pile** : Python 3.11 ou plus, gestionnaire `uv`. Le cœur ne dépend que de `typing-extensions`. Tout le reste est un extra de `pyproject.toml` (`langchain`, `redis`, `gliner2`, `config`…), et `all` les réunit.
- **Installer** : `uv sync` à la racine du dépôt.
- **Tester** : `uv run pytest`, puis `make lint` avant toute fusion. Détails dans [Lancer et écrire les tests](tests/lancer-et-ecrire-les-tests.md).
- **Essayer** : `uv run piighost anonymize "Écrivez à claire.dubois@example.com"`. La première exécution télécharge le catalogue `hub:piighost/generic:fab51b33`.
- **Services** : aucun pour les tests. Redis, une base SQL ou `piighost-api` ne servent qu'en exploitation. Voir [Stocker les conversations](exploitation/stockage-et-chiffrement.md) et [Configurer un pipeline](exploitation/configuration-et-hub.md).
- **Exemples** : scripts autonomes dans `examples/`, lancés par `uv run examples/<script>.py`.

## Les groupes du wiki

- **Besoins** : [Besoins par profil](besoins-par-profil.md).
- **Processus** : [Protéger un message](processus/proteger-un-message.md), [Suivre une conversation](processus/suivre-une-conversation.md), [Imposer une liste blanche et une liste noire](processus/imposer-une-liste-blanche-et-noire.md), [Laisser un outil agir](processus/laisser-un-outil-agir.md), [Afficher une réponse streamée](processus/afficher-une-reponse-streamee.md).
- **Intégrations** : [Brancher la protection sur un agent et ses outils](integrations/agents-et-outils.md).
- **Exploitation** : [Configurer un pipeline par fichier, hub et ligne de commande](exploitation/configuration-et-hub.md), [Stocker les conversations et protéger les traces](exploitation/stockage-et-chiffrement.md).
- **Architecture** : [Ajouter ou remplacer un composant du pipeline](architecture/ports-et-extension.md).
- **Tests** : [Lancer et écrire les tests](tests/lancer-et-ecrire-les-tests.md), [Tests d'acceptation](tests/tests-d-acceptation.md).
- **Référence** : [Glossaire](glossaire.md), [Registre des écarts doc / code](reference/ecarts-doc-code.md), [Points à régler](reference/points-a-regler.md).

## Points de vigilance transverses

1. **L'identifiant de conversation décide du partage des jetons.** Un appel sans identifiant est refusé, par LangChain, les hooks Claude Code et le serveur. Une application qui nomme `default` partage ses jetons entre tous ses utilisateurs. Seule la commande `piighost` s'y rabat, pour une commande isolée. Voir [Suivre une conversation](processus/suivre-une-conversation.md#règles-à-connaître).
2. **Corriger un message ancien peut renuméroter les jetons**, et une réponse du modèle peut alors être restaurée avec le nom d'une autre personne. Voir [Suivre une conversation](processus/suivre-une-conversation.md#règles-à-connaître).
3. **La mémoire et l'historique de l'agent contiennent des données en clair, et tout ce qui n'est pas traité aussi** : un outil Claude Code non listé (Grep), ou un résultat d'outil sous « Entrée seule » ou « Aucun ». Chiffrez le stockage, et protégez l'historique de LangGraph ou de Pydantic AI. Voir [Stocker les conversations](exploitation/stockage-et-chiffrement.md) et [Brancher la protection sur un agent](integrations/agents-et-outils.md#pièges).
4. **Les traces techniques portent le texte en clair par défaut.** Configurez un masqueur de traces avant de les envoyer à un service tiers. Voir [Stocker les conversations et protéger les traces](exploitation/stockage-et-chiffrement.md#masquer-les-traces).
5. **Effacer une conversation ne vide que le processus qui reçoit la demande.** Les autres processus gardent une copie temporaire sans `token_memo_ttl`. Voir [Stocker les conversations](exploitation/stockage-et-chiffrement.md#règles-à-connaître).
6. **Un détecteur ou un garde-fou à base de modèle échoue en ouvert.** Une sortie illisible du modèle donne zéro détection, et le message part sans protection. Voir les [points de vigilance](besoins-par-profil.md#points-de-vigilance).

---
type: testing
title: Lancer et écrire les tests
description: Comment lancer les tests et le contrôle qualité de PIIGhost, comment la suite est organisée, ce que la CI GitHub exécute, et quels tests ne tournent nulle part en CI.
tags: [testing, pytest, ci, lint, pyrefly, bandit, integration]
verified:
  - by: openwiki/0.6.1
    at: 2026-10-01T18:36:49.731Z
sources:
  - id: openwiki-source-164e2da859b5277df81c7d94
    resource: repo://.github/workflows/ci.yml
  - id: openwiki-source-b34ce104402cf07f200388d7
    resource: repo://.github/workflows/integration.yml
  - id: openwiki-source-012f2c78e3b1446dfc35803f
    resource: repo://Makefile
  - id: openwiki-source-05ccef8d4cf1698187f20464
    resource: repo://pyproject.toml
  - id: openwiki-source-6b9df10d5bfa4c0d085e4eb7
    resource: repo://tests/components/detector/test_contract.py
  - id: openwiki-source-2c17b9fa5fee8d4587d88a77
    resource: repo://tests/integrations/llama_index/test_query_engine.py
generated: { by: "claude-code", at: "2026-10-01T18:36:49.731Z" }
---

# Lancer et écrire les tests

## En bref

- PIIGhost a plus de mille tests automatiques. Ils tournent en quelques secondes sans télécharger de modèle d'IA.
- Les tests qui chargent de vrais modèles sont à part. Ils tournent chaque nuit sur GitHub.
- Avant toute fusion, un contrôle bloquant vérifie la mise en forme, les types, la sécurité du code et la documentation.
- Une partie des tests (32 le 2026-10-01) n'est lancée par aucune tâche automatique, faute des bibliothèques nécessaires. Voir [Ce qui ne tourne nulle part en CI](#ce-qui-ne-tourne-nulle-part-en-ci).

Les termes sont définis dans le [glossaire](../glossary.md).

## Lancer les tests

| Vous voulez… | Commande |
|---|---|
| Installer l'environnement de développement | `uv sync` |
| Lancer toute la suite rapide | `uv run pytest` |
| Lancer un test précis | `uv run pytest tests/pipeline/test_pipeline.py -k "nom_du_test"` |
| Lancer les tests qui chargent des modèles | `uv run pytest -m integration` |
| Corriger la mise en forme | `make format` |
| Passer le contrôle bloquant | `make lint` |

`addopts` exclut le marqueur `integration` par défaut et désactive les extensions `anyio` et `langsmith_plugin` (`pyproject.toml:166`). Avec `asyncio_mode = "auto"`, un test `async def` n'a pas besoin de décorateur.

### Vérifier

Le 2026-10-01, sur `develop`, `uv run pytest -q` affiche `1128 passed, 32 skipped, 3 deselected`. Les 3 tests désélectionnés sont les tests `integration`.

## Ce que contrôle `make lint`

`make lint` ne modifie rien et échoue au premier problème (`Makefile:11-16`) :

1. `ruff format --check .` : mise en forme.
2. `ruff check .` : règles de style, dont les annotations de type obligatoires.
3. `pyrefly check src tests examples docs/tools` : vérification des types, sur des chemins explicites.
4. `bandit -c pyproject.toml -r src examples` : sécurité du code.
5. `python skills/piighost-docs/scripts/audit.py` : audit des pages de documentation.

## Comment la suite est organisée

| Dossier | Contenu |
|---|---|
| `tests/components/` | Un sous-dossier par étape, c'est-à-dire détecteurs, liste à masquer et liste à laisser en clair, chevauchements, expansion, liens, résolveurs, anonymiseur, jetons, garde-fous |
| `tests/pipeline/` | Pipeline simple, pipeline de conversation, correction humaine, listes intégrées au pipeline |
| `tests/conversation_memory/`, `tests/crypto/` | Stockages et chiffrement |
| `tests/config/`, `tests/cli/`, `tests/test_hub.py` | Configuration, ligne de commande, hub |
| `tests/integrations/` | LangChain, Pydantic AI, LlamaIndex, Claude Code, client HTTP |
| `tests/observation/` | Spans OpenTelemetry et masquage des traces |
| `tests/models/`, `tests/text/` | Modèles de données, limites de mots, espaces, découpage |
| `tests/regression/` | API publique et imports sans dépendances optionnelles |
| `tests/skills/test_docs_audit.py` | Le script d'audit de la documentation |

## Écrire un test

1. Placez le fichier dans le dossier de l'étape testée, sur le modèle du test voisin.
2. Utilisez `ExactMatchDetector({"Claire Dubois": "PERSON"})` comme détecteur, pour ne charger aucun modèle.
3. Pour un stockage, utilisez `InMemoryConversationMemory()`, ou `fakeredis` pour Redis comme `tests/conversation_memory/test_redis.py:21-27`.
4. Si le test exige une dépendance optionnelle, appelez `pytest.importorskip("nom_du_module")`.
5. Si le test charge un vrai modèle (torch, gliner2, spacy, transformers), marquez-le `@pytest.mark.integration`.
6. Pour un nouveau détecteur, ajoutez aussi son constructeur à `DETECTORS` dans `tests/components/detector/test_contract.py`.

### Vérifier

```bash
uv run pytest chemin/du/test.py -v
make lint
```

## Ce que la CI GitHub exécute

| Workflow | Déclencheur | Ce qu'il lance |
|---|---|---|
| `ci.yml`, tâche `lint` | push et pull request sur `master` et `develop`, sauf changements de doc seuls | `uv sync --locked --dev`, puis `make lint` (Python 3.13) |
| `ci.yml`, tâche `audit` | idem | `pip-audit` sur toutes les dépendances verrouillées, avec une vulnérabilité `nltk` acquittée |
| `ci.yml`, tâche `tests` | après `lint` et `audit` | `uv run pytest --cov=piighost` sur Python 3.11, 3.12, 3.13 et 3.14 |
| `integration.yml` | chaque nuit à 03:00 UTC, ou à la main | `uv sync --all-extras --all-groups`, modèle spaCy `en_core_web_sm`, puis `pytest -m integration` |

Un changement qui ne touche que des fichiers `.md`, `docs/` ou `LICENSE` ne déclenche pas `ci.yml` (`paths-ignore`).

## Ce qui ne tourne nulle part en CI

Le groupe `dev` installe les extras `config, argon2, crypto, redis, mistral, langchain, pydantic-ai, observation, fuzzy, sqlalchemy` (`pyproject.toml:150-151`). Il n'installe ni `llama-index`, ni `gliner2`, ni `spacy`, ni `transformers`, ni `presidio`.

- Dans la tâche `tests`, les tests qui demandent ces bibliothèques par `importorskip` sont sautés.
- Dans `integration.yml`, ces bibliothèques sont installées, mais `-m integration` ne sélectionne que les 3 tests marqués.

Les tests sautés et non marqués ne tournent donc dans aucune tâche. Le 2026-10-01, ce sont 32 tests, parmi lesquels :

- `tests/integrations/llama_index/` (les deux fichiers) ;
- les entrées `gliner2`, `transformers`, `presidio` et `spacy` de `tests/components/detector/test_contract.py` ;
- `tests/components/guard/test_gliner2_guard.py` ;
- `tests/components/detector/ner/test_presidio.py`, et les tests non marqués de `test_spacy.py` et `test_transformers.py` ;
- `tests/config/test_presidio_detector.py`.

Pour les lancer en local :

```bash
uv sync --all-extras --all-groups
uv run pytest -rs
uv sync
```

Revenez ensuite à l'environnement par défaut avec `uv sync`, puis relancez `make lint`. Un environnement chargé de tous les extras peut masquer une erreur d'import ou de type que la CI verrait.

## Pièges

- **Un test sauté passe pour réussi.** Lancez `pytest -rs` pour voir la liste et la raison de chaque saut.
- **Le conftest d'observation installe un traceur global** pour toute la session. L'avertissement des traces en clair est donc filtré dans `pyproject.toml:172-174`, et seuls ses propres tests le vérifient.
- **`pyrefly` reçoit des chemins explicites.** Sans eux, il ne vérifie rien dans un worktree git et échoue quand même (`Makefile:8-10`).
- **Les tests Redis utilisent `fakeredis`.** Le comportement d'un vrai serveur ou d'un cluster n'est pas couvert.

Voir aussi [Ajouter ou remplacer un composant](../architecture/ports-and-extension.md) pour les tests de contrat et d'imports.

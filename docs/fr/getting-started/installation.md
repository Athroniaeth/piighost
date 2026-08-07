---
icon: lucide/download
---

# Installation

## Prérequis

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommandé) ou pip

## Installation

Le socle n'a aucune dépendance optionnelle. Il suffit pour un pipeline local qui dé-identifie par regex ou par valeurs connues, sans modèle ni réseau.

=== "uv"

    ```bash
    uv add piighost
    ```

=== "pip"

    ```bash
    pip install piighost
    ```

## Extras

Les détecteurs à modèle, le middleware et les backends optionnels sont des extras à combiner selon les besoins.

=== "uv"

    ```bash
    uv add 'piighost[gliner2]'       # détecteur GLiNER2 (NER)
    uv add 'piighost[spacy]'         # détecteur spaCy (NER)
    uv add 'piighost[transformers]'  # détecteur transformers (NER)
    uv add 'piighost[llm]'           # détecteur LLM (extraction structurée)
    uv add 'piighost[middleware]'    # middleware LangChain/LangGraph
    uv add 'piighost[config]'        # configuration TOML et JSON
    uv add 'piighost[fuzzy]'         # résolveur d'entités fuzzy (Jaro-Winkler)
    uv add 'piighost[redis]'         # mémoire de conversation Redis
    uv add 'piighost[crypto]'        # chiffrement AES-GCM des valeurs stockées
    uv add 'piighost[argon2]'        # hachage Argon2id des clés de stockage
    uv add 'piighost[mistral]'       # garde-fou de modération Mistral
    uv add 'piighost[client]'        # client HTTP pour piighost-api
    uv add 'piighost[observation]'   # traçage OpenTelemetry
    uv add 'piighost[all]'           # tous les extras
    ```

=== "pip"

    ```bash
    pip install 'piighost[gliner2]'
    pip install 'piighost[spacy]'
    pip install 'piighost[transformers]'
    pip install 'piighost[llm]'
    pip install 'piighost[middleware]'
    pip install 'piighost[config]'
    pip install 'piighost[fuzzy]'
    pip install 'piighost[redis]'
    pip install 'piighost[crypto]'
    pip install 'piighost[argon2]'
    pip install 'piighost[mistral]'
    pip install 'piighost[client]'
    pip install 'piighost[observation]'
    pip install 'piighost[all]'
    ```

Les extras se combinent. Une mémoire de conversation Redis chiffrée s'installe avec `piighost[redis,crypto]`, en ajoutant `argon2` pour un hachage de clé plus résistant.

## Installation pour le développement

```bash
git clone https://github.com/Athroniaeth/piighost.git
cd piighost
uv sync
```

## Commandes de développement

```bash
uv sync                              # installer les dépendances
make lint                            # format (ruff) + lint (ruff) + types (pyrefly)
uv run pytest                        # lancer tous les tests
uv run pytest tests/ -k "test_name"  # lancer un test précis
```

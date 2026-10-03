---
icon: lucide/download
---

# Installation

## Prérequis

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommandé) ou pip

## Installer le socle

Le socle n'a aucune dépendance optionnelle. Il suffit pour un pipeline local qui dé-identifie par regex ou par valeurs connues, sans modèle ni réseau.

Installez-le avec `uv`, ou avec `pip`.

=== "uv"

    ```bash
    uv add piighost
    ```

=== "pip"

    ```bash
    pip install piighost
    ```

## Extras

Les détecteurs à modèle, le middleware et les backends optionnels sont des extras à combiner selon les besoins. La liste complète est dans `pyproject.toml`.

=== "uv"

    ```bash
    uv add 'piighost[gliner2]'     # détecteur GLiNER2 (NER)
    uv add 'piighost[langchain]'   # middleware LangChain/LangGraph
    uv add 'piighost[all]'         # tous les extras
    ```

=== "pip"

    ```bash
    pip install 'piighost[gliner2]'
    pip install 'piighost[langchain]'
    pip install 'piighost[all]'
    ```

Les extras se combinent. Une mémoire de conversation Redis chiffrée s'installe avec `piighost[redis,crypto]`. Ajoutez l'extra `argon2` pour un hachage de clé plus résistant.

## Vérifier l'installation

Affichez la version installée.

=== "uv"

    ```bash
    uv run python -c "import piighost; print(piighost.__version__)"
    ```

=== "pip"

    ```bash
    python -c "import piighost; print(piighost.__version__)"
    ```

La commande affiche un numéro de version, `2.0.0` par exemple. Une `ImportError` signifie que le paquet n'est pas installé dans l'environnement actif.

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

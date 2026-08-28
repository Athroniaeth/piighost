---
icon: lucide/download
---

# Installation

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip

## Installation

The core has no optional dependency. It is enough for a local pipeline that de-identifies by regex or by known values, with no model and no network.

Install it with `uv`, or with `pip`.

=== "uv"

    ```bash
    uv add piighost
    ```

=== "pip"

    ```bash
    pip install piighost
    ```

## Extras

Model-based detectors, the middleware, and the optional backends are extras to combine as needed. The full list is in `pyproject.toml`.

=== "uv"

    ```bash
    uv add 'piighost[gliner2]'     # GLiNER2 NER detector
    uv add 'piighost[langchain]'  # LangChain/LangGraph middleware
    uv add 'piighost[all]'         # every extra
    ```

=== "pip"

    ```bash
    pip install 'piighost[gliner2]'
    pip install 'piighost[langchain]'
    pip install 'piighost[all]'
    ```

Extras compose. An encrypted Redis conversation memory installs with `piighost[redis,crypto]`, adding `argon2` for a more resistant key hash.

## Development installation

```bash
git clone https://github.com/Athroniaeth/piighost.git
cd piighost
uv sync
```

## Development commands

```bash
uv sync                              # install dependencies
make lint                            # format (ruff) + lint (ruff) + types (pyrefly)
uv run pytest                        # run all tests
uv run pytest tests/ -k "test_name"  # run a single test
```

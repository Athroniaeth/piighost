---
icon: lucide/git-pull-request
---

# Contributing

Thanks for your interest in `piighost`. This page summarises the contribution workflow. For the authoritative version, see [`CONTRIBUTING.md`](https://github.com/Athroniaeth/piighost/blob/master/.github/CONTRIBUTING.md) at the repository root.

## Prerequisites

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/) as package manager
- A GitHub account

## Getting started

1. **Fork** the repository on GitHub.
2. **Clone** your fork locally:

    ```bash
    git clone https://github.com/YOUR-USERNAME/piighost.git
    cd piighost
    git remote add upstream https://github.com/Athroniaeth/piighost.git
    ```

3. **Install** dependencies:

    ```bash
    uv sync
    ```

## Workflow

### Create a branch

Always from `master`:

```bash
git checkout -b feat/my-feature
```

### Follow the conventions

- **Protocols** at every pipeline stage keep components swappable.
- **Frozen dataclasses** for data models (`Entity`, `Detection`, `Span`).
- **`ExactMatchDetector`** in tests, never a real NER model in CI.
- **Conventional commits** through Commitizen (`feat:`, `fix:`, `refactor:`, etc.).

### Local checks

Before opening a PR:

```bash
make format                          # fix the format and the lint with ruff
make lint                            # check without changing anything
uv run pytest                        # run the tests
uv run pytest tests/ -k "test_name"  # run a single test
```

`make lint` changes no file and fails on the first problem. It checks the format with `ruff format --check`, the lint with `ruff check`, the types with `pyrefly`, the security with `bandit`, then the documentation with the page audit script. `make format` fixes what ruff can fix.

### Open the pull request

- Clear title following the Commitizen format.
- Description that explains the *why* rather than the *what*.
- Link the related issue (`Fixes #42`).
- Screenshots or output samples when relevant.

## Extension points

The most common places to contribute without touching the core:

- **New detector**: implement the `AnyDetector` protocol. See [Extending piighost](../extending.md).
- **New regex pack**: publish a pattern group on the [piighost hub](https://hub.piighost.dev), which a config then pulls by reference.
- **New placeholder factory**: implement `AnyPlaceholderFactory`.

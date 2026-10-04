---
type: testing
title: Run and write tests
description: How to run the tests and the quality gate of PIIGhost, how the suite is organized, what GitHub CI runs, and which tests run nowhere in CI.
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

# Run and write tests

## In short

- PIIGhost has more than a thousand automated tests. They run in a few seconds without downloading any AI model.
- The tests that load real models are kept apart. They run every night on GitHub.
- Before any merge, a blocking check verifies formatting, types, code security and documentation.
- Some of the tests (32 on 2026-10-01) are run by no automated job, because the libraries they need are missing. See [What runs nowhere in CI](#what-runs-nowhere-in-ci).

The terms are defined in the [glossary](../glossary.md).

## Run the tests

| You want to… | Command |
|---|---|
| Install the development environment | `uv sync` |
| Run the whole fast suite | `uv run pytest` |
| Run one specific test | `uv run pytest tests/pipeline/test_pipeline.py -k "test_name"` |
| Run the tests that load models | `uv run pytest -m integration` |
| Fix the formatting | `make format` |
| Pass the blocking check | `make lint` |

`addopts` excludes the `integration` marker by default and disables the `anyio` and `langsmith_plugin` plugins (`pyproject.toml:166`). With `asyncio_mode = "auto"`, an `async def` test needs no decorator.

### Check

On 2026-10-01, on `develop`, `uv run pytest -q` shows `1128 passed, 32 skipped, 3 deselected`. The 3 deselected tests are the `integration` tests.

## What `make lint` checks

`make lint` modifies nothing and fails at the first problem (`Makefile:11-16`):

1. `ruff format --check .`: formatting.
2. `ruff check .`: style rules, including mandatory type annotations.
3. `pyrefly check src tests examples docs/tools`: type checking, on explicit paths.
4. `bandit -c pyproject.toml -r src examples`: code security.
5. `python skills/piighost-docs/scripts/audit.py`: audit of the documentation pages.

## How the suite is organized

| Folder | Content |
|---|---|
| `tests/components/` | One subfolder per stage, that is detectors, deny list and allow list, overlaps, expansion, links, resolvers, anonymizer, placeholders, guard rails |
| `tests/pipeline/` | Simple pipeline, conversation pipeline, human correction, lists built into the pipeline |
| `tests/conversation_memory/`, `tests/crypto/` | Storage and encryption |
| `tests/config/`, `tests/cli/`, `tests/test_hub.py` | Configuration, command line, hub |
| `tests/integrations/` | LangChain, Pydantic AI, LlamaIndex, Claude Code, HTTP client |
| `tests/observation/` | OpenTelemetry spans and trace masking |
| `tests/models/`, `tests/text/` | Data models, word boundaries, spaces, splitting |
| `tests/regression/` | Public API and imports without optional dependencies |
| `tests/skills/test_docs_audit.py` | The documentation audit script |

## Write a test

1. Put the file in the folder of the stage under test, on the model of the neighboring test.
2. Use `ExactMatchDetector({"Claire Dubois": "PERSON"})` as the detector, so that no model loads.
3. For a storage backend, use `InMemoryConversationMemory()`, or `fakeredis` for Redis as in `tests/conversation_memory/test_redis.py:21-27`.
4. If the test requires an optional dependency, call `pytest.importorskip("module_name")`.
5. If the test loads a real model (torch, gliner2, spacy, transformers), mark it `@pytest.mark.integration`.
6. For a new detector, also add its constructor to `DETECTORS` in `tests/components/detector/test_contract.py`.

### Check

```bash
uv run pytest path/to/test.py -v
make lint
```

## What GitHub CI runs

| Workflow | Trigger | What it runs |
|---|---|---|
| `ci.yml`, `lint` job | push and pull request on `master` and `develop`, except doc-only changes | `uv sync --locked --dev`, then `make lint` (Python 3.13) |
| `ci.yml`, `audit` job | same | `pip-audit` on all locked dependencies, with one acknowledged `nltk` vulnerability |
| `ci.yml`, `tests` job | after `lint` and `audit` | `uv run pytest --cov=piighost` on Python 3.11, 3.12, 3.13 and 3.14 |
| `integration.yml` | every night at 03:00 UTC, or by hand | `uv sync --all-extras --all-groups`, spaCy model `en_core_web_sm`, then `pytest -m integration` |

A change that touches only `.md` files, `docs/` or `LICENSE` does not trigger `ci.yml` (`paths-ignore`).

## What runs nowhere in CI

The `dev` group installs the extras `config, argon2, crypto, redis, mistral, langchain, pydantic-ai, observation, fuzzy, sqlalchemy` (`pyproject.toml:150-151`). It installs neither `llama-index`, nor `gliner2`, nor `spacy`, nor `transformers`, nor `presidio`.

- In the `tests` job, the tests that request these libraries through `importorskip` are skipped.
- In `integration.yml`, these libraries are installed, but `-m integration` selects only the 3 marked tests.

The skipped and unmarked tests therefore run in no job. On 2026-10-01, these are 32 tests, among them:

- `tests/integrations/llama_index/` (both files),
- the `gliner2`, `transformers`, `presidio` and `spacy` entries of `tests/components/detector/test_contract.py`,
- `tests/components/guard/test_gliner2_guard.py`,
- `tests/components/detector/ner/test_presidio.py`, and the unmarked tests of `test_spacy.py` and `test_transformers.py`,
- `tests/config/test_presidio_detector.py`.

To run them locally:

```bash
uv sync --all-extras --all-groups
uv run pytest -rs
uv sync
```

Then go back to the default environment with `uv sync`, and run `make lint` again. An environment loaded with every extra can hide an import or type error that CI would see.

## Pitfalls

- **A skipped test looks like a passed one.** Run `pytest -rs` to see the list and the reason for each skip.
- **The observation conftest installs a global tracer** for the whole session. The clear-text tracing warning is therefore filtered in `pyproject.toml:172-174`, and only its own tests check it.
- **`pyrefly` receives explicit paths.** Without them, it checks nothing in a git worktree and fails anyway (`Makefile:8-10`).
- **The Redis tests use `fakeredis`.** The behavior of a real server or of a cluster is not covered.

See also [Add or replace a component](../architecture/ports-and-extension.md) for the contract and import tests.

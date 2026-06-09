# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PIIGhost is a composable PII anonymization pipeline for LLM agents. It detects, anonymizes, and deanonymizes sensitive entities using pluggable detectors (GLiNER2, spaCy, Transformers, LLM, regex), with a LangChain middleware for LangGraph agents, TOML-driven configuration, and an HTTP client for the companion `piighost-api` server.

## Development Commands

```bash
uv sync                      # Install dependencies (dev group included)
make lint                    # ruff format + ruff check --fix + pyrefly + bandit
uv run pytest                # Run all tests (integration tests deselected by default)
uv run pytest tests/test_anonymizer.py -k "test_name"  # Run a single test
uv run pytest -m integration # Run integration tests (load torch/gliner2/spacy)
make docs-build              # Build EN + FR docs (zensical)
make docs-watch              # Serve EN docs with live reload (docs-watch-fr for FR)
```

Tests marked `integration` load heavy optional dependencies and are excluded by the default `addopts`. `asyncio_mode = "auto"`, so async tests need no decorator.

## Architecture

### Anonymization Pipeline

`AnonymizationPipeline` (`pipeline/base.py`) orchestrates 5 stages plus an optional guard:

1. **Detect**: `AnyDetector` protocol (`detector/base.py`). Implementations: `Gliner2Detector`, `SpacyDetector`, `TransformersDetector` (all extend `BaseNERDetector` for external→internal label mapping), `LLMDetector` (LangChain structured output), `RegexDetector` (with optional checksum validators from `validators.py`: Luhn, IBAN, NIR), `ExactMatchDetector` (tests), `CompositeDetector` (chains detectors), `ChunkedDetector` (wraps any detector with overlapping-chunk splitting for long texts). Pre-built regex pattern dicts live in `detector/patterns/` (generic, us, eu, fr).
2. **Resolve Spans**: `AnySpanConflictResolver` — `ConfidenceSpanConflictResolver` keeps the highest-confidence detection when spans overlap.
3. **Link Entities**: `AnyEntityLinker` — `ExactEntityLinker` finds all occurrences via word-boundary regex and groups them; `link_entities()` links entities across messages.
4. **Resolve Entities**: `AnyEntityConflictResolver` — `MergeEntityConflictResolver` (union-find) or `FuzzyEntityConflictResolver` (Jaro-Winkler, `similarity.py`).
5. **Anonymize**: `AnyAnonymizer` — `Anonymizer` applies span-based replacement using an `AnyPlaceholderFactory`.
6. **Guard rail** (optional): `AnyGuardRail` (`guard.py`) re-checks anonymized output for residual PII via `check(text, tokens=...)`, where `tokens` are the placeholders the pipeline just emitted so the guard can ignore them. `DetectorGuardRail` re-runs a detector, `LLMGuardRail` (`guard_llm.py`) uses an LLM prompted to ignore placeholders. Raises `PIIRemainingError`.

All stages run through a single template method `_anonymize_with_span()` in `pipeline/base.py`, which calls hooks (`_link_stage`, `_record_entities`, `_render_stage`) in order; the thread pipeline overrides these hooks to add cross-message linking, conversation-memory recording, and memory-wide rendering.

All stages use **protocols** (structural subtyping) for dependency injection. Tests use `ExactMatchDetector` to avoid loading real models. Data models (`Entity`, `Detection`, `Span` in `models.py`) are frozen dataclasses.

### Placeholder Factories & Preservation Tags

`placeholder_tags.py` defines a phantom-type hierarchy describing what a placeholder preserves: label axis (`<PERSON>` vs `[REDACT]`), identity axis (`<<PERSON:1>>` uniquely identifies), realism axis (Opaque / Hashed / Faker), plus `PreservesShape` (masks like `j***@mail.com`). Pipelines are generic on this tag; the middleware requires `PreservesIdentity` to deanonymize safely.

Factories in `placeholder.py`: `RedactPlaceholderFactory`, `LabelPlaceholderFactory`, `MaskPlaceholderFactory`, `RedactCounterPlaceholderFactory`, `RedactHashPlaceholderFactory`, `LabelCounterPlaceholderFactory` (`<<PERSON:1>>`), `LabelHashPlaceholderFactory`. Faker-based factories in `ph_factory/`: `FakerPlaceholderFactory`, `FakerCounterPlaceholderFactory`, `FakerHashPlaceholderFactory`. Hash factories support a pepper via `PIIGHOST_HASH_PEPPER`.

### Conversation Layer

`ThreadAnonymizationPipeline` (`pipeline/thread.py`) extends the base pipeline with:
- **Thread isolation**: memory and cache scoped per `thread_id` (propagated via a ContextVar, defaults to `"default"`)
- `ConversationMemory` accumulates entities across messages per thread, deduplicated by `(text.lower(), label)`, tracking case variants so "patrick" in message 2 shares the placeholder of "Patrick" in message 1. Memory is cache-backed (write-through snapshots persisted to the cache backend, hydrated per call so multi-worker deployments see each other's entities) and injectable via `memory_factory`.
- `forget_thread(thread_id)` purges a conversation from both RAM and the cache backend (via a per-thread key index, since aiocache has no portable prefix scan)
- `deanonymize_with_ent()` / `anonymize_with_ent()` for string-based token replacement on any text
- aiocache-backed caching of detector results and anonymization mappings (SHA-256 keyed, prefixed by thread_id). `cache_ttl` defaults to 3600 s (one hour) on every entry the pipeline writes; pass `None` to keep entries until backend eviction. In TOML configs the knob is `[pipeline] cache_ttl` (`0` disables expiry). `cache/sqlalchemy.py` provides `SQLAlchemyCache`, an aiocache-compatible backend for SQLite/PostgreSQL persistence (required for multi-worker deployments).

### Middleware Integration

`PIIAnonymizationMiddleware` (`middleware.py`) extends LangChain's `AgentMiddleware`:
- Extracts `thread_id` from LangGraph config via `get_config()["configurable"]["thread_id"]`; `require_thread_id=True` raises instead of falling back to the shared `"default"` thread when no thread id is present
- `abefore_model` anonymizes messages before the LLM sees them; `aafter_model` deanonymizes for user display (cache-based, `CacheMissError` falls back to entity-based)
- `awrap_tool_call` behavior is controlled by `ToolCallStrategy`: `FULL` (deanonymize args, re-anonymize result), `INBOUND_ONLY`, or `PASSTHROUGH`. Tool-call args are deanonymized recursively through nested dict/list/tuple containers (`_deanonymize_value`); other container types pass through unchanged

### TOML Configuration & CLI

`config/` builds a full pipeline from a TOML file: `load_config()` parses into Pydantic models (`config/models/`, discriminated unions per component type), `build_pipeline()` dispatches to each component's `from_config()` classmethod (`config/builders.py`, optional imports deferred), `load_pipeline()` combines both and returns the pipeline plus a `PipelineManifest`. The `piighost` CLI (`cli/`) exposes `validate <file.toml>` and `schema`. Detector labels accept a list or an `{emitted: model}` mapping dict.

### Other Components

- `client.py`: `PIIGhostClient`, async httpx client for a remote piighost-api server (`detect`, `anonymize`, `deanonymize`, `override_detections`)
- `observation/`: backend-agnostic tracing protocols (`AbstractObservationService`, mirroring Langfuse v3 vocabulary) with Langfuse and Opik adapters; the pipeline emits per-stage spans when a service is provided
- `labels.py`: common label constants (`PERSON`, `EMAIL`, ...); custom labels remain allowed

### Optional Dependencies

Nearly everything beyond the core is an extra (`pyproject.toml`): `gliner2`, `spacy`, `transformers`, `llm`, `faker`, `middleware`, `client`, `sqlalchemy`, `config`, `langfuse`, `opik`, `all`. Imports of optional packages stay inside functions/modules that need them; `tests/test_optional_dependencies.py` enforces this. Keep new optional features behind the same pattern.

### Design Patterns

Config coupling is **one-way**: `config/builders.py` maps config types to component classes and dispatches to each component's `from_config()`, but core modules never import `piighost.config` at runtime (config-model type hints in core are guarded by `TYPE_CHECKING`). This is enforced by `tests/test_core_no_extras.py`. Adding a new component means a core class plus a config model plus a builder entry, never a core-to-config import.

## Conventions

- **Commits**: Conventional Commits via Commitizen (`feat:`, `fix:`, `refactor:`, etc.); releases via `cz bump`
- **Type checking**: PyReFly (not mypy)
- **Formatting/linting**: Ruff; security lint via Bandit (both run by `make lint`)
- **Package manager**: uv (not pip)
- **Python**: 3.10+ runtime support (dev on 3.12+)

## Documentation

Docs are bilingual and mirrored: every page exists in both `docs/en/` and `docs/fr/`, with nav declared in `zensical.toml` (EN) and `zensical.fr.toml` (FR). Built with Zensical. When touching one language, update the other.

## Examples

- `examples/graph/`: LangGraph agent with PII middleware (own uv sub-project: Aegra, FastAPI, PostgreSQL, Langfuse) — see its README
- `examples/llm/`, `examples/observation/`: standalone PEP 723 inline-metadata scripts (run with `uv run <script>`)
- `examples/streamlit/playground.py`: interactive playground
- `examples/detectors/`: regex pattern catalogs

New examples should be PEP 723 scripts, not uv sub-projects.

## Working with downstream consumers

`piighost-api` and `piighost-chat` both depend on this lib. When you change something here and want to test it end-to-end against either consumer **before** publishing a new release, do **not** bump-and-publish. Use the consumer's local-dev workflow:

- **piighost-api** (`~/PycharmProjects/piighost-api`):
  - Default `make install` resolves piighost from PyPI.
  - `make dev-local` layers an editable install of `../piighost` on top, so changes here propagate live to the running API. Re-run after any `uv sync` (which would otherwise reset piighost back to PyPI).
- **piighost-chat** (`~/PycharmProjects/piighost-chat`):
  - The backend's pyproject still has `[tool.uv.sources] piighost = { path = "../../piighost", editable = true }` as the default; `make install` (the chat repo's Makefile) already gives you the editable lib without an extra step.
  - Docker stack: `make docker-up-local` mounts this repo into the piighost-api container via `compose.dev.yml`, so the full chat pipeline runs against the local lib.

Net: an agent iterating on this lib should not feel pressure to release just to validate. Bumping (via `cz bump`) and publishing is reserved for consumer pin updates and external users.

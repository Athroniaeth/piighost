# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

PIIGhost is a composable PII de-identification pipeline for LLM agents. It detects, anonymizes, and deanonymizes sensitive entities using pluggable detectors (regex, GLiNER2, spaCy, Transformers, LLM), with a LangChain middleware for LangGraph agents, TOML/JSON-driven configuration, and an HTTP client for the companion `piighost-api` server. The design is hexagonal: every stage is a port (an `Any*` runtime_checkable Protocol) with a `Base*` template ABC, and configuration couples to the core in one direction only.

## Development Commands

```bash
uv sync                      # Install dependencies (dev group included)
make format                  # Auto-fix: ruff format + ruff check --fix
make lint                    # Blocking gate: ruff format --check + ruff check + pyrefly + bandit
uv run pytest                # Run all tests (integration tests deselected by default)
uv run pytest tests/pipeline/test_pipeline.py -k "test_name"  # Run a single test
uv run pytest -m integration # Run integration tests (load torch/gliner2/spacy)
make docs-build              # Build EN + FR docs (zensical)
make docs-watch              # Serve EN docs with live reload (docs-watch-fr for FR)
```

`make lint` is a real gate (non-mutating, fails on any issue); use `make format` to auto-fix. Tests marked `integration` load heavy optional dependencies and are excluded by the default `addopts`. `asyncio_mode = "auto"`, so async tests need no decorator.

## Architecture

Each pipeline stage is a package under `src/piighost/components/` whose `base.py` holds the port (`Any*` Protocol) and a `Base*` template ABC; concrete adapters are sibling modules.

### Anonymization Pipeline

`AnonymizationPipeline` (`pipeline/base.py`, extends `BaseAnonymizationPipeline`) runs the stages in order. Only the detector is required: the linker defaults to `ExactEntityLinker` and the anonymizer to `Anonymizer(LabelCounterPlaceholderFactory())`, and the overlap, expand, entity-resolve, override, and guard stages default to disabled.

1. **Detect**: `AnyDetector` (`components/detector/base.py`). `RegexDetector` (prebuilt pattern catalogs in `components/detector/patterns/`: generic, us, eu, fr; no checksum validators, so it matches on shape alone and never drops an OCR-mangled value), `ExactMatchDetector` (tests), `CompositeDetector` (runs several concurrently), `ChunkedDetector` (overlapping-chunk splitting for long text), and the model detectors `Gliner2Detector` / `SpacyDetector` / `TransformersDetector` (extend `BaseNERDetector` for label mapping) plus `LLMDetector` (LangChain structured output).
2. **Override** (optional): `AnyDetectionOverride` (`components/override/`) imposes a server whitelist and blacklist on every detection set.
3. **Resolve overlaps** (optional): `AnyOverlapResolver` / `ConfidenceOverlapResolver` keeps the highest-confidence detection when spans overlap.
4. **Expand** (optional): `AnyDetectionExpander` / `WordBoundaryExpander` adds missed occurrences.
5. **Link**: `AnyEntityLinker` / `ExactEntityLinker` groups detections that share a value and label into an `Entity`.
6. **Resolve entities** (optional): `AnyEntityResolver` / `MergeEntityResolver` (union-find) or `FuzzyEntityResolver` (Jaro-Winkler, `fuzzy` extra).
7. **Anonymize**: `AnyAnonymizer` / `Anonymizer` applies span-based replacement using an `AnyPlaceholderFactory`.
8. **Guard rail** (optional): `AnyGuardRail` (`components/guard/`) re-checks the output for residual PII and raises `PIIRemainingError`. `DetectorGuardRail` re-runs a detector, `LLMGuardRail` (`guard/llm.py`) prompts an LLM to ignore placeholders, `ModerationGuardRail` (`guard/moderation.py`, `mistral` extra) backs the check with Mistral.

Data models (`Entity`, `Detection`, `Span`) are frozen dataclasses under `models/`. Tests use `ExactMatchDetector` to avoid loading real models.

### Placeholder Factories & Preservation Tags

`components/placeholder/tags.py` defines a phantom-type hierarchy (a `str` subclass) describing what a token preserves: label (`<PERSON>` vs `[REDACT]`), identity (`<<PERSON:1>>` uniquely identifies), realism (Opaque / Hashed), and shape (masks like `j***@mail.com`). Pipelines are generic on this tag. Factories in `components/placeholder/`: `RedactPlaceholderFactory`, `LabelPlaceholderFactory`, `MaskPlaceholderFactory`, `LabelCounterPlaceholderFactory` (`<<PERSON:1>>`), `LabelHashPlaceholderFactory` (pepper via `PIIGHOST_HASH_PEPPER`). The middleware requires a token that preserves recognizable identity (`PreservesRecognizableIdentity`) so it can find and restore it. There is no Faker factory.

### Conversation Layer

`ThreadAnonymizationPipeline` (`pipeline/thread.py`) extends the base pipeline to keep a value's token stable across a whole thread, assigning tokens over the union of every message's detections. `conversation_memory/` holds the memory port plus `InMemoryConversationMemory` and a Redis backend (`redis_backend.py`, `redis` extra); the Redis backend optionally encrypts stored values with AES-GCM and hashes the storage keys with Argon2id (`crypto/`, `crypto` / `argon2` extras, keyed by `PIIGHOST_CIPHER_KEY`). `thread_id` propagates via a ContextVar (default `"default"`); `require_thread_id` refuses the shared default. `forget_thread(thread_id)` purges a conversation. There is no result cache (no aiocache, no SQLAlchemy cache).

### Middleware Integration

`PIIAnonymizationMiddleware` (`integrations/middleware/langchain.py`) extends LangChain's `AgentMiddleware`:
- Reads `thread_id` from the LangGraph config; `require_thread_id` defaults to `True`, so a missing thread id raises instead of leaking into the shared default.
- Anonymizes messages before the model sees them and deanonymizes for user display.
- `ToolCallStrategy` (`INPUT` / `OUTPUT` / `FULL` / `PASSTHROUGH`) governs tool-call de- and re-anonymization; `InventedPlaceholderStrategy` (`KEEP` / `DROP` / `RAISE`) handles tokens the model made up; `AssistantEntityStrategy` (`PRESERVE` / `ANONYMIZE` / `IGNORE`) handles values the assistant introduces.
- Requires a pipeline whose tokens are recognizable (`pipeline.recognizer`), else raises at construction.

### Configuration & CLI

`config/` builds a full pipeline from a TOML or JSON file via pydantic-settings. `PipelineConfig` and each component config carry a `build()` method (no builder registry, no `from_config` classmethods); `load_config`, `load_pipeline`, and `load_thread_pipeline` combine parsing and building. Secrets are read from the environment only (`PIIGHOST_HASH_PEPPER`, `PIIGHOST_CIPHER_KEY`, `MISTRAL_API_KEY`), raising `ConfigError` at build time when missing. The `piighost` CLI (`cli/`) exposes `validate <file>` and `schema`.

### Other Components

- `integrations/client/remote.py`: `PIIGhostClient`, async httpx client for a remote piighost-api server.
- `observation/`: OpenTelemetry-native tracing behind a `get_tracer()` seam. The pipeline emits per-stage spans; an optional `observation_redactor` tokenizes span payloads so traces stay safe for a PII-untrusted backend. There is no Langfuse or Opik library adapter.
- `text/`: `RecursiveCharacterTextSplitter` and word-boundary helpers used by `ChunkedDetector`.

### Optional Dependencies

Nearly everything beyond the core is an extra (`pyproject.toml`): `gliner2`, `spacy`, `transformers`, `llm`, `middleware`, `config`, `fuzzy`, `redis`, `crypto`, `argon2`, `mistral`, `client`, `observation`, `all`. Imports of optional packages stay inside the modules that need them, guarded and exposed lazily through the package `__getattr__`; `tests/test_optional_dependencies.py` enforces this. Keep new optional features behind the same pattern.

### Design Patterns

Config coupling is **one-way**: `config/` imports and builds the core components, but core modules never import `piighost.config` at runtime (config-model type hints in core are guarded by `TYPE_CHECKING`). Every stage ships an `Any*` port and a `Base*` template in its `base.py`; adding a component means a core adapter plus a config model with a `build()`, never a core-to-config import.

## Conventions

- **Commits**: Conventional Commits via Commitizen (`feat:`, `fix:`, `refactor:`, etc.); releases via `cz bump`
- **Type checking**: PyReFly (not mypy); `make lint` is a blocking gate, `make format` auto-fixes
- **Formatting/linting**: Ruff; security lint via Bandit
- **Package manager**: uv (not pip)
- **Python**: 3.11+

## Documentation

Docs are bilingual and mirrored: every page exists in both `docs/en/` and `docs/fr/`, with nav declared in `zensical.toml` (EN) and `zensical.fr.toml` (FR). Built with Zensical. When touching one language, update the other, and keep the code blocks byte-identical between them.

## Examples

- `examples/`: standalone PEP 723 inline-metadata scripts (`anonymize_basic.py`, `thread_conversation.py`, `guard_rail.py`, `langchain_middleware.py`, `placeholder_styles.py`, plus `strategies/`, `observation/`, `config/`), run with `uv run <script>`.
- `examples/legacy/`: pre-rewrite examples kept for reference, excluded from lint and type checking.

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

# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

### Feat

- **cli**: add `piighost anonymize [TEXT|-]` reading an argument or stdin, with `--config` for a config file, `--api` for a remote piighost-api, `--thread-id`, and `--json` for the text plus detections. The typer app is now built lazily, so running the CLI without typer prints a short install hint to stderr instead of a traceback
- **config**: `linker` and `anonymizer` are optional in `PipelineConfig`, defaulting to `ExactEntityLinker` and an `Anonymizer` with a label-counter factory, so a detector-only config builds a full pipeline
- **api**: re-export the core building blocks from the package root, so `from piighost import AnonymizationPipeline, RegexDetector, Detection, PIIGhostError` works; resolved lazily per name, so the facade never imports an optional extra
- **client**: `PIIGhostClient` accepts `timeout`, `headers` (for example an auth token), and `retries` when built from a base URL. The detection wire format was verified against piighost-api and left unchanged: the server's detect preview uses `start_pos`/`end_pos` and its corrected endpoint accepts `Detection.to_dict()` (`start`/`end`); the two are deliberate, not a mismatch
- **observation**: treat clear-text tracing as an explicit choice. With a tracer provider actually configured and no `observation_redactor`, the pipeline warns once that its traces carry clear PII; `trace_clear_text=True` acknowledges it and silences the warning. Non-breaking: the default still traces clear text. Added `AnyObservationTracer.is_active()` so the nudge fires only when spans really record

### Documentation

- **security**: document the threat-model boundaries the hardening surfaced, the LangGraph state and checkpointer holding restored PII while tool_calls stay tokenized, user-typed token injection and its neutralization, values the assistant introduces staying clear under `PRESERVE`, and NER truncation of over-long text; note them in `SECURITY.md` with a pointer to the full model
- **readme**: fix the stale reference/middleware link (now reference/langchain) and the CLAUDE.md test-path reference

### Fix

- **integrations**: stop mutating the AIMessage tool_calls in the LangChain middleware, so deanonymized tool arguments no longer persist in the LangGraph state nor reach the model on the next turn
- **integrations**: anonymize list/block message content (the Anthropic and multimodal default) and structured (dict/list) tool results, in both the LangChain and Pydantic AI integrations, which previously flowed to the model in clear
- **pipeline**: resolve overlapping detections by default (`ConfidenceOverlapResolver`), which was intended from the start; unresolved overlaps previously corrupted the output and leaked a clear fragment of the losing detection. A true tie now keeps the first detector in order, and `Anonymizer.render` raises `OverlappingSpansError` if any overlap survives to it
- **anonymizer**: deanonymize in a single regex pass, longest token first, so a token that prefixes another (e.g. `[PERSON:1` vs `[PERSON:10` with an empty suffix) no longer corrupts restoration and a restored value that looks like a token is never rescanned
- **placeholder**: bound the token grammar to a label with an optional identifier instead of any `<<...>>` run, so a C++ shift or markdown no longer trips the invented-token guard, and bound the streaming buffer so a stray unclosed `<<` is released rather than held until flush
- **anonymizer**: neutralize a token a user typed in the input (`escape_existing_tokens`, on by default), so it cannot masquerade as an issued token and restore another entity's value
- **detector**: `ExactMatchDetector` now matches on word boundaries (no `Ann` inside `Anne`) and is case-insensitive by default (`case_sensitive` to opt out)
- **detector**: `TransformersDetector` loads its pipeline with `aggregation_strategy` (default `simple`), so sub-word tokens are grouped into whole entities instead of emitted piecemeal
- **detector**: NER detectors accept `max_chars` with `auto_chunk` (default on), so a text longer than the model context is chunked and remapped rather than silently truncated, or raises `TextTooLongError` when chunking is off
- **detector**: `LLMDetector` wraps the source text in tags and instructs the model to treat it as data, not instructions, and exposes `confidence` for arbitration against a NER detector
- **guard**: `LLMGuardRail` accepts `prefix`/`suffix`, so the default prompt's placeholder examples match the pipeline's real delimiters instead of a hardcoded `<<LABEL:N>>`
- **detector**: `RegexDetector` compiles its patterns under `re.ASCII`, so `\d` and the other shape classes match ASCII only; a Unicode digit look-alike (an Arabic-Indic numeral) no longer matches an ASCII-digit PII pattern

### Performance

- **pipeline**: memoize the thread-token map by the thread content it derives from, so rewriting a long history or resolving a stream token by token no longer relinks and re-resolves the whole thread each call (was quadratic with `FuzzyEntityResolver`)
- **memory**: the Redis backend reads a whole thread in one `MGET` instead of one `GET` per message, makes `remember` atomic under a `WATCH` (so concurrent first writes cannot duplicate the index digest), and drops expired digests from the index opportunistically
- **memory**: `InMemoryConversationMemory` no longer creates a phantom entry when reading an unknown thread, and gains `max_threads` (LRU eviction) and `ttl` (lazy expiry) to bound its growth; exposed on `InMemoryConfig`
- **detector**: `ChunkedDetector` scans its chunks concurrently with `asyncio.gather`, so an I/O-bound detector overlaps its calls

## 1.5.0 (2026-08-28)

### Feat

- expose piighost.__version__ from installed distribution metadata
- **integrations**: rename AssistantEntityStrategy to EntityCreateByAssistantStrategy
- **integrations**: optional debug log for the Claude Code hook runner
- **integrations**: targeted per-tool field anonymization for Claude Code tool outputs
- **integrations**: add capture logger to discover Claude Code tool-output shapes
- **integrations**: Claude Code hooks integration for PII de-identification
- **integrations**: stream deanonymization via TextDeidentifier.deanonymize_stream

### Fix

- **examples**: type the streaming example's async generator and guard the optional import for the lint gate

## 1.4.0 (2026-08-23)

### Feat

- **integrations**: move the LangChain middleware to piighost.integrations.langchain

### Fix

- **ci**: silence bandit B105 and widen transformers pyrefly ignores

## 1.3.0 (2026-08-21)

### Feat

- **llama-index**: add the PIIQueryEngine wrapper
- **llama-index**: add the PIINodeAnonymizer ingestion transform
- **config**: add PresidioDetectorConfig
- **detector**: add the Presidio detector adapter

### Fix

- **llama-index**: robust import guard and pyrefly suppressions for a clean env

## 1.2.0 (2026-08-21)

### Feat

- **detector**: add Gliner2PiiDetector PII preset
- **config**: add SqlAlchemyMemoryConfig, make Redis crypto optional
- **memory**: add the SQLAlchemy conversation memory backend
- **memory**: make Redis crypto optional, warn on plaintext
- **memory**: add PIIGhostSecurityWarning and the warn_plaintext helper
- **pydantic-ai**: add assistant_strategy, matching the middleware

### Fix

- **memory**: surface ConfigError for half-configured crypto; test empty-hit; note upsert race

## 1.1.1 (2026-08-16)

### Fix

- **pydantic-ai**: de-identify the tool boundary via tool_strategy
- **examples**: make de-identification visible by asking for a name's first letter

## 1.1.0 (2026-08-15)

### Feat

- resolve a thread's tokens to values on the pipeline and client
- **pipeline**: default ThreadAnonymizationPipeline components, minimal examples
- **integrations**: add Pydantic AI PII de-identification capability
- **placeholder**: add AsyncPlaceholderStreamDecoder for streaming deanonymization

## 1.0.1 (2026-08-13)

### Fix

- **client**: expose detect and labels previews on PIIGhostClient

## 1.0.0 (2026-08-11)

First stable release. PIIGhost was rewritten from scratch into a composable,
hexagonal de-identification pipeline: every stage is a port (an `Any*` protocol)
with a `Base*` template, so detectors, linkers, resolvers, anonymizers, guards,
memory backends, and observation are swappable, and configuration couples to the
core in one direction only.

### BREAKING CHANGE

- The entire public API was redesigned. Imports now live under
  `piighost.components.*`, `piighost.pipeline`, `piighost.config`, and
  `piighost.integrations.*`. `AnonymizationPipeline(detector)` needs only a
  detector, the linker and anonymizer default. The v1 package is gone, along
  with the faker, cache (aiocache), sqlalchemy, langfuse, and opik extras.

### Feat

- **pipeline**: composable detect, resolve overlaps, expand, link, resolve
  entities, anonymize, and guard, with the optional stages disabled by default;
  `ThreadAnonymizationPipeline` keeps tokens stable across a conversation.
- **detector**: regex with EU/US/FR/generic catalogs, exact-match, composite,
  chunked, GLiNER2, spaCy, transformers, and LLM detectors behind one port.
- **placeholder**: redact, label, label-counter, label-hash, and mask factories,
  with a phantom-type tag hierarchy describing what each token preserves; the
  middleware requires a recognizable-identity token.
- **integrations**: LangChain/LangGraph PIIAnonymizationMiddleware with
  tool-call, invented-placeholder, and assistant-entity strategies and strict
  thread isolation; an async HTTP client for a remote piighost-api.
- **config**: pydantic-settings TOML and JSON that build a full pipeline, a
  `piighost` CLI (validate, schema), and secrets read from the environment.
- **memory**: in-memory and Redis conversation memory, with optional AES-GCM
  encryption and Argon2id key hashing of the stored values.
- **observation**: OpenTelemetry-native per-stage spans with an optional payload
  redactor.

### Docs

- New bilingual documentation site (English and French) with an animated
  de-identification hero.

## 0.14.0 (2026-06-10)

### BREAKING CHANGE

- AnyGuardRail.check now receives tokens (third-party guard rails must add the parameter); pipeline cache entries now expire after 3600s by default (set cache_ttl=None in code or cache_ttl = 0 in TOML to keep the previous unbounded retention).

### Feat

- **pipeline**: public detect_entities(thread_id)/get_resolved_tokens/observation; client forget_thread
- **config**: [cache] TOML section (memory/redis/sqlalchemy) with env-var URL indirection
- **config**: expose thresholds, prefixes, salts, validators and mask options in TOML
- **middleware**: recursive tool-arg deanonymization and require_thread_id strict mode
- **pipeline**: forget_thread purge API, 1h default cache TTL, redacted middleware logs
- **guard**: token-aware check() ignores the placeholders the pipeline emitted
- **models**: validate Span bounds, mask Detection repr, add Entity.canonical

### Fix

- **client**: URL-encode thread_id in forget_thread; pin the observation property
- **config**: lazy SQLAlchemy schema, actionable redis ConfigError, CI redis group, serializer contract
- **pipeline**: serialize forget_thread with in-flight writes; expose cache_ttl in TOML
- **pipeline**: lock the key index against concurrent writes; re-publish expired memory snapshots
- **pipeline**: skip empty memory buckets in snapshot; pin fuzzy-merge rank stability
- **pipeline**: stable first-seen token ordering; cache-backed injectable memory
- **pipeline**: cache-first short-circuit on both pipelines; document factory and hook contracts
- **guard**: boundary-anchored, coverage-based token exemption; reject bare-str tokens
- **resolver**: fuzzy keeps anchor-clustering semantics; discriminating scale test
- **packaging**: core no longer imports pydantic; config dispatch lives in builders only
- **pipeline**: word-boundary matching in anonymize_with_ent replacement

### Refactor

- **pipeline**: drop unreachable cache-None branches; truthful docstrings and protocol slimming
- **pipeline**: single stage template with hooks; async opt-in observation pacing

### Perf

- **resolver**: true union-find merge; run composite detectors concurrently

## 0.13.0 (2026-06-02)

### Feat

- **config/detector**: detector `labels` now accept a `{emitted: model}` mapping
  (not just a list) for `gliner2`, `spacy`, `transformers`, and `llm` — query the
  model with one vocabulary and emit clean labels. `transformers` gains an
  optional `labels` field.

## 0.12.1 (2026-06-01)

### Fix

- **config**: alias `AnonymizerConfig` to its single concrete config instead of a
  single-member discriminated union. pydantic >= 2.12 rejects `Discriminator`
  on a non-`Union` type (`TypeError: Discriminator must be used with a Union
  type`), which broke importing `piighost.config.models.pipeline` (and therefore
  `piighost.placeholder` / `piighost.anonymizer`) under pydantic 2.12+.

## 0.12.0 (2026-05-25)

### Feat

- **config**: add TOML pipeline configuration loader (#)
- **cli**: add piighost validate and piighost schema commands
- **config**: export JSON Schema of PipelineConfig
- **config**: translate regex compilation errors into ConfigError
- **config**: add TOML loader, build_pipeline, and PipelineManifest
- **config**: add builder dispatch tables
- add Config + from_config to resolvers, linkers, anonymizer, placeholder factories
- **detector**: add Config + from_config to spacy/transformers/llm/chunked detectors
- **detector**: add Config + from_config to Gliner2Detector
- **detector**: add Config + from_config to RegexDetector
- **config**: add top-level PipelineConfig and PipelineMeta
- **config**: add anonymizer and placeholder factory configuration models
- **config**: add span/linker/entity resolver configuration models
- **config**: add detector configuration models (discriminated union)
- **config**: add _ComponentConfig base model
- **config**: add ConfigError and Pydantic translator
- **examples**: render highlighted spans and detection table
- **examples**: wire streamlit run button to gliner detection
- **examples**: add streamlit input source switcher
- **examples**: add streamlit threshold, flat_ner, chunking sidebar
- **examples**: add streamlit labels widget with presets
- **examples**: add streamlit model selector with cached loader
- **examples**: scaffold streamlit playground entrypoint
- **examples**: wire pipeline as a LangGraph state machine
- **examples**: round-trip deanonymize the extracted JSON
- **examples**: add LLMGuardRail check on extracted JSON
- **examples**: structured extraction via instructor + Mistral
- **examples**: wire piighost CompositeDetector for notarial deeds
- **examples**: scaffold notarial extraction script

### Fix

- **config**: expose validate alias and wire transformers threshold
- **config**: pass locale through to FakerCounter/FakerHash placeholder factories
- **examples**: stabilize LLMGuardRail with temperature=0 + tight prompt
- **examples**: make notarial extraction green end-to-end
- **examples**: final review polish on notarial extraction
- **examples**: drop anticipatory imports + correct gender in sample

### Refactor

- **examples**: move LLMGuardRail into the pipeline
- **examples**: drop LangGraph wrapper from notarial extraction

## 0.11.0 (2026-05-04)

### BREAKING CHANGE

- observation traces emitted by AnonymizationPipeline
are no longer redacted by default. Pass
observation_ph_factory=RedactPlaceholderFactory() to restore the
prior behaviour.

### Feat

- **observation**: wire helpers into ThreadAnonymizationPipeline
- **observation**: wire _obs_text and _obs_detections_to_dicts into base pipeline
- **observation**: default observation_ph_factory to None (raw text)
- **observation**: script to compute HITL precision/recall/F1 per label
- **observation**: script to export HITL traces as a NER dataset
- **observation**: include raw text and label vocabulary in HITL input
- **observation**: emit HITL trace from override_detections
- **cache**: short-circuit anonymize and observation on cached mapping

### Fix

- **observation**: propagate trace attributes around root observation

## 0.10.0 (2026-04-30)

### BREAKING CHANGE

- observe_raw_text was removed. Configure
observation_ph_factory= instead; pass any AnyPlaceholderFactory.

### Feat

- **observation**: add Opik backend for the observation service
- **observation**: redact via placeholder factory instead of [REDACT] sentinel
- **observation**: redact raw user text in observation payloads by default
- **observation**: abstract observation service + Langfuse impl
- **cache**: add SQLAlchemyCache backend for persistent / shared caches
- **guard**: add LLMGuardRail backed by a LangChain chat model
- **pipeline**: add guard-rail stage with DetectorGuardRail
- **placeholder**: add salt and pepper to hash placeholder factories
- **pipeline**: warn when ThreadAnonymizationPipeline uses unshared cache

### Fix

- **ci**: install sqlalchemy extra and skip tests when missing
- **observation**: use propagate_attributes for trace fields in Langfuse v4
- **deps**: include aiosqlite in the sqlalchemy extra

### Refactor

- **models**: drop Detection.__repr__ masking, use standard dataclass repr

## 0.9.1 (2026-04-26)

## 0.9.0 (2026-04-25)

### BREAKING CHANGE

- the four renames above plus the Counter separator
change. Update class imports, factory references, and any code that
parses ``<<LABEL_N>>`` tokens to expect ``<<LABEL:N>>``. The
RealisticHash strategy helpers (``hashed_email``, ``hashed_with_prefix``,
``hashed_template``) are removed; use base/template strings or the new
``fake_*`` callables.
- ConstantPlaceholderFactory (added in the previous
commit) is renamed to RedactPlaceholderFactory, and the existing
RedactPlaceholderFactory is renamed to LabelPlaceholderFactory.
Update imports and class references.
- HashPlaceholderFactory is renamed to
LabeledHashPlaceholderFactory. Update imports and class references.
- HashPlaceholderFactory and RedactPlaceholderFactory
now produce tokens wrapped in <<...>> instead of <...>. Any cache or
LLM prompt that referenced the old format will need to be cleared
or updated. The change is purely cosmetic: the cache mapping logic,
the type system, and the middleware constraint are unaffected.

### Feat

- **placeholder**: add Counter variants, restructure naming as Style+Mechanism
- **placeholder**: add Constant, AnonymousHash, RealisticHash factories; rename Hash
- **pipeline**: allow disabling NER compensator components
- **placeholder**: wrap Hash and Redact tokens in <<...>>
- **placeholder**: tag factories with preservation level for type-safe wiring
- **middleware**: add ToolCallStrategy for tool-call handling
- expose core Protocol types from the top-level package
- expose piighost.labels module with common PII label constants
- **pipeline**: bound ConversationMemory growth via LRU eviction
- **pipeline**: add cache_ttl parameter to bound cache entry lifetime

### Fix

- **lint**: resolve pyrefly errors across src, tests, and examples
- **tests**: replace re.NOFLAG with 0 for Python 3.10 compatibility
- **pipeline**: make ThreadAnonymizationPipeline thread_id propagation concurrency-safe

### Refactor

- **placeholder**: swap Constant and Redact factory names
- **placeholder**: split identity from label via multi-inheritance
- **placeholder**: turn preservation tags into an inheritance hierarchy
- **middleware**: expose tool_strategy as a public attribute
- replace @dataclass with explicit __init__ on behavior classes
- **models**: move Detection and Entity serialization into dataclasses
- **pipeline**: name cache key prefixes as module constants
- **similarity**: extract Jaro-Winkler magic numbers into named constants

### Perf

- **pipeline**: replace token loop with single-pass regex alternation
- **memory**: O(1) canonical lookup in ConversationMemory
- **chunked**: run chunk detections concurrently via asyncio.gather
- pre-compile regex patterns in hot paths

## 0.8.0 (2026-04-24)

### Feat

- **models**: mask raw PII text in Detection repr
- **detector**: add regex packs by region and checksum validators
- expose ExactMatchDetector publicly

### Fix

- **client**: use typing_extensions.Self on Python 3.10
- **test**: restrict pytest to tests/ to skip scripts/ demos

### Refactor

- **test**: drop the unused first setup in roundtrip length test

### Perf

- **test**: disable unused pytest plugins (anyio, faker, langsmith)
- **test**: exclude heavy-dep tests by default and enable asyncio auto mode

## 0.7.0 (2026-04-16)

### Feat

- add detect preview and detection override to pipeline and client

## 0.6.0 (2026-04-16)

### Feat

- add ChunkedDetector for long texts exceeding NER model context windows
- add LLMDetector for entity extraction via structured output
- add BaseNERDetector ABC with internal/external label mapping
- add base classes with min_text_length and confidence_threshold filtering

## 0.5.1 (2026-04-07)

### Fix

- skip ToolMessages in abefore/aafter_model, reject non-reversible factories

## 0.5.0 (2026-03-31)

### Feat

- add transformers detector for hugging face ner models
- add spacy detector for spacy NER model integration
- add piighost[all] optional group and dependency acceptance tests

### Fix

- raise DeanonymizationError instead of silently skipping missing tokens

## 0.4.2 (2026-03-30)

### Fix

- guard optional dependency imports (aiocache, faker, langgraph)

## 0.4.1 (2026-03-30)

### Fix

- impossible to use client because annotation are after import

## 0.4.0 (2026-03-30)

### Feat

- add async http client for piighost-api

## 0.3.0 (2026-03-29)

### Feat

- add cross-message entity linking via linker.link_entities
- add faker placeholder factory with configurable label-to-provider strategies
- add mask placeholder factory with configurable label-to-function masking strategies
- add mask placeholder factory for partial masking anonymization strategy

### Refactor

- extract _deanonymize helper and clean up middleware
- convert lambda assignments to def functions in tests
- reorganize tests directory to mirror src package structure
- create own module for each step of pipeline

## 0.2.0 (2026-03-28)

### Feat

- add cache-backed deanonymization with CacheMissError fallback and fix middleware await
- **v2**: add fuzzy entity resolution with jaro-winkler and levenshtein similarity
- **v2**: add conversation memory and conversation anonymization pipeline for cross-message deanonymization
- **v2**: add conversation memory and conversation anonymization pipeline for cross-message token consistency
- **v2**: add async anonymization pipeline with aiocache detector and deanonymization cache
- **v2**: add Anonymizer with placeholder factories (counter, hash, redact), make Entity frozen
- **v2**: add merge entity conflict resolver with union-find strategy
- **v2**: add entity model and exact entity linker for detection expansion and grouping
- **v2**: add span conflict resolver with confidence-based strategy
- **v2**: add detector with word-boundary regex matching
- **v2**: rework models of library
- add last work of claude code (full bullshit lmao)
- add RedactPlaceholderFactory with irreversible anonymization guard
- add pre-built PII regex detector examples for US and Europe

### Fix

- **v2**: resolve lint errors, fix tuple return types and default cache serialization

### Refactor

- **v2**: delete old code, set v2 to main package
- complete review of code, delete useless code
- **v2**: remove abstract base classes, keep protocol + implementation only
- extract PlaceholderRegistry from Pipeline, clarify Anonymizer statefulness and public API
- deduplicate pipeline/placeholder cache, fix types and dead code, dispatch AI/tool messages via reanonymize in abefore_model
- replace isinstance checks with polymorphic PlaceholderFactory hierarchy

## [0.1.0] - 2025-03-22

### Features

- **anonymizer**: 4-stage pipeline (Detect → Expand → Map → Replace) with protocol-based dependency injection
- **detector**: `GlinerDetector` using GLiNER2 NER for entity detection
- **occurrence-finder**: `RegexOccurrenceFinder` for word-boundary regex matching of all entity occurrences
- **placeholder-factory**: `CounterPlaceholderFactory` for stable `<<LABEL_N>>` tags
- **span-replacer**: `SpanReplacer` with reverse spans for reliable deanonymization
- **pipeline**: `AnonymizationPipeline` with `PlaceholderStore` protocol for cross-session caching (SHA-256 keyed)
- **middleware**: `PIIAnonymizationMiddleware` for LangChain/LangGraph hooks on `abefore_model`, `aafter_model`, `awrap_tool_call`
- **pipeline**: `deanonymize_value` for per-argument placeholder resolution
- **examples**: LangGraph + FastAPI example with React frontend and Aegra integration

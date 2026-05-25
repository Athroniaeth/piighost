# TOML pipeline configuration — design

**Status:** draft (awaiting user review)
**Date:** 2026-05-25
**Scope:** `piighost` (library) and `piighost-api` (REST server)
**Stack:** Python 3.12+, Pydantic v2, `tomllib` (stdlib), Typer, Litestar (server)

## Goal

Replace the current Python-file pipeline definition (`pipeline:pipeline` import path consumed by `piighost-api`) with a declarative TOML format owned by the `piighost` library. A TOML configuration fully describes a `ThreadAnonymizationPipeline` without any user-supplied Python code.

Primary drivers:

1. **Security.** An API operator should never load arbitrary Python at boot. Today `piighost-api serve myconfig:pipeline` imports a user module, which is a code-execution vector. TOML removes that vector.
2. **Configurability for non-developers.** A declarative format makes it realistic to ship a future web UI that builds pipelines visually. The JSON Schema exported from the Pydantic models is the contract that UI consumes.
3. **Smaller barrier to entry.** A user can try `piighost-api` by writing 20 lines of TOML instead of by writing Python that wires up six dataclasses.

## Non-goals

- **HTTP / RPC detectors.** A reserved `type = "http"` slot is left in the schema for a future detector that delegates to a remote inference service, but the implementation is out of scope here. Phase suivante.
- **Multi-configuration in a single instance.** One API process serves one TOML. Multiple configs at runtime is multi-process, multi-container, multi-pod, handled by the deployment layer, not by `piighost-api`.
- **Lazy model loading / LRU eviction.** Models load at boot, fail fast. No on-demand load.
- **Entry-point based plugin extension.** No third-party components in this phase. The component registry is closed and shipped with the library.
- **Web UI.** This spec produces the JSON Schema the UI will need, nothing more.
- **Community config repository.** Out of scope. Mentioned in conversation as a long-term direction.
- **Backwards compatibility with the Python `module:variable` loader in `piighost-api`.** Removed. See migration section.

## Architecture overview

```
piighost (library)
└── piighost/
    ├── config/                       NEW
    │   ├── __init__.py               # public API: load_pipeline, load_config,
    │   │                             # build_pipeline, export_schema, validate
    │   ├── loader.py                 # parses TOML → Pydantic models → instances
    │   ├── builders.py               # type[Config] → type[Component] mappings
    │   ├── errors.py                 # ConfigError hierarchy
    │   └── models/
    │       ├── __init__.py
    │       ├── pipeline.py           # top-level PipelineConfig
    │       ├── detector.py           # discriminated union of detector configs
    │       ├── span_resolver.py
    │       ├── entity_linker.py
    │       ├── entity_resolver.py
    │       ├── anonymizer.py
    │       └── placeholder.py
    └── cli/                          NEW
        └── __init__.py               # Typer entry-point: piighost validate / schema

piighost-api
└── piighost_api/
    ├── cli.py                        UPDATED  (serve signature changes)
    ├── app.py                        UPDATED  (load via piighost.config,
    │                                          /v1/config → /v1/labels)
    └── loader.py                     REMOVED
```

The `piighost` library gains two new sub-packages (`config`, `cli`). The rest of the library is untouched. `piighost-api` shrinks (its own loader becomes a one-line call to `piighost.config.load_pipeline`).

## TOML schema

### Top-level layout

```toml
[pipeline]                      # entire section optional; defaults below
name = "pii-en-multi"           # optional, exposed by /v1/labels
description = "..."             # optional, free text
schema_version = 1              # optional, default 1, currently the only valid value

[[detectors]]
# at least one [[detectors]] entry; multiple form an implicit CompositeDetector
type = "regex"
# ...

[span_resolver]
type = "confidence"             # default if section omitted

[entity_linker]
type = "exact"                  # default if section omitted

[entity_resolver]
type = "merge"                  # default if section omitted

[anonymizer]
type = "default"                # default if section omitted

[anonymizer.placeholder_factory]
type = "label_counter"          # default if section omitted
```

All stage sections except `[[detectors]]` are optional. Omitted sections use the documented defaults above. At least one detector entry is mandatory.

### Detector types

| `type`         | Library class             | Required params                              |
| -------------- | ------------------------- | -------------------------------------------- |
| `regex`        | `RegexDetector`           | `patterns: dict[str, str]`                   |
| `gliner2`      | `Gliner2Detector`         | `model: str`, `labels: list[str]`            |
| `spacy`        | `SpacyDetector`           | `model: str`, `labels: list[str]`            |
| `transformers` | `TransformersDetector`    | `model: str`                                 |
| `llm`          | `LLMDetector`             | `provider`, `model`, `labels` (api key: env) |
| `chunked`      | `ChunkedDetector`         | `chunk_size: int`, `inner: <detector cfg>`   |

A future `http` detector is described in "Phase suivante" below. It is conceptually reserved but **not** present in the discriminator in this phase. A TOML using `type = "http"` is rejected by Pydantic's discriminator with the standard "unknown type" error, same as any typo.

Each detector entry accepts an optional `name: str` used in the `/v1/labels` response grouping. `ExactMatchDetector` is intentionally not exposed (test-only).

### Resolver / linker / anonymizer types

| Section            | `type` values                                                              |
| ------------------ | -------------------------------------------------------------------------- |
| `span_resolver`    | `confidence`, `disabled`                                                   |
| `entity_linker`    | `exact`, `disabled`                                                        |
| `entity_resolver`  | `merge`, `fuzzy` (with `threshold: float`), `disabled`                     |
| `anonymizer`       | `default`                                                                  |
| `placeholder_factory` | `label_counter`, `label_hash`, `label`, `mask`, `redact_counter`, `redact_hash`, `redact`, `faker_counter`, `faker_hash`, `faker` |

`faker_*` factories accept an optional `locale: str` (default `"en_US"`).

### Validation rules

- `extra = "forbid"` on every Pydantic model. Unknown keys are errors, not warnings.
- Regex patterns are compiled at load. A `re.error` becomes a `ConfigError` with the offending pattern key.
- `threshold` fields are bounded `0.0 <= x <= 1.0`.
- `chunk_size` is bounded `>= 1`.
- API keys, secrets, peppers are never present in TOML. The relevant detectors read them from environment variables (`PIIGHOST_LLM_API_KEY`, etc.). A TOML containing an `api_key` key under `[[detectors]]` is rejected by `extra = "forbid"`.

### Example

```toml
[pipeline]
name = "pii-en-multi"
schema_version = 1

[[detectors]]
name = "common"
type = "regex"
patterns = { EMAIL = "[a-zA-Z0-9._%+\\-]+@[a-zA-Z0-9.\\-]+\\.[a-zA-Z]{2,}", IP_V4 = "\\b(?:\\d{1,3}\\.){3}\\d{1,3}\\b" }

[[detectors]]
name = "gliner2"
type = "gliner2"
model = "fastino/gliner2-multi-v1"
threshold = 0.5
labels = ["person", "city", "email address"]

[anonymizer.placeholder_factory]
type = "label_counter"
```

## Loader architecture

### Component-config pairing

Each existing component class gains a `Config` class-attribute pointing to its Pydantic model and a `from_config` classmethod that builds an instance from a validated config. Example:

```python
# piighost/detector/gliner2.py
@dataclass(frozen=True)
class Gliner2Detector:
    model: GLiNER2
    threshold: float
    labels: tuple[str, ...]

    Config: ClassVar[type[BaseModel]] = "Gliner2DetectorConfig"  # forward ref

    @classmethod
    def from_config(cls, cfg: "Gliner2DetectorConfig") -> "Gliner2Detector":
        return cls(
            model=GLiNER2.from_pretrained(cfg.model),
            threshold=cfg.threshold,
            labels=tuple(cfg.labels),
        )

    def detect(self, text: str) -> list[Detection]: ...
```

This keeps two distinct types (the config and the operational component) but makes the relationship between them owned by the component itself, not by a separate factory file. Rationale: a `Gliner2Detector` holds a 500 MB PyTorch model, which is not serializable, has no place in a TOML, and would break `model_dump()` if fused into a `BaseModel`. Configs and components have different lifecycles and responsibilities.

### Pydantic models

```python
# piighost/config/models/detector.py
from typing import Annotated, ClassVar, Literal
from pydantic import BaseModel, ConfigDict, Discriminator, Field

class _ComponentConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

class RegexDetectorConfig(_ComponentConfig):
    type: Literal["regex"]
    name: str | None = None
    patterns: dict[str, str]

class Gliner2DetectorConfig(_ComponentConfig):
    type: Literal["gliner2"]
    name: str | None = None
    model: str
    threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    labels: list[str] = Field(min_length=1)

# ... one model per concrete component

DetectorConfig = Annotated[
    RegexDetectorConfig
    | Gliner2DetectorConfig
    | SpacyDetectorConfig
    | TransformersDetectorConfig
    | LLMDetectorConfig
    | ChunkedDetectorConfig,
    Discriminator("type"),
]
```

`PipelineConfig` at the top level:

```python
class PipelineConfig(_ComponentConfig):
    pipeline: PipelineMeta = Field(default_factory=PipelineMeta)
    detectors: list[DetectorConfig] = Field(min_length=1)
    span_resolver: SpanResolverConfig = Field(default_factory=ConfidenceSpanResolverConfig)
    entity_linker: EntityLinkerConfig = Field(default_factory=ExactEntityLinkerConfig)
    entity_resolver: EntityResolverConfig = Field(default_factory=MergeEntityResolverConfig)
    anonymizer: AnonymizerConfig = Field(default_factory=DefaultAnonymizerConfig)
```

### Builders (factory mapping)

`piighost/config/builders.py` holds plain `dict` mappings from config type to component type. Dispatch is by config class identity, not by string. Pydantic has already discriminated and produced the right config subclass.

```python
_DETECTOR_BUILDERS: dict[type[BaseModel], type[AnyDetector]] = {
    RegexDetectorConfig: RegexDetector,
    Gliner2DetectorConfig: Gliner2Detector,
    SpacyDetectorConfig: SpacyDetector,
    TransformersDetectorConfig: TransformersDetector,
    LLMDetectorConfig: LLMDetector,
    ChunkedDetectorConfig: ChunkedDetector,
}

def build_detector(cfg: DetectorConfig) -> AnyDetector:
    return _DETECTOR_BUILDERS[type(cfg)].from_config(cfg)
```

Same pattern for span resolvers, entity linkers, entity resolvers, anonymizer placeholder factories. Five small mappings, no global mutable state, fully type-checkable.

### Public API

```python
# piighost/config/__init__.py

def load_config(path: str | Path) -> PipelineConfig:
    """Parse and validate a TOML file. Does not instantiate components."""

def build_pipeline(cfg: PipelineConfig) -> tuple[ThreadAnonymizationPipeline, PipelineManifest]:
    """Instantiate the pipeline + return an introspectable manifest."""

def load_pipeline(path: str | Path) -> tuple[ThreadAnonymizationPipeline, PipelineManifest]:
    """Convenience: load_config + build_pipeline in one call."""

def export_schema() -> dict:
    """Return the JSON Schema of PipelineConfig (used by piighost schema CLI
    and by future configuration UIs)."""

def validate(path: str | Path) -> PipelineConfig:
    """Alias of load_config, exposed under a name that makes the CLI intent
    obvious (piighost validate <file>)."""
```

### Manifest for introspection

```python
@dataclass(frozen=True)
class DetectorManifest:
    name: str | None
    type: str
    labels: list[str]

@dataclass(frozen=True)
class PipelineManifest:
    name: str | None
    schema_version: int
    detectors: list[DetectorManifest]
    placeholder_factory_type: str   # not exposed by /v1/labels; reserved
                                    # for a future /v1/manifest route and
                                    # for in-process debug logging
```

`build_pipeline` returns the manifest alongside the pipeline. The manifest is the source of truth for `/v1/labels`. Label introspection works by component type:

```python
def _detector_labels(d: AnyDetector) -> list[str]:
    if isinstance(d, RegexDetector):     return sorted(d.patterns.keys())
    if isinstance(d, ChunkedDetector):   return _detector_labels(d.inner)
    if hasattr(d, "labels"):             return sorted(d.labels)
    return []
```

`CompositeDetector` is never named in the manifest. It is created implicitly when multiple `[[detectors]]` entries are present, and the manifest lists the constituents.

### Error handling

```python
class ConfigError(Exception):
    """Raised when a TOML configuration cannot be loaded into a pipeline."""

    @classmethod
    def from_pydantic(cls, err: ValidationError, path: Path) -> "ConfigError":
        """Translate a Pydantic ValidationError into a human-readable
        message that names the failing TOML location and the reason."""
```

Example error message:

```
ConfigError: invalid configuration in /etc/piighost/pipeline.toml
  detectors[1].threshold: input should be <= 1.0, got 1.5
  detectors[2].patterns.EMAIL: regex did not compile: missing ')'
```

No line numbers (stdlib `tomllib` does not expose them in a structured way), but the dotted path is precise enough.

## piighost-api changes

### CLI

```python
# piighost_api/cli.py

@app.command()
def serve(
    config: Path | None = typer.Option(
        None, "--config", "-c",
        help="Path to TOML config file. Falls back to PIIGHOST_CONFIG env var.",
    ),
    host: str = typer.Option("127.0.0.1"),
    port: int = typer.Option(8000),
    log_level: str = typer.Option("info"),
) -> None:
    config = config or Path(os.environ.get("PIIGHOST_CONFIG", "")) or None
    if config is None or not config.exists():
        typer.echo(
            "Missing --config or PIIGHOST_CONFIG. Pass a TOML file path.",
            err=True,
        )
        raise typer.Exit(code=1)
    os.environ["PIIGHOST_CONFIG"] = str(config.resolve())
    uvicorn.run("piighost_api.cli:_create_app", factory=True,
                host=host, port=port, log_level=log_level)


def _create_app():
    from piighost_api.app import create_app
    return create_app(Path(os.environ["PIIGHOST_CONFIG"]))
```

The positional `pipeline: str` argument is gone. The `PIIGHOST_PIPELINE` env var is gone.

### `create_app`

```python
def create_app(config_path: Path) -> Litestar:
    pipeline, manifest = load_pipeline(config_path)
    # ... rest unchanged: observation, auth, lifespan, routes ...
    # `manifest` is captured by the /v1/labels closure.
```

### `loader.py` is deleted

`piighost_api/loader.py` (the `module:variable` loader) is removed entirely. Its responsibility moves to `piighost.config.load_pipeline`.

## /v1/labels route

Replaces `/v1/config` (deleted). Format:

```json
{
  "pipeline": {"name": "pii-en-multi", "schema_version": 1},
  "detectors": [
    {"name": "common",  "type": "regex",   "labels": ["CREDIT_CARD", "EMAIL", "IP_V4", "URL"]},
    {"name": "gliner2", "type": "gliner2", "labels": ["city", "email address", "person"]}
  ]
}
```

msgspec structs:

```python
class DetectorLabelsSchema(msgspec.Struct):
    name: str | None
    type: str
    labels: list[str]

class PipelineMetaSchema(msgspec.Struct):
    name: str | None
    schema_version: int

class LabelsResponse(msgspec.Struct):
    pipeline: PipelineMetaSchema
    detectors: list[DetectorLabelsSchema]
```

Handler:

```python
@get("/v1/labels", exclude_from_auth=True)
async def labels() -> LabelsResponse:
    return LabelsResponse(
        pipeline=PipelineMetaSchema(
            name=manifest.name,
            schema_version=manifest.schema_version,
        ),
        detectors=[
            DetectorLabelsSchema(name=d.name, type=d.type, labels=d.labels)
            for d in manifest.detectors
        ],
    )
```

`exclude_from_auth=True` matches `/health` and `/`. Labels are part of the public API contract, not sensitive data.

## CLI helpers

A new `piighost` console entry-point is added (`pyproject.toml`: `piighost = "piighost.cli:main"`), using Typer.

```bash
piighost validate ./pipeline.toml
# Parses + validates with Pydantic. Does not instantiate detectors
# (no model loading). Prints "OK" on success, structured error on failure.
# Exit code 0 on success, 1 on validation error.

piighost schema
# Prints the JSON Schema of PipelineConfig to stdout (indented JSON).
# Used by the future web UI for form rendering and by editor tooling.
```

`piighost init` (scaffold a starter TOML) is not in this phase. Copying from the docs is enough.

## Testing strategy

### piighost

New `tests/test_config.py`:

- **Round-trip per detector type.** A TOML containing exactly one detector of each type loads to a working pipeline. ML-heavy detectors (`gliner2`, `spacy`, `transformers`) gated by pytest markers and skipped if the model is not available locally. `llm` mocked.
- **Validation errors.** Six fixture TOMLs covering: unknown key (`extra="forbid"`), wrong type, threshold out of bounds, unparseable regex, missing required field, empty `[[detectors]]`. Each raises `ConfigError` with the expected path in the message.
- **Defaults.** A minimal TOML with only one `[[detectors]]` block instantiates a full pipeline with `confidence`, `exact`, `merge`, `default` + `label_counter`.
- **Manifest correctness.** Multi-detector TOML produces a manifest whose `detectors` list matches the input order, with correct labels per detector type (regex → patterns keys; gliner2 → labels list; chunked → inner labels).
- **JSON Schema export.** `export_schema()` returns a dict with `$defs`, `discriminator`, and all known `type` values. Snapshot test to flag accidental schema breakage.

### piighost-api

- Existing fixtures replace `pipeline.py` with `pipeline.toml`.
- New test for `/v1/labels` covering single-detector and multi-detector configs (groupings, ordering).
- New test that `serve` without `--config` and without `PIIGHOST_CONFIG` exits with code 1 and a clear message.
- Test that `/v1/config` returns 404 (route removed).

## Migration and breaking changes

### piighost (library)

Additive. No breaking change. Minor version bump.

Conventional commit:
```
feat(config): add TOML pipeline configuration loader
```

### piighost-api

Breaking:

- `piighost-api serve <module:variable>` → `piighost-api serve --config <path.toml>`.
- `PIIGHOST_PIPELINE` env var → `PIIGHOST_CONFIG`.
- `/v1/config` route deleted, replaced by `/v1/labels` with a richer body.
- Public `create_app(pipeline_path: str)` signature changes to `create_app(config_path: Path)`.
- `loader.py` deleted.

Pre-1.0 versioning convention: minor bump with `!` marker.

Conventional commit:
```
feat(cli)!: replace Python pipeline loader with TOML configuration

BREAKING CHANGE: piighost-api serve now requires --config <path.toml>
instead of a module:variable Python import path. /v1/config is
replaced by /v1/labels with a per-detector grouping. See the new
migration guide for the equivalent TOML of common Python pipelines.
```

### piighost-chat and piighost-proofreader

No required change. They consume the REST API. Verify they do not call `/v1/config`; if they do, update to `/v1/labels`.

## Documentation deliverables

In the same PR as the implementation:

- `piighost/docs/en/...` and `piighost/docs/fr/...`: new "TOML configuration" page with the full schema and three example pipelines (mono-detector regex, multi-detector GLiNER2 + regex, LLM with Faker placeholders).
- `piighost-api/docs/en/getting-started/quickstart.md`: replace the `pipeline:pipeline` example with a minimal `pipeline.toml`.
- `piighost-api/docs/en/reference/cli.md`: new `serve --config` signature.
- `piighost-api/docs/en/reference/endpoints.md`: replace `/v1/config` section with `/v1/labels`.
- `piighost-api/docs/en/migration.md` (new): "Migrating from Python pipeline files" with a before/after table for each component.

## Open questions / phase suivante

- **HTTP detector.** Reserved `type = "http"` slot. Phase suivante adds the implementation + a reference inference service that hosts GLiNER2 behind an HTTP endpoint. That unlocks running multiple `piighost-api` instances against a single model server.
- **Web UI.** Consumes `piighost schema` output to render the form. Lives in its own repository.
- **Community config repository.** Long-term direction mentioned during brainstorming.
- **Entry-point plugin extension.** If third-party components become a real need, the registry becomes open via `pyproject.toml`'s `[project.entry-points."piighost.detectors"]`. The dispatch mapping would be populated at startup from those entry points. Out of scope for this phase.

"""Pipeline configuration settings and the loading entry points.

PipelineConfig is a pydantic-settings model layering, in decreasing precedence,
explicit init arguments, environment variables prefixed PIIGHOST_, then the TOML
file. The file path is injected per call through a context variable read by
settings_customise_sources, so the path is not frozen at class definition.
"""

import tomllib
from contextvars import ContextVar
from pathlib import Path
from typing import ClassVar, cast

from pydantic import ValidationError
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

from piighost.components.placeholder.tags import PlaceholderPreservation
from piighost.config.models.anonymizer import AnonymizerConfig
from piighost.config.models.detector import DetectorConfig
from piighost.config.models.entity_resolver import EntityResolverConfig
from piighost.config.models.expander import ExpanderConfig
from piighost.config.models.guard import GuardConfig
from piighost.config.models.linker import LinkerConfig
from piighost.config.models.memory import MemoryConfig
from piighost.config.models.overlap_resolver import OverlapResolverConfig
from piighost.config.models.override import OverrideConfig
from piighost.config.models.placeholder import PlaceholderConfig
from piighost.exceptions import ConfigError, ConfigFileError, ConfigValidationError
from piighost.pipeline import (
    AnonymizationPipeline,
    BaseAnonymizationPipeline,
    ThreadAnonymizationPipeline,
)

_toml_path: ContextVar[Path | None] = ContextVar("_toml_path", default=None)
"""The TOML file the current load reads, set by load_config, read by the source."""


class PipelineConfig(BaseSettings):
    """The whole pipeline configuration, loaded from TOML with env overrides.

    Attributes:
        name: An optional name for the pipeline, a top-level scalar an env var
            can override.
        detector: The detector stage configuration.
        linker: The entity linker configuration.
        anonymizer: The anonymizer configuration.
        overlap_resolver: The optional overlapping-detection resolver stage.
        expander: The optional missed-occurrence expander stage.
        entity_resolver: The optional entity-conflict resolver stage.
        guard: The optional residual-PII guard rail stage.
        override: The optional detection-override stage.
        observation_redactor: The optional placeholder factory redacting
            observation payloads.
        memory: The optional conversation memory; when set, the pipeline is a
            thread pipeline keeping per-thread state.
    """

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_prefix="PIIGHOST_", extra="forbid"
    )

    name: str | None = None
    detector: DetectorConfig
    linker: LinkerConfig
    anonymizer: AnonymizerConfig
    overlap_resolver: OverlapResolverConfig | None = None
    expander: ExpanderConfig | None = None
    entity_resolver: EntityResolverConfig | None = None
    guard: GuardConfig | None = None
    override: OverrideConfig | None = None
    observation_redactor: PlaceholderConfig | None = None
    memory: MemoryConfig | None = None

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Layer init, then env, then the TOML file the current load points at."""
        sources: list[PydanticBaseSettingsSource] = [init_settings, env_settings]
        path = _toml_path.get()
        if path is not None:
            sources.append(TomlConfigSettingsSource(settings_cls, toml_file=path))
        return tuple(sources)

    def build(self) -> BaseAnonymizationPipeline[PlaceholderPreservation]:
        """Assemble the pipeline the configuration describes.

        A configured memory yields a ThreadAnonymizationPipeline keeping a
        per-thread conversation memory; without it, a stateless
        AnonymizationPipeline.
        """
        detector = self.detector.build()
        linker = self.linker.build()
        anonymizer = self.anonymizer.build()
        overlap_resolver = (
            self.overlap_resolver.build() if self.overlap_resolver else None
        )
        expander = self.expander.build() if self.expander else None
        entity_resolver = self.entity_resolver.build() if self.entity_resolver else None
        guard = self.guard.build() if self.guard else None
        override = self.override.build() if self.override else None
        observation_redactor = (
            self.observation_redactor.build() if self.observation_redactor else None
        )
        if self.memory is not None:
            return ThreadAnonymizationPipeline(
                detector,
                linker,
                anonymizer,
                memory=self.memory.build(),
                overlap_resolver=overlap_resolver,
                expander=expander,
                entity_resolver=entity_resolver,
                guard=guard,
                observation_redactor=observation_redactor,
                override=override,
            )
        return AnonymizationPipeline(
            detector,
            linker,
            anonymizer,
            overlap_resolver=overlap_resolver,
            expander=expander,
            entity_resolver=entity_resolver,
            guard=guard,
            observation_redactor=observation_redactor,
            override=override,
        )


def load_config(path: str | Path) -> PipelineConfig:
    """Parse and validate a TOML file into a PipelineConfig, building nothing.

    Raises:
        ConfigFileError: If the file is missing, unreadable, or invalid TOML.
        ConfigValidationError: If the parsed data fails schema validation.
    """
    resolved = Path(path)
    if not resolved.is_file():
        raise ConfigFileError(f"configuration file not found: {resolved}")

    token = _toml_path.set(resolved)
    try:
        return PipelineConfig()
    except tomllib.TOMLDecodeError as exc:
        raise ConfigFileError(f"invalid TOML in {resolved}: {exc}") from exc
    except OSError as exc:
        raise ConfigFileError(f"cannot read {resolved}: {exc}") from exc
    except ValidationError as exc:
        raise ConfigValidationError(
            f"invalid configuration in {resolved}: {exc}"
        ) from exc
    finally:
        _toml_path.reset(token)


def load_pipeline(path: str | Path) -> AnonymizationPipeline[PlaceholderPreservation]:
    """Load a configuration and build its stateless AnonymizationPipeline.

    Raises:
        ConfigError: If the configuration declares a memory, which describes a
            thread pipeline; use load_thread_pipeline instead.
    """
    pipeline = load_config(path).build()
    if not isinstance(pipeline, AnonymizationPipeline):
        raise ConfigError(
            "this configuration declares a memory; use load_thread_pipeline"
        )
    return cast(AnonymizationPipeline[PlaceholderPreservation], pipeline)


def load_thread_pipeline(
    path: str | Path,
) -> ThreadAnonymizationPipeline[PlaceholderPreservation]:
    """Load a configuration and build its ThreadAnonymizationPipeline.

    Raises:
        ConfigError: If the configuration declares no memory, which a thread
            pipeline needs; use load_pipeline instead.
    """
    pipeline = load_config(path).build()
    if not isinstance(pipeline, ThreadAnonymizationPipeline):
        raise ConfigError("this configuration declares no memory; use load_pipeline")
    return cast(ThreadAnonymizationPipeline[PlaceholderPreservation], pipeline)

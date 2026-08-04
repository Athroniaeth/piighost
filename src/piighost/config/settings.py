"""Pipeline configuration settings and the loading entry points.

PipelineConfig is a pydantic-settings model layering, in decreasing precedence,
explicit init arguments, environment variables prefixed PIIGHOST_, then the TOML
file. The file path is injected per call through a context variable read by
settings_customise_sources, so the path is not frozen at class definition.
"""

import tomllib
from contextvars import ContextVar
from pathlib import Path
from typing import ClassVar

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
from piighost.config.models.linker import LinkerConfig
from piighost.exceptions import ConfigFileError, ConfigValidationError
from piighost.pipeline import AnonymizationPipeline

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
    """

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_prefix="PIIGHOST_", extra="forbid"
    )

    name: str | None = None
    detector: DetectorConfig
    linker: LinkerConfig
    anonymizer: AnonymizerConfig

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

    def build(self) -> AnonymizationPipeline[PlaceholderPreservation]:
        """Assemble the AnonymizationPipeline the configuration describes."""
        detector = self.detector.build()
        linker = self.linker.build()
        anonymizer = self.anonymizer.build()
        return AnonymizationPipeline(detector, linker, anonymizer)


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
    """Load a configuration and build its AnonymizationPipeline."""
    return load_config(path).build()

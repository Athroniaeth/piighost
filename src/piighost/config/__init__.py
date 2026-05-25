"""Declarative TOML configuration for piighost pipelines.

Public API:

* :func:`load_config` parses a TOML file into a validated ``PipelineConfig``
  without instantiating any component.
* :func:`build_pipeline` turns a ``PipelineConfig`` into a working
  ``ThreadAnonymizationPipeline`` and a ``PipelineManifest`` describing
  what was built.
* :func:`load_pipeline` is the ``load_config`` + ``build_pipeline`` convenience.
* :func:`validate` is an alias of :func:`load_config`, exposed under a name
  that matches the CLI subcommand.
* :func:`export_schema` dumps the JSON Schema of ``PipelineConfig`` for
  tooling (CLI, future configuration UI).
* :class:`ConfigError` is the single exception type raised by this module.

Symbols other than ``ConfigError`` are lazy-imported via ``__getattr__``
to break a circular import between ``piighost.anonymizer`` /
``piighost.placeholder`` (which import ``piighost.config.models`` at
module load time) and ``piighost.config.loader`` (which imports
``piighost.anonymizer``).
"""

from piighost.config.errors import ConfigError

__all__ = [
    "ConfigError",
    "DetectorManifest",
    "PipelineConfig",
    "PipelineManifest",
    "build_pipeline",
    "export_schema",
    "load_config",
    "load_pipeline",
    "validate",
]


def __getattr__(name: str):
    """Lazy import to avoid a circular import with ``piighost.anonymizer``."""
    if name == "DetectorManifest":
        from piighost.config.loader import DetectorManifest

        return DetectorManifest
    if name == "PipelineManifest":
        from piighost.config.loader import PipelineManifest

        return PipelineManifest
    if name == "build_pipeline":
        from piighost.config.loader import build_pipeline

        return build_pipeline
    if name == "export_schema":
        from piighost.config.loader import export_schema

        return export_schema
    if name == "load_config":
        from piighost.config.loader import load_config

        return load_config
    if name == "load_pipeline":
        from piighost.config.loader import load_pipeline

        return load_pipeline
    if name == "validate":
        from piighost.config.loader import load_config

        return load_config
    if name == "PipelineConfig":
        from piighost.config.models.pipeline import PipelineConfig

        return PipelineConfig
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

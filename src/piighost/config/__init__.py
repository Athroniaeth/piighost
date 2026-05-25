"""Declarative TOML configuration for piighost pipelines.

Public API:

* :func:`load_config` parses a TOML file into a validated ``PipelineConfig``
  without instantiating any component.
* :func:`build_pipeline` turns a ``PipelineConfig`` into a working
  ``ThreadAnonymizationPipeline`` and a ``PipelineManifest`` describing
  what was built.
* :func:`load_pipeline` is the ``load_config`` + ``build_pipeline`` convenience.
* :func:`export_schema` dumps the JSON Schema of ``PipelineConfig`` for
  tooling (CLI, future configuration UI).
* :class:`ConfigError` is the single exception type raised by this module.
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
]


def __getattr__(name: str):
    """Lazy import to avoid circular dependencies."""
    if name == "DetectorManifest":
        from piighost.config.loader import DetectorManifest

        return DetectorManifest
    elif name == "PipelineManifest":
        from piighost.config.loader import PipelineManifest

        return PipelineManifest
    elif name == "build_pipeline":
        from piighost.config.loader import build_pipeline

        return build_pipeline
    elif name == "export_schema":
        from piighost.config.loader import export_schema

        return export_schema
    elif name == "load_config":
        from piighost.config.loader import load_config

        return load_config
    elif name == "load_pipeline":
        from piighost.config.loader import load_pipeline

        return load_pipeline
    elif name == "PipelineConfig":
        from piighost.config.models.pipeline import PipelineConfig

        return PipelineConfig
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

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

__all__ = ["ConfigError"]

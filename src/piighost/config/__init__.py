"""Configuration: build a pipeline from a TOML file.

This package needs the config optional dependencies (pydantic-settings). It is
guarded so importing it without them raises an ImportError pointing at the
extra. The core never imports this package; configuration depends on the core,
not the other way round.
"""

import importlib.util

if importlib.util.find_spec("pydantic_settings") is None:
    raise ImportError(
        "piighost configuration requires the config extra. "
        "Install it with: pip install piighost[config]"
    )

from piighost.config.settings import (
    PipelineConfig,
    load_config,
    load_pipeline,
    load_thread_pipeline,
)

__all__ = [
    "PipelineConfig",
    "load_config",
    "load_pipeline",
    "load_thread_pipeline",
]

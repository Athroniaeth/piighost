"""Config error family, re-exported from the core exceptions module.

The classes live in piighost.exceptions so a caller can catch them without the
config extra installed; this module re-exports them for config-local imports.
"""

from piighost.exceptions import (
    ConfigError,
    ConfigFileError,
    ConfigValidationError,
)

__all__ = ["ConfigError", "ConfigFileError", "ConfigValidationError"]

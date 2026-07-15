"""Errors raised by :mod:`piighost.config`."""

from pathlib import Path

from pydantic import ValidationError


class ConfigError(Exception):
    """Raised when a TOML configuration cannot be loaded into a pipeline."""

    @classmethod
    def from_pydantic(cls, err: ValidationError, path: Path) -> "ConfigError":
        """Translate a Pydantic ``ValidationError`` into a readable message.

        Each Pydantic error gets a line of the form ``loc.dotted.path: reason``
        where ``loc.dotted.path`` is the TOML key location (e.g.
        ``detectors[1].threshold``).
        """
        lines = [f"invalid configuration in {path}"]
        for error in err.errors():
            loc = ".".join(_render_loc_part(p) for p in error["loc"])
            lines.append(f"  {loc}: {error['msg']}")
        return cls("\n".join(lines))


def _render_loc_part(part: object) -> str:
    """Render a Pydantic location segment (string or int index)."""
    if isinstance(part, int):
        return f"[{part}]"
    return str(part)

"""Shared base config model."""

from pydantic import BaseModel, ConfigDict


class _ComponentConfig(BaseModel):
    """Common base for all component configuration models.

    Forbids unknown keys and freezes instances so that validated config
    cannot be mutated by callers. ``protected_namespaces`` is emptied
    because several detector configs declare a ``model`` field (HF/spaCy
    model identifier), which would otherwise collide with the default
    ``model_`` Pydantic protected namespace.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        protected_namespaces=(),
    )

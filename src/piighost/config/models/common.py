"""Shared base for the component configuration models."""

from pydantic import BaseModel, ConfigDict


class _ComponentConfig(BaseModel):
    """Base for a component's configuration model.

    Forbids keys the model does not declare, so a typo in a TOML table fails
    validation instead of being silently ignored.
    """

    model_config = ConfigDict(extra="forbid")

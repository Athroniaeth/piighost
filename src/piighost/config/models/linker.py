"""Entity linker configuration model."""

from typing import Literal

from piighost.components.linker import ExactEntityLinker
from piighost.components.linker.base import AnyEntityLinker
from piighost.config.models.common import _ComponentConfig


class ExactLinkerConfig(_ComponentConfig):
    """Config for the exact entity linker, grouping by casefolded value."""

    type: Literal["exact"]

    def build(self) -> AnyEntityLinker:
        """Build an ExactEntityLinker."""
        return ExactEntityLinker()


LinkerConfig = ExactLinkerConfig
"""The linker configuration.

A plain alias while one linker exists; it becomes a discriminated union when a
second linker lands in the coverage brick.
"""

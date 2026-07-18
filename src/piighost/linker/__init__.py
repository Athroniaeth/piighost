"""Entity linkers: group detections that refer to the same value.

base.py holds the abstractions, the AnyEntityLinker port and the
BaseEntityLinker template; concrete linkers live in sibling modules.
"""

from piighost.linker.base import AnyEntityLinker, BaseEntityLinker
from piighost.linker.exact import ExactEntityLinker

__all__ = ["AnyEntityLinker", "BaseEntityLinker", "ExactEntityLinker"]

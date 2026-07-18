"""Regression guards for imports.

Smoke-test that the package and its public API import cleanly. Import-time
failures such as syntax errors, circular imports, or broken re-exports surface
here before any behavioral test runs.
"""

import importlib
import pkgutil

import pytest

import piighost

# The public symbols consumers import, as (module, name) pairs. Adding a public
# export is one line here; renaming or removing one breaks the matching case.
PUBLIC_API: list[tuple[str, str]] = [
    ("piighost.models", "Span"),
    ("piighost.models", "Detection"),
    ("piighost.models", "Entity"),
    ("piighost.models", "Chunk"),
    ("piighost.detector", "AnyDetector"),
    ("piighost.detector", "ExactMatchDetector"),
    ("piighost.detector", "ChunkedDetector"),
    ("piighost.text", "AnySplitter"),
    ("piighost.text", "RecursiveCharacterTextSplitter"),
    ("piighost.text", "boundary_wrap"),
    ("piighost.text", "find_all_word_boundary"),
    ("piighost.resolver", "AnyOverlapResolver"),
    ("piighost.resolver", "BaseOverlapResolver"),
    ("piighost.resolver", "ConfidenceOverlapResolver"),
    ("piighost.expander", "AnyDetectionExpander"),
    ("piighost.expander", "WordBoundaryExpander"),
    ("piighost.linker", "AnyEntityLinker"),
    ("piighost.linker", "BaseEntityLinker"),
    ("piighost.linker", "ExactEntityLinker"),
    ("piighost.entity_resolver", "AnyEntityResolver"),
    ("piighost.entity_resolver", "BaseEntityResolver"),
    ("piighost.entity_resolver", "MergeEntityResolver"),
    ("piighost.entity_resolver", "SeparateEntityResolver"),
    ("piighost.exceptions", "PIIGhostError"),
    ("piighost.exceptions", "SpanError"),
    ("piighost.exceptions", "NegativeSpanStartError"),
    ("piighost.exceptions", "SpanOrderingError"),
    ("piighost.exceptions", "DetectionError"),
    ("piighost.exceptions", "ConfidenceError"),
    ("piighost.exceptions", "EntityError"),
    ("piighost.exceptions", "EmptyEntityError"),
    ("piighost.exceptions", "MixedLabelError"),
]


def test_package_imports() -> None:
    """Check that the top-level package name has not changed."""
    assert piighost.__name__ == "piighost"


@pytest.mark.parametrize(("module", "name"), PUBLIC_API)
def test_public_symbol_is_importable(module: str, name: str) -> None:
    """Check that no public symbol was renamed, moved, or removed."""
    module_type = importlib.import_module(module)
    assert hasattr(module_type, name)


def test_every_module_imports_cleanly() -> None:
    """Check that no module fails to import (syntax error, circular import)."""
    # walk_packages recurses into packages (ispkg=True) to reach their
    # submodules. A failed import propagates here and fails the test with its
    # real traceback. When optional-dependency modules land, this loop will need
    # to skip their guarded ImportError (install piighost[...]); none exist yet.
    for module_info in pkgutil.walk_packages(piighost.__path__, prefix="piighost."):
        importlib.import_module(module_info.name)

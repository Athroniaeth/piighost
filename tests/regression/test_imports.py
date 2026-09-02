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
    ("piighost.components.detector", "AnyDetector"),
    ("piighost.components.detector", "ExactMatchDetector"),
    ("piighost.components.detector", "ChunkedDetector"),
    ("piighost.components.detector", "RegexDetector"),
    ("piighost.components.detector", "CompositeDetector"),
    ("piighost.components.detector.ner", "BaseNERDetector"),
    ("piighost.components.detector.patterns", "GENERIC_PATTERNS"),
    ("piighost.components.detector.patterns", "US_PATTERNS"),
    ("piighost.components.detector.patterns", "EU_PATTERNS"),
    ("piighost.components.detector.patterns", "FR_PATTERNS"),
    ("piighost.text", "AnySplitter"),
    ("piighost.text", "RecursiveCharacterTextSplitter"),
    ("piighost.text", "boundary_wrap"),
    ("piighost.text", "find_all_word_boundary"),
    ("piighost.components.overlap_resolver", "AnyOverlapResolver"),
    ("piighost.components.overlap_resolver", "BaseOverlapResolver"),
    ("piighost.components.overlap_resolver", "ConfidenceOverlapResolver"),
    ("piighost.components.expander", "AnyDetectionExpander"),
    ("piighost.components.expander", "BaseDetectionExpander"),
    ("piighost.components.expander", "WordBoundaryExpander"),
    ("piighost.components.linker", "AnyEntityLinker"),
    ("piighost.components.linker", "BaseEntityLinker"),
    ("piighost.components.linker", "ExactEntityLinker"),
    ("piighost.components.entity_resolver", "AnyEntityResolver"),
    ("piighost.components.entity_resolver", "BaseEntityResolver"),
    ("piighost.components.entity_resolver", "MergeEntityResolver"),
    ("piighost.components.entity_resolver", "SeparateEntityResolver"),
    ("piighost.components.anonymizer", "Anonymization"),
    ("piighost.components.anonymizer", "AnyAnonymizer"),
    ("piighost.components.anonymizer", "Anonymizer"),
    ("piighost.components.anonymizer", "BaseAnonymizer"),
    ("piighost.components.guard", "AnyGuardRail"),
    ("piighost.components.guard", "DetectorGuardRail"),
    ("piighost.components.guard", "GuardVerdict"),
    ("piighost.components.override", "AnyDetectionOverride"),
    ("piighost.components.override", "BlacklistStrategy"),
    ("piighost.components.override", "DetectionOverride"),
    ("piighost.components.override", "OverrideConflictStrategy"),
    ("piighost.components.override", "WhitelistStrategy"),
    ("piighost.pipeline", "AnonymizationPipeline"),
    ("piighost.pipeline", "AnyPipeline"),
    ("piighost.pipeline", "BaseAnonymizationPipeline"),
    ("piighost.pipeline", "ThreadAnonymizationPipeline"),
    ("piighost.pipeline", "AnyThreadPipeline"),
    ("piighost.integrations.langchain", "ToolCallStrategy"),
    ("piighost.integrations.langchain", "InventedPlaceholderStrategy"),
    ("piighost.integrations.langchain", "EntityCreateByAssistantStrategy"),
    ("piighost.conversation_memory", "AnyConversationMemory"),
    ("piighost.conversation_memory", "Forgotten"),
    ("piighost.conversation_memory", "InMemoryConversationMemory"),
    ("piighost.conversation_memory", "MessageRole"),
    ("piighost.observation", "AnyObservationSpan"),
    ("piighost.observation", "AnyObservationTracer"),
    ("piighost.observation", "NoOpSpan"),
    ("piighost.observation", "NoOpTracer"),
    ("piighost.observation", "get_tracer"),
    ("piighost.crypto.hasher", "AnyHasher"),
    ("piighost.crypto.hasher", "BaseHasher"),
    ("piighost.crypto.hasher", "Sha256Hasher"),
    ("piighost.crypto.cipher", "AnyCipher"),
    ("piighost.components.placeholder", "AnyPlaceholderFactory"),
    ("piighost.components.placeholder", "BaseCounterPlaceholderFactory"),
    ("piighost.components.placeholder", "BaseDelimitedPlaceholderFactory"),
    ("piighost.components.placeholder", "PlaceholderStreamDecoder"),
    ("piighost.components.placeholder", "LabelCounterPlaceholderFactory"),
    ("piighost.components.placeholder", "LabelHashPlaceholderFactory"),
    ("piighost.components.placeholder", "LabelPlaceholderFactory"),
    ("piighost.components.placeholder", "MaskPlaceholderFactory"),
    ("piighost.components.placeholder", "RedactPlaceholderFactory"),
    ("piighost.exceptions", "PIIGhostError"),
    ("piighost.exceptions", "SpanError"),
    ("piighost.exceptions", "NegativeSpanStartError"),
    ("piighost.exceptions", "SpanOrderingError"),
    ("piighost.exceptions", "DetectionError"),
    ("piighost.exceptions", "ConfidenceError"),
    ("piighost.exceptions", "EntityError"),
    ("piighost.exceptions", "EmptyEntityError"),
    ("piighost.exceptions", "MixedLabelError"),
    ("piighost.exceptions", "HasherError"),
    ("piighost.exceptions", "EmptyPepperError"),
    ("piighost.exceptions", "CipherError"),
    ("piighost.exceptions", "InvalidKeyLengthError"),
    ("piighost.exceptions", "AnonymizerError"),
    ("piighost.exceptions", "OverlappingSpansError"),
    ("piighost.exceptions", "DetectorError"),
    ("piighost.exceptions", "LabelMappingError"),
    ("piighost.exceptions", "TextTooLongError"),
    ("piighost.exceptions", "GuardError"),
    ("piighost.exceptions", "PIIRemainingError"),
    ("piighost.exceptions", "MiddlewareError"),
    ("piighost.exceptions", "InventedPlaceholderError"),
    ("piighost.exceptions", "MissingThreadIdError"),
    ("piighost.exceptions", "UnrecognizableFactoryError"),
    ("piighost.exceptions", "OverrideError"),
    ("piighost.exceptions", "ConflictingOverrideError"),
    ("piighost.exceptions", "ClientError"),
    ("piighost.exceptions", "RemoteError"),
    ("piighost.exceptions", "ConfigError"),
    ("piighost.exceptions", "ConfigFileError"),
    ("piighost.exceptions", "ConfigValidationError"),
]


# Core symbols the package root re-exports lazily, resolved to their home module.
FACADE_EXPORTS: list[tuple[str, str]] = [
    ("piighost.pipeline", "AnonymizationPipeline"),
    ("piighost.pipeline", "ThreadAnonymizationPipeline"),
    ("piighost.components.anonymizer", "Anonymizer"),
    ("piighost.components.detector", "ExactMatchDetector"),
    ("piighost.components.detector", "RegexDetector"),
    ("piighost.components.detector", "CompositeDetector"),
    ("piighost.components.detector", "ChunkedDetector"),
    ("piighost.components.placeholder", "LabelCounterPlaceholderFactory"),
    ("piighost.components.placeholder", "LabelHashPlaceholderFactory"),
    ("piighost.models", "Detection"),
    ("piighost.models", "Entity"),
    ("piighost.models", "Span"),
    ("piighost.exceptions", "PIIGhostError"),
]


def test_package_imports() -> None:
    """Check that the top-level package name has not changed."""
    assert piighost.__name__ == "piighost"


@pytest.mark.parametrize(("module", "name"), FACADE_EXPORTS)
def test_facade_reexports_core_symbol(module: str, name: str) -> None:
    """The package root exposes each core symbol, identical to its home module's."""
    home = importlib.import_module(module)
    assert getattr(piighost, name) is getattr(home, name)


def test_facade_lists_its_exports_in_dir() -> None:
    """Every facade name is discoverable through dir(piighost)."""
    listed = set(dir(piighost))
    assert {name for _, name in FACADE_EXPORTS} <= listed


def test_facade_rejects_an_unknown_attribute() -> None:
    """An attribute the facade does not export raises AttributeError."""
    with pytest.raises(AttributeError):
        piighost.NotAThing  # noqa: B018


def test_facade_all_matches_the_lazy_exports() -> None:
    """__all__ stays in sync with the lazily re-exported names, plus __version__."""
    exported = set(piighost.__all__) - {"__version__"}
    assert exported == set(piighost._LAZY_EXPORTS)


@pytest.mark.parametrize(("module", "name"), PUBLIC_API)
def test_public_symbol_is_importable(module: str, name: str) -> None:
    """Check that no public symbol was renamed, moved, or removed."""
    module_type = importlib.import_module(module)
    assert hasattr(module_type, name)


def test_every_module_imports_cleanly() -> None:
    """Check that no module fails to import (syntax error, circular import)."""
    # walk_packages recurses into packages (ispkg=True) to reach their
    # submodules. A module guarded behind an optional dependency raises
    # ImportError pointing at its extra (install piighost[...]) when that
    # dependency is absent; that is expected, so skip it and let any other
    # ImportError propagate with its real traceback.
    for module_info in pkgutil.walk_packages(piighost.__path__, prefix="piighost."):
        try:
            importlib.import_module(module_info.name)
        except ImportError as exc:
            if "piighost[" not in str(exc):
                raise

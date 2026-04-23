"""Tests for the piighost top-level public API surface."""

import piighost


class TestTopLevelExports:
    """Names advertised in __all__ are importable from piighost."""

    def test_all_names_resolve(self) -> None:
        for name in piighost.__all__:
            assert hasattr(piighost, name), f"{name} missing from piighost"

    def test_protocols_exposed(self) -> None:
        """Extension points (Protocol classes) are reachable from the top level."""
        from piighost import (
            AnyAnonymizer,
            AnyDetector,
            AnyEntityConflictResolver,
            AnyEntityLinker,
            AnyPlaceholderFactory,
            AnySpanConflictResolver,
        )

        # Just ensure the imports above don't raise and the names bind.
        assert AnyDetector is not None
        assert AnyEntityLinker is not None
        assert AnyEntityConflictResolver is not None
        assert AnySpanConflictResolver is not None
        assert AnyAnonymizer is not None
        assert AnyPlaceholderFactory is not None

    def test_no_accidental_leak(self) -> None:
        """No private names creep into the package's __all__."""
        for name in piighost.__all__:
            assert not name.startswith("_"), f"Private name leaked: {name}"

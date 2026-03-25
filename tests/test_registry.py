"""Tests for the PlaceholderRegistry."""

from piighost.anonymizer.models import AnonymizationResult, Placeholder
from piighost.registry import PlaceholderRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_result(
    original_text: str,
    anonymized_text: str,
    placeholders: tuple[Placeholder, ...],
) -> AnonymizationResult:
    """Build a minimal AnonymizationResult for testing."""
    return AnonymizationResult(
        original_text=original_text,
        anonymized_text=anonymized_text,
        placeholders=placeholders,
        reverse_spans=(),
    )


PATRICK = Placeholder("Patrick", "PERSON", "<<PERSON_1>>")
PAT = Placeholder("Pat", "PERSON", "<<PERSON_3>>")
MARIE = Placeholder("Marie", "PERSON", "<<PERSON_2>>")
PARIS = Placeholder("Paris", "LOCATION", "<<LOCATION_1>>")


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------


class TestRegister:
    """Tests for registering placeholders into the registry."""

    def test_register_result(self) -> None:
        registry = PlaceholderRegistry()
        result = _make_result(
            "Patrick habite à Paris.",
            "<<PERSON_1>> habite à <<LOCATION_1>>.",
            (PATRICK, PARIS),
        )
        registry.register(result)

        assert len(registry) == 2
        assert PATRICK in registry.placeholders
        assert PARIS in registry.placeholders

    def test_register_single_placeholder(self) -> None:
        registry = PlaceholderRegistry()
        registry.register_placeholder(PATRICK)

        assert len(registry) == 1
        assert registry.placeholders == (PATRICK,)

    def test_dedup_same_placeholder_twice(self) -> None:
        registry = PlaceholderRegistry()
        registry.register_placeholder(PATRICK)
        registry.register_placeholder(PATRICK)

        assert len(registry) == 1

    def test_dedup_across_results(self) -> None:
        registry = PlaceholderRegistry()
        r1 = _make_result("Patrick", "<<PERSON_1>>", (PATRICK,))
        r2 = _make_result(
            "Patrick aime Paris", "<<PERSON_1>> aime <<LOCATION_1>>", (PATRICK, PARIS)
        )
        registry.register(r1)
        registry.register(r2)

        assert len(registry) == 2  # PATRICK + PARIS, not 3

    def test_empty_result_no_effect(self) -> None:
        registry = PlaceholderRegistry()
        result = _make_result("hello", "hello", ())
        registry.register(result)
        assert len(registry) == 0


# ---------------------------------------------------------------------------
# Deanonymize
# ---------------------------------------------------------------------------


class TestDeanonymize:
    """Tests for deanonymize (placeholder → original)."""

    def test_replaces_tags_with_originals(self) -> None:
        registry = PlaceholderRegistry()
        registry.register_placeholder(PATRICK)
        registry.register_placeholder(PARIS)

        text = "<<PERSON_1>> habite à <<LOCATION_1>>."
        assert registry.deanonymize(text) == "Patrick habite à Paris."

    def test_no_match_returns_unchanged(self) -> None:
        registry = PlaceholderRegistry()
        registry.register_placeholder(PATRICK)

        text = "Rien de spécial ici."
        assert registry.deanonymize(text) == text

    def test_empty_registry_returns_unchanged(self) -> None:
        registry = PlaceholderRegistry()
        text = "<<PERSON_1>> est là"
        assert registry.deanonymize(text) == text

    def test_multiple_occurrences_replaced(self) -> None:
        registry = PlaceholderRegistry()
        registry.register_placeholder(PATRICK)

        text = "<<PERSON_1>> aime <<PERSON_1>>"
        assert registry.deanonymize(text) == "Patrick aime Patrick"

    def test_longest_tag_replaced_first(self) -> None:
        """Longer replacement tags must be matched before shorter substrings."""
        registry = PlaceholderRegistry()
        long_tag = Placeholder("Alice", "PERSON", "<<PERSON_10>>")
        short_tag = Placeholder("Bob", "PERSON", "<<PERSON_1>>")
        # Register short before long to provoke insertion-order bug.
        registry.register_placeholder(short_tag)
        registry.register_placeholder(long_tag)

        text = "<<PERSON_10>> et <<PERSON_1>>"
        result = registry.deanonymize(text)
        assert result == "Alice et Bob"


# ---------------------------------------------------------------------------
# Reanonymize
# ---------------------------------------------------------------------------


class TestReanonymize:
    """Tests for reanonymize (original → placeholder)."""

    def test_replaces_originals_with_tags(self) -> None:
        registry = PlaceholderRegistry()
        registry.register_placeholder(PATRICK)
        registry.register_placeholder(PARIS)

        text = "Patrick habite à Paris."
        assert registry.reanonymize(text) == "<<PERSON_1>> habite à <<LOCATION_1>>."

    def test_no_match_returns_unchanged(self) -> None:
        registry = PlaceholderRegistry()
        registry.register_placeholder(PATRICK)

        text = "Bonjour monde"
        assert registry.reanonymize(text) == text

    def test_empty_registry_returns_unchanged(self) -> None:
        registry = PlaceholderRegistry()
        text = "Patrick est là"
        assert registry.reanonymize(text) == text

    def test_longest_original_replaced_first(self) -> None:
        """'Patrick' must be replaced before 'Pat' to avoid corruption."""
        registry = PlaceholderRegistry()
        # Register short before long to provoke insertion-order bug.
        registry.register_placeholder(PAT)
        registry.register_placeholder(PATRICK)

        text = "Patrick et Pat sont là."
        result = registry.reanonymize(text)
        assert result == "<<PERSON_1>> et <<PERSON_3>> sont là."


# ---------------------------------------------------------------------------
# Point lookups
# ---------------------------------------------------------------------------


class TestLookup:
    """Tests for lookup_replacement and lookup_original."""

    def test_lookup_replacement_found(self) -> None:
        registry = PlaceholderRegistry()
        registry.register_placeholder(PATRICK)

        assert registry.lookup_replacement("<<PERSON_1>>") is PATRICK

    def test_lookup_replacement_not_found(self) -> None:
        registry = PlaceholderRegistry()
        assert registry.lookup_replacement("<<UNKNOWN>>") is None

    def test_lookup_original_found(self) -> None:
        registry = PlaceholderRegistry()
        registry.register_placeholder(PATRICK)

        assert registry.lookup_original("Patrick", "PERSON") is PATRICK

    def test_lookup_original_not_found(self) -> None:
        registry = PlaceholderRegistry()
        assert registry.lookup_original("Unknown", "PERSON") is None

    def test_lookup_original_wrong_label(self) -> None:
        registry = PlaceholderRegistry()
        registry.register_placeholder(PATRICK)

        assert registry.lookup_original("Patrick", "LOCATION") is None


# ---------------------------------------------------------------------------
# Reversibility
# ---------------------------------------------------------------------------


class TestReversible:
    """Tests for the reversible property."""

    def test_empty_is_reversible(self) -> None:
        registry = PlaceholderRegistry()
        assert registry.reversible is True

    def test_unique_replacements_reversible(self) -> None:
        registry = PlaceholderRegistry()
        registry.register_placeholder(PATRICK)
        registry.register_placeholder(MARIE)
        registry.register_placeholder(PARIS)

        assert registry.reversible is True

    def test_shared_replacement_not_reversible(self) -> None:
        registry = PlaceholderRegistry()
        redacted_patrick = Placeholder("Patrick", "PERSON", "[REDACTED]")
        redacted_paris = Placeholder("Paris", "LOCATION", "[REDACTED]")
        registry.register_placeholder(redacted_patrick)
        registry.register_placeholder(redacted_paris)

        assert registry.reversible is False


# ---------------------------------------------------------------------------
# Introspection
# ---------------------------------------------------------------------------


class TestClear:
    """Tests for the clear method."""

    def test_clear_empties_registry(self) -> None:
        registry = PlaceholderRegistry()
        registry.register_placeholder(PATRICK)
        registry.register_placeholder(PARIS)
        assert len(registry) == 2

        registry.clear()
        assert len(registry) == 0
        assert not registry

    def test_clear_preserves_object_identity(self) -> None:
        registry = PlaceholderRegistry()
        registry.register_placeholder(PATRICK)

        ref = registry
        registry.clear()
        assert registry is ref

    def test_clear_allows_re_registration(self) -> None:
        registry = PlaceholderRegistry()
        registry.register_placeholder(PATRICK)
        registry.clear()
        registry.register_placeholder(MARIE)

        assert len(registry) == 1
        assert registry.placeholders == (MARIE,)


class TestIntrospection:
    """Tests for __len__, __bool__, placeholders."""

    def test_len_empty(self) -> None:
        assert len(PlaceholderRegistry()) == 0

    def test_len_with_placeholders(self) -> None:
        registry = PlaceholderRegistry()
        registry.register_placeholder(PATRICK)
        registry.register_placeholder(PARIS)
        assert len(registry) == 2

    def test_bool_empty(self) -> None:
        assert not PlaceholderRegistry()

    def test_bool_non_empty(self) -> None:
        registry = PlaceholderRegistry()
        registry.register_placeholder(PATRICK)
        assert registry

    def test_placeholders_returns_tuple(self) -> None:
        registry = PlaceholderRegistry()
        registry.register_placeholder(PATRICK)
        registry.register_placeholder(PARIS)

        result = registry.placeholders
        assert isinstance(result, tuple)
        assert set(result) == {PATRICK, PARIS}

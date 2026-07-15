"""Tests for piighost.utils helpers."""

import re

from piighost.utils import (
    _word_boundary_pattern,
    boundary_wrap,
    find_all_word_boundary,
    hash_sha256,
)


class TestHashSha256:
    def test_deterministic(self):
        assert hash_sha256("hello") == hash_sha256("hello")

    def test_different_inputs_different_hashes(self):
        assert hash_sha256("hello") != hash_sha256("world")

    def test_empty_string(self):
        assert hash_sha256("") == hashlib_sha256_expected("")

    def test_unicode(self):
        assert hash_sha256("héllo 日本") == hashlib_sha256_expected("héllo 日本")

    def test_returns_hex_string(self):
        digest = hash_sha256("x")
        assert len(digest) == 64
        assert all(c in "0123456789abcdef" for c in digest)


def hashlib_sha256_expected(text: str) -> str:
    import hashlib

    return hashlib.sha256(text.encode()).hexdigest()


class TestBoundaryWrap:
    def test_alnum_fragment_wrapped_in_word_class_lookarounds(self):
        # boundary_wrap uses negative lookarounds against the word class
        # ([\w] + WORD_JOIN_CHARS) rather than \b, so -/' count as
        # word-internal.
        assert boundary_wrap("Patrick") == r"(?<![\w\-'])Patrick(?![\w\-'])"

    def test_special_prefix_gets_lookbehind(self):
        # "+33..." starts with a non-word char; the left edge still uses a
        # lookbehind so the fragment is not matched when glued to a word
        # char.
        wrapped = boundary_wrap("+33")
        assert wrapped.startswith(r"(?<![\w\-'])")
        assert re.escape("+33") in wrapped

    def test_non_word_suffix_gets_lookahead(self):
        wrapped = boundary_wrap("x.")
        assert wrapped.endswith(r"(?![\w\-'])")

    def test_wrapped_phone_matches_standalone_but_not_glued_digits(self):
        phone = "+33 6 12 34 56 78"
        pattern = re.compile(boundary_wrap(phone))
        # Matches when the phone stands alone in the text.
        assert pattern.search(f"Call me at {phone} tomorrow") is not None
        # Does not match when digits continue right after the fragment.
        assert pattern.search(f"Call me at {phone}90 tomorrow") is None


class TestFindAllWordBoundary:
    def test_simple_word_match(self):
        assert find_all_word_boundary("hello world", "world") == [(6, 11)]

    def test_no_match(self):
        assert find_all_word_boundary("hello world", "foo") == []

    def test_multiple_matches(self):
        assert find_all_word_boundary("abc abc abc", "abc") == [(0, 3), (4, 7), (8, 11)]

    def test_case_insensitive_default(self):
        assert find_all_word_boundary("Patrick and patrick", "patrick") == [
            (0, 7),
            (12, 19),
        ]

    def test_case_sensitive_flag(self):
        matches = find_all_word_boundary("Patrick and patrick", "patrick", flags=0)
        assert matches == [(12, 19)]

    def test_word_boundary_excludes_substring(self):
        """'cat' should not match inside 'category'."""
        assert find_all_word_boundary("category cat", "cat") == [(9, 12)]

    def test_special_char_prefix(self):
        """Fragment starting with special char uses lookaround."""
        assert find_all_word_boundary("price: $100 and $200", "$100") == [(7, 11)]

    def test_special_char_suffix(self):
        """Fragment ending with special char uses lookaround."""
        assert find_all_word_boundary("email: me@x.com ok", "me@x.com") == [(7, 15)]

    def test_unicode_fragment(self):
        assert find_all_word_boundary("café and Café", "café") == [(0, 4), (9, 13)]

    def test_empty_text(self):
        assert find_all_word_boundary("", "foo") == []

    def test_regex_metachars_escaped(self):
        """Metacharacters in fragment must be matched literally."""
        assert find_all_word_boundary("a.b and a.b", "a.b") == [(0, 3), (8, 11)]

    def test_underscore_is_word_char(self):
        """Underscore is treated as alphanumeric for boundary purposes."""
        assert find_all_word_boundary("foo_bar baz", "foo") == []
        assert find_all_word_boundary("foo bar", "foo") == [(0, 3)]

    def test_pattern_compilation_is_cached(self):
        """Repeated calls with the same fragment reuse the compiled pattern."""
        _word_boundary_pattern.cache_clear()
        find_all_word_boundary("abc abc", "abc")
        find_all_word_boundary("abc here", "abc")
        info = _word_boundary_pattern.cache_info()
        assert info.hits >= 1
        assert info.misses == 1


class TestBoundaryHyphen:
    def test_jean_not_matched_inside_hyphenated_name(self) -> None:
        """\"Jean\" must not match inside \"Jean-Paul\" (hyphen joins the word)."""
        from piighost.utils import find_all_word_boundary

        assert find_all_word_boundary("Jean-Paul est là", "Jean") == []
        # But genuine end-of-word punctuation still bounds it.
        assert find_all_word_boundary("Jean. Jean, Jean", "Jean") == [
            (0, 4),
            (6, 10),
            (12, 16),
        ]

    def test_apostrophe_joins_word(self) -> None:
        from piighost.utils import find_all_word_boundary

        assert find_all_word_boundary("d'Anne arrive", "Anne") == []

    def test_still_blocks_substring_without_boundary(self) -> None:
        from piighost.utils import find_all_word_boundary

        assert find_all_word_boundary("Jeanpolis", "Jean") == []

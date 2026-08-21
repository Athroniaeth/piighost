"""Word-boundary matching: find a fragment only when it stands as a whole word."""

import re
from functools import lru_cache

from piighost.models import Span

WORD_JOIN_CHARS = "-'"
"""Characters treated as part of a word, in addition to the word class.

A bare word boundary treats the hyphen and apostrophe as separators, so a
search for "Jean" would match the "Jean" inside "Jean-Paul" or "d'Anne", wrongly linking
a short name to an unrelated compound. These joiners are added to the
word-character class so a fragment is not matched when glued to them, while
genuine end-of-word punctuation such as a space, a period, a comma, or a newline
still bounds it. Edit this single constant to change what counts as a word
separator across detection, expansion, linking, and replacement.
"""

_WORD_CLASS = "[" + "\\w" + "".join(re.escape(char) for char in WORD_JOIN_CHARS) + "]"
"""Regex character class of what counts as inside a word.

The word class plus the WORD_JOIN_CHARS joiners, so a fragment glued to a
hyphen or apostrophe is treated as part of a larger word, not a match.
"""


def boundary_wrap(fragment: str) -> str:
    """Escape fragment and wrap it so it matches only as a whole word.

    The returned pattern rejects a match when the character right before or
    right after the fragment is a letter, a digit, an underscore, a hyphen, or
    an apostrophe. Because it counts the hyphen and apostrophe as part of a
    word, it does not find Jean inside Jean-Paul, nor Anne inside d'Anne, where
    a plain boundary would. The fragment must be non-empty, since an empty
    fragment would match at every position.

    >>> import re
    >>> re.search("Jean", "Jean-Paul")
    <re.Match object; span=(0, 4), match='Jean'>
    >>> print(re.search(boundary_wrap("Jean"), "Jean-Paul"))
    None

    >>> re.search("Jean", "Jeanne")
    <re.Match object; span=(0, 4), match='Jean'>
    >>> print(re.search(boundary_wrap("Jean"), "Jeanne"))
    None

    >>> re.search("Jean", "Jean Dupont")
    <re.Match object; span=(0, 4), match='Jean'>
    >>> re.search(boundary_wrap("Jean"), "Jean Dupont")
    <re.Match object; span=(0, 4), match='Jean'>
    """
    return f"(?<!{_WORD_CLASS}){re.escape(fragment)}(?!{_WORD_CLASS})"


@lru_cache(maxsize=1024)
def _word_boundary_pattern(fragment: str, flags: int) -> re.Pattern[str]:
    """Compile and cache the word-boundary pattern for a fragment and flags."""
    return re.compile(boundary_wrap(fragment), flags)


def find_all_word_boundary(
    text: str,
    fragment: str,
    flags: int = re.IGNORECASE,
) -> list[Span]:
    """Return the span of every word-boundary occurrence.

    The compiled pattern is cached per fragment and flags to avoid recompiling
    in hot paths.

    Args:
        text: The text to search.
        fragment: The substring to look for as a whole word.
        flags: Regex flags, case-insensitive by default.

    Returns:
        The span of every match, in order.
    """
    pattern = _word_boundary_pattern(fragment, int(flags))
    return [Span(match.start(), match.end()) for match in pattern.finditer(text)]

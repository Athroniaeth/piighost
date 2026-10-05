"""Word-boundary matching: find a fragment only when it stands as a whole word."""

import re
from functools import lru_cache

from piighost.exceptions import EmptyFragmentError
from piighost.models import Span

WORD_JOIN_CHARS = (
    "\u002d"  # hyphen-minus
    "\u00ad"  # soft hyphen
    "\u058a"  # Armenian hyphen
    "\u05be"  # Hebrew maqaf
    "\u1400"  # Canadian syllabics hyphen
    "\u1806"  # Mongolian todo soft hyphen
    "\u2010"  # hyphen
    "\u2011"  # non-breaking hyphen, the one Word types in place of the hyphen
    "\u2e17"  # double oblique hyphen
    "\u2e1a"  # hyphen with diaeresis
    "\u2e40"  # double hyphen
    "\u2e5d"  # oblique hyphen
    "\u30a0"  # katakana double hyphen
    "\ufe63"  # small hyphen-minus
    "\uff0d"  # fullwidth hyphen-minus
    "\U00010d6e"  # Garay hyphen, added in Unicode 16 (Python 3.14)
    "\U00010ead"  # Yezidi hyphenation mark
)
"""Characters treated as part of a word, in addition to the word class.

Every dash punctuation named a hyphen, and the soft one. Written as escapes,
since several are invisible or look like the ASCII one in source.

A bare word boundary treats the hyphen as a separator, so a search for "Jean"
would match the "Jean" inside "Jean-Paul", wrongly linking a short name to an
unrelated compound. Every hyphen is added to the word-character class so a
fragment glued to one is not a match, whichever hyphen the text was typed with.

A dash is not a joiner. The en dash, the em dash and the figure dash stand
between two words, or two places in "Paris–Lyon", so they bound a word.

The apostrophe is not a joiner, in any language. It ends the word before it as
often as it sits inside one: an elision (d'Anne, dell'Anna), a possessive
(Jean's), a quotation mark ('Jean'). As a boundary it finds the value in all of
them, and the cost is the other way round, a search for "Brien" also matching
inside "O'Brien", which hides more than asked and never leaves a value in clear.
Edit this single constant to change what counts as a word separator across
detection, expansion, linking, and replacement.
"""

_WORD_CLASS = "[" + "\\w" + "".join(re.escape(char) for char in WORD_JOIN_CHARS) + "]"
"""Regex character class of what counts as inside a word.

The word class plus the WORD_JOIN_CHARS hyphens, so a fragment glued to a
hyphen is treated as part of a larger word, not a match.
"""


_ANY_SPACE = r"(?u:\s)+"
"""What a space inside a fragment matches: any run of Unicode whitespace.

A value detected as "Paul Martin" is found again as "Paul\u00a0Martin", as
"Paul  Martin" and across a line break, since each writes the same value. The
Unicode flag is scoped to this group, so it holds whatever flags the caller
compiles with.
"""


def boundary_wrap(fragment: str) -> str:
    """Escape fragment and wrap it so it matches only as a whole word.

    The returned pattern rejects a match when the character right before or
    right after the fragment is a letter, a digit, an underscore or a hyphen.
    Because it counts the hyphen as part of a word, it does not find Jean inside
    Jean-Paul, where a plain boundary would. An apostrophe bounds a word, so Anne
    is found in d'Anne and Jean in Jean's. A space inside the fragment matches
    any run of whitespace, so Paul Martin is also found written with a no-break
    space, with two spaces, or across a line break.

    Raises:
        EmptyFragmentError: If the fragment is empty or only whitespace. Such a
            fragment matches at every position, so it would yield zero-width
            spans a Span refuses, surfacing as a SpanOrderingError far from its
            cause. A detector whose source is untrusted, an LLM returning an
            empty value, filters those out before calling this.

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
    words = fragment.split()
    if not words:
        raise EmptyFragmentError(
            "A word-boundary search needs a non-empty fragment; an empty one "
            "matches at every position of the text."
        )
    body = _ANY_SPACE.join(re.escape(word) for word in words)
    return f"(?<!{_WORD_CLASS}){body}(?!{_WORD_CLASS})"


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

    Raises:
        EmptyFragmentError: If the fragment is empty, through boundary_wrap.
    """
    pattern = _word_boundary_pattern(fragment, int(flags))
    return [Span(match.start(), match.end()) for match in pattern.finditer(text)]


def clear_boundary_cache() -> None:
    """Drop every compiled word-boundary pattern held in the shared cache.

    The cache is keyed by the fragment searched for, which is a PII value when
    the caller is a detector or an expander, so it outlives the thread the value
    came from. Forgetting a thread erases the store and the pipeline's own
    memoized tokens, not this process-wide cache, since one thread's erasure is
    not a reason to drop every other thread's compiled patterns. Call this at a
    point where the cost is acceptable, after a batch or on an erasure request
    covering the whole process.
    """
    _word_boundary_pattern.cache_clear()

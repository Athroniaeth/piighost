"""Word-boundary matching: find a fragment only when it stands as a whole word."""

import re
from functools import lru_cache

from piighost.exceptions import EmptyFragmentError
from piighost.models import Span

_HYPHEN_CODE_POINTS = (
    0x002D,
    0x00AD,
    0x058A,
    0x05BE,
    0x1400,
    0x1806,
    0x2010,
    0x2011,
    0x2E17,
    0x2E1A,
    0x2E40,
    0x2E5D,
    0x30A0,
    0xFE63,
    0xFF0D,
    0x10EAD,
)
"""Code points of the hyphens: every dash punctuation named a hyphen, and the soft one.

The hyphen-minus, the soft hyphen, the Armenian hyphen, the Hebrew maqaf, the
Canadian syllabics hyphen, the Mongolian todo soft hyphen, the hyphen and the
non-breaking hyphen Word types in its place, the double oblique hyphen, the
hyphen with diaeresis, the double hyphen, the oblique hyphen, the katakana
double hyphen, the small and the fullwidth hyphen-minus, and the Yezidi
hyphenation mark. Written as numbers, since several are invisible or look like
the ASCII one in source.
"""

WORD_JOIN_CHARS = "".join(map(chr, _HYPHEN_CODE_POINTS))
"""Characters treated as part of a word, in addition to the word class.

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

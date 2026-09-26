"""Word-boundary matching: find a fragment only when it stands as a whole word."""

import re
from functools import lru_cache

from piighost.exceptions import EmptyFragmentError
from piighost.models import Span

WORD_JOIN_CHARS = "-'\u2019"
"""Characters treated as part of a word, in addition to the word class.

A bare word boundary treats the hyphen and apostrophe as separators, so a
search for "Jean" would match the "Jean" inside "Jean-Paul", and "Brien" the one
inside "O'Brien", wrongly linking a short name to an unrelated compound. These
joiners, the typographic apostrophe included, are added to the word-character
class so a fragment is not matched when glued to them, while genuine end-of-word
punctuation such as a space, a period, a comma, or a newline still bounds it.
Edit this single constant to change what counts as a word separator across
detection, expansion, linking, and replacement.
"""

ELISIONS = (
    "c",
    "d",
    "j",
    "l",
    "m",
    "n",
    "s",
    "t",
    "qu",
    "jusqu",
    "lorsqu",
    "puisqu",
    "quoiqu",
)
"""French words that elide before a vowel, so the apostrophe after them ends them.

In "d'Anne" or "l'ACQUEREUR" the apostrophe is not inside a name, it closes the
article or preposition, and "Anne" stands as a word of its own. Counting it as a
joiner there hid "Ille-et-Vilaine" in "d'Ille-et-Vilaine" from the search. An
elision is only recognised when the clitic is itself a whole word, so
"aujourd'hui" and "prud'homme" stay single words.
"""

_JOINERS = "".join(re.escape(char) for char in WORD_JOIN_CHARS)
_APOSTROPHES = "'\u2019"

_WORD_CLASS = "[\\w" + _JOINERS + "]"
"""Regex character class of what counts as inside a word.

The word class plus the WORD_JOIN_CHARS joiners, so a fragment glued to a
hyphen or apostrophe is treated as part of a larger word, not a match.
"""


def _elision(clitic: str) -> str:
    """A lookbehind true right after the clitic and its apostrophe, the clitic standing alone."""
    letters = "".join(f"[{char}{char.upper()}]" for char in clitic)
    return f"(?<=(?<!{_WORD_CLASS}){letters}[{_APOSTROPHES}])"


_START = (
    "(?:(?<!"
    + _WORD_CLASS
    + ")|(?<=(?<![\\w\\-])["
    + _APOSTROPHES
    + "])|"
    + "|".join(map(_elision, ELISIONS))
    + ")"
)
"""What may precede a whole word: no word character, an opening quote, or an elision."""

_END = "(?![\\w\\-]|[" + _APOSTROPHES + "](?![sS](?!" + _WORD_CLASS + "))[\\w\\-])"
"""What may follow a whole word: no word character, nor an apostrophe inside one.

An apostrophe after the fragment ends it when a non-letter follows ("the
Jones' house") or a possessive s does ("Jean's car"), and joins it otherwise.
"""


def boundary_wrap(fragment: str) -> str:
    """Escape fragment and wrap it so it matches only as a whole word.

    The returned pattern rejects a match when the character right before or
    right after the fragment is a letter, a digit, an underscore, a hyphen, or
    an apostrophe. Because it counts the hyphen and apostrophe as part of a
    word, it does not find Jean inside Jean-Paul, nor Brien inside O'Brien,
    where a plain boundary would. Two apostrophes are boundaries all the same,
    the one closing a French elision, which finds Anne in d'Anne, and an
    English possessive, which finds Jean in Jean's.

    Raises:
        EmptyFragmentError: If the fragment is empty. Such a fragment matches at
            every position, so it would yield zero-width spans a Span refuses,
            surfacing as a SpanOrderingError far from its cause. A detector
            whose source is untrusted, an LLM returning an empty value, filters
            those out before calling this.

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
    if not fragment:
        raise EmptyFragmentError(
            "A word-boundary search needs a non-empty fragment; an empty one "
            "matches at every position of the text."
        )
    return f"{_START}{re.escape(fragment)}{_END}"


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

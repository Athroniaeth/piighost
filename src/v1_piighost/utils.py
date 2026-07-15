import hashlib
import re
from functools import lru_cache


def hash_sha256(text: str) -> str:
    """SHA-256 hash of a text string."""
    return hashlib.sha256(text.encode()).hexdigest()


WORD_JOIN_CHARS = "-'"
"""Characters treated as part of a word, in addition to ``\\w``.

``\\b`` treats ``-`` and ``'`` as separators, so ``\\bJean\\b`` matches
the "Jean" inside "Jean-Paul" or "d'Anne", wrongly linking a short name
to an unrelated compound. These joiners are added to the word-character
class used by :func:`boundary_wrap` so a fragment is not matched when
glued to them, while genuine end-of-word punctuation (space, ``.``,
``,``, newline) still bounds it. Edit this single constant to change
what counts as a word separator across detection, linking, guarding,
and replacement.
"""

_WORD_CLASS = "[" + "\\w" + "".join(re.escape(c) for c in WORD_JOIN_CHARS) + "]"
"""Regex character class of word-internal characters (``[\\w\\-']``)."""


def boundary_wrap(fragment: str) -> str:
    """Escape *fragment* and wrap it in word-boundary assertions.

    Wraps the fragment in negative lookarounds against
    :data:`_WORD_CLASS` (``\\w`` plus :data:`WORD_JOIN_CHARS`) so the
    fragment only matches when it is not glued to a word-internal
    character on either side. Unlike ``\\b`` this treats ``-`` and ``'``
    as part of a word, so "Jean" does not match inside "Jean-Paul".

    The fragment must be non-empty; an empty fragment would produce a
    zero-width pattern matching everywhere.
    """
    return f"(?<!{_WORD_CLASS}){re.escape(fragment)}(?!{_WORD_CLASS})"


@lru_cache(maxsize=1024)
def _word_boundary_pattern(fragment: str, flags: int) -> re.Pattern[str]:
    """Compile (and cache) the word-boundary pattern for *fragment*."""
    return re.compile(boundary_wrap(fragment), flags)


def find_all_word_boundary(
    text: str,
    fragment: str,
    flags: int = re.IGNORECASE,
) -> list[tuple[int, int]]:
    """Find all word-boundary occurrences of *fragment* in *text*.

    Uses ``\\b`` for alphanumeric/underscore boundaries and lookarounds
    ``(?<!\\w)``/``(?!\\w)`` for fragments starting or ending with special
    characters.

    The compiled pattern is cached per ``(fragment, flags)`` pair to avoid
    recompilation in hot paths.

    Args:
        text: The source text to search.
        fragment: The substring to look for.
        flags: Regex flags. Defaults to ``re.IGNORECASE``.

    Returns:
        A list of ``(start, end)`` tuples for every match.
    """
    pattern = _word_boundary_pattern(fragment, int(flags))
    return [(m.start(), m.end()) for m in pattern.finditer(text)]

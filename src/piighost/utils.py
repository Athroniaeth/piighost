import hashlib
import re
from functools import lru_cache


def hash_sha256(text: str) -> str:
    """SHA-256 hash of a text string."""
    return hashlib.sha256(text.encode()).hexdigest()


def boundary_wrap(fragment: str) -> str:
    """Escape *fragment* and wrap it in word-boundary assertions.

    Uses ``\\b`` for alphanumeric/underscore edges and lookarounds
    ``(?<!\\w)`` / ``(?!\\w)`` for fragments starting or ending with
    special characters.
    """
    prefix = r"\b" if fragment[0:1].isalnum() or fragment[0:1] == "_" else r"(?<!\w)"
    suffix = r"\b" if fragment[-1:].isalnum() or fragment[-1:] == "_" else r"(?!\w)"
    return f"{prefix}{re.escape(fragment)}{suffix}"


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

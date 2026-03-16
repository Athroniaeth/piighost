"""Text matching: find all occurrences of an entity in text.

GLiNER2 may detect only *one* occurrence of ``"Patrick"`` even if it appears
twice.  A ``TextMatcher`` scans the full text to find every position where
an entity surface form appears.
"""

from typing import Protocol


class TextMatcher(Protocol):
    """Interface for finding all occurrences of a query string in text."""

    def find_all(self, text: str, query: str) -> list[tuple[int, int]]:
        """Return every ``(start, end)`` where *query* appears in *text*.

        Args:
            text: The haystack.
            query: The needle.

        Returns:
            Non-overlapping ``(start, end)`` pairs, sorted by start.
        """
        ...  # pragma: no cover


class ExactMatcher:
    """Finds all exact (case-sensitive) occurrences of a query.

    Args:
        case_sensitive: When *False*, comparison is lowered on both sides.
    """

    def __init__(self, case_sensitive: bool = True) -> None:
        self._case_sensitive = case_sensitive

    def find_all(self, text: str, query: str) -> list[tuple[int, int]]:
        """Return every ``(start, end)`` of exact matches.

        Args:
            text: The haystack.
            query: The needle.

        Returns:
            Sorted, non-overlapping ``(start, end)`` pairs.
        """
        haystack = text if self._case_sensitive else text.lower()
        needle = query if self._case_sensitive else query.lower()
        results: list[tuple[int, int]] = []
        start = 0
        while True:
            idx = haystack.find(needle, start)
            if idx == -1:
                break
            results.append((idx, idx + len(query)))
            start = idx + len(query)
        return results

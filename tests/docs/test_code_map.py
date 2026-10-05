"""The files the "Change piighost's code" page names exist in the repository.

The page is written by hand, outside the OpenWiki job that keeps the domain
documentation in step with the code. A file it names could move and leave the
page pointing nowhere. This test reads the "Then" column of its table, in both
languages, and looks each path up in the repository.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
"""The repository root."""

PAGES = {
    lang: ROOT / "docs" / lang / "community" / "changing-the-code.md"
    for lang in ("en", "fr")
}
"""The page, in each language."""

CODE = re.compile(r"`([^`]+)`")
"""An inline code span of a table cell."""


def named_paths(page: Path) -> list[str]:
    """Every file or folder the last column of the page's table names.

    A code span counts when it reads as a path, a name ending in .py or
    holding a slash. A function name, an identifier pattern such as
    AT-<need>-<n>, or a placeholder such as <script> is not a path.
    """
    paths = []
    for line in page.read_text(encoding="utf-8").splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 3 or not cells[2] or set(cells[2]) <= set("-"):
            continue
        for span in CODE.findall(cells[2]):
            if ("/" in span or span.endswith(".py")) and "<" not in span:
                paths.append(span)
    return paths


def exists(path: str) -> bool:
    """Whether a path the page names matches something in the repository.

    The page writes paths relative to the package (components/placeholder/),
    to the root (tests/config/), or as a bare file name (tags.py), with a
    glob for a family of files (test_streaming*.py).
    """
    patterns = [path.rstrip("/"), f"src/piighost/{path.rstrip('/')}"]
    if "/" not in path:
        patterns += [f"src/**/{path}", f"tests/**/{path}"]
    return any(any(ROOT.glob(pattern)) for pattern in patterns)


@pytest.mark.parametrize("lang", PAGES)
def test_every_file_the_page_names_exists(lang: str) -> None:
    """Each path in the table of the page leads to a file or folder of the repository."""
    paths = named_paths(PAGES[lang])
    assert paths, "the table names no path: its format changed"
    assert [path for path in paths if not exists(path)] == []

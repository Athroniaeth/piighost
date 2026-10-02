"""Every code example the documentation shows runs, and prints what the page shows.

The examples live in docs/snippets/, one file per example, shared by the French
and English pages, which include them with `--8<-- "snippets/<file>:<section>"`.
A file that prints has a sibling .out holding its expected output, which the
page includes too: the output a reader sees is the output the code gives. A
file named test_*.py is a test file the page shows, and runs under pytest.
"""

import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

SNIPPETS_DIR = Path(__file__).resolve().parents[2] / "docs" / "snippets"
"""Where the documentation's examples live."""

SNIPPETS: list[Any] = [
    "quickstart.en.py",
    "quickstart.fr.py",
    "first_pipeline.py",
    "conversation.py",
    "basic_exact.py",
    "basic_factories.py",
    "testing.py",
    "test_testing.py",
    # These reach the hub or download a model.
    pytest.param("basic.py", marks=pytest.mark.integration),
    pytest.param("detector_hub.py", marks=pytest.mark.integration),
    pytest.param("detector_gliner2.py", marks=pytest.mark.integration),
]
"""Every example, the ones that need the network or a model marked integration."""

MIGRATED = [
    "getting-started/quickstart.md",
    "getting-started/first-pipeline.md",
    "getting-started/conversation.md",
    "examples/basic.md",
    "examples/testing.md",
]
"""The pages whose Python examples all come from docs/snippets/, in both languages."""

DOCS_DIR = SNIPPETS_DIR.parent
"""The documentation root, holding one folder per language."""

REQUIRES = {"detector_gliner2.py": "gliner2"}
"""The optional package an example needs, skipped when it is absent."""

TIMEOUT = 300
"""Seconds an example may take, a model download included."""


def _name(case: Any) -> str:
    """The file name a case of SNIPPETS stands for."""
    return case if isinstance(case, str) else case.values[0]


def _expected(snippet: Path) -> str | None:
    """The output a snippet's .out declares, its section markers removed."""
    out = snippet.with_suffix(".out")
    if not out.exists():
        return None
    lines = out.read_text(encoding="utf-8").splitlines(keepends=True)
    return "".join(line for line in lines if "--8<--" not in line)


def _run(snippet: Path, cwd: Path) -> subprocess.CompletedProcess[str]:
    """Run an example as a reader would, or a test file under pytest."""
    command = [sys.executable, str(snippet)]
    if snippet.name.startswith("test_"):
        command = [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            str(snippet),
        ]
    return subprocess.run(
        command, cwd=cwd, capture_output=True, text=True, timeout=TIMEOUT, check=False
    )


@pytest.mark.parametrize("name", SNIPPETS)
def test_an_example_runs_and_prints_what_the_page_shows(
    name: str, tmp_path: Path
) -> None:
    """An example exits cleanly, and its output is its .out, when it has one."""
    if name in REQUIRES:
        pytest.importorskip(REQUIRES[name])
    snippet = SNIPPETS_DIR / name
    result = _run(snippet, tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    expected = _expected(snippet)
    if expected is not None:
        assert result.stdout == expected


def test_every_example_is_listed() -> None:
    """A file added to docs/snippets/ without a case here would never run."""
    listed = {_name(case) for case in SNIPPETS}
    on_disk = {path.name for path in SNIPPETS_DIR.glob("*.py")}
    assert on_disk == listed


def test_every_output_has_its_example() -> None:
    """A .out without its .py would show an output no code produces."""
    orphans = [
        out.name
        for out in SNIPPETS_DIR.glob("*.out")
        if not out.with_suffix(".py").exists()
    ]
    assert orphans == []


@pytest.mark.parametrize("lang", ["fr", "en"])
@pytest.mark.parametrize("page", MIGRATED)
def test_a_migrated_page_writes_no_python_by_hand(page: str, lang: str) -> None:
    """A Python block of a migrated page is an include, so it cannot drift from its test."""
    text = (DOCS_DIR / lang / page).read_text(encoding="utf-8")
    blocks = re.findall(
        r"^(\s*)```python\n(.*?)^\1```", text, flags=re.DOTALL | re.MULTILINE
    )
    written = [body for _, body in blocks if "--8<--" not in body]
    assert written == []

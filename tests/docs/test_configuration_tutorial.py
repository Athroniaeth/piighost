"""The configuration tutorial runs as the page tells it, step after step.

getting-started/configuration.md grows one `pipeline.toml`, checks it with the
`piighost` CLI and runs it, in one folder. Its files live in
docs/snippets/configuration/, the page includes every one of them, and this test
replays the steps in the page's order: write or append a file, run a command,
compare what it prints with the output the page shows.
"""

import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

TUTORIAL_DIR = (
    Path(__file__).resolve().parents[2] / "docs" / "snippets" / "configuration"
)
"""The files of the tutorial, the ones the page includes."""


def _write(folder: Path, text: str, expected: str) -> None:
    """The reader starts `pipeline.toml` over with this content."""
    (folder / "pipeline.toml").write_text(text, encoding="utf-8")


def _append(folder: Path, text: str, expected: str) -> None:
    """The reader adds a section at the end of `pipeline.toml`."""
    config = folder / "pipeline.toml"
    config.write_text(
        config.read_text(encoding="utf-8") + "\n" + text, encoding="utf-8"
    )


def _run(command: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    # `python` and `piighost` are the ones of the environment running the test.
    path = os.pathsep.join([str(Path(sys.executable).parent), os.environ["PATH"]])
    return subprocess.run(
        command,
        shell=True,
        cwd=cwd,
        env={**os.environ, "PATH": path},
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )


def _passes(folder: Path, text: str, expected: str) -> None:
    """The command succeeds and prints the page's output."""
    result = _run(text, folder)
    assert result.returncode == 0, f"{text}{result.stderr}"
    assert result.stdout == expected, text


def _fails(folder: Path, text: str, expected: str) -> None:
    """The command fails, and its error ends on the lines the page shows."""
    result = _run(text, folder)
    assert result.returncode != 0, f"{text}{result.stdout}"
    tail = result.stderr.splitlines()[-len(expected.splitlines()) :]
    assert tail == expected.splitlines(), f"{text}{result.stderr}"


WRITE, APPEND, RUN, FAIL = _write, _append, _passes, _fails

STEPS: list[tuple[Callable[[Path, str, str], None], str, str | None]] = [
    # 1. Set up the check loop.
    (WRITE, "typo.toml", None),
    (FAIL, "validate.sh", "typo.out"),
    (RUN, "schema.sh", None),
    (WRITE, "email.toml", None),
    (RUN, "validate.sh", "validated.out"),
    # 2. Build a pipeline from three lines.
    (RUN, "run_email.sh", "email.out"),
    # 3. Pick the token.
    (WRITE, "redact.toml", None),
    (RUN, "run_email.sh", "redact.out"),
    # 4. Pull a group from the catalog.
    (WRITE, "catalog.toml", None),
    (RUN, "run_catalog.sh", "catalog.out"),
    (WRITE, "order.toml", None),
    (RUN, "run_order.sh", "order.out"),
    # 5. Run two detectors at once.
    (WRITE, "composite.toml", None),
    (RUN, "run_names.sh", "composite.out"),
    # 6. Merge the near-duplicate entities.
    (APPEND, "fuzzy.toml", None),
    (RUN, "run_names.sh", "fuzzy.out"),
    # 7. Keep the tokens across a conversation.
    (APPEND, "memory.toml", None),
    (RUN, "validate.sh", "validated.out"),
    (FAIL, "run_memory.sh", "memory.out"),
    (RUN, "thread.sh", "thread.out"),
]
"""The tutorial, in the page's order: (action, file, expected output)."""

FIRST_CATALOG_STEP = STEPS.index((WRITE, "catalog.toml", None))
"""From here the steps read a catalog group, cached once pulled."""


@pytest.mark.parametrize(
    "last",
    [
        pytest.param(FIRST_CATALOG_STEP, id="offline-steps"),
        pytest.param(len(STEPS), id="every-step", marks=pytest.mark.integration),
    ],
)
def test_the_tutorial_prints_what_the_page_shows(last: int, tmp_path: Path) -> None:
    """Each command prints the page's output, an error on stderr for a step that fails."""
    for script in TUTORIAL_DIR.glob("*.py"):
        shutil.copy(script, tmp_path)
    for action, name, out in STEPS[:last]:
        text = (TUTORIAL_DIR / name).read_text(encoding="utf-8")
        expected = out and (TUTORIAL_DIR / out).read_text(encoding="utf-8") or ""
        action(tmp_path, text, expected)


def test_every_file_of_the_tutorial_is_a_step() -> None:
    """A file of the folder no step uses would show the reader untested code."""
    used = {name for _, name, _ in STEPS} | {out for _, _, out in STEPS if out}
    used |= {path.name for path in TUTORIAL_DIR.glob("*.py")}
    assert {path.name for path in TUTORIAL_DIR.iterdir()} == used

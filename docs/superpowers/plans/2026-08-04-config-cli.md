# Config CLI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the `piighost` command-line interface with two subcommands, `validate` (validate a TOML config without building it) and `schema` (print the PipelineConfig JSON Schema), behind the `config` extra.

**Architecture:** A single guarded module `src/piighost/cli/__init__.py` holds a `typer.Typer` app with the two commands and `main()`, the target of the already-declared `piighost = piighost.cli:main` console script. Commands import `piighost.config` lazily in their body so importing the module only pulls typer.

**Tech Stack:** Python 3.11+, typer 0.24 (in the `config` extra), pytest + typer.testing.CliRunner.

---

## Conventions for every task

- Run tests with `uv run --no-sync`. Before each pytest run clear bytecode: `find src tests -name __pycache__ -type d -exec rm -rf {} +`.
- English only. Docstrings plain prose + bullet lists (no markdown/RST). No em dash. No `from __future__ import annotations`. Python 3.11+ native typing. Conventional Commits. Do NOT push. Do NOT create `__init__.py` under `tests/`.
- ANN is enforced on src and tests: annotate every parameter and return `-> None`.
- If pyrefly flags the typer argument declaration, keep the `Annotated[Path, typer.Argument(...)]` form used below (it is the type-clean typer idiom); report rather than suppress.

## File structure

- Create `src/piighost/cli/__init__.py` — the guarded typer app, `validate`, `schema`, `main`.
- Create `tests/cli/test_cli.py` — CliRunner tests.
- No `pyproject.toml` change: `typer>=0.12` is already in the `config` extra and dev group, and `[project.scripts] piighost = "piighost.cli:main"` is already declared.

## Verified API facts (rely on these)

- typer 0.24.2. `CliRunner().invoke(app, ["validate", path])` dispatches the subcommand (the app has two commands, so no single-command special-casing).
- On a result: `result.exit_code` is the code; `result.stderr` is stderr only (non-empty when the command wrote with `err=True`); `result.output` is stdout (plus stderr mixed in, but for `schema` stderr is empty so `result.output` is pure stdout).
- Command names are read as `command.callback.__name__` for each `command` in `app.registered_commands` (typer leaves `command.name` as None, defaulting to the callback name at runtime).
- `load_config(path)` raises `ConfigError` (base) for a missing file, invalid TOML, or invalid schema. `PipelineConfig.model_json_schema()` returns a dict whose `"properties"` includes `detector`, `linker`, `anonymizer`.

---

### Task 1: The piighost CLI (validate, schema)

**Files:**
- Create: `src/piighost/cli/__init__.py`
- Test: `tests/cli/test_cli.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/cli/test_cli.py`:

```python
"""Tests for the piighost command-line interface."""

import json
from pathlib import Path

from typer.testing import CliRunner

from piighost.cli import app

runner = CliRunner()

_VALID_TOML = """
name = "demo"

[detector]
type = "regex"
patterns = { EMAIL = "[a-z]+@[a-z.]+" }

[linker]
type = "exact"

[anonymizer.placeholder]
type = "redact"
"""


def _write(tmp_path: Path, text: str) -> Path:
    """Write text to a config.toml under tmp_path and return the path."""
    path = tmp_path / "config.toml"
    path.write_text(text)
    return path


class TestConformance:
    def test_app_exposes_the_two_commands(self) -> None:
        """The app registers exactly the validate and schema commands."""
        names = {command.callback.__name__ for command in app.registered_commands}
        assert names == {"validate", "schema"}


class TestValidate:
    def test_valid_config_exits_zero(self, tmp_path: Path) -> None:
        """validate on a valid config exits 0 and prints OK."""
        result = runner.invoke(app, ["validate", str(_write(tmp_path, _VALID_TOML))])
        assert result.exit_code == 0
        assert "OK" in result.output

    def test_invalid_schema_exits_one(self, tmp_path: Path) -> None:
        """validate on a config missing a detector type exits 1 with a message."""
        bad = _VALID_TOML.replace('type = "regex"\n', "")
        result = runner.invoke(app, ["validate", str(_write(tmp_path, bad))])
        assert result.exit_code == 1
        assert result.stderr

    def test_invalid_toml_exits_one(self, tmp_path: Path) -> None:
        """validate on syntactically invalid TOML exits 1."""
        result = runner.invoke(app, ["validate", str(_write(tmp_path, "x = = y"))])
        assert result.exit_code == 1
        assert result.stderr

    def test_missing_file_exits_one(self, tmp_path: Path) -> None:
        """validate on an absent file exits 1."""
        result = runner.invoke(app, ["validate", str(tmp_path / "absent.toml")])
        assert result.exit_code == 1
        assert result.stderr


class TestSchema:
    def test_schema_prints_json_with_expected_fields(self) -> None:
        """schema exits 0 and prints a JSON schema covering the components."""
        result = runner.invoke(app, ["schema"])
        assert result.exit_code == 0
        document = json.loads(result.output)
        assert {"detector", "linker", "anonymizer"} <= set(document["properties"])
```

- [ ] **Step 2: Run it to verify it fails**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/cli/test_cli.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'piighost.cli'`.

- [ ] **Step 3: Write the CLI module**

Create `src/piighost/cli/__init__.py`:

```python
"""piighost command-line interface (optional: config).

The CLI validates and inspects a pipeline configuration from the shell. It needs
typer, shipped with the config extra, so the module guards its import and raises
an ImportError pointing at the extra when typer is absent.

Subcommands:
- validate parses and validates a TOML config without building any component,
  exiting 0 on success and 1 on any configuration error.
- schema prints the JSON Schema of PipelineConfig to stdout.
"""

import importlib.util
import json
from pathlib import Path
from typing import Annotated

if importlib.util.find_spec("typer") is None:
    raise ImportError(
        "The piighost CLI requires typer. "
        "Install it with: pip install piighost[config]"
    )

import typer  # noqa: E402

app = typer.Typer(no_args_is_help=True, add_completion=False)


@app.command()
def validate(
    path: Annotated[Path, typer.Argument(help="Path to a TOML pipeline config.")],
) -> None:
    """Validate a pipeline TOML configuration without building it."""
    from piighost.config import load_config
    from piighost.exceptions import ConfigError

    try:
        load_config(path)
    except ConfigError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"OK: {path}")


@app.command()
def schema() -> None:
    """Print the JSON Schema of PipelineConfig to stdout."""
    from piighost.config import PipelineConfig

    document = PipelineConfig.model_json_schema()
    rendered = json.dumps(document, indent=2, ensure_ascii=False)
    typer.echo(rendered)


def main() -> None:
    """Entry point for the piighost console script."""
    app()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest tests/cli/test_cli.py -q`
Expected: PASS (6 tests).

- [ ] **Step 5: Verify the console script and the full suite**

Run: `uv run --no-sync piighost --help`
Expected: exit 0, help text listing `validate` and `schema`.

Run: `uv run --no-sync piighost schema | head -3`
Expected: the first lines of a JSON document (starts with `{`).

Run: `find src tests -name __pycache__ -type d -exec rm -rf {} +; uv run --no-sync pytest -q`
Expected: PASS (the full suite, including the module-walk regression which now also imports `piighost.cli`).

- [ ] **Step 6: Lint, types, commit**

Run: `uv run --no-sync ruff format && uv run --no-sync ruff check && uv run --no-sync pyrefly check src/piighost`
Expected: ruff clean, pyrefly 0 errors.

```bash
git add src/piighost/cli/__init__.py tests/cli/test_cli.py
git commit -m "feat(config): add the piighost CLI with validate and schema"
```

---

## Notes for the implementer

- `validate` calls `load_config` (validate only), NOT `load_pipeline`, so no component is built and no heavy model is loaded to check a config. Keep it that way.
- The lazy `from piighost.config import ...` inside each command body is deliberate: importing `piighost.cli` should only require typer, not trigger the config package import until a command runs.
- Catch `ConfigError` (the base), not its subclasses one by one, so file, TOML, and schema failures all map to exit code 1 with the message on stderr.
- Do not add anything to `PUBLIC_API`: `main` is a console-script entry point, and the module is behind the extra, covered by the walk `test_every_module_imports_cleanly`.
- Do not add commands beyond `validate` and `schema` (YAGNI, per the spec's out-of-scope).

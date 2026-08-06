"""piighost command-line interface (optional: config).

The CLI validates and inspects a pipeline configuration from the shell. It needs
typer, shipped with the config extra, so the module guards its import and raises
an ImportError pointing at the extra when typer is absent.

Subcommands:
- validate parses and validates a TOML or JSON config without building any
  component, exiting 0 on success and 1 on any configuration error.
- schema prints the JSON Schema of PipelineConfig to stdout.
"""

import importlib.util
import json
from pathlib import Path
from typing import Annotated

if importlib.util.find_spec("typer") is None:
    raise ImportError(
        "The piighost CLI requires typer. Install it with: pip install piighost[config]"
    )

import typer  # noqa: E402

app = typer.Typer(no_args_is_help=True, add_completion=False)


@app.command()
def validate(
    path: Annotated[
        Path, typer.Argument(help="Path to a TOML or JSON pipeline config.")
    ],
) -> None:
    """Validate a pipeline configuration file, TOML or JSON, without building it."""
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

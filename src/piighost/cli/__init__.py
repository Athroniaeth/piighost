"""``piighost`` command-line interface.

Subcommands:

* ``validate <file.toml>`` parses and validates a pipeline configuration
  without instantiating components. Exit code 0 on success, 1 on error.
* ``schema`` prints the JSON Schema of :class:`PipelineConfig` to stdout.

The CLI requires the ``config`` optional dependency group. A friendly
error explains how to install it if Typer is missing.
"""

import json
from pathlib import Path

import typer

app = typer.Typer(no_args_is_help=True, add_completion=False)


@app.command()
def validate(
    path: Path = typer.Argument(..., exists=False, help="Path to a TOML pipeline config."),
) -> None:
    """Validate a piighost pipeline TOML configuration."""
    from piighost.config import ConfigError, load_config

    try:
        load_config(path)
    except ConfigError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1)
    typer.echo(f"OK: {path}")


@app.command()
def schema() -> None:
    """Print the JSON Schema of PipelineConfig to stdout."""
    from piighost.config import export_schema

    typer.echo(json.dumps(export_schema(), indent=2, ensure_ascii=False))


def main() -> None:
    app()


if __name__ == "__main__":  # pragma: no cover
    main()

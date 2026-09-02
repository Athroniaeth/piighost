"""piighost command-line interface (optional: config).

The CLI validates and inspects a pipeline configuration and anonymizes text from
the shell. It needs typer, shipped with the config extra. The typer app is built
lazily, so importing this module never requires typer; running the CLI without it
prints a short install hint to stderr rather than a traceback.

Subcommands:
- validate parses and validates a TOML or JSON config without building any
  component, exiting 0 on success and 1 on any configuration error.
- schema prints the JSON Schema of PipelineConfig to stdout.
- anonymize anonymizes a text from an argument or stdin, through a config file, a
  remote piighost-api, or a default generic regex detector.
"""

import asyncio
import importlib.util
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any

if TYPE_CHECKING:
    import typer

    from piighost.pipeline.base import BaseAnonymizationPipeline

_TYPER_HINT = (
    "The piighost CLI requires typer. Install it with: pip install piighost[config]"
)


def _build_app() -> "typer.Typer":
    """Build the typer application and its commands. Requires typer."""
    import typer

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

    @app.command()
    def anonymize(
        text: Annotated[
            str | None,
            typer.Argument(help="Text to anonymize, or - to read stdin."),
        ] = None,
        config: Annotated[
            Path | None,
            typer.Option("--config", help="Pipeline config file (TOML or JSON)."),
        ] = None,
        api: Annotated[
            str | None,
            typer.Option("--api", help="Base URL of a piighost-api server."),
        ] = None,
        thread_id: Annotated[
            str,
            typer.Option(
                "--thread-id", help="Thread id for the API or a thread config."
            ),
        ] = "default",
        as_json: Annotated[
            bool,
            typer.Option(
                "--json", help="Print the anonymized text and detections as JSON."
            ),
        ] = False,
    ) -> None:
        """Anonymize a text via a config file, a remote API, or the default detector."""
        if config is not None and api is not None:
            typer.echo("Pass at most one of --config and --api.", err=True)
            raise typer.Exit(code=1)
        source = sys.stdin.read() if text is None or text == "-" else text
        output = asyncio.run(_anonymize(source, config, api, thread_id, as_json))
        typer.echo(output)

    return app


async def _anonymize(
    text: str,
    config: Path | None,
    api: str | None,
    thread_id: str,
    as_json: bool,
) -> str:
    """Anonymize a text remotely or locally and render the result for the shell."""
    if api is not None:
        anonymized, detections = await _anonymize_remote(text, api, thread_id, as_json)
    else:
        anonymized, detections = await _anonymize_local(
            text, config, thread_id, as_json
        )

    if as_json:
        payload = {"anonymized_text": anonymized, "detections": detections}
        return json.dumps(payload, ensure_ascii=False)
    return anonymized


async def _anonymize_remote(
    text: str, api: str, thread_id: str, as_json: bool
) -> tuple[str, list[dict[str, Any]]]:
    """Anonymize a text through a remote piighost-api, previewing detections for JSON."""
    from piighost.integrations.client import PIIGhostClient

    async with PIIGhostClient(api) as client:
        result = await client.anonymize(text, thread_id)
        detections: list[dict[str, Any]] = []
        if as_json:
            entities = await client.detect(text, thread_id)
            detections = [
                detection.to_dict()
                for entity in entities
                for detection in entity.detections
            ]
        return result.text, detections


async def _anonymize_local(
    text: str, config: Path | None, thread_id: str, as_json: bool
) -> tuple[str, list[dict[str, Any]]]:
    """Anonymize a text with a configured or default local pipeline."""
    from piighost.pipeline import AnonymizationPipeline, ThreadAnonymizationPipeline

    pipeline = _load_or_default(config)
    if isinstance(pipeline, ThreadAnonymizationPipeline):
        result = await pipeline.anonymize(text, thread_id)
    elif isinstance(pipeline, AnonymizationPipeline):
        result = await pipeline.anonymize(text)
    else:  # pragma: no cover - the config builds one of the two concrete pipelines
        raise TypeError(f"unsupported pipeline type: {type(pipeline).__name__}")

    detections: list[dict[str, Any]] = []
    if as_json:
        detections = [
            detection.to_dict() for detection in await pipeline.detector.detect(text)
        ]
    return result.text, detections


def _load_or_default(config: Path | None) -> "BaseAnonymizationPipeline[Any]":
    """Build the pipeline from a config, or a default generic regex one."""
    if config is not None:
        from piighost.config import load_config

        return load_config(config).build()

    from piighost.components.detector import RegexDetector
    from piighost.components.detector.patterns import GENERIC_PATTERNS
    from piighost.pipeline import AnonymizationPipeline

    detector = RegexDetector(GENERIC_PATTERNS)
    return AnonymizationPipeline(detector)


def __getattr__(name: str) -> Any:
    """Expose the typer app lazily, so importing the module never needs typer."""
    if name == "app":
        return _build_app()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def main() -> None:
    """Entry point for the piighost console script."""
    if importlib.util.find_spec("typer") is None:
        print(_TYPER_HINT, file=sys.stderr)
        raise SystemExit(1)
    _build_app()()

"""TOML loader for piighost pipelines."""

import re
import sys
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from piighost.anonymizer import Anonymizer
from piighost.config.builders import (
    build_anonymizer,
    build_detector,
    build_entity_linker,
    build_entity_resolver,
    build_placeholder_factory,
    build_span_resolver,
)
from piighost.config.errors import ConfigError
from piighost.config.models.pipeline import PipelineConfig
from piighost.detector.base import (
    AnyDetector,
    CompositeDetector,
    RegexDetector,
)
from piighost.pipeline.thread import ThreadAnonymizationPipeline

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # pyrefly: ignore[missing-import]


@dataclass(frozen=True)
class DetectorManifest:
    """Public-facing description of one declared detector."""

    name: str | None
    type: str
    labels: list[str]


@dataclass(frozen=True)
class PipelineManifest:
    """Public-facing description of the loaded pipeline.

    Source of truth for ``/v1/labels`` in ``piighost-api`` and for any
    other introspection consumer.
    """

    name: str | None
    schema_version: int
    detectors: list[DetectorManifest]
    placeholder_factory_type: str


def load_config(path: str | Path) -> PipelineConfig:
    """Parse and validate a TOML file. Does not instantiate components.

    Raises:
        ConfigError: If the file is missing, cannot be parsed, or fails
            validation against :class:`PipelineConfig`.
    """
    path = Path(path)
    try:
        raw_bytes = path.read_bytes()
    except OSError as exc:
        raise ConfigError(f"cannot read configuration file {path}: {exc}") from exc

    try:
        data = tomllib.loads(raw_bytes.decode("utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"invalid TOML syntax in {path}: {exc}") from exc

    try:
        return PipelineConfig.model_validate(data)
    except ValidationError as exc:
        raise ConfigError.from_pydantic(exc, path) from exc


def build_pipeline(
    cfg: PipelineConfig,
) -> tuple[ThreadAnonymizationPipeline, PipelineManifest]:
    """Instantiate components and return the pipeline + manifest."""

    detectors_instances: list[AnyDetector] = []
    for idx, d_cfg in enumerate(cfg.detectors):
        try:
            detectors_instances.append(build_detector(d_cfg))
        except re.error as exc:
            raise ConfigError(
                f"invalid regex in detectors[{idx}] ({d_cfg.name or d_cfg.type}): {exc}"
            ) from exc
    detector: AnyDetector = (
        detectors_instances[0]
        if len(detectors_instances) == 1
        else CompositeDetector(detectors=detectors_instances)
    )

    span_resolver = build_span_resolver(cfg.span_resolver)
    entity_linker = build_entity_linker(cfg.entity_linker)
    entity_resolver = build_entity_resolver(cfg.entity_resolver)
    anonymizer: Anonymizer = build_anonymizer(cfg.anonymizer)

    pipeline = ThreadAnonymizationPipeline(
        detector,
        anonymizer,
        span_resolver=span_resolver,
        entity_linker=entity_linker,
        entity_resolver=entity_resolver,
    )

    manifest = PipelineManifest(
        name=cfg.pipeline.name,
        schema_version=cfg.pipeline.schema_version,
        detectors=[
            DetectorManifest(
                name=d_cfg.name,
                type=d_cfg.type,
                labels=_detector_labels(d_inst),
            )
            for d_cfg, d_inst in zip(cfg.detectors, detectors_instances, strict=True)
        ],
        placeholder_factory_type=cfg.anonymizer.placeholder_factory.type,
    )
    return pipeline, manifest


def load_pipeline(
    path: str | Path,
) -> tuple[ThreadAnonymizationPipeline, PipelineManifest]:
    """Convenience: :func:`load_config` then :func:`build_pipeline`."""
    return build_pipeline(load_config(path))


def _detector_labels(d: AnyDetector) -> list[str]:
    """Return the labels a detector instance can emit, sorted."""
    if isinstance(d, RegexDetector):
        return sorted(d.patterns.keys())
    # ChunkedDetector wraps its inner detector via the .detector attribute.
    from piighost.detector.chunked import ChunkedDetector

    if isinstance(d, ChunkedDetector):
        return _detector_labels(d.detector)
    labels = getattr(d, "labels", None)
    if labels is None:
        # BaseNERDetector keeps external labels via the property.
        labels = getattr(d, "external_labels", None)
    if labels is None:
        return []
    return sorted(labels)

# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "piighost[observation]",
#     "langfuse>=3",
#     "opentelemetry-sdk>=1.30",
# ]
#
# [tool.uv.sources]
# piighost = { path = "../..", editable = true }
# ///
"""Trace the pipeline with OpenTelemetry, rendered in Langfuse or the console.

The pipeline emits OpenTelemetry spans through the piighost observation seam.
With Langfuse credentials in the environment (copy .env.example to .env), the
Langfuse v3 SDK is initialized with a should_export_span predicate admitting the
piighost scope, and captures those spans, being itself built on OTel. The whole
conversation is wrapped in one application-level span, so it renders as a single
trace: the conversation root, one child per pipeline call, and the stage spans
below each, grouped into a session by thread id. Without credentials the spans
print to the console instead, so the example runs offline and still shows the
span tree. Run with:
uv run examples/observation/langfuse_tracing.py
"""

import asyncio
import os
from pathlib import Path
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor

from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import ExactMatchDetector
from piighost.components.linker import ExactEntityLinker
from piighost.components.placeholder import LabelCounterPlaceholderFactory
from piighost.conversation_memory import InMemoryConversationMemory
from piighost.pipeline import ThreadAnonymizationPipeline


def _load_env() -> None:
    """Load the .env sitting next to this script, if present."""
    env_file = Path(__file__).with_name(".env")
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, _, value = stripped.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def _format_span(span: ReadableSpan) -> str:
    """Render one finished span as a compact single line."""
    attributes = dict(span.attributes or {})
    output = str(attributes.get("langfuse.observation.output", ""))
    return f"[span] {span.name:22} {output[:58]}\n"


def _export_piighost_spans(span: ReadableSpan) -> bool:
    """Let Langfuse export the piighost spans alongside its own.

    Langfuse v3 exports, by default, only its own spans, spans carrying gen_ai
    attributes, and spans from an allowlist of known LLM instrumentation scopes.
    The piighost scope is not on that list, so this predicate admits it (and its
    sub-scopes, such as this example's conversation root), plus Langfuse's own
    scope so SDK-created observations keep flowing.
    """
    scope = span.instrumentation_scope
    if scope is None:
        return False
    return (
        scope.name == "langfuse-sdk"
        or scope.name == "piighost"
        or scope.name.startswith("piighost.")
    )


def _configure_backend() -> Any:
    """Wire Langfuse when credentials exist, else print spans to the console.

    Returns the Langfuse client, to flush before exiting, or None in console
    mode. Initializing the Langfuse v3 client registers an OTel tracer provider,
    and the should_export_span predicate admits the piighost spans into its
    exporter.
    """
    if os.environ.get("LANGFUSE_PUBLIC_KEY") and os.environ.get("LANGFUSE_SECRET_KEY"):
        from langfuse import Langfuse  # pyrefly: ignore[missing-import]

        client = Langfuse(should_export_span=_export_piighost_spans)
        host = os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com")
        print(f"backend: Langfuse ({host})")
        return client

    provider = TracerProvider()
    exporter = ConsoleSpanExporter(formatter=_format_span)
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    trace.set_tracer_provider(provider)
    print("backend: console (copy .env.example to .env to use Langfuse)")
    return None


async def main() -> None:
    """Anonymize a small conversation, traced as one application-level trace.

    The pipeline spans nest under whatever span is current, so opening one
    conversation-level span around the calls renders the whole exchange as a
    single trace: the conversation root, then one child per call, each with its
    stage spans below.
    """
    _load_env()
    client = _configure_backend()

    pipeline = ThreadAnonymizationPipeline(
        ExactMatchDetector({"Emma": "PERSON", "Liam": "PERSON"}),
        ExactEntityLinker(),
        Anonymizer(LabelCounterPlaceholderFactory()),
        InMemoryConversationMemory(),
    )

    tracer = trace.get_tracer("piighost.example")
    with tracer.start_as_current_span("pii-conversation") as conversation:
        # Langfuse fills the stored trace name and session only from these
        # root-span attributes; the observation names alone leave them empty.
        conversation.set_attribute("langfuse.trace.name", "pii-conversation")
        conversation.set_attribute("langfuse.session.id", "demo-thread")

        first = await pipeline.anonymize("Hi, I am Emma.", "demo-thread")
        second = await pipeline.anonymize("Emma met Liam today.", "demo-thread")
        restored = await pipeline.deanonymize(second.text, "demo-thread")

    print()
    print("anonymized 1:", first.text)
    print("anonymized 2:", second.text)
    print("restored:    ", restored)

    if client is not None:
        client.flush()


if __name__ == "__main__":
    asyncio.run(main())

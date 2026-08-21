"""LlamaIndex ingestion transform that anonymizes node text (optional: llama-index).

A TransformComponent that anonymizes each node's text before it is embedded, so
the embedding provider never sees PII. It calls the thread pipeline's anonymize
directly, since ingestion only anonymizes and never restores. This module needs
the llama-index package; it is guarded so importing it without the dependency
raises an ImportError pointing at the extra.
"""

import asyncio
import importlib.util
from typing import Any

from pydantic import ConfigDict

from piighost.pipeline import AnyThreadPipeline

if importlib.util.find_spec("llama_index") is None:
    raise ImportError(
        "The LlamaIndex integration requires the llama-index package. "
        "Install it with: pip install piighost[llama-index]"
    )

from llama_index.core.schema import TransformComponent  # pyrefly: ignore[missing-import]  # noqa: E402


class PIINodeAnonymizer(TransformComponent):
    """Anonymize each node's text within a corpus thread before embedding.

    Placed in an index or ingestion pipeline's transformations before the
    embedding model, so the index is built on anonymized text and no PII reaches
    the embedding provider. A value keeps one token across the corpus because
    every node is anonymized into the same thread.

    The sync __call__ path uses asyncio.run, so it cannot run inside an already
    active event loop. When ingesting from async code, drive the async path,
    IngestionPipeline.arun, so acall is awaited directly.

    Attributes:
        pipeline: The thread pipeline that detects and tokenizes.
        thread_id: The corpus thread every node is anonymized into.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    pipeline: AnyThreadPipeline
    thread_id: str

    def __call__(self, nodes: Any, **kwargs: Any) -> Any:
        """Run the async anonymization from LlamaIndex's sync ingestion path."""
        return asyncio.run(self.acall(nodes, **kwargs))

    async def acall(self, nodes: Any, **kwargs: Any) -> Any:
        """Replace each node's text with its anonymized form in the thread."""
        for node in nodes:
            result = await self.pipeline.anonymize(node.text, self.thread_id)
            node.text = result.text
        return nodes

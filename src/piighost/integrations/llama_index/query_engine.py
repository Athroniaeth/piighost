"""LlamaIndex query-engine wrapper that de-identifies a RAG query (optional: llama-index).

Wraps any query engine: it anonymizes the query into the corpus thread so
retrieval matches the anonymized index, delegates to the inner engine, and
deanonymizes the answer through the shared TextDeidentifier so the caller sees
real values while the model only ever saw tokens. This module needs the
llama-index package; it is guarded so importing it without the dependency raises
an ImportError pointing at the extra.
"""

import asyncio
from typing import Any, Generic

from typing_extensions import TypeVar

from piighost.components.placeholder.tags import PreservesRecognizableIdentity
from piighost.integrations._deidentify import TextDeidentifier
from piighost.integrations.langchain.strategy import InventedPlaceholderStrategy
from piighost.pipeline import AnyThreadPipeline

try:
    from llama_index.core.base.base_query_engine import (  # pyrefly: ignore[missing-import]
        BaseQueryEngine,
    )
except ImportError as exc:
    raise ImportError(
        "The LlamaIndex integration requires the llama-index package. "
        "Install it with: pip install piighost[llama-index]"
    ) from exc

IdentityT = TypeVar(
    "IdentityT",
    bound=PreservesRecognizableIdentity,
    default=PreservesRecognizableIdentity,
)


class PIIQueryEngine(BaseQueryEngine, Generic[IdentityT]):
    """Anonymize a RAG query and restore the answer around any inner engine.

    The wrapper anonymizes the query into the corpus thread so retrieval matches
    the anonymized index, delegates to the inner engine, and deanonymizes the
    answer. The sync _query path uses asyncio.run, so it cannot run inside an
    already active event loop; from async code, use aquery so _aquery is awaited
    directly. It wraps a non-streaming engine; a streaming inner engine raises,
    since restoring a token split across stream chunks is a separate concern.

    Attributes:
        invented_strategy: How a token the pipeline never issued is handled when
            restoring the answer, KEEP, DROP, or RAISE.
    """

    def __init__(
        self,
        inner: Any,
        pipeline: AnyThreadPipeline[IdentityT],
        thread_id: str,
        invented_strategy: InventedPlaceholderStrategy = InventedPlaceholderStrategy.RAISE,
        callback_manager: Any = None,
    ) -> None:
        """Wrap the inner engine and build the shared de-identifier."""
        super().__init__(callback_manager)
        self._inner = inner
        self._deidentifier = TextDeidentifier(pipeline, invented_strategy)
        self._thread_id = thread_id
        self.invented_strategy = invented_strategy

    async def _aquery(self, query_bundle: Any) -> Any:
        """Anonymize the query, delegate, then deanonymize the answer."""
        anonymized = await self._deidentifier.anonymize(
            query_bundle.query_str, self._thread_id
        )
        response = await self._inner.aquery(anonymized)
        if not hasattr(response, "response"):
            raise NotImplementedError(
                "PIIQueryEngine cannot restore a streaming response, whose tokens "
                "arrive split across chunks. Build the inner engine with "
                "streaming=False."
            )
        if response.response is not None:
            response.response = await self._deidentifier.deanonymize(
                response.response, self._thread_id
            )
        return response

    def _query(self, query_bundle: Any) -> Any:
        """Run the async query from LlamaIndex's sync query path."""
        return asyncio.run(self._aquery(query_bundle))

    def _get_prompt_modules(self) -> dict[str, Any]:
        """No prompt modules: this engine only wraps another one."""
        return {}

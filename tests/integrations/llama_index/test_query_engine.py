"""Tests for the LlamaIndex query-engine wrapper.

A fake inner engine and an ExactMatchDetector thread pipeline keep everything
offline; they skip when llama-index is absent.
"""

import pytest

pytest.importorskip("llama_index")

from llama_index.core.base.response.schema import Response  # pyrefly: ignore[missing-import]  # noqa: E402

from piighost.components.detector import ExactMatchDetector  # noqa: E402
from piighost.integrations.llama_index import PIIQueryEngine  # noqa: E402
from piighost.pipeline import ThreadAnonymizationPipeline  # noqa: E402


class _FakeInner:
    """A stand-in query engine recording the query it received.

    It returns a real LlamaIndex Response so the base engine's public query and
    aquery, which validate the response type on their instrumentation event, run
    without loading a retriever or a model.
    """

    def __init__(self, response: str) -> None:
        self._response = response
        self.received: str | None = None

    async def aquery(self, query: str) -> Response:
        self.received = query
        return Response(response=self._response)

    def query(self, query: str) -> Response:
        self.received = query
        return Response(response=self._response)


def _pipeline() -> ThreadAnonymizationPipeline:
    detector = ExactMatchDetector({"Emma": "PERSON"})
    return ThreadAnonymizationPipeline(detector)


class TestQuery:
    async def test_anonymizes_query_and_restores_answer(self) -> None:
        """The inner engine sees the anonymized query; the answer is restored."""
        from llama_index.core.schema import QueryBundle  # pyrefly: ignore[missing-import]

        inner = _FakeInner("<<PERSON:1>> is in the office")
        engine = PIIQueryEngine(inner=inner, pipeline=_pipeline(), thread_id="t")
        response = await engine._aquery(QueryBundle(query_str="Where is Emma?"))
        assert inner.received == "Where is <<PERSON:1>>?"
        assert response.response == "Emma is in the office"

    def test_sync_query_bridges_to_aquery(self) -> None:
        """The public sync query path anonymizes and restores too."""
        inner = _FakeInner("<<PERSON:1>> is here")
        engine = PIIQueryEngine(inner=inner, pipeline=_pipeline(), thread_id="t")
        response = engine.query("Where is Emma?")
        assert inner.received == "Where is <<PERSON:1>>?"
        assert response.response == "Emma is here"

    async def test_rejects_a_streaming_response(self) -> None:
        """A streaming inner response, which has no .response, is refused."""
        from llama_index.core.schema import QueryBundle  # pyrefly: ignore[missing-import]

        class _StreamingResponse:
            def __init__(self) -> None:
                self.response_gen = iter(())

        class _StreamingInner:
            async def aquery(self, query: str) -> _StreamingResponse:
                return _StreamingResponse()

        inner = _StreamingInner()
        engine = PIIQueryEngine(inner=inner, pipeline=_pipeline(), thread_id="t")
        with pytest.raises(NotImplementedError):
            await engine._aquery(QueryBundle(query_str="Where is Emma?"))

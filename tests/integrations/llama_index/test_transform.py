"""Tests for the LlamaIndex node anonymizer transform.

An ExactMatchDetector over an in-memory thread pipeline keeps a value's token
stable across nodes, so no model loads and no network call is made; they skip
when llama-index is absent.
"""

import pytest

pytest.importorskip("llama_index")

from llama_index.core.schema import TextNode  # pyrefly: ignore[missing-import]  # noqa: E402

from piighost.components.detector import ExactMatchDetector  # noqa: E402
from piighost.integrations.llama_index import PIINodeAnonymizer  # noqa: E402
from piighost.pipeline import ThreadAnonymizationPipeline  # noqa: E402


def _pipeline() -> ThreadAnonymizationPipeline:
    detector = ExactMatchDetector({"Emma": "PERSON", "Paris": "LOCATION"})
    return ThreadAnonymizationPipeline(detector)


class TestAnonymize:
    async def test_anonymizes_each_node_text(self) -> None:
        """Each node's text is replaced with its anonymized form."""
        transform = PIINodeAnonymizer(pipeline=_pipeline(), thread_id="corpus")
        nodes = [TextNode(text="Emma lives in Paris")]
        result = await transform.acall(nodes)
        assert result[0].text == "<<PERSON:1>> lives in <<LOCATION:1>>"

    async def test_keeps_one_token_per_value_across_nodes(self) -> None:
        """A value repeated across nodes keeps the same token within the thread."""
        transform = PIINodeAnonymizer(pipeline=_pipeline(), thread_id="corpus")
        nodes = [TextNode(text="Emma lives in Paris"), TextNode(text="Emma works")]
        result = await transform.acall(nodes)
        assert result[0].text == "<<PERSON:1>> lives in <<LOCATION:1>>"
        assert result[1].text == "<<PERSON:1>> works"

    def test_sync_call_bridges_to_acall(self) -> None:
        """The sync __call__ path anonymizes the nodes too."""
        transform = PIINodeAnonymizer(pipeline=_pipeline(), thread_id="corpus")
        nodes = [TextNode(text="Emma works")]
        result = transform(nodes)
        assert result[0].text == "<<PERSON:1>> works"

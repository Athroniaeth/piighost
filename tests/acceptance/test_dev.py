"""Acceptance tests of the developer's stories, through public entry points.

Each test carries the id of the acceptance test it implements, AT-<story>-<n>,
the same in every language of the documentation.
"""

from piighost.components.detector import ExactMatchDetector
from piighost.pipeline import ThreadAnonymizationPipeline


def _pipeline() -> ThreadAnonymizationPipeline:
    """Build a thread pipeline that knows two people."""
    return ThreadAnonymizationPipeline(
        ExactMatchDetector({"Emma": "PERSON", "Liam": "PERSON"})
    )


class TestThreadIsolation:
    async def test_a_token_restores_in_its_own_thread_only(self) -> None:
        """A token issued in one thread never restores to another thread's value (AT-DEV-3-2)."""
        pipeline = _pipeline()
        assert (await pipeline.anonymize("Hi Emma", "a")).text == "Hi <<PERSON:1>>"
        assert (await pipeline.anonymize("Hi Liam", "b")).text == "Hi <<PERSON:1>>"

        assert await pipeline.deanonymize("<<PERSON:1>>", "a") == "Emma"
        assert await pipeline.deanonymize("<<PERSON:1>>", "b") == "Liam"
        assert await pipeline.deanonymize("<<PERSON:1>>", "c") == "<<PERSON:1>>"

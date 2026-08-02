"""Moderation guard rail: classify residual PII with a moderation model.

It depends on a small structural view of the moderation client, not on any SDK,
so the concrete client, such as mistralai's Mistral (install piighost[mistral]),
is wired at the composition root and this module needs no optional dependency.
"""

from typing import Protocol, runtime_checkable

from piighost.guard.base import GuardVerdict

_DEFAULT_MODEL = "mistral-moderation-latest"
_DEFAULT_THRESHOLD = 0.5
_PII_CATEGORY = "pii"


class _ModerationResult(Protocol):
    """One moderation result, its per-category scores."""

    category_scores: dict[str, float] | None


class _ModerationResponse(Protocol):
    """A moderation response, one result per input."""

    results: list[_ModerationResult]


class _ModerationClassifiers(Protocol):
    """The classifiers namespace of a moderation client."""

    async def moderate_async(
        self, model: str, inputs: str
    ) -> _ModerationResponse: ...


@runtime_checkable
class AnyModerationClient(Protocol):
    """The slice of a moderation client this guard uses.

    A mistralai Mistral instance satisfies it structurally, and so does a fake in
    a test, so the guard depends on the capability, not on the SDK.
    """

    classifiers: _ModerationClassifiers


class ModerationGuardRail:
    """Classify residual PII with a moderation model's PII category score.

    It moderates the anonymized text and reads the PII category score, flagging
    the verdict when the score reaches the threshold. Being a different modality
    from a detector, it catches PII a detection-based pipeline structurally
    cannot localize, at the cost of a text-level verdict without spans.

    Attributes:
        model: The moderation model to call.
        threshold: The PII score at or above which the verdict is flagged.
    """

    def __init__(
        self,
        client: AnyModerationClient,
        model: str = _DEFAULT_MODEL,
        threshold: float = _DEFAULT_THRESHOLD,
    ) -> None:
        """Store the moderation client, the model, and the flagging threshold."""
        self._client = client
        self.model = model
        self.threshold = threshold

    async def check(self, text: str) -> GuardVerdict:
        """Return a verdict from the moderation model's PII score for the text."""
        response = await self._client.classifiers.moderate_async(
            model=self.model, inputs=text
        )
        results = response.results
        scores = results[0].category_scores if results else None
        score = (scores or {}).get(_PII_CATEGORY, 0.0)

        return GuardVerdict(flagged=score >= self.threshold, score=score)

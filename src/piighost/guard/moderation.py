"""Moderation guard rail using Mistral's moderation model (optional: mistralai).

This module needs the mistralai package. It is guarded so that importing it
without the dependency raises an ImportError pointing at the extra to install.
The core guard package never imports it eagerly.
"""

import importlib.util

from piighost.guard.base import GuardVerdict

if importlib.util.find_spec("mistralai") is None:
    raise ImportError(
        "ModerationGuardRail requires the mistralai package. "
        "Install it with: pip install piighost[mistral]"
    )

from mistralai.client import Mistral  # noqa: E402

_DEFAULT_MODEL = "mistral-moderation-latest"
_DEFAULT_THRESHOLD = 0.5
_PII_CATEGORY = "pii"


class ModerationGuardRail:
    """Classify residual PII with Mistral's moderation model.

    It moderates the anonymized text with the injected Mistral client and reads
    the PII category score, flagging the verdict when the score reaches the
    threshold. Being a different modality from a detector, it catches PII a
    detection-based pipeline cannot localize, at the cost of a text-level verdict
    without spans.

    Attributes:
        model: The moderation model to call.
        threshold: The PII score at or above which the verdict is flagged.
    """

    def __init__(
        self,
        client: Mistral,
        model: str = _DEFAULT_MODEL,
        threshold: float = _DEFAULT_THRESHOLD,
    ) -> None:
        """Store the Mistral client, the model, and the flagging threshold."""
        self._client = client
        self.model = model
        self.threshold = threshold

    async def check(self, text: str) -> GuardVerdict:
        """Return a verdict from the moderation model's PII score for the text."""
        response = await self._client.classifiers.moderate_async(
            model=self.model, inputs=text
        )
        results = response.results

        if not results:
            score = 0.0
        else:
            scores = results[0].category_scores or {}
            score = scores.get(_PII_CATEGORY, 0.0)

        return GuardVerdict(flagged=score >= self.threshold, score=score)

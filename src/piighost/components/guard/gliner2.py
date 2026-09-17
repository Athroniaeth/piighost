"""GLiNER2 guard rail using a local safety model (optional: gliner2).

This module needs the gliner2 package. It is guarded so that importing it
without the dependency raises an ImportError pointing at the extra to install.
The core guard package never imports it eagerly.
"""

import asyncio
import importlib.util

from piighost.components.guard.base import GuardVerdict

if importlib.util.find_spec("gliner2") is None:
    raise ImportError(
        "Gliner2GuardRail requires the gliner2 package. "
        "Install it with: pip install piighost[gliner2]"
    )

from gliner2 import GLiNER2  # pyrefly: ignore[missing-import]

DEFAULT_MODEL = "fastino/GLiNER2-Guardrails-PII-Multi"
"""The 300M multilingual checkpoint that moderates and extracts in one pass."""

DEFAULT_TASK = "response_safety"
"""The classification task read: whether a produced text is safe to return.

The model also answers prompt_safety, for text on its way in. A guard rail runs
on what the pipeline is about to hand back, which is a response.
"""

DEFAULT_LABELS = ("safe", "unsafe")
"""The two answers the safety tasks choose between."""

DEFAULT_THRESHOLD = 0.5
"""Confidence at or above which an unsafe verdict flags, on a 0 to 1 scale."""


class Gliner2GuardRail:
    """Classify residual PII with a GLiNER2 guardrail model, locally.

    It asks the model whether the de-identified text is safe to return and flags
    the verdict when the answer is unsafe with enough confidence. Being a
    different modality from a detector, it catches what a detection-based
    pipeline cannot localize, at the cost of a text-level verdict without spans.
    This is what ModerationGuardRail does, without the API call: the model runs
    in the process, so the text being checked, which still holds whatever leaked,
    never leaves the machine.

    A str model is loaded with GLiNER2.from_pretrained; a loaded instance is used
    as-is, which is how a caller shares one checkpoint between this guard and a
    Gliner2Detector.

    Attributes:
        model: The loaded GLiNER2 model the text is classified with.
        task: The classification task read from the model's answer.
        labels: The answers the task chooses between, the unsafe one last.
        threshold: The confidence at or above which an unsafe answer flags.
    """

    def __init__(
        self,
        model: GLiNER2 | str = DEFAULT_MODEL,
        task: str = DEFAULT_TASK,
        labels: tuple[str, ...] = DEFAULT_LABELS,
        threshold: float = DEFAULT_THRESHOLD,
    ) -> None:
        """Store or load the model, then set the task, labels and threshold."""
        self.model = GLiNER2.from_pretrained(model) if isinstance(model, str) else model
        self.task = task
        self.labels = labels
        self.threshold = threshold

    async def check(self, text: str) -> GuardVerdict:
        """Return a verdict from the model's safety answer for the text."""
        answer = await asyncio.to_thread(
            self.model.classify_text,
            text,
            {self.task: list(self.labels)},
            include_confidence=True,
        )
        verdict = answer.get(self.task) or {}
        label = verdict.get("label")
        score = float(verdict.get("confidence", 0.0))
        unsafe = self.labels[-1]
        return GuardVerdict(
            flagged=label == unsafe and score >= self.threshold, score=score
        )

"""Guard rail abstractions: the port and the verdict it returns."""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from piighost.models import Detection


@dataclass(frozen=True, slots=True)
class GuardVerdict:
    """The classification a guard rail returns for an anonymized text.

    A guard classifies, it does not decide: it reports whether PII seems to
    remain and how it knows, leaving the choice to reject to the caller. The
    detail depends on the guard, a score from a moderation model or the residual
    detections from a detector, so both are optional.

    Attributes:
        flagged: Whether the guard judges that PII remains.
        score: The guard's confidence that PII remains, when it produces one,
            else None.
        detections: The residual detections the guard localized, when it works
            by detection, else empty.
    """

    flagged: bool
    score: float | None = None
    detections: tuple[Detection, ...] = ()


@runtime_checkable
class AnyGuardRail(Protocol):
    """A component that classifies anonymized text for residual PII.

    After the pipeline anonymizes a text, a guard rail scans the output alone and
    returns a GuardVerdict saying whether PII seems to remain. It judges the
    anonymized text only: the placeholders it carries are clearly synthetic, so a
    check meant for real PII does not mistake them for it. Deciding what to do
    with a flagged verdict, such as raising PIIRemainingError, is the caller's
    job, not the guard's.

    There is no Base template: guards differ by their whole checking mechanism,
    re-running a local detector versus calling an external moderation or LLM
    API, not by a single hook over one input, so there is no shared skeleton to
    template. This is the pairwise exception to the always-template rule.
    """

    async def check(self, text: str) -> GuardVerdict:
        """Return a verdict on whether the anonymized text still holds PII.

        Args:
            text: The anonymized text to re-check.

        Returns:
            The guard's verdict, flagged when PII seems to remain, with a score
            or the residual detections when the guard produces them.
        """
        ...

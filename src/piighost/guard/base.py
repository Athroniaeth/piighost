"""Guard rail abstractions: the port for re-checking anonymized output."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class AnyGuardRail(Protocol):
    """A component that re-checks anonymized text for residual PII.

    After the pipeline anonymizes a text, a guard rail scans the output alone to
    confirm nothing slipped through, and raises PIIRemainingError when PII
    remains. It judges the anonymized text only: the placeholders it carries are
    clearly synthetic, so a check meant for real PII does not mistake them for
    it.

    There is no Base template: guards differ by their whole checking mechanism,
    re-running a local detector versus calling an external moderation or LLM
    API, not by a single hook over one input, so there is no shared skeleton to
    template. This is the pairwise exception to the always-template rule.
    """

    async def check(self, text: str) -> None:
        """Raise PIIRemainingError if the anonymized text still holds PII.

        Args:
            text: The anonymized text to re-check.

        Raises:
            PIIRemainingError: If PII remains in the text.
        """
        ...

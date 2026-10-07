# /// script
# requires-python = ">=3.11"
# dependencies = ["piighost", "laya"]
#
# [tool.uv.sources]
# piighost = { path = "..", editable = true }
# ///
"""Ask an open decision model whether PII is left, as a piighost guard rail.

Laya (Convai Innovations, Apache 2.0) is an open counterpart of Jev: instead
of generating text, it answers a typed question, here a yes or no, with a
calibrated probability, in one forward pass. A guard rail asks the same kind
of question of the de-identified text before it leaves, and nothing leaves the
machine to get the answer.

piighost's guard stage is a port, AnyGuardRail, with a single method. Laya
plugs into it in a dozen lines, below, without any change to the library.

This shows how a decision model plugs into the port, not a guard to deploy.
On 200 de-identified texts, half of them leaking, Laya does not separate the
leaking texts from the clean ones. Its AUROC is 0.50, chance level, and at the
default threshold it catches 69 leaks out of 100 and flags 60 clean texts out
of 100. The placeholders raise its score more than real personal data does. A
span detector that ignores what it finds on placeholders, DetectorGuardRail
over Gliner2PiiDetector, does far better. The figures are in
https://github.com/Athroniaeth/piighost/tree/master/benchmarks/decision_guard

The checkpoint downloads on first use. On CPU, a check takes 0.2 to 0.7 s.
Run with:
uv run examples/guard_rail_laya.py
"""

import asyncio

from laya import Router  # pyrefly: ignore[missing-import]

from piighost.components.detector import RegexDetector
from piighost.components.guard import GuardVerdict
from piighost.exceptions import PIIRemainingError
from piighost.pipeline import AnonymizationPipeline

QUESTION = (
    "Does this text contain personal data in clear: a person's name, an email, "
    "a phone number, a postal address, an IBAN, an ID number?"
)
"""The one question asked of every output, answered yes or no."""


class LayaGuardRail:
    """Flag a de-identified text when Laya says personal data is left.

    Attributes:
        router: The Laya router, which loads its checkpoint on first use.
        threshold: The probability of a yes at or above which the text flags.
    """

    def __init__(self, threshold: float = 0.5) -> None:
        """Load the router; the English checkpoint, whatever the language."""
        self.router = Router()
        self.threshold = threshold

    async def check(self, text: str) -> GuardVerdict:
        """Ask the question in a worker thread, since Laya's call blocks."""
        question = {"pii": {"type": "noul", "instructions": QUESTION}}
        result = await asyncio.to_thread(
            self.router.predict, text, question, model="english"
        )
        score = result["answers"]["pii"]["noul"]
        return GuardVerdict(flagged=score >= self.threshold, score=score)


EMAIL = r"[\w.+-]+@[\w.-]+\.\w{2,}"
"""All the primary detector knows: a name is not a shape it can describe."""

CLEAN = "The meeting moves to Thursday, write to a@b.co if you cannot come."
"""Only an email, which the primary pass takes, so the guard passes."""

LEAKING = "Please forward the contract to Claire Dubois, a@b.co is her assistant."
"""A name the primary pass cannot see, which the guard catches."""


async def main() -> None:
    """Show the guard passing a clean output, then refusing a leaking one."""
    guard = LayaGuardRail()
    pipeline = AnonymizationPipeline(RegexDetector({"EMAIL": EMAIL}), guard=guard)

    result = await pipeline.anonymize(CLEAN)
    print(f"clean    : {result.text}")

    try:
        await pipeline.anonymize(LEAKING)
    except PIIRemainingError as exc:
        print(f"refused  : {exc}")


if __name__ == "__main__":
    asyncio.run(main())

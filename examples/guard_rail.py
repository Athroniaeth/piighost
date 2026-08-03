# /// script
# requires-python = ">=3.11"
# dependencies = ["piighost"]
#
# [tool.uv.sources]
# piighost = { path = "..", editable = true }
# ///
"""Catch residual PII with a deterministic guard rail.

A guard rail re-checks the anonymized output for PII that slipped past the
pipeline's detector. This one is deterministic: it re-runs a RegexDetector, so
it uses no model and no network, and the same input always yields the same
verdict. The pipeline's primary detector knows one name by exact match; the
guard, a complementary regex detector, catches structured PII such as an email
or a phone by shape, which the narrow primary detector never looked for.

When the guard flags residual PII, the pipeline raises PIIRemainingError naming
the leaked labels. The placeholders the pipeline emitted are not PII-shaped, so
the guard leaves them alone. Run with:
uv run examples/guard_rail.py
"""

import asyncio

from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import ExactMatchDetector, RegexDetector
from piighost.components.detector.patterns import GENERIC_PATTERNS, US_PATTERNS
from piighost.components.guard import DetectorGuardRail
from piighost.components.linker import ExactEntityLinker
from piighost.components.placeholder import (
    LabelCounterPlaceholderFactory,
    PreservesLabeledIdentityOpaque,
)
from piighost.exceptions import PIIRemainingError
from piighost.pipeline import AnonymizationPipeline


def _build_pipeline() -> AnonymizationPipeline[PreservesLabeledIdentityOpaque]:
    """Wire a pipeline whose narrow name detector is backed by a regex guard.

    The detector only knows the literal name; the guard re-runs an email and
    phone regex over the output, catching structured PII the detector missed.
    """
    guard_detector = RegexDetector({**GENERIC_PATTERNS, **US_PATTERNS})
    return AnonymizationPipeline(
        ExactMatchDetector({"Emma Doe": "PERSON"}),
        ExactEntityLinker(),
        Anonymizer(LabelCounterPlaceholderFactory()),
        guard=DetectorGuardRail(guard_detector),
    )


async def main() -> None:
    """Show the guard passing, then flagging a leak, then used on its own."""
    pipeline = _build_pipeline()

    # 1. Only the known name appears, so the guard finds nothing and it passes.
    clean = await pipeline.anonymize("Emma Doe opened a ticket.")
    print("guard passed:  ", clean.text)

    # 2. The name is anonymized, but an email and a phone slip past the primary
    #    detector; the regex guard catches them and the pipeline refuses.
    leaky = "Emma Doe opened a ticket from emma@corp.com; call 415-555-2671."
    try:
        await pipeline.anonymize(leaky)
    except PIIRemainingError as error:
        leaked = sorted({detection.label for detection in error.detections})
        print("guard flagged: ", leaked)

    # 3. A guard is usable on its own, returning a verdict rather than raising.
    #    It flags the clear email but leaves the synthetic placeholder alone.
    guard = DetectorGuardRail(RegexDetector(GENERIC_PATTERNS))
    verdict = await guard.check("Reach <<PERSON:1>> at leaked@corp.com.")
    residual = [detection.text for detection in verdict.detections]
    print("standalone:    ", f"flagged={verdict.flagged}, residual={residual}")


if __name__ == "__main__":
    asyncio.run(main())

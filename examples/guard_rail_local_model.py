# /// script
# requires-python = ">=3.11"
# dependencies = ["piighost[gliner2]"]
#
# [tool.uv.sources]
# piighost = { path = "..", editable = true }
# ///
"""Refuse a leaking answer with a local safety model, no API call.

ModerationGuardRail classifies the de-identified output with Mistral, which
means sending text that still holds whatever leaked to a third party. That is
an odd shape for the last stage of a de-identification pipeline.

Gliner2GuardRail asks the same question of a model that runs in the process:
fastino/GLiNER2-Guardrails-PII-Multi, a 300M multilingual checkpoint that does
safety moderation and PII extraction in one forward pass. The verdict carries a
confidence, like the moderation one, and nothing leaves the machine.

The cost is a model in memory and a download on first use. Run with:
uv run examples/guard_rail_local_model.py
"""

import asyncio

from piighost.components.detector import RegexDetector
from piighost.components.guard import Gliner2GuardRail
from piighost.exceptions import PIIRemainingError
from piighost.pipeline import AnonymizationPipeline

EMAIL = r"[\w.+-]+@[\w.-]+\.\w{2,}"
"""All the primary detector knows: a name is not a shape it can describe."""

CLEAN = "Write to a@b.co about the invoice."
"""Only structured PII, so the primary pass takes it and the guard passes."""

LEAKING = "Write to John Doe, 12 rue des Lilas, 75008 Paris."
"""A name and an address the primary pass cannot see, which the guard catches."""


async def main() -> None:
    """Show the guard passing a clean output, then refusing a leaking one."""
    guard = Gliner2GuardRail()
    pipeline = AnonymizationPipeline(RegexDetector({"EMAIL": EMAIL}), guard=guard)

    result = await pipeline.anonymize(CLEAN)
    print(f"clean    : {result.text}")

    try:
        await pipeline.anonymize(LEAKING)
    except PIIRemainingError as exc:
        print(f"refused  : {exc}")

    # A guard is usable on its own, without a pipeline raising for you.
    verdict = await guard.check("Write to <<EMAIL:1>> about the invoice.")
    print(f"tokens   : flagged={verdict.flagged} score={verdict.score:.4f}")


if __name__ == "__main__":
    asyncio.run(main())

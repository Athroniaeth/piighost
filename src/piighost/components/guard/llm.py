"""LLM guard rail (optional: llm).

Re-checks anonymized text with a chat model prompted to ignore placeholders and
flag only residual clear-form PII, by wrapping an LLMDetector with a guard
prompt. This module needs the langchain-core package; it is guarded so importing
it without the dependency raises an ImportError pointing at the extra.
"""

import importlib.util

from piighost.components.guard.base import GuardVerdict

if importlib.util.find_spec("langchain_core") is None:
    raise ImportError(
        "LLMGuardRail requires the langchain-core package. "
        "Install it with: pip install piighost[llm]"
    )

from langchain_core.language_models import BaseChatModel  # noqa: E402

from piighost.components.detector.llm import LLMDetector  # noqa: E402

_GUARD_PROMPT = (
    "You are auditing text that has already been anonymized. Your job is to "
    "find Personally Identifiable Information (PII) that is still present in "
    "clear form, despite the anonymization step.\n\n"
    "Extract clear-form entities matching these labels:\n"
    "{labels}\n\n"
    "Tokens of the form <<LABEL:NUMBER>> or <<LABEL:HEX>> (for example "
    "<<PERSON:1>>, <<LOCATION:a3f9>>) are placeholders, not PII; never flag "
    "them. Only flag entities that appear in the text in clear form. If no "
    "clear-form PII remains, return an empty list."
)


class LLMGuardRail:
    """Guard rail backed by a LangChain chat model.

    It wraps an LLMDetector configured with a guard prompt that tells the model
    to ignore placeholders and flag only residual clear-form PII, then reports a
    verdict. A str model is loaded like LLMDetector's; a loaded instance is used
    as-is. A custom prompt must contain a {labels} placeholder.
    """

    def __init__(
        self,
        model: BaseChatModel | str,
        labels: list[str] | dict[str, str],
        prompt: str | None = None,
        provider: str | None = None,
    ) -> None:
        """Build the internal LLMDetector with the guard prompt."""
        self._detector = LLMDetector(
            model=model,
            labels=labels,
            prompt=prompt or _GUARD_PROMPT,
            provider=provider,
        )

    async def check(self, text: str) -> GuardVerdict:
        """Return a verdict flagged when the model finds residual clear-form PII."""
        residual = await self._detector.detect(text)
        return GuardVerdict(flagged=bool(residual), detections=tuple(residual))

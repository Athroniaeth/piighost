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

from langchain_core.language_models import BaseChatModel

from piighost.components.detector.llm import LLMDetector


def _guard_prompt(prefix: str, suffix: str) -> str:
    """Build the guard prompt, its placeholder examples in the given delimiters.

    The examples of what not to flag follow the delimiters the pipeline actually
    emits, so a pipeline built with custom delimiters is described correctly. The
    {labels} placeholder stays literal for LangChain to fill at format time.
    """
    hint = (
        f"Tokens of the form {prefix}LABEL:NUMBER{suffix} or "
        f"{prefix}LABEL:HEX{suffix} (for example {prefix}PERSON:1{suffix}, "
        f"{prefix}LOCATION:a3f9{suffix}) are placeholders, not PII; never flag them."
    )
    return (
        "You are auditing text that has already been anonymized. Your job is to "
        "find Personally Identifiable Information (PII) that is still present in "
        "clear form, despite the anonymization step.\n\n"
        "Extract clear-form entities matching these labels:\n"
        "{labels}\n\n"
        + hint
        + " Only flag entities that appear in the text in clear form. If no "
        "clear-form PII remains, return an empty list."
    )


class LLMGuardRail:
    """Guard rail backed by a LangChain chat model.

    It wraps an LLMDetector configured with a guard prompt that tells the model
    to ignore placeholders and flag only residual clear-form PII, then reports a
    verdict. A str model is loaded like LLMDetector's; a loaded instance is used
    as-is. A custom prompt must contain a {labels} placeholder. When no custom
    prompt is given, the default prompt's placeholder examples follow prefix and
    suffix, so they match the delimiters the pipeline emits.
    """

    def __init__(
        self,
        model: BaseChatModel | str,
        labels: list[str] | dict[str, str],
        prompt: str | None = None,
        provider: str | None = None,
        prefix: str = "<<",
        suffix: str = ">>",
    ) -> None:
        """Build the internal LLMDetector with the guard prompt."""
        self._detector = LLMDetector(
            model=model,
            labels=labels,
            prompt=prompt or _guard_prompt(prefix, suffix),
            provider=provider,
        )

    async def check(self, text: str) -> GuardVerdict:
        """Return a verdict flagged when the model finds residual clear-form PII."""
        residual = await self._detector.detect(text)
        return GuardVerdict(flagged=bool(residual), detections=tuple(residual))

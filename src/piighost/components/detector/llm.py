"""LLM detector (optional: llm).

Wraps a LangChain chat model that extracts PII as structured (text, label)
pairs, then locates each value in the source text. This module needs the
langchain-core package (and pydantic, pulled in with it); it is guarded so
importing it without the dependency raises an ImportError pointing at the extra.
"""

import importlib.util
import logging
from enum import Enum

from piighost.components.detector.ner.base import BaseNERDetector
from piighost.models import Detection
from piighost.text import find_all_word_boundary

if importlib.util.find_spec("langchain_core") is None:
    raise ImportError(
        "LLMDetector requires the langchain-core package. "
        "Install it with: pip install piighost[llm]"
    )

from langchain_core.language_models import BaseChatModel  # noqa: E402
from langchain_core.prompts import ChatPromptTemplate  # noqa: E402
from pydantic import BaseModel  # noqa: E402

logger = logging.getLogger(__name__)

_DEFAULT_PROMPT = (
    "You are a Named Entity Recognition (NER) system specialized in "
    "extracting Personally Identifiable Information (PII).\n\n"
    "Extract all entities from the user's text that match these labels:\n"
    "{labels}\n\n"
    "Return each entity exactly as it appears in the text. Only extract "
    "entities that are actually present in the text."
)


def _make_schema(labels: list[str]) -> type[BaseModel]:
    """Build a pydantic extraction model whose label field is a labels enum.

    The runtime Enum of the labels becomes an enum constraint in the JSON Schema
    that with_structured_output sends to the provider, so the model can only
    return a configured label.
    """
    label_enum = Enum("Label", [(label, label) for label in labels])  # pyrefly: ignore[invalid-argument]

    class _Entity(BaseModel):
        text: str
        label: label_enum

    class _Extraction(BaseModel):
        entities: list[_Entity]

    return _Extraction


class LLMDetector(BaseNERDetector):
    """Detect PII with a LangChain chat model via structured output.

    The model is asked to extract (text, label) pairs against a schema whose
    label field is constrained to the configured labels. Each extracted value is
    then located in the source text by word-boundary search, so a value the
    model invented but absent from the text yields nothing. labels is required,
    since the schema is built from it. A str model is loaded with init_chat_model;
    a loaded instance is used as-is.

    A custom prompt must contain a {labels} placeholder and, per LangChain's
    f-string format, double any other literal curly brace as {{ or }}. The source
    text is passed as a template value, so curly braces in it are safe.
    """

    def __init__(
        self,
        model: BaseChatModel | str,
        labels: list[str] | dict[str, str],
        prompt: str | None = None,
        provider: str | None = None,
    ) -> None:
        """Store or load the model, then build the schema, prompt, and chain."""
        super().__init__(labels)
        if isinstance(model, str):
            from langchain.chat_models import init_chat_model

            model = init_chat_model(model, model_provider=provider)
        self._schema = _make_schema(self.internal_labels)
        self._structured = model.with_structured_output(self._schema)
        self._prompt_template = ChatPromptTemplate.from_messages(
            [("system", prompt or _DEFAULT_PROMPT), ("human", "{text}")]
        )

    async def _raw_detect(self, text: str) -> list[Detection]:
        """Extract via the model, then locate each value in the source text."""
        if not text:
            return []

        messages = self._prompt_template.format_messages(
            labels=", ".join(self.internal_labels), text=text
        )
        result = await self._structured.ainvoke(messages)

        entities = getattr(result, "entities", None)
        if entities is None:
            logger.warning(
                "LLMDetector structured output returned no usable result "
                "(got %s); treating as no detections.",
                type(result).__name__,
            )
            return []

        detections: list[Detection] = []
        for entity in entities:
            for span in find_all_word_boundary(text, entity.text):
                detections.append(
                    Detection(
                        span=span,
                        text=text[span.start : span.end],
                        label=entity.label.value,
                        confidence=1.0,
                    )
                )
        return detections

"""LLM-based entity detector using structured output."""

import importlib.util
from typing import TYPE_CHECKING, Any, ClassVar, cast

if TYPE_CHECKING:
    from piighost.config.models.detector import LLMDetectorConfig

from piighost.models import Detection, Span
from piighost.utils import find_all_word_boundary

if importlib.util.find_spec("langchain_core") is None:
    raise ImportError(
        "You must install langchain-core to use LLMDetector, "
        "please install piighost[llm]"
    )

from enum import Enum

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

_DEFAULT_PROMPT = (
    "You are a Named Entity Recognition (NER) system specialized in "
    "extracting Personally Identifiable Information (PII).\n\n"
    "Extract all entities from the user's text that match these labels:\n"
    "{labels}\n\n"
    "Return each entity exactly as it appears in the text. "
    "Only extract entities that are actually present in the text."
)


def _make_schema(labels: list[str]) -> type[BaseModel]:
    """Build a Pydantic model with a dynamically generated Label enum.

    Converts a plain list of label strings into an ``Enum`` at runtime
    using the functional ``Enum()`` constructor::

        Enum("Label", {"PERSON": "PERSON", "LOCATION": "LOCATION"})

    This is strictly equivalent to writing the following by hand::

        class Label(Enum):
            PERSON = "PERSON"
            LOCATION = "LOCATION"

    The enum is then used as the type for the ``label`` field in the
    inner ``_Entity`` model.  When Pydantic serializes this model to
    JSON Schema (which ``BaseChatModel.with_structured_output`` sends
    to the LLM provider), it produces an ``"enum": ["PERSON", "LOCATION"]``
    constraint that forces the LLM to return only valid labels.

    Args:
        labels: The entity type names to include in the enum
            (e.g. ``["PERSON", "LOCATION"]``).

    Returns:
        A Pydantic model class with an ``entities`` field containing
        a list of items, each with ``text: str`` and ``label: Label``.
    """
    # pyrefly cannot analyze the functional Enum form when members come from
    # a runtime-built iterable, so we tell it this is intentional.
    LabelEnum = Enum(  # type: ignore[invalid-argument]
        "Label",
        [(label, label) for label in labels],
    )

    class _Entity(BaseModel):
        """A single extracted entity."""

        text: str
        label: LabelEnum  # type: ignore[valid-type]

    class _Extraction(BaseModel):
        """List of entities extracted from the text."""

        entities: list[_Entity]

    return _Extraction


def _normalize_labels(labels: list[str] | dict[str, str]) -> dict[str, str]:
    """Normalize labels into an ``{external: internal}`` mapping (list = identity)."""
    if isinstance(labels, dict):
        return dict(labels)
    return {label: label for label in labels}


class LLMDetector:
    """Detect entities using an LLM with structured output.

    Unlike traditional NER models that return character-level spans
    directly, this detector asks an LLM to extract ``(text, label)``
    pairs via a Pydantic schema, then locates every occurrence of
    each extracted entity in the source text using word-boundary
    matching (``find_all_word_boundary``).

    If the LLM hallucinates an entity that does not appear in the
    source text, it is silently ignored (word-boundary search returns
    no matches).

    Args:
        model: A LangChain chat model supporting ``with_structured_output``.
        labels: Entity types the LLM should extract.  Either a plain list
            (e.g. ``["PERSON", "LOCATION"]``) for an identity mapping, or a
            ``{external: internal}`` dict that maps the label emitted in
            ``Detection.label`` (the external, piighost-facing name) to the
            label the LLM is prompted to return (the internal model name).
            For example ``{"PERSONNE": "person"}`` prompts the LLM for
            ``"person"`` and re-maps each result to ``"PERSONNE"``.
        prompt: Optional custom system prompt template.  Must contain a
            ``{labels}`` placeholder that will be replaced by the
            comma-separated label list.  When ``None``, a built-in PII
            extraction prompt is used.

    Example:
        >>> from langchain_openai import ChatOpenAI
        >>> model = ChatOpenAI(model="gpt-4o-mini")
        >>> detector = LLMDetector(model=model, labels=["PERSON", "LOCATION"])
        >>> detections = await detector.detect("Patrick habite à Paris")
    """

    Config: ClassVar[type["LLMDetectorConfig"]]

    @classmethod
    def from_config(cls, cfg: "LLMDetectorConfig") -> "LLMDetector":
        """Build an ``LLMDetector`` from its validated configuration.

        Initialises the chat model via LangChain's ``init_chat_model``
        helper, which resolves the provider and model name at runtime.
        """
        from langchain_core.language_models import init_chat_model

        llm = init_chat_model(cfg.model, model_provider=cfg.provider)
        return cls(model=llm, labels=cfg.labels)

    def __init__(
        self,
        model: BaseChatModel,
        labels: list[str] | dict[str, str],
        prompt: str | None = None,
    ) -> None:
        self._label_map = _normalize_labels(labels)  # {external: internal}
        self._reverse: dict[str, str] = {}
        for external, internal in self._label_map.items():
            if internal in self._reverse:
                raise ValueError(
                    f"Label mapping conflict: internal label '{internal}' is used by "
                    f"multiple external labels ('{self._reverse[internal]}' and '{external}')."
                )
            self._reverse[internal] = external
        self._internal = list(self._label_map.values())
        self._prompt = prompt or _DEFAULT_PROMPT
        self._schema = _make_schema(self._internal)
        self._chain = model.with_structured_output(self._schema)

    async def detect(self, text: str) -> list[Detection]:
        """Extract entities from *text* using the LLM.

        Sends the text to the LLM which returns structured
        ``(text, label)`` pairs.  Each pair is then located in the
        source text via word-boundary regex to produce ``Detection``
        objects with accurate position spans.

        Args:
            text: The input text to search for entities.

        Returns:
            A list of ``Detection`` objects, one per occurrence found.
            All detections have ``confidence=1.0``.
        """
        if not text:
            return []

        system_content = self._prompt.format(labels=", ".join(self._internal))
        messages = [
            SystemMessage(content=system_content),
            HumanMessage(content=text),
        ]

        # with_structured_output wires the chain to return an instance of
        # self._schema (a dynamically generated Pydantic class with an
        # ``entities`` field), but LangChain types ainvoke's return as
        # ``dict | BaseModel``.  Cast to Any so the field access below is
        # untyped rather than wrongly typed.
        result = cast(Any, await self._chain.ainvoke(messages))

        detections: list[Detection] = []
        for entity in result.entities:
            for start, end in find_all_word_boundary(text, entity.text):
                detections.append(
                    Detection(
                        text=text[start:end],
                        label=self._reverse[entity.label.value],
                        position=Span(start_pos=start, end_pos=end),
                        confidence=1.0,
                    ),
                )

        return detections


from piighost.config.models.detector import LLMDetectorConfig  # noqa: E402

LLMDetector.Config = LLMDetectorConfig

"""GLiNER2 detector (optional: gliner2).

Wraps a GLiNER2 model so a caller injects a loaded instance or passes a model
name to load. This module needs the gliner2 package; it is guarded so importing
it without the dependency raises an ImportError pointing at the extra.
"""

import importlib.util
from typing import ClassVar

from piighost.components.detector.ner.base import BaseNERDetector
from piighost.models import Detection, Span

if importlib.util.find_spec("gliner2") is None:
    raise ImportError(
        "Gliner2Detector requires the gliner2 package. "
        "Install it with: pip install piighost[gliner2]"
    )

from gliner2 import GLiNER2  # pyrefly: ignore[missing-import]


class Gliner2Detector(BaseNERDetector):
    """Detect PII with a GLiNER2 model.

    labels is required, because GLiNER2 is queried with the internal labels. A
    str model is loaded with GLiNER2.from_pretrained; a loaded instance is used
    as-is.

    Attributes:
        model: The loaded GLiNER2 model queried for entities.
        threshold: The confidence at or above which an entity is kept.
    """

    def __init__(
        self,
        model: GLiNER2 | str,
        labels: list[str] | dict[str, str],
        threshold: float = 0.5,
        max_concurrency: int | None = None,
    ) -> None:
        """Store or load the model, then set the labels and threshold."""
        super().__init__(labels, max_concurrency=max_concurrency)
        self.model = GLiNER2.from_pretrained(model) if isinstance(model, str) else model
        self.threshold = threshold

    async def _raw_detect(self, text: str) -> list[Detection]:
        """Run GLiNER2 and build one detection per entity, native labels kept."""
        result = await self._run_blocking(
            self.model.extract_entities,
            text,
            self.internal_labels,
            threshold=self.threshold,
            include_spans=True,
            include_confidence=True,
        )
        detections: list[Detection] = []
        for native_label, entities in result["entities"].items():
            for entity in entities:
                span = Span(entity["start"], entity["end"])
                detection = Detection(
                    span=span,
                    text=entity["text"],
                    label=native_label,
                    confidence=entity["confidence"],
                )
                detections.append(detection)
        return detections


class Gliner2PiiDetector(Gliner2Detector):
    """Detect PII with the GLiNER2-PII model and a preset PII label set.

    A ready-to-use Gliner2Detector over fastino's GLiNER2 model fine-tuned for
    PII, with a default label map so neither a model id nor a label list is
    needed. The labels span the model's taxonomy, from names and contact details
    to identifiers, payment data, digital identity, secrets, and sensitive dates.
    Pass labels to narrow or extend the set, or model to inject a loaded
    instance, for example in a test, so no weights are downloaded.
    """

    DEFAULT_MODEL = "fastino/gliner2-privacy-filter-PII-multi"
    """The GLiNER2 model fine-tuned for PII, loaded when no model is given."""

    DEFAULT_LABELS: ClassVar[dict[str, str]] = {
        "PERSON": "person",
        "EMAIL": "email address",
        "PHONE": "phone number",
        "LOCATION": "location",
        "ADDRESS": "street address",
        "ORGANIZATION": "organization",
        "DATE_OF_BIRTH": "date of birth",
        "CREDIT_CARD": "credit card number",
        "IBAN": "iban",
        "SSN": "social security number",
        "TAX_ID": "tax identification number",
        "PASSPORT": "passport number",
        "DRIVER_LICENSE": "driver's license number",
        "IP_ADDRESS": "ip address",
        "CRYPTO": "cryptocurrency wallet address",
        "API_KEY": "api key",
        "PASSWORD": "password",  # nosec B105  # a label description, not a secret
    }
    """External-to-native PII labels queried by default, over the model taxonomy."""

    def __init__(
        self,
        model: GLiNER2 | str | None = None,
        labels: list[str] | dict[str, str] | None = None,
        threshold: float = 0.5,
        max_concurrency: int | None = None,
    ) -> None:
        """Default the model and labels to the PII preset, then delegate."""
        resolved_model = model if model is not None else self.DEFAULT_MODEL
        resolved_labels = labels if labels is not None else self.DEFAULT_LABELS
        super().__init__(
            resolved_model,
            resolved_labels,
            threshold=threshold,
            max_concurrency=max_concurrency,
        )

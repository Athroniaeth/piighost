import re
from collections import defaultdict
from typing import (
    Optional,
    List,
    TypedDict,
    Required,
    NotRequired,
    Dict,
)
from uuid import uuid4

from gliner2 import GLiNER2


# extractor = GLiNER2.from_pretrained("fastino/gliner2-base-v1")


class Detection(TypedDict):
    """Gliner2 detection class"""

    text: Required[str]
    confidence: NotRequired[float]
    start: NotRequired[int]
    end: NotRequired[int]


class CustomDetection(TypedDict):
    """Gliner2 detection class"""

    text: Required[str]
    entity_type: Required[str]
    confidence: NotRequired[float]
    start: NotRequired[int]
    end: NotRequired[int]


class ThreadID(str): ...


class Placeholder(str): ...


def get_placeholder(label: str, index: int) -> Placeholder:
    return Placeholder(f"<{label}_{index}>".upper())


def ensure_thread_id(thread_id: Optional[str]) -> ThreadID:
    value = thread_id or uuid4().hex
    assert value is not None, "Must have value for thread id"
    return ThreadID(value)


class Anonymizer:
    extractor: GLiNER2
    entity_type: List[str]

    def __init__(self, extractor: GLiNER2, entity_types: Optional[List[str]] = None):
        self.extractor = extractor
        self.entity_types = entity_types or ["company", "person", "product", "location"]

    def detect_entities(self, text: str) -> List[CustomDetection]:
        """Anonymize the given text"""
        detections: List[CustomDetection] = []
        result = self.extractor.extract_entities(
            text,
            self.entity_types,
            include_spans=True,
            include_confidence=True,
        )

        list_entity: List[Detection]
        for entity_type, list_entity in result["entities"].items():
            for entity in list_entity:
                value = CustomDetection(
                    text=entity["text"],
                    entity_type=entity_type,
                    confidence=entity["confidence"],
                    start=entity["start"],
                    end=entity["end"],
                )
                detections.append(value)

        return detections

    def get_placeholders(
        self, detections: List[CustomDetection]
    ) -> Dict[Placeholder, List[CustomDetection]]:
        """Get placeholder based on detections"""
        placeholders: Dict[Placeholder, List[CustomDetection]] = defaultdict(list)

        # Detect which detection have same placeholder
        for detection in detections:
            label = detection["entity_type"]

            for index in range(1, 1000):
                placeholder = get_placeholder(label, index)
                # If placeholder don't exist, is the first time
                if placeholder not in placeholders:
                    placeholders[placeholder].append(detection)
                    break
                else:
                    # Check if same detection object
                    first_detection = placeholders[placeholder][0]

                    # Todo : use fuzzy matching ?
                    if first_detection["text"] == detection["text"]:
                        placeholders[placeholder].append(detection)
                        break

        return placeholders

    def detect_placeholders(
        self,
        text: str,
        placeholders: Dict[Placeholder, List[CustomDetection]],
    ) -> Dict[Placeholder, List[CustomDetection]]:
        """Detect additional occurrences of already detected entities.

        GLiNER often detects only the first occurrence of an entity.
        This method scans the full text to find additional matches
        of the detected entity strings.

        Args:
            text: Original input text.
            placeholders: Existing placeholders mapped to detections.

        Returns:
            Updated placeholders with additional detections.
        """

        new_placeholders: Dict[Placeholder, List[CustomDetection]] = placeholders.copy()

        for placeholder, detections in placeholders.items():
            if not detections:
                continue

            reference = detections[0]
            entity_text = reference["text"]
            entity_type = reference["entity_type"]

            pattern = re.escape(entity_text)

            # Existing spans to avoid duplicates
            existing_spans = {
                (d["start"], d["end"])
                for d in detections
                if "start" in d and "end" in d
            }

            for match in re.finditer(pattern, text):
                start, end = match.span()

                if (start, end) in existing_spans:
                    continue

                new_detection: CustomDetection = CustomDetection(
                    text=entity_text,
                    entity_type=entity_type,
                    confidence=1.0,
                    start=start,
                    end=end,
                )

                new_placeholders[placeholder].append(new_detection)

        return new_placeholders

    def apply_placeholders(
        self,
        text: str,
        placeholders: Dict[Placeholder, List[CustomDetection]],
    ) -> str:
        """Replace detected entities in text with placeholders."""

        replacements = []

        for placeholder, detections in placeholders.items():
            for detection in detections:
                start = detection.get("start")
                end = detection.get("end")

                if start is None or end is None:
                    continue

                replacements.append((start, end, placeholder))

        # Important: sort in reverse order to preserve indices
        replacements.sort(key=lambda x: x[0], reverse=True)

        for start, end, placeholder in replacements:
            text = text[:start] + placeholder + text[end:]

        return text

    def anonymize(
        self, text: str, thread_id: Optional[str] = None
    ) -> tuple[str, Dict[Placeholder, List[CustomDetection]]]:
        """Anonymize the given text"""
        thread_id = ensure_thread_id(thread_id)
        detections = self.detect_entities(text)
        placeholders = self.get_placeholders(detections)
        placeholders = self.detect_placeholders(text, placeholders)
        text = self.apply_placeholders(text, placeholders)
        return text, placeholders

    def deanonymize(self, text: str) -> str:
        return text


def main():
    extractor = GLiNER2.from_pretrained("fastino/gliner2-base-v1")
    anonymizer = Anonymizer(extractor)
    text, detections = anonymizer.anonymize(
        "Apple Inc. CEO Tim Cook announced iPhone 15 in Cupertino. Cupertino is nice town. Paris is capital !"
    )
    for entity_type, list_placeholder in detections.items():
        print(entity_type)
        for placeholder in list_placeholder:
            print(f"\t{placeholder}")

    print(text)


if __name__ == "__main__":
    main()

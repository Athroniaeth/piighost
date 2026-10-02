# isort: split
# --8<-- [start:regex]
from piighost.components.detector import RegexDetector

detector = RegexDetector({"EMAIL": r"[\w.+-]+@[\w.-]+\.\w{2,}"})
detections = await detector.detect("write to alice@example.com")
# [Detection(span=Span(9, 26), text="alice@example.com", label="EMAIL", confidence=1.0)]
# --8<-- [end:regex]
# Not shown: what the comments above say.
from piighost.models import Detection, Span

assert detections == [
    Detection(span=Span(9, 26), text="alice@example.com", label="EMAIL", confidence=1.0)
]


# isort: split
# --8<-- [start:exact]
from piighost.components.detector import ExactMatchDetector

detector = ExactMatchDetector({"Patrick": "PERSON", "Lyon": "LOCATION"})
detections = await detector.detect("Patrick lives in Lyon")
# --8<-- [end:exact]
# Not shown: what the comments above say.
assert [d.text for d in detections] == ["Patrick", "Lyon"]


# isort: split
# --8<-- [start:bridge]
from piighost.components.detector.ner import BridgeDetector, OffsetUnit


async def runner(text: str, labels: list[str], threshold: float):
    return [{"start": 0, "end": 10, "label": "person", "score": 0.92}]


detector = BridgeDetector(
    runner, {"PERSON": "person"}, offset_unit=OffsetUnit.CODE_POINT, threshold=0.4
)
await detector.detect("Emma Rossi works at Acme.")
# [Detection(span=Span(0, 10), text="Emma Rossi", label="PERSON", confidence=0.92)]
# --8<-- [end:bridge]
# Not shown: what the comments above say.
assert await detector.detect("Emma Rossi works at Acme.") == [
    Detection(span=Span(0, 10), text="Emma Rossi", label="PERSON", confidence=0.92)
]

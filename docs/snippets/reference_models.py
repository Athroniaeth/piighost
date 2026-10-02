# isort: split
# --8<-- [start:replace]
from dataclasses import replace

from piighost.models import Detection, Span

detection = Detection(span=Span(0, 7), text="Patrick", label="PERSON", confidence=1.0)
moved = replace(detection, span=detection.span.shift(10))
# moved == Detection(span=Span(10, 17), text="Patrick", label="PERSON", confidence=1.0)
# --8<-- [end:replace]
# Not shown: what the comments above say.
assert moved == Detection(
    span=Span(10, 17), text="Patrick", label="PERSON", confidence=1.0
)


# isort: split
# --8<-- [start:to_dict]
from piighost.models import Detection, Span

detection = Detection(span=Span(0, 7), text="Patrick", label="PERSON", confidence=1.0)
detection.to_dict()
# {"start": 0, "end": 7, "text": "Patrick", "label": "PERSON", "confidence": 1.0}
# --8<-- [end:to_dict]
# Not shown: what the comments above say.
assert detection.to_dict() == {
    "start": 0,
    "end": 7,
    "text": "Patrick",
    "label": "PERSON",
    "confidence": 1.0,
}


# isort: split
# --8<-- [start:entity]
from piighost.models import Detection, Entity, Span

first = Detection(span=Span(0, 7), text="Patrick", label="PERSON", confidence=1.0)
second = Detection(span=Span(20, 27), text="Patrick", label="PERSON", confidence=0.8)
entity = Entity(detections=(first, second))

entity.label  # "PERSON"
entity.text  # "Patrick"
entity.spans  # (Span(0, 7), Span(20, 27))
# --8<-- [end:entity]
# Not shown: what the comments above say.
assert (entity.label, entity.text) == ("PERSON", "Patrick")
assert entity.spans == (Span(0, 7), Span(20, 27))


# isort: split
# --8<-- [start:splitter]
from piighost.text import RecursiveCharacterTextSplitter

splitter = RecursiveCharacterTextSplitter(chunk_size=20, chunk_overlap=5)
chunks = splitter.split("Patrick lives in Lyon and works in Paris.")
# chunks[0] == Chunk(text="Patrick lives in", start=0)
# chunks[1] == Chunk(text="in Lyon and works in", start=14)
# --8<-- [end:splitter]
# Not shown: what the comments above say.
from piighost.models import Chunk

assert chunks[0] == Chunk(text="Patrick lives in", start=0)
assert chunks[1] == Chunk(text="in Lyon and works in", start=14)

from piighost.components.detector import ExactMatchDetector
from piighost.models import Detection, Span
from piighost.pipeline import ThreadAnonymizationPipeline

pipeline = ThreadAnonymizationPipeline(
    ExactMatchDetector({"Patrick": "PERSON", "Paris": "LOCATION", "Marie": "PERSON"})
)

# isort: split
# --8<-- [start:anonymize]
a1 = await pipeline.anonymize("Patrick lives in Paris.", thread_id="user-A")
a2 = await pipeline.anonymize("Patrick wrote to Marie.", thread_id="user-A")
# Patrick keeps <<PERSON:1>> across both turns.
# --8<-- [end:anonymize]
# Not shown: what the comments above say.
assert a1.text == "<<PERSON:1>> lives in <<LOCATION:1>>."
assert a2.text == "<<PERSON:1>> wrote to <<PERSON:2>>."


# isort: split
# --8<-- [start:anonymize_corrected]
detection = Detection(span=Span(0, 5), text="Marie", label="PERSON", confidence=1.0)
detections = [detection]
result = await pipeline.anonymize_corrected("Marie called.", "user-A", detections)
# --8<-- [end:anonymize_corrected]
# Not shown: what the comments above say.
assert result.text == "<<PERSON:2>> called."


# isort: split
# --8<-- [start:deanonymize]
reply = await pipeline.deanonymize("Message sent to <<PERSON:2>>.", thread_id="user-A")
# reply == "Message sent to Marie."
# --8<-- [end:deanonymize]
# Not shown: what the comments above say.
assert reply == "Message sent to Marie."


# isort: split
# --8<-- [start:forget_thread]
forgotten = await pipeline.forget_thread("user-A")
# forgotten.messages, forgotten.detections
# --8<-- [end:forget_thread]
# Not shown: what the comments above say.
assert forgotten.messages and forgotten.detections


# isort: split
# --8<-- [start:clear_boundary_cache]
from piighost.text import clear_boundary_cache

await pipeline.forget_thread("user-A")
clear_boundary_cache()
# --8<-- [end:clear_boundary_cache]

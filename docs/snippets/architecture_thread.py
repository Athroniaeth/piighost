from piighost.components.detector import ExactMatchDetector
from piighost.pipeline import ThreadAnonymizationPipeline

thread_pipeline = ThreadAnonymizationPipeline(ExactMatchDetector({"Patrick": "PERSON"}))
text = "Patrick habite à Paris."
reply = "Bonjour <<PERSON:1>>."

# isort: split
# --8<-- [start:example]
result = await thread_pipeline.anonymize(text, thread_id="t-42")
restored = await thread_pipeline.deanonymize(reply, thread_id="t-42")
dropped = await thread_pipeline.forget_thread("t-42")
# --8<-- [end:example]

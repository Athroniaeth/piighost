from piighost.components.detector import ExactMatchDetector
from piighost.pipeline import AnonymizationPipeline

detector = ExactMatchDetector({"Patrick": "PERSON"})

# isort: split
# --8<-- [start:example]
pipeline = AnonymizationPipeline(
    detector=detector,
    trace_clear_text=True,  # I know traces carry clear PII, ship them to a trusted backend only
)
# --8<-- [end:example]

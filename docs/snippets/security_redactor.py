from piighost.components.detector import ExactMatchDetector
from piighost.pipeline import AnonymizationPipeline

detector = ExactMatchDetector({"Patrick": "PERSON"})

# isort: split
# --8<-- [start:example]
from piighost.components.placeholder import LabelCounterPlaceholderFactory

redactor = LabelCounterPlaceholderFactory()
pipeline = AnonymizationPipeline(
    detector,
    observation_redactor=redactor,  # <<PERSON:1>>, <<PERSON:2>>, <<EMAIL:1>>, ...
)
# --8<-- [end:example]


# Not shown: the examples above, put to work.
assert pipeline is not None

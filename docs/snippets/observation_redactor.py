from piighost.components.detector import ExactMatchDetector

detector = ExactMatchDetector({"Patrick": "PERSON"})

# isort: split
# --8<-- [start:example]
from piighost.components.placeholder import LabelPlaceholderFactory
from piighost.pipeline import AnonymizationPipeline

redactor = LabelPlaceholderFactory()
pipeline = AnonymizationPipeline(detector, observation_redactor=redactor)
# --8<-- [end:example]

from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import ExactMatchDetector
from piighost.components.linker import ExactEntityLinker
from piighost.components.placeholder import LabelCounterPlaceholderFactory

detector = ExactMatchDetector({"Patrick": "PERSON"})
linker = ExactEntityLinker()
anonymizer = Anonymizer(LabelCounterPlaceholderFactory())

# isort: split
# --8<-- [start:example]
from piighost.components.placeholder import LabelPlaceholderFactory
from piighost.pipeline import AnonymizationPipeline

redactor = LabelPlaceholderFactory()
pipeline = AnonymizationPipeline(
    detector,
    linker,
    anonymizer,
    observation_redactor=redactor,
)
# --8<-- [end:example]

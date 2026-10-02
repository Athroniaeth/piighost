from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import ExactMatchDetector
from piighost.components.linker import ExactEntityLinker
from piighost.components.placeholder import LabelCounterPlaceholderFactory
from piighost.pipeline import AnonymizationPipeline

detector = ExactMatchDetector({"Patrick": "PERSON"})
linker = ExactEntityLinker()
anonymizer = Anonymizer(LabelCounterPlaceholderFactory())

# isort: split
# --8<-- [start:example]
from piighost.components.placeholder import LabelCounterPlaceholderFactory

redactor = LabelCounterPlaceholderFactory()
pipeline = AnonymizationPipeline(
    detector=detector,
    linker=linker,
    anonymizer=anonymizer,
    observation_redactor=redactor,  # <<PERSON:1>>, <<EMAIL:2>>, ...
)
# --8<-- [end:example]


# Not shown: the examples above, put to work.
assert pipeline is not None

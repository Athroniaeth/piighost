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
AnonymizationPipeline(
    detector,
    linker,
    anonymizer,
    overlap_resolver=None,  # AnyOverlapResolver, defaults to ConfidenceOverlapResolver
    expander=None,  # AnyDetectionExpander
    entity_resolver=None,  # AnyEntityResolver
    guard=None,  # AnyGuardRail
    override=None,  # AnyDetectionOverride
)
# --8<-- [end:example]

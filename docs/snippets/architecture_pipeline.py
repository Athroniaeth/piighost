# Run with top-level await, as the page shows it.

# isort: split
# --8<-- [start:example]
from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import ExactMatchDetector
from piighost.components.linker import ExactEntityLinker
from piighost.components.placeholder import LabelCounterPlaceholderFactory
from piighost.pipeline import AnonymizationPipeline

detector = ExactMatchDetector({"Patrick": "PERSON"})
linker = ExactEntityLinker()
factory = LabelCounterPlaceholderFactory()
anonymizer = Anonymizer(factory)
pipeline = AnonymizationPipeline(
    detector=detector,
    linker=linker,
    anonymizer=anonymizer,
)
result = await pipeline.anonymize("Patrick habite à Paris.")
# result.text   -> "<<PERSON:1>> habite à Paris."
# result.tokens -> {Entity("Patrick"): "<<PERSON:1>>"}
restored = pipeline.deanonymize(result.text, result.tokens)
# restored -> "Patrick habite à Paris."
# --8<-- [end:example]

# Not shown: what the comments above announce.
assert result.text == "<<PERSON:1>> habite à Paris."
assert restored == "Patrick habite à Paris."

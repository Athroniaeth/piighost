from piighost.components.detector import ExactMatchDetector
from piighost.pipeline import AnonymizationPipeline

pipeline = AnonymizationPipeline(
    ExactMatchDetector({"Patrick": "PERSON", "Paris": "LOCATION"})
)

# isort: split
# --8<-- [start:anonymize]
result = await pipeline.anonymize("Patrick lives in Paris.")
# result.text == "<<PERSON:1>> lives in <<LOCATION:1>>."
# --8<-- [end:anonymize]
# Not shown: what the comments above say.
assert result.text == "<<PERSON:1>> lives in <<LOCATION:1>>."


# isort: split
# --8<-- [start:deanonymize]
original = pipeline.deanonymize(result.text, result.tokens)
# original == "Patrick lives in Paris."
# --8<-- [end:deanonymize]
# Not shown: what the comments above say.
assert original == "Patrick lives in Paris."

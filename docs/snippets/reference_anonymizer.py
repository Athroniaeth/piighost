# isort: split
# --8<-- [start:anonymize]
from piighost.components.anonymizer import Anonymizer
from piighost.components.placeholder import LabelCounterPlaceholderFactory
from piighost.models import Detection, Entity, Span

factory = LabelCounterPlaceholderFactory()
anonymizer = Anonymizer(factory)

detection = Detection(span=Span(0, 7), text="Patrick", label="PERSON", confidence=0.9)
entity = Entity(detections=(detection,))

result = anonymizer.anonymize("Patrick is nice", [entity])
# result.text == "<<PERSON:1>> is nice"
# result.tokens == {entity: "<<PERSON:1>>"}
# --8<-- [end:anonymize]
# Not shown: what the comments above say.
assert result.text == "<<PERSON:1>> is nice"
assert result.tokens == {entity: "<<PERSON:1>>"}


# isort: split
# --8<-- [start:create]
tokens = anonymizer.create([entity])
# {entity: "<<PERSON:1>>"}
# --8<-- [end:create]
# Not shown: what the comments above say.
assert tokens == {entity: "<<PERSON:1>>"}


# isort: split
# --8<-- [start:render]
rendered = anonymizer.render("Patrick is nice", [entity], tokens)
# "<<PERSON:1>> is nice"
# --8<-- [end:render]
# Not shown: what the comments above say.
assert rendered == "<<PERSON:1>> is nice"


# isort: split
# --8<-- [start:deanonymize]
original = anonymizer.deanonymize("<<PERSON:1>> is nice", result.tokens)
# "Patrick is nice"
# --8<-- [end:deanonymize]
# Not shown: what the comments above say.
assert original == "Patrick is nice"

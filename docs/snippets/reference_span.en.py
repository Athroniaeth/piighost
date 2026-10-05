# isort: split
# --8<-- [start:example]
from piighost.models import Span

span = Span(9, 26)
span.length  # 17
span.extract("write to alice@example.com")  # "alice@example.com"
span.overlaps(Span(26, 30))  # False, the two ranges are adjacent
span.shift(-9)  # Span(0, 17)
# --8<-- [end:example]
# Not shown: what the comments above say.
assert span.length == 17
assert span.extract("write to alice@example.com") == "alice@example.com"
assert not span.overlaps(Span(26, 30))
assert span.shift(-9) == Span(0, 17)

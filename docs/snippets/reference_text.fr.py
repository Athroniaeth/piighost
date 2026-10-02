# isort: split
# --8<-- [start:example]
from piighost.text import normalize_spaces, value_key

normalize_spaces("06\u00a012\u202f34")  # "06 12 34", même longueur
value_key("Paul\u00a0Martin") == value_key("paul  MARTIN")  # True, la même valeur
# --8<-- [end:example]
# Not shown: what the comments above say.
assert normalize_spaces("06\u00a012\u202f34") == "06 12 34"
assert value_key("Paul\u00a0Martin") == value_key("paul  MARTIN")

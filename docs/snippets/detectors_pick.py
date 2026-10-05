from piighost.catalog import pull
from piighost.components.detector import RegexDetector

# isort: split
# --8<-- [start:example]
generic = pull("catalog:piighost/generic")
french = pull("catalog:piighost/fr")
patterns = {
    "EMAIL": generic["EMAIL"],
    "FR_IBAN": french["FR_IBAN"],
}
detector = RegexDetector(patterns)
# --8<-- [end:example]

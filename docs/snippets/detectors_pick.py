from piighost.components.detector import RegexDetector
from piighost.hub import pull

# isort: split
# --8<-- [start:example]
generic = pull("hub:piighost/generic:fab51b33")
french = pull("hub:piighost/fr:6802f5ef")
patterns = {
    "EMAIL": generic["EMAIL"],
    "FR_IBAN": french["FR_IBAN"],
}
detector = RegexDetector(patterns)
# --8<-- [end:example]

from piighost.components.detector import RegexDetector

# isort: split
# --8<-- [start:example]
from piighost.hub import pull

detector = RegexDetector.from_hub("hub:piighost/generic")
detector = RegexDetector({**pull("hub:piighost/generic"), **pull("hub:piighost/fr")})
# --8<-- [end:example]

from piighost.components.detector import RegexDetector

# isort: split
# --8<-- [start:example]
from piighost.hub import pull

detector = RegexDetector.from_hub("hub:piighost/generic:fab51b33")
detector = RegexDetector(
    {**pull("hub:piighost/generic:fab51b33"), **pull("hub:piighost/fr:6802f5ef")}
)
# --8<-- [end:example]

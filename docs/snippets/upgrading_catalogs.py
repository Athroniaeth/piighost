from piighost.components.detector import RegexDetector

# isort: split
# --8<-- [start:example]
from piighost.catalog import pull

detector = RegexDetector.from_catalog("catalog:piighost/generic")
detector = RegexDetector(
    {**pull("catalog:piighost/generic"), **pull("catalog:piighost/fr")}
)
# --8<-- [end:example]

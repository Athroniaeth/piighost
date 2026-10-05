# isort: split
# --8<-- [start:from_catalog]
from piighost.components.detector import RegexDetector

detector = RegexDetector.from_catalog("piighost/logs:fd79aec6")
detections = await detector.detect("mail me at a@b.co from 10.0.0.1")
# --8<-- [end:from_catalog]


# isort: split
# --8<-- [start:merge]
from piighost.catalog import pull
from piighost.components.detector import RegexDetector

detector = RegexDetector.from_catalog("catalog:piighost/generic")
merged = RegexDetector(
    {**pull("catalog:piighost/generic"), **pull("catalog:piighost/fr")}
)
# --8<-- [end:merge]

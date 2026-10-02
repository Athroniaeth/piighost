# isort: split
# --8<-- [start:from_hub]
from piighost.components.detector import RegexDetector

detector = RegexDetector.from_hub("piighost/logs:fd79aec6")
detections = await detector.detect("mail me at a@b.co from 10.0.0.1")
# --8<-- [end:from_hub]


# isort: split
# --8<-- [start:merge]
from piighost.components.detector import RegexDetector
from piighost.hub import pull

detector = RegexDetector.from_hub("hub:piighost/generic:fab51b33")
merged = RegexDetector(
    {**pull("hub:piighost/generic:fab51b33"), **pull("hub:piighost/fr:6802f5ef")}
)
# --8<-- [end:merge]

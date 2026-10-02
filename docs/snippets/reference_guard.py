from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import ExactMatchDetector, RegexDetector
from piighost.components.guard import DetectorGuardRail
from piighost.components.linker import ExactEntityLinker
from piighost.components.placeholder import LabelCounterPlaceholderFactory
from piighost.exceptions import PIIRemainingError
from piighost.hub import pull
from piighost.pipeline import AnonymizationPipeline

# The primary detector only knows the literal name. The guard re-runs a broader
# email and phone regex over the short output to catch structured PII it missed.
guard_detector = RegexDetector(
    {**pull("hub:piighost/generic:fab51b33"), **pull("hub:piighost/us:29d5c0a5")}
)
pipeline = AnonymizationPipeline(
    ExactMatchDetector({"Emma Doe": "PERSON"}),
    ExactEntityLinker(),
    Anonymizer(LabelCounterPlaceholderFactory()),
    guard=DetectorGuardRail(guard_detector),
)

try:
    result = await pipeline.anonymize("Emma Doe, reachable at emma@acme.com.")
except PIIRemainingError as error:
    print(error)  # Anonymized text still contains PII: ['EMAIL']
    print(error.detections)  # the residual detections behind the flag

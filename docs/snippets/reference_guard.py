from piighost.components.detector import ExactMatchDetector, RegexDetector
from piighost.components.guard import DetectorGuardRail
from piighost.exceptions import PIIRemainingError
from piighost.hub import pull
from piighost.pipeline import AnonymizationPipeline

# The primary detector only knows the literal name. The guard re-runs a broader
# email and phone regex over the short output to catch structured PII it missed.
guard_detector = RegexDetector(
    {**pull("hub:piighost/generic"), **pull("hub:piighost/us")}
)
pipeline = AnonymizationPipeline(
    ExactMatchDetector({"Emma Doe": "PERSON"}),
    guard=DetectorGuardRail(guard_detector),
)

try:
    result = await pipeline.anonymize("Emma Doe, reachable at emma@acme.com.")
except PIIRemainingError as error:
    print(error)  # Anonymized text still contains PII: ['EMAIL']
    print(error.detections)  # the residual detections behind the flag

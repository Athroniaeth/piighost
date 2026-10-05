from piighost.components.detector import RegexDetector
from piighost.components.guard import Gliner2GuardRail
from piighost.pipeline import AnonymizationPipeline

pipeline = AnonymizationPipeline(
    RegexDetector({"EMAIL": r"[\w.+-]+@[\w.-]+\.\w{2,}"}),
    guard=Gliner2GuardRail(),
)

await pipeline.anonymize("Write to a@b.co about the invoice.")
# Write to <<EMAIL:1>> about the invoice.

await pipeline.anonymize("Write to John Doe, 12 rue des Lilas, 75008 Paris.")
# PIIRemainingError: A guard flagged residual PII (score 0.997)

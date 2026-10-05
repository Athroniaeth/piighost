from piighost.components.detector.ner import Gliner2Detector
from piighost.components.guard import DetectorGuardRail

# isort: split
# --8<-- [start:example]
DetectorGuardRail(
    Gliner2Detector(
        model="fastino/GLiNER2-Guardrails-PII-Multi",
        labels=["person", "address"],
        threshold=0.5,
    )
)
# --8<-- [end:example]

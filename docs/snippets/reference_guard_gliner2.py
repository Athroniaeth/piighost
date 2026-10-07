from piighost.components.detector.ner import Gliner2PiiDetector
from piighost.components.guard import DetectorGuardRail

# isort: split
# --8<-- [start:example]
DetectorGuardRail(
    Gliner2PiiDetector(
        labels={
            "PERSON": "person",
            "EMAIL": "email address",
            "PHONE": "phone number",
            "ADDRESS": "street address",
            "IBAN": "iban",
            "ID_NUMBER": "social security number",
        },
        threshold=0.9,
    )
)
# --8<-- [end:example]

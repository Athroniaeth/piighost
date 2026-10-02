model = "fastino/gliner2-multi-v1"

# isort: split
# --8<-- [start:example]
from piighost.components.detector.ner import Gliner2Detector

# Query GLiNER2 with "person" and "company" but emit "PERSON" / "COMPANY".
detector = Gliner2Detector(
    model,
    labels={"PERSON": "person", "COMPANY": "company"},
)
# --8<-- [end:example]

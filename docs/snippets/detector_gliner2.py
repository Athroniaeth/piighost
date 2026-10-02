# --8<-- [start:detector]
from piighost.components.detector.ner import Gliner2Detector

detector = Gliner2Detector(
    model="fastino/gliner2-multi-v1",
    labels=["PERSON", "LOCATION"],
    threshold=0.5,
)
# --8<-- [end:detector]

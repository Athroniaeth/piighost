from piighost.components.detector.ner import Gliner2Detector
from piighost.pipeline import ThreadAnonymizationPipeline

detector = Gliner2Detector(
    "fastino/gliner2-multi-v1",
    labels=["PERSON", "LOCATION"],
    threshold=0.5,
)
pipeline = ThreadAnonymizationPipeline(detector)

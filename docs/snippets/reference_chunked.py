from piighost.components.detector import ChunkedDetector
from piighost.components.detector.ner import SpacyDetector

spacy_detector = SpacyDetector(model="en_core_web_sm")
detector = ChunkedDetector(spacy_detector)

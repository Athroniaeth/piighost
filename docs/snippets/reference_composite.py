from piighost.components.detector import CompositeDetector, RegexDetector
from piighost.components.detector.ner import Gliner2Detector

email_detector = RegexDetector({"EMAIL": r"[\w.+-]+@[\w.-]+\.\w{2,}"})
person_detector = Gliner2Detector(model="fastino/gliner2-multi-v1", labels=["PERSON"])
detector = CompositeDetector([email_detector, person_detector])

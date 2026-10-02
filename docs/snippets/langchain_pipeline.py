from piighost.components.anonymizer import Anonymizer
from piighost.components.detector.ner import Gliner2Detector
from piighost.components.linker import ExactEntityLinker
from piighost.components.placeholder import LabelCounterPlaceholderFactory
from piighost.conversation_memory import InMemoryConversationMemory
from piighost.pipeline import ThreadAnonymizationPipeline

detector = Gliner2Detector(
    "fastino/gliner2-multi-v1",
    labels=["PERSON", "LOCATION"],
    threshold=0.5,
)
linker = ExactEntityLinker()
factory = LabelCounterPlaceholderFactory()
anonymizer = Anonymizer(factory)
memory = InMemoryConversationMemory()
pipeline = ThreadAnonymizationPipeline(
    detector,
    linker,
    anonymizer,
    memory,
)

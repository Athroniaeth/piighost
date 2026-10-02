import asyncio

from gliner2 import GLiNER2

from piighost.components.anonymizer import Anonymizer
from piighost.components.detector.ner.gliner2 import Gliner2Detector
from piighost.components.linker import ExactEntityLinker
from piighost.components.placeholder import LabelCounterPlaceholderFactory
from piighost.conversation_memory import InMemoryConversationMemory
from piighost.pipeline import ThreadAnonymizationPipeline

model = GLiNER2.from_pretrained("fastino/gliner2-multi-v1")
detector = Gliner2Detector(model=model, threshold=0.5, labels=["PERSON", "LOCATION"])
factory = LabelCounterPlaceholderFactory()
anonymizer = Anonymizer(factory)
linker = ExactEntityLinker()
memory = InMemoryConversationMemory()

pipeline = ThreadAnonymizationPipeline(
    detector=detector,
    linker=linker,
    anonymizer=anonymizer,
    memory=memory,
)


async def main():
    result = await pipeline.anonymize("Patrick is in Lyon.", thread_id="user-A")
    print(result.text)  # <<PERSON:1>> is in <<LOCATION:1>>.

    original = await pipeline.deanonymize(result.text, thread_id="user-A")
    print(original)  # Patrick is in Lyon.


asyncio.run(main())

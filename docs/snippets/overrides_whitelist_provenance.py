import asyncio

from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import ExactMatchDetector
from piighost.components.linker import ExactEntityLinker
from piighost.components.override import DetectionOverride, WhitelistStrategy
from piighost.components.placeholder import LabelCounterPlaceholderFactory
from piighost.conversation_memory import InMemoryConversationMemory, MessageRole
from piighost.pipeline import ThreadAnonymizationPipeline


def build_pipeline(strategy: WhitelistStrategy) -> ThreadAnonymizationPipeline:
    detector = ExactMatchDetector({})
    whitelist = ExactMatchDetector({"Acme": "ORG"})
    override = DetectionOverride(whitelist=whitelist, whitelist_strategy=strategy)
    linker = ExactEntityLinker()
    factory = LabelCounterPlaceholderFactory()
    anonymizer = Anonymizer(factory)
    memory = InMemoryConversationMemory()
    return ThreadAnonymizationPipeline(
        detector,
        linker,
        anonymizer,
        memory,
        override=override,
    )


async def main():
    for strategy in WhitelistStrategy:
        pipeline = build_pipeline(strategy)
        assistant = await pipeline.anonymize("Acme rocks", "t1", MessageRole.ASSISTANT)
        user = await pipeline.anonymize("I love Acme", "t1")
        print(strategy.value, "->", assistant.text, "|", user.text)


asyncio.run(main())

import asyncio

from piighost.components.detector import ExactMatchDetector
from piighost.components.override import DenyListStrategy, DetectionOverride
from piighost.conversation_memory import MessageRole
from piighost.pipeline import ThreadAnonymizationPipeline


def build_pipeline(strategy: DenyListStrategy) -> ThreadAnonymizationPipeline:
    detector = ExactMatchDetector({})
    deny_list = ExactMatchDetector({"Acme": "ORG"})
    override = DetectionOverride(deny_list=deny_list, deny_list_strategy=strategy)
    return ThreadAnonymizationPipeline(detector, override=override)


async def main():
    for strategy in DenyListStrategy:
        pipeline = build_pipeline(strategy)
        assistant = await pipeline.anonymize("Acme rocks", "t1", MessageRole.ASSISTANT)
        user = await pipeline.anonymize("I love Acme", "t1")
        print(strategy.value, "->", assistant.text, "|", user.text)


asyncio.run(main())

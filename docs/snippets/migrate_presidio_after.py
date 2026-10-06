# Not shown: the model the page names, replaced by a scripted one.
from _offline import offline_langchain

offline_langchain(
    "Thank you {0}, I will write to {1}.",
    secrets=("Patrick Martin", "patrick@example.com"),
)

# isort: split
# --8<-- [start:after]
import asyncio

from langchain.chat_models import init_chat_model
from presidio_analyzer import AnalyzerEngine

from piighost.components.detector.ner import PresidioDetector
from piighost.pipeline import ThreadAnonymizationPipeline

detector = PresidioDetector(
    AnalyzerEngine(), labels={"PERSON": "PERSON", "EMAIL": "EMAIL_ADDRESS"}
)
pipeline = ThreadAnonymizationPipeline(detector)
model = init_chat_model("openai:gpt-5.6-terra")


async def main() -> None:
    safe = await pipeline.anonymize(
        "Patrick Martin wrote from patrick@example.com.", thread_id="thread-42"
    )
    print(safe.text)

    reply = await model.ainvoke(safe.text)
    print(await pipeline.deanonymize(reply.content, thread_id="thread-42"))


asyncio.run(main())
# --8<-- [end:after]

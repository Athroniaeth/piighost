# Not shown: the model the page names, replaced by a scripted one.
from _offline import offline_langchain

offline_langchain("", secrets=())

# isort: split
# --8<-- [start:example]
from piighost.components.detector import LLMDetector

detector = LLMDetector(
    model="gpt-5.6-terra",
    labels=["PERSON", "EMAIL"],
    provider="openai",
)
# --8<-- [end:example]

# /// script
# requires-python = ">=3.11"
# dependencies = ["piighost[langchain]", "langchain-openai"]
#
# [tool.uv.sources]
# piighost = { path = "..", editable = true }
# ///
"""Stream a real model's reply through the middleware, deanonymized token by token.

The middleware anonymizes the prompt, so the model only ever streams placeholder
tokens; deanonymize_stream restores each token on the fly as it completes, holding
back only a token split across chunks. Unlike the offline middleware example, this
needs a real streaming model, so run it with the OpenAI key from examples/.env:

    uv run --env-file examples/.env examples/langchain_streaming.py
"""

import asyncio
from collections.abc import AsyncIterator

from langchain.agents import create_agent
from langchain_core.messages import AIMessageChunk, HumanMessage
from langchain_openai import ChatOpenAI  # pyrefly: ignore[missing-import]

from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import ExactMatchDetector
from piighost.components.linker import ExactEntityLinker
from piighost.components.placeholder import (
    LabelCounterPlaceholderFactory,
    PreservesLabeledIdentityOpaque,
)
from piighost.conversation_memory import InMemoryConversationMemory
from piighost.integrations.langchain import PIIAnonymizationMiddleware
from piighost.pipeline import ThreadAnonymizationPipeline

SYSTEM = (
    "Placeholder tokens like <<PERSON:1>> stand for real names. Always reuse the "
    "exact token verbatim wherever you refer to that person; never invent a name."
)


def _build_pipeline() -> ThreadAnonymizationPipeline[PreservesLabeledIdentityOpaque]:
    """A thread pipeline over a counter factory, whose tokens preserve identity."""
    detector = ExactMatchDetector({"Emma": "PERSON"})
    linker = ExactEntityLinker()
    factory = LabelCounterPlaceholderFactory()
    anonymizer = Anonymizer(factory)
    memory = InMemoryConversationMemory()
    return ThreadAnonymizationPipeline(detector, linker, anonymizer, memory)


async def main() -> None:
    """Stream one real reply and restore its placeholder tokens as they arrive."""
    pipeline = _build_pipeline()
    middleware = PIIAnonymizationMiddleware(pipeline)
    model = ChatOpenAI(model="gpt-5.6-terra", temperature=0)
    agent = create_agent(model=model, system_prompt=SYSTEM, middleware=[middleware])

    thread_id = "stream-1"
    config = {"configurable": {"thread_id": thread_id}}
    request = {
        "messages": [
            HumanMessage(
                "My name is Emma. Write a warm two-sentence welcome addressed to me "
                "by name, and use my name twice."
            )
        ]
    }

    raw: list[str] = []

    async def model_text() -> AsyncIterator[str]:
        """Yield the model's streamed text chunks, recording each raw one."""
        async for chunk, _meta in agent.astream(
            request, config, stream_mode="messages"
        ):
            if isinstance(chunk, AIMessageChunk) and isinstance(chunk.content, str):
                if chunk.content:
                    raw.append(chunk.content)
                    yield chunk.content

    print("restored, streamed token by token:\n")
    async for piece in middleware.deanonymize_stream(model_text(), thread_id):
        print(piece, end="", flush=True)
    print("\n")

    joined = "".join(raw)
    print("what the model actually streamed (anonymized):")
    print(f"  {joined!r}")
    token_seen = "<<PERSON:1>>" in joined
    split = any(chunk.count("<<") != chunk.count(">>") for chunk in raw)
    print(
        f"\nchunks: {len(raw)}   token in stream: {token_seen}   split across chunks: {split}"
    )


if __name__ == "__main__":
    asyncio.run(main())

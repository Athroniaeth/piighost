# /// script
# requires-python = ">=3.11"
# dependencies = ["piighost", "langchain-openai>=0.3", "numpy>=1.26", "python-dotenv>=1.0"]
#
# [tool.uv.sources]
# piighost = { path = "../..", editable = true }
# ///
"""Retrieval-augmented generation where OpenAI never sees the PII.

A minimalist RAG over a tiny in-memory corpus, showing how to keep PII out of
both the embedding and the generation calls with a piighost pipeline. Every
document is anonymized into one corpus thread before it is embedded, so a value
keeps the same token across the whole corpus. The query is anonymized into the
same thread, so its tokens match the corpus and retrieval still works. The model
answers over anonymized context, and the reply is deanonymized for the user, so
OpenAI only ever handled tokens like <<PERSON:1>>, never Patrick or Paris.

The anonymization uses the piighost pipeline directly, not the middleware, since
the RAG flow is orchestrated by hand. A tiny curated corpus keeps retrieval on
anonymized text good enough for a demo; on a real corpus, embedding anonymized
text trades some retrieval quality for privacy, and a durable thread backed by
SqlAlchemyConversationMemory would replace the in-memory pipeline.

It runs against openai:gpt-5.6-terra and OpenAI embeddings, so set an OPENAI_API_KEY in
the environment (copy .env.example to .env). Run with:
uv run examples/langchain/rag.py
"""

import asyncio

from dotenv import load_dotenv
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import ChatOpenAI, OpenAIEmbeddings  # pyrefly: ignore[missing-import]

from piighost.components.detector import ExactMatchDetector
from piighost.pipeline import ThreadAnonymizationPipeline

THREAD = "docs"

CORPUS = [
    "Patrick manages the Lyon office and lives in Paris.",
    "Marie is the contact for the Berlin branch.",
    "The Paris office handles European support.",
]


async def main() -> None:
    """Index an anonymized corpus, answer a query, and restore the reply."""
    load_dotenv()
    labels = {
        "Patrick": "PERSON",
        "Marie": "PERSON",
        "Paris": "LOCATION",
        "Lyon": "LOCATION",
        "Berlin": "LOCATION",
    }
    detector = ExactMatchDetector(labels)
    pipeline = ThreadAnonymizationPipeline(detector)

    # Ingest: anonymize each document into the corpus thread, then embed the
    # anonymized text, so a value keeps one token across the corpus and no PII
    # ever reaches the embedding provider.
    chunks = []
    for document in CORPUS:
        anonymized = await pipeline.anonymize(document, THREAD)
        chunks.append(anonymized.text)

    embeddings = OpenAIEmbeddings(model="text-embedding-3-small")
    store = InMemoryVectorStore(embeddings)
    await store.aadd_texts(chunks)

    # Query: anonymized into the same thread, so its tokens match the corpus.
    question = "Where does Patrick live?"
    anonymized_question = (await pipeline.anonymize(question, THREAD)).text

    matches = await store.asimilarity_search(anonymized_question, k=2)
    context = "\n".join(match.page_content for match in matches)

    # Generate over anonymized context; the model only ever sees tokens.
    prompt = (
        "Answer the question using only the context.\n\n"
        f"Context:\n{context}\n\nQuestion: {anonymized_question}"
    )
    llm = ChatOpenAI(model="gpt-5.6-terra")
    reply = await llm.ainvoke(prompt)
    model_answer = str(reply.content)

    answer = await pipeline.deanonymize(model_answer, THREAD)

    print("== what OpenAI saw (anonymized) ==")
    print(f"  context : {context.replace(chr(10), ' | ')}")
    print(f"  question: {anonymized_question}")
    print(f"  reply   : {model_answer!r}")
    print("\n== what the user sees (restored) ==")
    print(f"  {answer!r}")


if __name__ == "__main__":
    asyncio.run(main())

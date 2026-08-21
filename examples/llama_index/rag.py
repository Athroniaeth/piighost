# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "piighost[llama-index]",
#     "llama-index-embeddings-openai>=0.3",
#     "llama-index-llms-openai>=0.3",
#     "python-dotenv>=1.0",
# ]
#
# [tool.uv.sources]
# piighost = { path = "../..", editable = true }
# ///
"""Retrieval-augmented generation in LlamaIndex where OpenAI never sees the PII.

A minimalist RAG over a tiny corpus, showing the two piighost LlamaIndex
components. PIINodeAnonymizer anonymizes each document into one corpus thread
before it is embedded, so the embedding provider only ever sees tokens.
PIIQueryEngine anonymizes the query into the same thread, so its tokens match the
corpus and retrieval works, then deanonymizes the answer for the user. OpenAI only
ever handled tokens like <<PERSON:1>>, never Patrick or Paris.

An ExactMatchDetector keeps the demo deterministic. It runs against OpenAI
embeddings and gpt-5.5, so set an OPENAI_API_KEY in the environment (copy
.env.example to .env). Run with:
uv run examples/llama_index/rag.py
"""

from dotenv import load_dotenv
from llama_index.core import Document, Settings, VectorStoreIndex
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.openai import OpenAIEmbedding  # pyrefly: ignore[missing-import]
from llama_index.llms.openai import OpenAI  # pyrefly: ignore[missing-import]

from piighost.components.detector import ExactMatchDetector
from piighost.integrations.llama_index import PIINodeAnonymizer, PIIQueryEngine
from piighost.pipeline import ThreadAnonymizationPipeline

THREAD = "docs"

CORPUS = [
    "Patrick manages the Lyon office and lives in Paris.",
    "Marie is the contact for the Berlin branch.",
    "The Paris office handles European support.",
]


def main() -> None:
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

    Settings.embed_model = OpenAIEmbedding(model="text-embedding-3-small")
    Settings.llm = OpenAI(model="gpt-5.5")

    # Ingest: the anonymizer runs before embedding, so the embedding provider
    # only ever sees tokens, and a value keeps one token across the corpus.
    anonymizer = PIINodeAnonymizer(pipeline=pipeline, thread_id=THREAD)
    documents = [Document(text=text) for text in CORPUS]
    index = VectorStoreIndex.from_documents(
        documents,
        transformations=[SentenceSplitter(), anonymizer],
    )

    # Query: the wrapper anonymizes the question into the same thread, so its
    # tokens match the corpus, and restores the answer for the user.
    engine = PIIQueryEngine(
        inner=index.as_query_engine(),
        pipeline=pipeline,
        thread_id=THREAD,
    )
    answer = engine.query("Where does Patrick live?")

    print("== what the user sees (restored) ==")
    print(f"  {answer.response!r}")


if __name__ == "__main__":
    main()

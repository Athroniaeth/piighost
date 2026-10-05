# Not shown: the OpenAI models the page names, replaced by offline ones.
from _offline import offline_llama_index

offline_llama_index(secrets=("Patrick", "Paris"))

# isort: split
# --8<-- [start:pipeline]
from piighost.components.detector import ExactMatchDetector
from piighost.pipeline import ThreadAnonymizationPipeline

THREAD = "docs"
detector = ExactMatchDetector({"Patrick": "PERSON", "Paris": "LOCATION"})
pipeline = ThreadAnonymizationPipeline(detector)
# --8<-- [end:pipeline]


# isort: split
# --8<-- [start:ingest]
from llama_index.core import Document, Settings, VectorStoreIndex
from llama_index.core.node_parser import SentenceSplitter
from llama_index.embeddings.openai import OpenAIEmbedding

from piighost.integrations.llama_index import PIINodeAnonymizer

Settings.embed_model = OpenAIEmbedding(model="text-embedding-3-small")
anonymizer = PIINodeAnonymizer(pipeline=pipeline, thread_id=THREAD)
index = VectorStoreIndex.from_documents(
    [Document(text="Patrick lives in Paris.")],
    transformations=[SentenceSplitter(), anonymizer],
)
# --8<-- [end:ingest]


# isort: split
# --8<-- [start:query]
from llama_index.llms.openai import OpenAI

from piighost.integrations.llama_index import PIIQueryEngine

Settings.llm = OpenAI(model="gpt-5.6-terra")
engine = PIIQueryEngine(
    inner=index.as_query_engine(),
    pipeline=pipeline,
    thread_id=THREAD,
)
answer = engine.query("Where does Patrick live?")
print(answer.response)
# --8<-- [end:query]

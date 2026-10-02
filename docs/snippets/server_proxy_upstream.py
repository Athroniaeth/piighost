from openai import OpenAI

# isort: split
# --8<-- [start:example]
client = OpenAI(
    base_url="http://127.0.0.1:8000/openai/v1",
    api_key="sk-...",
    default_headers={"X-PIIGhost-Upstream": "http://vllm.internal:8000/v1"},
)
# --8<-- [end:example]

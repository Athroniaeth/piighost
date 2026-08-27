# Examples

Standalone [PEP 723](https://peps.python.org/pep-0723/) scripts, each with its own
inline dependencies. Run any of them with `uv`, which resolves the dependencies on
the fly:

```bash
uv run examples/anonymize_basic.py
```

The agent and API examples read secrets (an OpenAI key, ...) from a `.env` file.
Copy `examples/.env.example` to `examples/.env` and fill it in first.

## Core pipeline

| Script | What it shows |
|--------|---------------|
| [`anonymize_basic.py`](anonymize_basic.py) | Anonymize a text and restore it with the base pipeline. |
| [`thread_conversation.py`](thread_conversation.py) | Anonymize a whole conversation with the thread-aware pipeline. |
| [`guard_rail.py`](guard_rail.py) | Catch residual PII with a deterministic guard rail. |
| [`placeholder_styles.py`](placeholder_styles.py) | Compare placeholder styles on one text. |

## LangChain

| Script | What it shows |
|--------|---------------|
| [`langchain_middleware.py`](langchain_middleware.py) | Run a LangChain agent behind the PII anonymization middleware. |
| [`langchain_streaming.py`](langchain_streaming.py) | Stream a real model's reply through the middleware, deanonymized token by token. |
| [`langchain/base.py`](langchain/base.py) | The middleware on a minimal agent. |
| [`langchain/tools.py`](langchain/tools.py) | A LangGraph agent whose tool receives the real value, not the token. |
| [`langchain/rag.py`](langchain/rag.py) | Retrieval-augmented generation where the model never sees the PII. |

## Strategies

| Script | What it shows |
|--------|---------------|
| [`strategies/tool_call.py`](strategies/tool_call.py) | Contrast the four tool-call strategies of the middleware. |
| [`strategies/invented_placeholder.py`](strategies/invented_placeholder.py) | Handle placeholder tokens the model invents, under each strategy. |
| [`strategies/assistant_entity.py`](strategies/assistant_entity.py) | Preserve entities the assistant introduces, under each strategy. |

## Other integrations

| Script | What it shows |
|--------|---------------|
| [`pydantic_ai/base.py`](pydantic_ai/base.py) | Run a Pydantic AI agent behind the PII de-identification capability. |
| [`pydantic_ai/tools.py`](pydantic_ai/tools.py) | A Pydantic AI agent whose tool receives the real value, not the token. |
| [`llama_index/rag.py`](llama_index/rag.py) | Retrieval-augmented generation in LlamaIndex where the model never sees the PII. |
| [`transformers/privacy_filter.py`](transformers/privacy_filter.py) | Detect and anonymize PII locally with a Transformers model. |

## Configuration and observation

| Script | What it shows |
|--------|---------------|
| [`config/run.py`](config/run.py) | Load every example piighost configuration and exercise each one. |
| [`observation/langfuse_tracing.py`](observation/langfuse_tracing.py) | Trace the pipeline with OpenTelemetry, rendered in Langfuse or the console. |

The `config/` directory also holds the sample TOML/JSON files (`minimal.toml`,
`pipeline.toml`, `thread_redis.toml`, `minimal.json`) those scripts load.

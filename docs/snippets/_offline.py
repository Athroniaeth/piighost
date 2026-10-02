"""Offline stand-ins for the models the pages name, imported by their tests only.

A page shows the code a reader runs against a real provider. Its file swaps the
provider for a scripted model, in lines the page does not include, before the
code the page shows. The model answers from the tokens it receives, and fails
when a value it should never see reaches it: the example checks the
de-identification, not the model.
"""

import importlib
import json
import re
import sys
import types
from collections.abc import Iterator
from typing import Any

TOKEN = re.compile(r"<<[A-Z_]+:\d+>>")
"""A placeholder of LabelCounterPlaceholderFactory, the one the pages use."""

STREAM_PIECE = 4
"""Characters per streamed chunk, fewer than a token, so every token is cut."""


def _check(text: str, secrets: tuple[str, ...]) -> None:
    leaked = [secret for secret in secrets if secret in text]
    if leaked:
        raise AssertionError(f"the model received {leaked} in clear")


def offline_langchain(reply: str, secrets: tuple[str, ...]) -> None:
    """Make a model name given to LangChain build a scripted chat model.

    Its first turn calls the agent's first tool with the token of the question,
    its second answers `reply` filled with the tokens of the question and of the
    tool result, in order.
    """
    import langchain.chat_models
    from langchain.agents import factory
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.messages import (
        AIMessage,
        AIMessageChunk,
        HumanMessage,
        ToolMessage,
    )
    from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
    from langchain_core.tools import BaseTool

    class ScriptedChatModel(BaseChatModel):
        tool: str = ""
        argument: str = ""

        @property
        def _llm_type(self) -> str:
            return "scripted"

        def bind_tools(self, tools: Any, **kwargs: Any) -> "ScriptedChatModel":
            first = tools[0]
            # A structured output binds a schema, not a tool: nothing to call.
            if not isinstance(first, BaseTool):
                return self
            return self.model_copy(
                update={"tool": first.name, "argument": next(iter(first.args))}
            )

        def _reply(self, messages: Any) -> AIMessage:
            _check(" ".join(repr(message) for message in messages), secrets)
            question = next(
                message for message in messages if isinstance(message, HumanMessage)
            )
            tokens = TOKEN.findall(str(question.content))
            results = [
                message for message in messages if isinstance(message, ToolMessage)
            ]
            # With a tool result, or no tool to call, the turn answers.
            if results or not self.tool:
                tokens += TOKEN.findall(str(results[-1].content)) if results else []
                return AIMessage(content=reply.format(*tokens))
            call = {
                "name": self.tool,
                "args": {self.argument: tokens[0]},
                "id": "call-1",
                "type": "tool_call",
            }
            return AIMessage(content="", tool_calls=[call])

        def _generate(
            self,
            messages: Any,
            stop: Any = None,
            run_manager: Any = None,
            **kwargs: Any,
        ) -> ChatResult:
            message = self._reply(messages)
            return ChatResult(generations=[ChatGeneration(message=message)])

        def _stream(
            self,
            messages: Any,
            stop: Any = None,
            run_manager: Any = None,
            **kwargs: Any,
        ) -> Iterator[ChatGenerationChunk]:
            """Stream the reply in pieces of a few characters, cutting its tokens."""
            message = self._reply(messages)
            if message.tool_calls:
                call = message.tool_calls[0]
                piece = {**call, "args": json.dumps(call["args"]), "index": 0}
                chunk = AIMessageChunk(content="", tool_call_chunks=[piece])
                yield ChatGenerationChunk(message=chunk)
                return
            text = str(message.content)
            for start in range(0, len(text), STREAM_PIECE):
                chunk = AIMessageChunk(content=text[start : start + STREAM_PIECE])
                yield ChatGenerationChunk(message=chunk)

    # create_agent holds its own reference, the detectors import it when called.
    factory.init_chat_model = lambda model, **kwargs: ScriptedChatModel()
    langchain.chat_models.init_chat_model = factory.init_chat_model


def offline_pydantic_ai(reply: str, secrets: tuple[str, ...]) -> None:
    """Make `Agent("provider:name")` run a scripted model.

    It answers `reply` filled with the tokens of the user prompts, in order.
    """
    from pydantic_ai import models
    from pydantic_ai.messages import ModelResponse, TextPart, UserPromptPart
    from pydantic_ai.models.function import FunctionModel

    def answer(messages: Any, info: Any) -> ModelResponse:
        _check(repr(messages), secrets)
        prompts = [
            part.content
            for message in messages
            for part in message.parts
            if isinstance(part, UserPromptPart)
        ]
        tokens = TOKEN.findall(" ".join(map(str, prompts)))
        return ModelResponse(parts=[TextPart(reply.format(*tokens))])

    models.infer_model = lambda model, *args, **kwargs: FunctionModel(answer)


def _module(name: str, **attributes: Any) -> None:
    parent = name.rpartition(".")[0]
    try:
        importlib.import_module(parent)
    except ModuleNotFoundError:
        sys.modules[parent] = types.ModuleType(parent)
    module = types.ModuleType(name)
    vars(module).update(attributes)
    sys.modules[name] = module


def offline_llama_index(secrets: tuple[str, ...]) -> None:
    """Make `llama_index.embeddings.openai` and `llama_index.llms.openai` offline.

    The embedding model fails on a clear value, so it checks what ingestion
    sends. The LLM answers with the context line that holds the query's token.
    """
    from llama_index.core.embeddings import MockEmbedding
    from llama_index.core.llms import CompletionResponse, CustomLLM, LLMMetadata

    class OpenAIEmbedding(MockEmbedding):
        def __init__(self, model: str = "", **kwargs: Any) -> None:
            super().__init__(embed_dim=8)

        def _get_text_embedding(self, text: str) -> list[float]:
            _check(text, secrets)
            return super()._get_text_embedding(text)

        def _get_query_embedding(self, query: str) -> list[float]:
            _check(query, secrets)
            return super()._get_query_embedding(query)

    class OpenAI(CustomLLM):
        def __init__(self, model: str = "", **kwargs: Any) -> None:
            super().__init__()

        @property
        def metadata(self) -> LLMMetadata:
            return LLMMetadata()

        def complete(
            self, prompt: str, formatted: bool = False, **kwargs: Any
        ) -> CompletionResponse:
            _check(prompt, secrets)
            query = next(
                line for line in prompt.splitlines() if line.startswith("Query:")
            )
            token = TOKEN.search(query).group()
            context = next(
                line for line in prompt.splitlines() if token in line and line != query
            )
            return CompletionResponse(text=context)

        def stream_complete(
            self, prompt: str, formatted: bool = False, **kwargs: Any
        ) -> Any:
            raise NotImplementedError

    _module("llama_index.embeddings.openai", OpenAIEmbedding=OpenAIEmbedding)
    _module("llama_index.llms.openai", OpenAI=OpenAI)

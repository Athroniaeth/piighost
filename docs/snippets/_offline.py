"""Offline stand-ins for the models the pages name, imported by their tests only.

A page shows the code a reader runs against a real provider. Its file swaps the
provider for a scripted model, in lines the page does not include, before the
code the page shows. The model answers from the tokens it receives, and fails
when a value it should never see reaches it: the example checks the
de-identification, not the model.
"""

import importlib
import re
import sys
import types
from typing import Any

TOKEN = re.compile(r"<<[A-Z_]+:\d+>>")
"""A placeholder of LabelCounterPlaceholderFactory, the one the pages use."""


def _check(text: str, secrets: tuple[str, ...]) -> None:
    leaked = [secret for secret in secrets if secret in text]
    if leaked:
        raise AssertionError(f"the model received {leaked} in clear")


def offline_langchain(reply: str, secrets: tuple[str, ...]) -> None:
    """Make `create_agent(model="provider:name")` build a scripted chat model.

    Its first turn calls the agent's first tool with the token of the question,
    its second answers `reply` filled with the tokens of the question and of the
    tool result, in order.
    """
    from langchain.agents import factory
    from langchain_core.language_models.chat_models import BaseChatModel
    from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
    from langchain_core.outputs import ChatGeneration, ChatResult

    class ScriptedChatModel(BaseChatModel):
        tool: str = ""
        argument: str = ""

        @property
        def _llm_type(self) -> str:
            return "scripted"

        def bind_tools(self, tools: Any, **kwargs: Any) -> "ScriptedChatModel":
            first = tools[0]
            return self.model_copy(
                update={"tool": first.name, "argument": next(iter(first.args))}
            )

        def _generate(
            self,
            messages: Any,
            stop: Any = None,
            run_manager: Any = None,
            **kwargs: Any,
        ) -> ChatResult:
            _check(" ".join(repr(message) for message in messages), secrets)
            question = next(
                message for message in messages if isinstance(message, HumanMessage)
            )
            tokens = TOKEN.findall(str(question.content))
            results = [
                message for message in messages if isinstance(message, ToolMessage)
            ]
            if results:
                tokens += TOKEN.findall(str(results[-1].content))
                message = AIMessage(content=reply.format(*tokens))
            else:
                call = {
                    "name": self.tool,
                    "args": {self.argument: tokens[0]},
                    "id": "call-1",
                    "type": "tool_call",
                }
                message = AIMessage(content="", tool_calls=[call])
            return ChatResult(generations=[ChatGeneration(message=message)])

    factory.init_chat_model = lambda model, **kwargs: ScriptedChatModel()


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

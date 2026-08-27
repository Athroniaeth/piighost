"""Tests for the LangChain PII anonymization middleware."""

import importlib
import importlib.util
import sys
from typing import Any, cast

import pytest

from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import ExactMatchDetector
from piighost.components.linker import ExactEntityLinker
from piighost.components.placeholder import (
    LabelCounterPlaceholderFactory,
    PreservesRecognizableIdentity,
)
from piighost.conversation_memory import InMemoryConversationMemory, MessageRole
from piighost.exceptions import InventedPlaceholderError, UnrecognizableFactoryError
from piighost.integrations.langchain import (
    EntityCreateByAssistantStrategy,
    InventedPlaceholderStrategy,
    ToolCallStrategy,
)
from piighost.integrations.langchain.middleware import PIIAnonymizationMiddleware
from piighost.pipeline import AnyThreadPipeline, ThreadAnonymizationPipeline

_MODULE = "piighost.integrations.langchain.middleware"


def _pipeline() -> ThreadAnonymizationPipeline:
    """Build a thread pipeline whose counter tokens preserve identity."""
    return ThreadAnonymizationPipeline(
        ExactMatchDetector({"Emma": "PERSON", "Liam": "PERSON"}),
        ExactEntityLinker(),
        Anonymizer(LabelCounterPlaceholderFactory()),
        InMemoryConversationMemory(),
    )


def _text(message: Any) -> str:
    """Return a message's text content as a plain string."""
    content = message.content
    return content if isinstance(content, str) else str(content)


class TestOptionalDependencyGuard:
    def test_missing_langchain_explains_how_to_install(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Importing without langchain points the user at piighost[middleware]."""
        real_find_spec = importlib.util.find_spec

        def find_spec(name: str, *args: Any, **kwargs: Any) -> object:
            if name == "langchain":
                return None
            return real_find_spec(name, *args, **kwargs)

        monkeypatch.setattr(importlib.util, "find_spec", find_spec)
        sys.modules.pop(_MODULE, None)

        with pytest.raises(ImportError, match=r"piighost\[middleware\]"):
            importlib.import_module(_MODULE)

        sys.modules.pop(_MODULE, None)


class TestWhenInstalled:
    def _middleware(self, monkeypatch: pytest.MonkeyPatch) -> Any:
        """Build the middleware with a stubbed thread-id config."""
        module = importlib.import_module(_MODULE)
        monkeypatch.setattr(
            module, "get_config", lambda: {"configurable": {"thread_id": "t1"}}
        )
        return module.PIIAnonymizationMiddleware(_pipeline())

    async def test_before_model_anonymizes_messages(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The user message is anonymized before the model sees it."""
        pytest.importorskip("langchain")
        from langchain_core.messages import HumanMessage

        middleware = self._middleware(monkeypatch)
        state = {"messages": [HumanMessage("Hi Emma")]}
        update = await middleware.abefore_model(state, None)
        assert update["messages"][0].content == "Hi <<PERSON:1>>"

    async def test_after_model_deanonymizes_for_display(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A model reply carrying thread tokens is restored for the user."""
        pytest.importorskip("langchain")
        from langchain_core.messages import AIMessage, HumanMessage

        middleware = self._middleware(monkeypatch)
        await middleware.abefore_model({"messages": [HumanMessage("Hi Emma")]}, None)

        reply = {"messages": [AIMessage("Hello <<PERSON:1>>")]}
        await middleware.aafter_model(reply, None)
        assert reply["messages"][0].content == "Hello Emma"

    async def test_no_pii_leaves_messages_untouched(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A message with nothing to anonymize yields no update."""
        pytest.importorskip("langchain")
        from langchain_core.messages import HumanMessage

        middleware = self._middleware(monkeypatch)
        update = await middleware.abefore_model(
            {"messages": [HumanMessage("nothing here")]}, None
        )
        assert update is None


class _FakeRequest:
    """A minimal stand-in for a langgraph ToolCallRequest."""

    def __init__(self, args: dict[str, str]) -> None:
        self.tool_call = {"name": "t", "args": args, "id": "c1", "type": "tool_call"}


class TestToolCalls:
    async def _run(
        self, monkeypatch: pytest.MonkeyPatch, strategy: ToolCallStrategy
    ) -> tuple[dict[str, str], Any]:
        """Run one tool call under a strategy, over a thread that knows Emma.

        Returns the arguments the tool actually received and the response content.
        """
        pytest.importorskip("langchain")
        from langchain_core.messages import HumanMessage, ToolMessage

        module = importlib.import_module(_MODULE)
        monkeypatch.setattr(
            module, "get_config", lambda: {"configurable": {"thread_id": "t1"}}
        )
        middleware = module.PIIAnonymizationMiddleware(
            _pipeline(), tool_strategy=strategy
        )
        await middleware.abefore_model({"messages": [HumanMessage("Hi Emma")]}, None)

        received: dict[str, dict[str, str]] = {}

        async def handler(request: Any) -> object:
            received["args"] = request.tool_call["args"]
            return ToolMessage(content="Contact Emma", tool_call_id="c1")

        request = _FakeRequest({"name": "<<PERSON:1>>"})
        response = await middleware.awrap_tool_call(request, handler)
        return received["args"], response.content

    @pytest.mark.parametrize(
        ("strategy", "arg_seen", "response_out"),
        [
            (ToolCallStrategy.FULL, "Emma", "Contact <<PERSON:1>>"),
            (ToolCallStrategy.INPUT, "Emma", "Contact Emma"),
            (ToolCallStrategy.OUTPUT, "<<PERSON:1>>", "Contact <<PERSON:1>>"),
            (ToolCallStrategy.PASSTHROUGH, "<<PERSON:1>>", "Contact Emma"),
        ],
    )
    async def test_strategy_routes_each_direction(
        self,
        monkeypatch: pytest.MonkeyPatch,
        strategy: ToolCallStrategy,
        arg_seen: str,
        response_out: str,
    ) -> None:
        """Each strategy deanonymizes the args and anonymizes the result or not."""
        args, content = await self._run(monkeypatch, strategy)
        assert args["name"] == arg_seen
        assert content == response_out

    async def test_before_model_never_rewrites_a_tool_message(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The before-model pass leaves a tool message raw, even under INPUT."""
        pytest.importorskip("langchain")
        from langchain_core.messages import HumanMessage, ToolMessage

        module = importlib.import_module(_MODULE)
        monkeypatch.setattr(
            module, "get_config", lambda: {"configurable": {"thread_id": "t1"}}
        )
        middleware = module.PIIAnonymizationMiddleware(
            _pipeline(), tool_strategy=ToolCallStrategy.INPUT
        )
        await middleware.abefore_model({"messages": [HumanMessage("Hi Emma")]}, None)

        state = {"messages": [ToolMessage(content="Contact Emma", tool_call_id="c1")]}
        update = await middleware.abefore_model(state, None)
        assert update is None
        assert state["messages"][0].content == "Contact Emma"


class TestInventedPlaceholders:
    def _middleware(
        self, monkeypatch: pytest.MonkeyPatch, strategy: InventedPlaceholderStrategy
    ) -> Any:
        """Build the middleware under an invented-placeholder strategy."""
        module = importlib.import_module(_MODULE)
        monkeypatch.setattr(
            module, "get_config", lambda: {"configurable": {"thread_id": "t1"}}
        )
        return module.PIIAnonymizationMiddleware(
            _pipeline(), invented_strategy=strategy
        )

    async def _reply(self, middleware: Any, text: str) -> str:
        """Anonymize a first message, then run a model reply through aafter_model."""
        from langchain_core.messages import AIMessage, HumanMessage

        await middleware.abefore_model({"messages": [HumanMessage("Hi Emma")]}, None)
        reply = {"messages": [AIMessage(text)]}
        await middleware.aafter_model(reply, None)
        return _text(reply["messages"][0])

    @pytest.mark.parametrize(
        ("strategy", "expected"),
        [
            (InventedPlaceholderStrategy.KEEP, "Hi Emma, cc <<PERSON:9>>"),
            (InventedPlaceholderStrategy.DROP, "Hi Emma, cc "),
        ],
    )
    async def test_kept_or_dropped(
        self,
        monkeypatch: pytest.MonkeyPatch,
        strategy: InventedPlaceholderStrategy,
        expected: str,
    ) -> None:
        """KEEP leaves an invented token in the reply, DROP strips it out."""
        pytest.importorskip("langchain")
        middleware = self._middleware(monkeypatch, strategy)
        content = await self._reply(middleware, "Hi <<PERSON:1>>, cc <<PERSON:9>>")
        assert content == expected

    async def test_raise_refuses_an_invented_token(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """RAISE refuses a reply carrying a token the pipeline never issued."""
        pytest.importorskip("langchain")
        middleware = self._middleware(monkeypatch, InventedPlaceholderStrategy.RAISE)
        with pytest.raises(InventedPlaceholderError, match=r"<<PERSON:9>>"):
            await self._reply(middleware, "Hi <<PERSON:1>>, cc <<PERSON:9>>")

    async def test_only_issued_tokens_pass_under_raise(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A reply carrying only issued tokens restores cleanly under RAISE."""
        pytest.importorskip("langchain")
        middleware = self._middleware(monkeypatch, InventedPlaceholderStrategy.RAISE)
        content = await self._reply(middleware, "Hi <<PERSON:1>>")
        assert content == "Hi Emma"

    async def test_invented_tool_argument_is_refused(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An invented token in a deanonymized tool argument is refused too."""
        pytest.importorskip("langchain")
        from langchain_core.messages import HumanMessage, ToolMessage

        module = importlib.import_module(_MODULE)
        monkeypatch.setattr(
            module, "get_config", lambda: {"configurable": {"thread_id": "t1"}}
        )
        middleware = module.PIIAnonymizationMiddleware(
            _pipeline(), invented_strategy=InventedPlaceholderStrategy.RAISE
        )
        await middleware.abefore_model({"messages": [HumanMessage("Hi Emma")]}, None)

        async def handler(request: Any) -> object:
            return ToolMessage(content="ok", tool_call_id="c1")

        request = _FakeRequest({"name": "<<PERSON:9>>"})
        with pytest.raises(InventedPlaceholderError):
            await middleware.awrap_tool_call(request, handler)


class TestAssistantProvenance:
    def _middleware(
        self, monkeypatch: pytest.MonkeyPatch, strategy: EntityCreateByAssistantStrategy
    ) -> Any:
        """Build the middleware under an assistant-entity strategy."""
        module = importlib.import_module(_MODULE)
        monkeypatch.setattr(
            module, "get_config", lambda: {"configurable": {"thread_id": "t1"}}
        )
        return module.PIIAnonymizationMiddleware(
            _pipeline(), assistant_strategy=strategy
        )

    async def _assistant_then_user(self, middleware: Any) -> str:
        """Let the assistant introduce Emma, then anonymize a user reference."""
        from langchain_core.messages import AIMessage, HumanMessage

        await middleware.abefore_model({"messages": [AIMessage("It is Emma")]}, None)
        state = {"messages": [HumanMessage("what about Emma")]}
        await middleware.abefore_model(state, None)
        return _text(state["messages"][0])

    async def test_preserve_keeps_assistant_value_clear(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Under PRESERVE, a user reference to an assistant value stays in clear."""
        pytest.importorskip("langchain")
        middleware = self._middleware(
            monkeypatch, EntityCreateByAssistantStrategy.PRESERVE
        )
        assert await self._assistant_then_user(middleware) == "what about Emma"

    async def test_anonymize_treats_assistant_value_as_pii(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Under ANONYMIZE, an assistant-introduced value is anonymized."""
        pytest.importorskip("langchain")
        middleware = self._middleware(
            monkeypatch, EntityCreateByAssistantStrategy.ANONYMIZE
        )
        assert await self._assistant_then_user(middleware) == "what about <<PERSON:1>>"

    async def test_ignore_does_not_analyze_assistant_messages(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Under IGNORE, an assistant message is left untouched."""
        pytest.importorskip("langchain")
        from langchain_core.messages import AIMessage

        middleware = self._middleware(
            monkeypatch, EntityCreateByAssistantStrategy.IGNORE
        )
        update = await middleware.abefore_model(
            {"messages": [AIMessage("It is Emma")]}, None
        )
        assert update is None


class TestFactoryContract:
    async def test_a_non_delimited_factory_is_refused(self) -> None:
        """Building the middleware on a non-delimited factory fails fast."""
        pytest.importorskip("langchain")
        from piighost.components.placeholder import MaskPlaceholderFactory

        module = importlib.import_module(_MODULE)
        pipeline = ThreadAnonymizationPipeline(
            ExactMatchDetector({"Emma": "PERSON"}),
            ExactEntityLinker(),
            Anonymizer(MaskPlaceholderFactory()),
            InMemoryConversationMemory(),
        )
        with pytest.raises(UnrecognizableFactoryError, match="delimited"):
            module.PIIAnonymizationMiddleware(pipeline)

    def test_reads_the_recognizer_from_the_pipeline(self) -> None:
        """The middleware takes its recognizer from the pipeline's property."""

        class _Remoteish:
            """A minimal pipeline exposing only what the middleware reads."""

            recognizer = LabelCounterPlaceholderFactory()

            async def anonymize(
                self, text: object, thread_id: object, role: object = MessageRole.USER
            ) -> object:
                return None

            async def anonymize_corrected(
                self, text: object, thread_id: object, detections: object
            ) -> object:
                return None

            async def deanonymize(self, text: object, thread_id: object) -> object:
                return text

            async def forget_thread(self, thread_id: object) -> object:
                return None

        middleware = PIIAnonymizationMiddleware(
            cast(AnyThreadPipeline[PreservesRecognizableIdentity], _Remoteish())
        )
        assert middleware._deid._recognizer is _Remoteish.recognizer

    def test_a_pipeline_without_a_recognizer_is_refused(self) -> None:
        """A pipeline whose recognizer is None fails fast at construction."""

        class _Unrecognizable:
            """A pipeline that emits no recognizable token grammar."""

            recognizer = None

        with pytest.raises(UnrecognizableFactoryError, match="recognizable"):
            PIIAnonymizationMiddleware(
                cast(
                    AnyThreadPipeline[PreservesRecognizableIdentity], _Unrecognizable()
                )
            )

"""Tests for the LangChain PII anonymization middleware."""

import importlib
import importlib.util
import sys

import pytest

from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import ExactMatchDetector
from piighost.components.linker import ExactEntityLinker
from piighost.components.placeholder import LabelCounterPlaceholderFactory
from piighost.conversation_memory import InMemoryConversationMemory
from piighost.pipeline import ThreadAnonymizationPipeline

_MODULE = "piighost.integrations.middleware.langchain"


def _pipeline() -> ThreadAnonymizationPipeline:
    """Build a thread pipeline whose counter tokens preserve identity."""
    return ThreadAnonymizationPipeline(
        ExactMatchDetector({"Emma": "PERSON", "Liam": "PERSON"}),
        ExactEntityLinker(),
        Anonymizer(LabelCounterPlaceholderFactory()),
        InMemoryConversationMemory(),
    )


class TestOptionalDependencyGuard:
    def test_missing_langchain_explains_how_to_install(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Importing without langchain points the user at piighost[middleware]."""
        real_find_spec = importlib.util.find_spec

        def find_spec(name: str, *args: object, **kwargs: object) -> object:
            if name == "langchain":
                return None
            return real_find_spec(name, *args, **kwargs)

        monkeypatch.setattr(importlib.util, "find_spec", find_spec)
        sys.modules.pop(_MODULE, None)

        with pytest.raises(ImportError, match=r"piighost\[middleware\]"):
            importlib.import_module(_MODULE)

        sys.modules.pop(_MODULE, None)


class TestWhenInstalled:
    def _middleware(self, monkeypatch: pytest.MonkeyPatch) -> object:
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

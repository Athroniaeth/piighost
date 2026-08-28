"""Tests for the Pydantic AI PII de-identification capability."""

from dataclasses import dataclass

import pytest

pytest.importorskip("pydantic_ai")

from pydantic_ai import Agent
from pydantic_ai.messages import (
    ModelMessage,
    ModelResponse,
    TextPart,
    ToolCallPart,
    UserPromptPart,
)
from pydantic_ai.models.function import AgentInfo, FunctionModel

from piighost.components.anonymizer import Anonymizer
from piighost.components.detector import ExactMatchDetector
from piighost.components.linker import ExactEntityLinker
from piighost.components.placeholder import LabelCounterPlaceholderFactory
from piighost.conversation_memory import InMemoryConversationMemory
from piighost.exceptions import InventedPlaceholderError
from piighost.integrations.langchain import (
    EntityCreateByAssistantStrategy,
    ToolCallStrategy,
)
from piighost.integrations.pydantic_ai import pii_hooks
from piighost.pipeline import ThreadAnonymizationPipeline


def _pipeline() -> ThreadAnonymizationPipeline:
    """Build a thread pipeline over a counter factory and in-memory backend."""
    return ThreadAnonymizationPipeline(
        ExactMatchDetector({"Emma": "PERSON", "Liam": "PERSON"}),
        ExactEntityLinker(),
        Anonymizer(LabelCounterPlaceholderFactory()),
        InMemoryConversationMemory(),
    )


def _model_facing_text(messages: list[ModelMessage]) -> str:
    """Return every string content the model would read, joined."""
    contents = [
        part.content
        for message in messages
        for part in message.parts
        if isinstance(part, (UserPromptPart, TextPart))
        and isinstance(part.content, str)
    ]
    return " ".join(contents)


class TestAroundTheModel:
    async def test_model_sees_placeholders_and_reply_is_restored(self) -> None:
        """The model works on placeholders, and its reply is restored for the user."""
        seen: list[str] = []

        def model_fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
            seen.append(_model_facing_text(messages))
            return ModelResponse(parts=[TextPart(content="Hello <<PERSON:1>>")])

        hooks = pii_hooks(_pipeline(), "t1")
        agent = Agent(FunctionModel(model_fn), capabilities=[hooks])
        result = await agent.run("Hi Emma")
        assert seen[-1] == "Hi <<PERSON:1>>"
        assert result.output == "Hello Emma"


class TestMultiTurn:
    async def test_prior_turn_pii_is_not_leaked_to_the_model(self) -> None:
        """A value from an earlier turn is re-anonymized before the next model call."""
        seen: list[str] = []

        def model_fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
            seen.append(_model_facing_text(messages))
            return ModelResponse(parts=[TextPart(content="Noted <<PERSON:1>>")])

        hooks = pii_hooks(_pipeline(), "t1")
        agent = Agent(FunctionModel(model_fn), capabilities=[hooks])
        first = await agent.run("Hi Emma")
        await agent.run("bye", message_history=first.all_messages())
        assert "Emma" not in " ".join(seen)


class TestInventedStrategy:
    async def test_an_invented_token_in_the_reply_is_refused(self) -> None:
        """RAISE refuses a reply holding a token the pipeline never issued."""

        def model_fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
            return ModelResponse(parts=[TextPart(content="ghost <<PERSON:9>>")])

        hooks = pii_hooks(_pipeline(), "t1")
        agent = Agent(FunctionModel(model_fn), capabilities=[hooks])
        with pytest.raises(InventedPlaceholderError):
            await agent.run("Hi Emma")


class TestThreadIdGetter:
    async def test_thread_id_is_resolved_from_the_run_context(self) -> None:
        """A callable thread id reads the conversation id from the run's deps."""

        @dataclass
        class Deps:
            thread_id: str

        seen: list[str] = []

        def model_fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
            seen.append(_model_facing_text(messages))
            return ModelResponse(parts=[TextPart(content="ok")])

        hooks = pii_hooks(_pipeline(), lambda ctx: ctx.deps.thread_id)
        agent = Agent(FunctionModel(model_fn), deps_type=Deps, capabilities=[hooks])
        await agent.run("Hi Emma", deps=Deps(thread_id="conv-1"))
        assert seen[-1] == "Hi <<PERSON:1>>"


class TestTools:
    async def test_tool_gets_the_value_and_its_result_is_reanonymized(self) -> None:
        """The tool receives the real value; its result is re-anonymized for the model."""
        received: dict[str, str] = {}
        seen: list[str] = []
        state = {"calls": 0}

        def send_email(to: str, body: str) -> str:
            received["to"] = to
            received["body"] = body
            return f"Email sent to {to}."

        def model_fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
            for message in messages:
                for part in message.parts:
                    content = getattr(part, "content", None)
                    if isinstance(content, str):
                        seen.append(content)
            state["calls"] += 1
            if state["calls"] == 1:
                args = {"to": "<<PERSON:1>>", "body": "hi <<PERSON:1>>"}
                return ModelResponse(
                    parts=[ToolCallPart(tool_name="send_email", args=args)]
                )
            return ModelResponse(
                parts=[TextPart(content="Done, emailed <<PERSON:1>>.")]
            )

        hooks = pii_hooks(_pipeline(), "t1")
        agent = Agent(FunctionModel(model_fn), tools=[send_email], capabilities=[hooks])
        result = await agent.run("Email Emma.")

        assert received == {"to": "Emma", "body": "hi Emma"}
        assert "Emma" not in " ".join(seen)
        assert result.output == "Done, emailed Emma."

    async def test_passthrough_leaves_the_arguments_as_tokens(self) -> None:
        """PASSTHROUGH runs the tool on the placeholder, deanonymizing nothing."""
        received: dict[str, str] = {}
        state = {"calls": 0}

        def send_email(to: str) -> str:
            received["to"] = to
            return "ok"

        def model_fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
            state["calls"] += 1
            if state["calls"] == 1:
                args = {"to": "<<PERSON:1>>"}
                return ModelResponse(
                    parts=[ToolCallPart(tool_name="send_email", args=args)]
                )
            return ModelResponse(parts=[TextPart(content="ok")])

        hooks = pii_hooks(_pipeline(), "t1", tool_strategy=ToolCallStrategy.PASSTHROUGH)
        agent = Agent(FunctionModel(model_fn), tools=[send_email], capabilities=[hooks])
        await agent.run("Email Emma.")

        assert received["to"] == "<<PERSON:1>>"


class TestAssistantStrategy:
    async def _seen_on_second_turn(
        self, strategy: EntityCreateByAssistantStrategy
    ) -> str:
        """Let the assistant introduce Emma, then read what turn two shows the model."""
        seen: list[str] = []
        state = {"calls": 0}

        def model_fn(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
            state["calls"] += 1
            if state["calls"] == 1:
                return ModelResponse(parts=[TextPart(content="It is Emma")])
            seen.append(_model_facing_text(messages))
            return ModelResponse(parts=[TextPart(content="ok")])

        hooks = pii_hooks(_pipeline(), "t1", assistant_strategy=strategy)
        agent = Agent(FunctionModel(model_fn), capabilities=[hooks])
        first = await agent.run("hello")
        await agent.run("what about Emma", message_history=first.all_messages())
        return seen[-1]

    async def test_preserve_keeps_the_assistant_value_clear(self) -> None:
        """PRESERVE leaves a user reference to an assistant-introduced value in clear."""
        seen = await self._seen_on_second_turn(EntityCreateByAssistantStrategy.PRESERVE)
        assert "what about Emma" in seen

    async def test_anonymize_treats_the_assistant_value_as_pii(self) -> None:
        """ANONYMIZE tokenizes a value the assistant introduced."""
        seen = await self._seen_on_second_turn(
            EntityCreateByAssistantStrategy.ANONYMIZE
        )
        assert "what about <<PERSON:1>>" in seen
        assert "Emma" not in seen

    async def test_ignore_leaves_the_assistant_message_unanalyzed(self) -> None:
        """IGNORE skips the assistant text, so the user reference tokenizes fresh."""
        seen = await self._seen_on_second_turn(EntityCreateByAssistantStrategy.IGNORE)
        assert "It is Emma" in seen
        assert "what about <<PERSON:1>>" in seen

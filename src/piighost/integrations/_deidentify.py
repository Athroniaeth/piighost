"""Framework-agnostic text de-identification shared by the integrations.

The LangChain middleware and the Pydantic AI capability both need the same
thing: anonymize a string before the model sees it, deanonymize a string the
model returned, and decide what to do with a placeholder the model invented. That
logic lives here once, over a ThreadAnonymizationPipeline (local or remote), so
the two integrations cannot drift. The pipeline stays pure: deanonymize only
restores known tokens, and the invented-placeholder policy is applied here, at
the integration boundary, not inside the pipeline.
"""

from typing import Any, Generic

from typing_extensions import TypeVar

from piighost.components.placeholder.tags import PreservesRecognizableIdentity
from piighost.conversation_memory import MessageRole
from piighost.exceptions import InventedPlaceholderError, UnrecognizableFactoryError
from piighost.integrations.langchain.strategy import InventedPlaceholderStrategy
from piighost.pipeline import AnyThreadPipeline

IdentityT = TypeVar(
    "IdentityT",
    bound=PreservesRecognizableIdentity,
    default=PreservesRecognizableIdentity,
)


class TextDeidentifier(Generic[IdentityT]):
    """Anonymize and deanonymize a string within a thread, over any pipeline.

    A thin, framework-agnostic core shared by the framework integrations. It
    delegates detection, token assignment, and replacement to the pipeline, and
    owns only the invented-placeholder policy applied on restore. The pipeline
    must expose a recognizer, so a token the model invented can be found again and
    refused, checked once here at construction.

    Attributes:
        invented_strategy: How a token the pipeline never issued is handled on
            restore, KEEP, DROP, or RAISE.
    """

    def __init__(
        self,
        pipeline: AnyThreadPipeline[IdentityT],
        invented_strategy: InventedPlaceholderStrategy = InventedPlaceholderStrategy.RAISE,
    ) -> None:
        """Store the pipeline and strategy, requiring a recognizable token grammar."""
        recognizer = pipeline.recognizer
        if recognizer is None:
            raise UnrecognizableFactoryError(
                "PII de-identification needs a pipeline exposing a delimited token "
                "recognizer, whose tokens can be found again to detect invented "
                "ones; got a pipeline with no recognizable grammar."
            )
        self._pipeline = pipeline
        self._recognizer = recognizer
        self.invented_strategy = invented_strategy

    async def anonymize(
        self, text: str, thread_id: str, role: MessageRole = MessageRole.USER
    ) -> str:
        """Anonymize a text within the thread and return the anonymized string."""
        result = await self._pipeline.anonymize(text, thread_id, role)
        return result.text

    async def deanonymize(self, text: str, thread_id: str) -> str:
        """Deanonymize a text, then apply the invented-placeholder strategy."""
        restored = await self._pipeline.deanonymize(text, thread_id)
        return self._handle_invented(restored)

    async def deanonymize_value(self, value: Any, thread_id: str) -> Any:
        """Deanonymize the strings inside nested dict, list, and tuple containers.

        A tool call's arguments are a nested structure, so this walks it and
        deanonymizes every string it holds, leaving other values untouched. Each
        string still goes through deanonymize, so the invented-placeholder
        strategy applies to a token the model put in a tool argument.
        """
        if isinstance(value, str):
            return await self.deanonymize(value, thread_id)
        if isinstance(value, dict):
            return {
                key: await self.deanonymize_value(item, thread_id)
                for key, item in value.items()
            }
        if isinstance(value, (list, tuple)):
            items = [await self.deanonymize_value(item, thread_id) for item in value]
            return tuple(items) if isinstance(value, tuple) else items
        return value

    def _handle_invented(self, text: str) -> str:
        """Apply the invented-placeholder strategy to already deanonymized text.

        Every issued token was replaced during deanonymization, so any token still
        matching the factory's grammar was invented by the model. KEEP leaves it,
        DROP removes it, RAISE refuses it. The factory is delimited by
        construction, so its grammar is always recognizable here.
        """
        invented = self._recognizer.find_tokens(text)

        if not invented or self.invented_strategy is InventedPlaceholderStrategy.KEEP:
            return text

        if self.invented_strategy is InventedPlaceholderStrategy.RAISE:
            raise InventedPlaceholderError(
                f"Deanonymized text holds tokens the pipeline never issued: {invented}",
                invented,
            )

        cleaned = text
        for token in invented:
            cleaned = cleaned.replace(token, "")
        return cleaned

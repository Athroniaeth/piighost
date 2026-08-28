"""Remote thread pipeline client over HTTP (optional: client).

PIIGhostClient is a remote stand-in for a ThreadAnonymizationPipeline: it
implements the same AnyThreadPipeline port by calling piighost-api. This module
needs the httpx package; it is guarded so importing it without the dependency
raises an ImportError pointing at the extra.
"""

import importlib.util
import urllib.parse
from typing import Self, cast

from piighost.components.anonymizer.base import Anonymization
from piighost.components.placeholder.base import BaseDelimitedPlaceholderFactory
from piighost.components.placeholder.label_counter import (
    LabelCounterPlaceholderFactory,
)
from piighost.components.placeholder.tags import PreservesRecognizableIdentity
from piighost.conversation_memory.base import Forgotten, MessageRole
from piighost.exceptions import RemoteError
from piighost.models import Detection, Entity, Span

if importlib.util.find_spec("httpx") is None:
    raise ImportError(
        "PIIGhostClient requires the httpx package. "
        "Install it with: pip install piighost[client]"
    )

import httpx


class PIIGhostClient:
    """A remote thread pipeline, calling piighost-api over HTTP.

    It implements the AnyThreadPipeline port so a caller, such as the
    middleware, drives a remote pipeline exactly like a local one. The server
    owns the token mapping, so anonymize returns an Anonymization with empty
    tokens and deanonymize restores through the server. The token grammar is
    declared by the recognizer, defaulting to the standard delimited grammar a
    piighost server emits, overridable when the server is configured otherwise.

    Beyond the strict port it exposes two conveniences a local pipeline offers
    through its parts: detect previews a message's entities without anonymizing,
    and labels returns the detector's label vocabulary.
    """

    def __init__(
        self,
        client: "httpx.AsyncClient | str",
        recognizer: BaseDelimitedPlaceholderFactory | None = None,
    ) -> None:
        """Store or build the HTTP client and the token recognizer.

        A str is a base URL: the client builds and owns its AsyncClient, closed
        by aclose or the context manager. An injected AsyncClient is used as-is
        and never closed here, it belongs to the caller.
        """
        if isinstance(client, str):
            self._client = httpx.AsyncClient(base_url=client)
            self._owns_client = True
        else:
            self._client = client
            self._owns_client = False
        self._recognizer = recognizer or LabelCounterPlaceholderFactory()

    @property
    def recognizer(self) -> BaseDelimitedPlaceholderFactory | None:
        """The grammar of the tokens the server emits."""
        return self._recognizer

    async def anonymize(
        self, text: str, thread_id: str, role: MessageRole = MessageRole.USER
    ) -> Anonymization[PreservesRecognizableIdentity]:
        """Anonymize a message remotely, returning empty-token Anonymization.

        The token mapping lives server-side, so the returned tokens are empty; a
        caller restores through deanonymize, not by reading tokens.
        """
        payload: dict[str, object] = {
            "text": text,
            "thread_id": thread_id,
            "role": role.value,
        }
        data = await self._post("/v1/anonymize", payload)
        anonymized_text = cast(str, data["anonymized_text"])
        return Anonymization(text=anonymized_text, tokens={})

    async def anonymize_corrected(
        self, text: str, thread_id: str, detections: list[Detection]
    ) -> Anonymization[PreservesRecognizableIdentity]:
        """Re-anonymize a user message remotely with a corrected detection set.

        The token mapping lives server-side, so the returned tokens are empty; a
        caller restores through deanonymize, not by reading tokens.
        """
        payload: dict[str, object] = {
            "text": text,
            "thread_id": thread_id,
            "detections": [detection.to_dict() for detection in detections],
        }
        data = await self._post("/v1/anonymize/corrected", payload)
        anonymized_text = cast(str, data["anonymized_text"])
        return Anonymization(text=anonymized_text, tokens={})

    async def deanonymize(self, text: str, thread_id: str) -> str:
        """Deanonymize text remotely through the server's thread mapping."""
        payload: dict[str, object] = {"text": text, "thread_id": thread_id}
        data = await self._post("/v1/deanonymize", payload)
        return cast(str, data["text"])

    async def forget_thread(self, thread_id: str) -> Forgotten:
        """Erase a thread server-side and report what was dropped."""
        safe_id = urllib.parse.quote(thread_id, safe="")
        response = await self._client.delete(f"/v1/threads/{safe_id}")
        data = self._json(response)
        return Forgotten(
            messages=cast(int, data["messages"]),
            detections=cast(int, data["detections"]),
        )

    async def detect(self, text: str, thread_id: str = "default") -> list[Entity]:
        """Preview the entities a message's PII groups into, without anonymizing.

        The server runs detection and linking but does not tokenize the text or
        touch the thread's memory, so this is safe for a human review pass before
        the message is anonymized for real. It reaches past the strict thread
        pipeline port, offering the detection a local pipeline exposes through its
        detector and linker.
        """
        payload: dict[str, object] = {"text": text, "thread_id": thread_id}
        data = await self._post("/v1/detect", payload)
        entities = cast("list[dict[str, object]]", data["entities"])
        return [self._entity_from_wire(entity) for entity in entities]

    async def labels(self) -> list[str]:
        """Return the label vocabulary the server's detector can emit.

        A remote counterpart to reading a local pipeline's detector labels, this
        is the set a caller can offer for human correction. It reaches past the
        strict thread pipeline port.
        """
        response = await self._client.get("/v1/labels")
        data = self._json(response)
        return list(cast("list[str]", data["labels"]))

    async def thread_token_map(self, thread_id: str) -> dict[str, str]:
        """Fetch the thread's placeholder-to-value map from the server.

        The remote counterpart of the local pipeline's thread_token_map: it fetches
        the whole thread map in one call so a caller resolves a stream with cheap
        lookups rather than deanonymizing token by token.
        """
        safe_id = urllib.parse.quote(thread_id, safe="")
        response = await self._client.get(f"/v1/threads/{safe_id}/tokens")
        data = self._json(response)
        return cast("dict[str, str]", data["tokens"])

    async def aclose(self) -> None:
        """Close the underlying client when this one built it."""
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> Self:
        """Enter the async context, returning the client."""
        return self

    async def __aexit__(self, *args: object) -> None:
        """Close the client on context exit."""
        await self.aclose()

    async def _post(self, path: str, payload: dict[str, object]) -> dict[str, object]:
        """POST a JSON payload and return the parsed body, raising on non-2xx."""
        response = await self._client.post(path, json=payload)
        return self._json(response)

    def _json(self, response: "httpx.Response") -> dict[str, object]:
        """Return a response's JSON body, raising RemoteError on a non-2xx.

        It guards the status only, not the body shape: a 2xx response missing an
        expected key is a wire-contract breach and surfaces as a KeyError, not a
        RemoteError.
        """
        if response.is_success:
            return response.json()
        raise RemoteError(
            f"piighost-api returned {response.status_code}: {response.text}",
            response.status_code,
        )

    @staticmethod
    def _detection_from_wire(detection: dict[str, object]) -> Detection:
        """Rebuild a Detection from the server's detection preview wire shape."""
        span = Span(cast(int, detection["start_pos"]), cast(int, detection["end_pos"]))
        return Detection(
            span=span,
            text=cast(str, detection["text"]),
            label=cast(str, detection["label"]),
            confidence=cast(float, detection["confidence"]),
        )

    @classmethod
    def _entity_from_wire(cls, entity: dict[str, object]) -> Entity:
        """Rebuild an Entity from the server's detection preview wire shape."""
        detections = cast("list[dict[str, object]]", entity["detections"])
        rebuilt = tuple(cls._detection_from_wire(detection) for detection in detections)
        return Entity(detections=rebuilt)

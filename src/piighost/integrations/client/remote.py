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
from piighost.models import Detection

if importlib.util.find_spec("httpx") is None:
    raise ImportError(
        "PIIGhostClient requires the httpx package. "
        "Install it with: pip install piighost[client]"
    )

import httpx  # noqa: E402


class PIIGhostClient:
    """A remote thread pipeline, calling piighost-api over HTTP.

    It implements the AnyThreadPipeline port so a caller, such as the
    middleware, drives a remote pipeline exactly like a local one. The server
    owns the token mapping, so anonymize returns an Anonymization with empty
    tokens and deanonymize restores through the server. The token grammar is
    declared by the recognizer, defaulting to the standard delimited grammar a
    piighost server emits, overridable when the server is configured otherwise.
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
        return Anonymization(text=cast(str, data["anonymized_text"]), tokens={})

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
        return Anonymization(text=cast(str, data["anonymized_text"]), tokens={})

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

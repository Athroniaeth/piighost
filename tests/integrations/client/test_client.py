"""Tests for the PIIGhostClient, a remote thread pipeline over HTTP."""

import json
from collections.abc import Callable
from typing import Any, cast

import httpx
import pytest

from piighost.components.placeholder import LabelCounterPlaceholderFactory
from piighost.conversation_memory import Forgotten, MessageRole
from piighost.exceptions import RemoteError
from piighost.integrations.client import PIIGhostClient
from piighost.models import Detection, Span
from piighost.pipeline import AnyThreadPipeline


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> PIIGhostClient:
    """Build a client over a MockTransport driven by handler."""
    transport = httpx.MockTransport(handler)
    http = httpx.AsyncClient(transport=transport, base_url="http://api")
    return PIIGhostClient(http)


class TestConformance:
    def test_satisfies_the_port(self) -> None:
        """PIIGhostClient is an AnyThreadPipeline."""
        client = _client(lambda request: httpx.Response(200, json={}))
        assert isinstance(client, AnyThreadPipeline)


class TestAnonymize:
    async def test_posts_and_returns_empty_token_anonymization(self) -> None:
        """anonymize posts text, thread, role and returns the server text."""
        seen: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["path"] = request.url.path
            seen["body"] = json.loads(request.content)
            return httpx.Response(200, json={"anonymized_text": "Hi <<PERSON:1>>"})

        client = _client(handler)
        result = await client.anonymize("Hi Emma", "t1")
        assert seen["path"] == "/v1/anonymize"
        assert seen["body"] == {"text": "Hi Emma", "thread_id": "t1", "role": "user"}
        assert result.text == "Hi <<PERSON:1>>"
        assert result.tokens == {}

    async def test_serializes_the_role_value(self) -> None:
        """The role is sent as its enum value."""
        seen: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["body"] = json.loads(request.content)
            return httpx.Response(200, json={"anonymized_text": "x"})

        client = _client(handler)
        await client.anonymize("x", "t1", MessageRole.ASSISTANT)
        body = cast("dict[str, Any]", seen["body"])
        assert body["role"] == "assistant"


class TestAnonymizeCorrected:
    async def test_posts_serialized_detections(self) -> None:
        """anonymize_corrected posts the corrected detections as dicts."""
        seen: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["path"] = request.url.path
            seen["body"] = json.loads(request.content)
            return httpx.Response(200, json={"anonymized_text": "<<PERSON:1>>"})

        client = _client(handler)
        detection = Detection(
            span=Span(0, 4), text="Emma", label="PERSON", confidence=1.0
        )
        result = await client.anonymize_corrected("Emma", "t1", [detection])
        assert seen["path"] == "/v1/anonymize/corrected"
        body = cast("dict[str, Any]", seen["body"])
        assert body["detections"] == [detection.to_dict()]
        assert result.text == "<<PERSON:1>>"


class TestDeanonymize:
    async def test_posts_and_returns_the_restored_text(self) -> None:
        """deanonymize posts the tokenized text and returns the restored one."""
        seen: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["path"] = request.url.path
            return httpx.Response(200, json={"text": "Emma"})

        client = _client(handler)
        restored = await client.deanonymize("<<PERSON:1>>", "t1")
        assert seen["path"] == "/v1/deanonymize"
        assert restored == "Emma"


class TestForgetThread:
    async def test_deletes_and_returns_a_forgotten(self) -> None:
        """forget_thread deletes the thread and reports what was dropped."""
        seen: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["method"] = request.method
            seen["path"] = request.url.raw_path.decode()
            return httpx.Response(200, json={"messages": 2, "detections": 5})

        client = _client(handler)
        forgotten = await client.forget_thread("t 1")
        assert seen["method"] == "DELETE"
        assert seen["path"] == "/v1/threads/t%201"
        assert forgotten == Forgotten(messages=2, detections=5)


class TestDetect:
    async def test_posts_and_parses_entities(self) -> None:
        """detect posts the text and rebuilds entities from the preview."""
        seen: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["path"] = request.url.path
            seen["body"] = json.loads(request.content)
            return httpx.Response(
                200,
                json={
                    "entities": [
                        {
                            "label": "PERSON",
                            "placeholder": "",
                            "detections": [
                                {
                                    "text": "Emma",
                                    "label": "PERSON",
                                    "start_pos": 3,
                                    "end_pos": 7,
                                    "confidence": 0.9,
                                }
                            ],
                        }
                    ]
                },
            )

        client = _client(handler)
        entities = await client.detect("Hi Emma", "t1")
        assert seen["path"] == "/v1/detect"
        assert seen["body"] == {"text": "Hi Emma", "thread_id": "t1"}
        assert len(entities) == 1
        detection = entities[0].detections[0]
        assert detection.text == "Emma"
        assert detection.label == "PERSON"
        assert detection.span == Span(3, 7)
        assert detection.confidence == 0.9


class TestLabels:
    async def test_gets_and_returns_the_vocabulary(self) -> None:
        """labels gets the server metadata and returns its label list."""
        seen: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["method"] = request.method
            seen["path"] = request.url.path
            return httpx.Response(
                200,
                json={
                    "name": "demo",
                    "detector": "regex",
                    "labels": ["EMAIL", "PERSON"],
                },
            )

        client = _client(handler)
        labels = await client.labels()
        assert seen["method"] == "GET"
        assert seen["path"] == "/v1/labels"
        assert labels == ["EMAIL", "PERSON"]


class TestThreadTokenMap:
    async def test_gets_and_returns_the_thread_map(self) -> None:
        """thread_token_map gets the thread's token-to-value map, id url-quoted."""
        seen: dict[str, object] = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["method"] = request.method
            seen["path"] = request.url.raw_path.decode()
            return httpx.Response(200, json={"tokens": {"<<PERSON:1>>": "Emma"}})

        client = _client(handler)
        token_map = await client.thread_token_map("t 1")
        assert seen["method"] == "GET"
        assert seen["path"] == "/v1/threads/t%201/tokens"
        assert token_map == {"<<PERSON:1>>": "Emma"}


class TestErrors:
    async def test_non_2xx_raises_remote_error(self) -> None:
        """A non-2xx response raises RemoteError with the status."""
        client = _client(lambda request: httpx.Response(503, text="down"))
        with pytest.raises(RemoteError, match="503"):
            await client.anonymize("x", "t1")


class TestRecognizer:
    def test_defaults_to_a_delimited_recognizer(self) -> None:
        """Without an override, the client declares the standard grammar."""
        from piighost.components.placeholder.base import (
            BaseDelimitedPlaceholderFactory,
        )

        client = _client(lambda request: httpx.Response(200, json={}))
        assert isinstance(client.recognizer, BaseDelimitedPlaceholderFactory)

    def test_recognizer_is_overridable(self) -> None:
        """A caller can declare the server's grammar explicitly."""
        factory = LabelCounterPlaceholderFactory()
        transport = httpx.MockTransport(lambda r: httpx.Response(200, json={}))
        http = httpx.AsyncClient(transport=transport, base_url="http://api")
        client = PIIGhostClient(http, recognizer=factory)
        assert client.recognizer is factory


class TestLifecycle:
    async def test_a_base_url_str_builds_and_closes_its_client(self) -> None:
        """A str base_url makes the client own and close its AsyncClient."""
        client = PIIGhostClient("http://api")
        assert client._owns_client is True
        await client.aclose()
        assert client._client.is_closed is True

    async def test_an_injected_client_is_not_closed(self) -> None:
        """An injected AsyncClient is left open, it belongs to the caller."""
        transport = httpx.MockTransport(lambda r: httpx.Response(200, json={}))
        http = httpx.AsyncClient(transport=transport, base_url="http://api")
        client = PIIGhostClient(http)
        await client.aclose()
        assert http.is_closed is False
        await http.aclose()


class TestClientConfiguration:
    async def test_url_client_carries_timeout_and_headers(self) -> None:
        """A URL-built client applies the given timeout and static headers."""
        client = PIIGhostClient(
            "http://api",
            timeout=12.5,
            headers={"Authorization": "Bearer token"},
        )
        assert client._client.headers["Authorization"] == "Bearer token"
        assert client._client.timeout.read == 12.5
        await client.aclose()

    async def test_retries_build_a_retrying_transport(self) -> None:
        """Passing retries builds the client over a retrying HTTP transport."""
        client = PIIGhostClient("http://api", retries=3)
        assert client._owns_client is True
        assert isinstance(client._client._transport, httpx.AsyncHTTPTransport)
        await client.aclose()
